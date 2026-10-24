"""Worker: leases jobs and runs them. A crashed worker's job is picked up again after its lease."""

from datetime import UTC, datetime

from bionexus.storage.ports import JobStore
from bionexus.workflow.runner import RunExecutor


class Worker:
    def __init__(self, queue: JobStore, executor: RunExecutor) -> None:
        self._queue = queue
        self._executor = executor

    def run_pending(self, now: datetime | None = None) -> int:
        """Process every available job; returns how many were run."""
        processed = 0
        while job := self._queue.lease(now or datetime.now(UTC)):
            self._executor.execute(job.run_id)
            self._queue.complete(job)
            processed += 1
        return processed
