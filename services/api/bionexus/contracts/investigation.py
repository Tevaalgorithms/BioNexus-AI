"""The investigation request and its lifecycle."""

from datetime import date
from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field, field_validator

MAX_TARGETS = 5


class InvestigationRequest(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    disease: str = Field(min_length=2)
    targets: tuple[str, ...] = Field(min_length=1, max_length=MAX_TARGETS)
    question: str = Field(min_length=5)
    evidence_cutoff: date

    @field_validator("targets")
    @classmethod
    def normalise_targets(cls, targets: tuple[str, ...]) -> tuple[str, ...]:
        return tuple(dict.fromkeys(t.strip().upper() for t in targets))


class InvestigationStatus(StrEnum):
    QUEUED = "queued"
    RUNNING = "running"
    WAITING_FOR_REVIEW = "waiting_for_review"
    COMPLETED = "completed"
    INCOMPLETE = "incomplete"
    FAILED = "failed"
    CANCELLED = "cancelled"
    SUPERSEDED = "superseded"


_S = InvestigationStatus

ALLOWED_TRANSITIONS: dict[InvestigationStatus, frozenset[InvestigationStatus]] = {
    _S.QUEUED: frozenset({_S.RUNNING, _S.CANCELLED}),
    _S.RUNNING: frozenset({_S.WAITING_FOR_REVIEW, _S.INCOMPLETE, _S.FAILED, _S.CANCELLED}),
    _S.WAITING_FOR_REVIEW: frozenset({_S.COMPLETED, _S.SUPERSEDED, _S.CANCELLED}),
    _S.COMPLETED: frozenset({_S.SUPERSEDED}),
    _S.INCOMPLETE: frozenset({_S.QUEUED, _S.SUPERSEDED}),
    _S.FAILED: frozenset({_S.QUEUED}),
    _S.CANCELLED: frozenset(),
    _S.SUPERSEDED: frozenset(),
}
