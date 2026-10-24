"""Small records shared by storage adapters."""

from datetime import UTC, datetime

from pydantic import BaseModel, Field


class AuditEvent(BaseModel):
    actor: str
    action: str
    detail: str
    at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class RunEvent(BaseModel):
    """A sanitized progress event shown in the scientist activity timeline."""

    run_id: str
    seq: int
    kind: str
    data: dict = Field(default_factory=dict)
