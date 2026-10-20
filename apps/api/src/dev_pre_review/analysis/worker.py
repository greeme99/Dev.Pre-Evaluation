"""Background worker thread draining the single-job queue."""

import threading
import time

from dev_pre_review.analysis.exceptions import StepFailed
from dev_pre_review.analysis.jobs import JobRunner

__all__ = ["JobWorker", "StepFailed"]


class JobWorker:
    THREAD_NAME = "analysis-job-worker"

    def __init__(self, runner: JobRunner, poll_interval: float = 0.5) -> None:
        self.runner = runner
        self.poll_interval = poll_interval
        self._wake_event = threading.Event()
        self._stop_event = threading.Event()
        self._thread: threading.Thread | None = None

    def start(self) -> None:
        if self._thread is not None and self._thread.is_alive():
            return
        self._stop_event.clear()
        self._wake_event.clear()
        self._thread = threading.Thread(target=self._run_loop, name=self.THREAD_NAME, daemon=True)
        self._thread.start()

    def notify(self) -> None:
        self._wake_event.set()

    def stop(self, timeout: float = 5.0) -> None:
        self._stop_event.set()
        self._wake_event.set()
        if self._thread is not None and self._thread.is_alive():
            self._thread.join(timeout=timeout)
        self._thread = None

    def _run_loop(self) -> None:
        while not self._stop_event.is_set():
            job = self.runner.run_next()
            if job is not None:
                # Drained one job, check if more jobs queued immediately
                continue

            self._wake_event.wait(timeout=self.poll_interval)
            self._wake_event.clear()
            time.sleep(0.001)
