"""Persistent single-job queue: FIFO, restart recovery, cancel, retry (TC-016~TC-018)."""

import threading
import time
from uuid import UUID

import pytest
from conftest import Repos, Seed

from dev_pre_review.analysis.jobs import JobRunner
from dev_pre_review.analysis.worker import JobWorker, StepFailed
from dev_pre_review.domain.enums import ANALYSIS_STEPS, AnalysisStep, JobState
from dev_pre_review.domain.errors import VersionConflict
from dev_pre_review.domain.models import AnalysisJob

Executed = list[tuple[UUID, AnalysisStep]]


def recording_handlers(executed: Executed) -> dict[AnalysisStep, object]:
    def make(step: AnalysisStep) -> object:
        def handler(job: AnalysisJob) -> None:
            executed.append((job.id, step))

        return handler

    return {step: make(step) for step in ANALYSIS_STEPS}


@pytest.fixture
def executed() -> Executed:
    return []


@pytest.fixture
def runner(repos: Repos, executed: Executed) -> JobRunner:
    return JobRunner(repos.jobs, recording_handlers(executed))  # type: ignore[arg-type]


def steps_of(executed: Executed, job_id: UUID) -> list[AnalysisStep]:
    return [step for jid, step in executed if jid == job_id]


def test_jobs_run_one_at_a_time_in_fifo_order(repos: Repos, seed: Seed, executed: Executed) -> None:
    observed: list[tuple[JobState, int]] = []

    def validate(job: AnalysisJob) -> None:
        executed.append((job.id, AnalysisStep.VALIDATE))
        if job.id == first.id:
            observed.append((repos.jobs.get(second.id).state, repos.jobs.count_running()))

    handlers = recording_handlers(executed)
    handlers[AnalysisStep.VALIDATE] = validate
    runner = JobRunner(repos.jobs, handlers)  # type: ignore[arg-type]

    first = runner.enqueue(seed.new_job())
    second = runner.enqueue(seed.new_job())

    assert runner.run_next() is not None
    assert runner.run_next() is not None
    assert runner.run_next() is None

    assert observed == [(JobState.QUEUED, 1)]
    assert [jid for jid, _ in executed] == [first.id] * 6 + [second.id] * 6
    assert repos.jobs.get(second.id).state is JobState.COMPLETED


def test_claim_refuses_while_another_job_is_running(repos: Repos, seed: Seed) -> None:
    repos.jobs.add(seed.new_job())
    repos.jobs.add(seed.new_job())

    assert repos.jobs.claim_next() is not None
    assert repos.jobs.claim_next() is None


def test_interrupted_job_resumes_from_last_completed_step(
    repos: Repos, seed: Seed, executed: Executed
) -> None:
    # Simulate a crash: job persisted as running after validate and extract completed.
    job = repos.jobs.add(seed.new_job())
    job = repos.jobs.update(job.start())
    job = repos.jobs.update(job.complete_step(AnalysisStep.VALIDATE))
    job = repos.jobs.update(job.complete_step(AnalysisStep.EXTRACT))

    restarted = JobRunner(repos.jobs, recording_handlers(executed))  # type: ignore[arg-type]
    resumed = restarted.resume_pending()

    assert [j.id for j in resumed] == [job.id]
    assert resumed[0].state is JobState.QUEUED
    assert resumed[0].next_step is AnalysisStep.RULES

    finished = restarted.run_next()
    assert finished is not None
    assert finished.state is JobState.COMPLETED
    assert steps_of(executed, job.id) == [
        AnalysisStep.RULES,
        AnalysisStep.RETRIEVE,
        AnalysisStep.SUGGEST,
        AnalysisStep.EXPORT_READY,
    ]


def test_cancel_running_job_stops_at_step_boundary(
    repos: Repos, seed: Seed, executed: Executed
) -> None:
    handlers = recording_handlers(executed)

    def extract(job: AnalysisJob) -> None:
        executed.append((job.id, AnalysisStep.EXTRACT))
        runner.cancel(job.id)

    handlers[AnalysisStep.EXTRACT] = extract
    runner = JobRunner(repos.jobs, handlers)  # type: ignore[arg-type]
    job = runner.enqueue(seed.new_job())

    result = runner.run_next()

    assert result is not None
    assert result.state is JobState.CANCELLED
    assert result.completed_steps == (AnalysisStep.VALIDATE, AnalysisStep.EXTRACT)
    assert steps_of(executed, job.id) == [AnalysisStep.VALIDATE, AnalysisStep.EXTRACT]


def test_cancel_during_final_handler_wins_over_completion(
    repos: Repos, seed: Seed, executed: Executed
) -> None:
    handlers = recording_handlers(executed)
    runner = JobRunner(repos.jobs, handlers)  # type: ignore[arg-type]

    def cancel_during_export(job: AnalysisJob) -> None:
        executed.append((job.id, AnalysisStep.EXPORT_READY))
        runner.cancel(job.id)

    handlers[AnalysisStep.EXPORT_READY] = cancel_during_export
    runner.enqueue(seed.new_job())

    result = runner.run_next()

    assert result is not None
    assert result.state is JobState.CANCELLED
    assert result.completed_steps[-1] is AnalysisStep.EXPORT_READY


def test_cancel_queued_job_is_never_executed(
    runner: JobRunner, seed: Seed, executed: Executed
) -> None:
    job = runner.enqueue(seed.new_job())
    assert runner.cancel(job.id).state is JobState.CANCELLED
    assert runner.run_next() is None
    assert executed == []


def test_retry_failed_step_does_not_rerun_completed_steps(
    repos: Repos, seed: Seed, executed: Executed
) -> None:
    attempts = {"rules": 0}
    handlers = recording_handlers(executed)

    def rules(job: AnalysisJob) -> None:
        executed.append((job.id, AnalysisStep.RULES))
        attempts["rules"] += 1
        if attempts["rules"] == 1:
            raise StepFailed("rule_engine_error")

    handlers[AnalysisStep.RULES] = rules
    runner = JobRunner(repos.jobs, handlers)  # type: ignore[arg-type]
    job = runner.enqueue(seed.new_job())

    failed = runner.run_next()
    assert failed is not None
    assert failed.state is JobState.FAILED
    assert failed.failed_step is AnalysisStep.RULES
    assert failed.error_code == "rule_engine_error"

    assert runner.retry(job.id).state is JobState.QUEUED
    done = runner.run_next()

    assert done is not None
    assert done.state is JobState.COMPLETED
    steps = steps_of(executed, job.id)
    assert steps.count(AnalysisStep.VALIDATE) == 1
    assert steps.count(AnalysisStep.EXTRACT) == 1
    assert steps.count(AnalysisStep.RULES) == 2


def test_unexpected_error_records_code_without_message(
    repos: Repos, seed: Seed, executed: Executed
) -> None:
    handlers = recording_handlers(executed)

    def boom(job: AnalysisJob) -> None:
        raise RuntimeError(r"C:\Users\secret\drawing.pdf contents")

    handlers[AnalysisStep.VALIDATE] = boom
    runner = JobRunner(repos.jobs, handlers)  # type: ignore[arg-type]
    runner.enqueue(seed.new_job())

    failed = runner.run_next()

    assert failed is not None
    assert failed.state is JobState.FAILED
    assert failed.error_code == "unexpected_error"


def test_stale_update_is_rejected(repos: Repos, seed: Seed) -> None:
    job = repos.jobs.add(seed.new_job())
    repos.jobs.update(job.request_cancel())

    with pytest.raises(VersionConflict):
        repos.jobs.update(job.start())


def test_runner_requires_a_handler_for_every_step(repos: Repos) -> None:
    with pytest.raises(ValueError, match="missing handlers"):
        JobRunner(repos.jobs, {})


def test_worker_thread_drains_queue(runner: JobRunner, repos: Repos, seed: Seed) -> None:
    worker = JobWorker(runner, poll_interval=0.05)
    worker.start()
    try:
        jobs = [runner.enqueue(seed.new_job()) for _ in range(2)]
        worker.notify()

        deadline = time.monotonic() + 5
        while time.monotonic() < deadline:
            states = {repos.jobs.get(j.id).state for j in jobs}
            if states == {JobState.COMPLETED}:
                break
            time.sleep(0.02)
        assert states == {JobState.COMPLETED}
    finally:
        worker.stop()

    assert not any(t.name == JobWorker.THREAD_NAME for t in threading.enumerate())
