from datetime import datetime

from pydantic import BaseModel


class Job(BaseModel):
    job_id: str
    run_id: str
    idempotency_key: str
    done: bool = False
    attempts: int = 0
    lease_expires: datetime | None = None
