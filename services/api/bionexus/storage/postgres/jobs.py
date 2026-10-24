"""The durable job queue: idempotent enqueue and an atomic, lease-based claim."""

import uuid
from datetime import datetime

from bionexus.jobs.models import Job
from bionexus.storage.in_memory import LEASE_SECONDS, MAX_ATTEMPTS
from bionexus.storage.postgres.database import Database


class PostgresJobs:
    def __init__(self, db: Database) -> None:
        self._db = db

    def find(self, idempotency_key: str) -> Job | None:
        row = self._db.fetch_one(
            "SELECT * FROM jobs WHERE idempotency_key = %s", (idempotency_key,)
        )
        return Job(**_job_fields(row)) if row else None

    def enqueue(self, run_id: str, idempotency_key: str) -> Job:
        job_id = uuid.uuid4().hex
        self._db.execute(
            "INSERT INTO jobs (job_id, run_id, idempotency_key) VALUES (%s, %s, %s)"
            " ON CONFLICT (idempotency_key) DO NOTHING",
            (job_id, run_id, idempotency_key),
        )
        found = self.find(idempotency_key)
        if found is None:
            raise RuntimeError("job was not stored")
        return found

    def lease(self, now: datetime) -> Job | None:
        """Atomic claim using SKIP LOCKED so concurrent workers never take the same job."""
        row = self._db.fetch_one(
            """UPDATE jobs SET attempts = attempts + 1,
                      lease_expires = %s + make_interval(secs => %s)
               WHERE job_id = (
                   SELECT job_id FROM jobs
                   WHERE NOT done AND attempts < %s
                     AND (lease_expires IS NULL OR lease_expires <= %s)
                   ORDER BY created_at FOR UPDATE SKIP LOCKED LIMIT 1)
               RETURNING *""",
            (now, LEASE_SECONDS, MAX_ATTEMPTS, now),
        )
        return Job(**_job_fields(row)) if row else None

    def complete(self, job: Job) -> None:
        self._db.execute(
            "UPDATE jobs SET done = true, lease_expires = NULL WHERE job_id = %s", (job.job_id,)
        )

    def depth(self) -> int:
        row = self._db.fetch_one("SELECT count(*) AS n FROM jobs WHERE NOT done")
        return int(row["n"]) if row else 0


def _job_fields(row: dict) -> dict:
    keys = ("job_id", "run_id", "idempotency_key", "done", "attempts", "lease_expires")
    return {k: row[k] for k in keys}
