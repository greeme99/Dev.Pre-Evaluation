"""Single-job pipeline execution runner."""

from collections.abc import Callable
from uuid import UUID

from dev_pre_review.analysis.exceptions import StepFailed
from dev_pre_review.domain.enums import ANALYSIS_STEPS, AnalysisStep, JobState
from dev_pre_review.domain.models import AnalysisJob
from dev_pre_review.storage.repositories import JobRepository

StepHandler = Callable[[AnalysisJob], None]


class JobRunner:
    def __init__(self, jobs: JobRepository, handlers: dict[AnalysisStep, StepHandler]) -> None:
        missing = set(ANALYSIS_STEPS) - set(handlers.keys())
        if missing:
            raise ValueError(f"missing handlers for steps: {missing}")
        self.jobs = jobs
        self.handlers = handlers

    def enqueue(self, job: AnalysisJob) -> AnalysisJob:
        return self.jobs.add(job)

    def cancel(self, job_id: UUID) -> AnalysisJob:
        job = self.jobs.get(job_id)
        updated = job.request_cancel()
        return self.jobs.update(updated)

    def retry(self, job_id: UUID) -> AnalysisJob:
        job = self.jobs.get(job_id)
        updated = job.retry()
        return self.jobs.update(updated)

    def resume_pending(self) -> list[AnalysisJob]:
        interrupted = self.jobs.list_interrupted()
        resumed: list[AnalysisJob] = []
        for job in interrupted:
            recovered = job.recover_after_restart()
            resumed.append(self.jobs.update(recovered))
        return resumed

    def run_next(self) -> AnalysisJob | None:
        job = self.jobs.claim_next()
        if job is None:
            return None

        while job.next_step is not None:
            fresh = self.jobs.get(job.id)
            if fresh.state is JobState.CANCELLING:
                cancelled = fresh.confirm_cancel()
                return self.jobs.update(cancelled)

            step = job.next_step
            handler = self.handlers[step]
            try:
                handler(job)
            except StepFailed as exc:
                fresh = self.jobs.get(job.id)
                failed = fresh.fail(step, exc.error_code)
                return self.jobs.update(failed)
            except Exception:  # noqa: BLE001
                fresh = self.jobs.get(job.id)
                failed = fresh.fail(step, "unexpected_error")
                return self.jobs.update(failed)

            fresh = self.jobs.get(job.id)
            job = self.jobs.update(fresh.complete_step(step))

            if job.state is JobState.CANCELLING:
                cancelled = job.confirm_cancel()
                return self.jobs.update(cancelled)

        return job
