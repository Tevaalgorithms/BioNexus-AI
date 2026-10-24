"""RunState: everything about one investigation run. It is plain data, so it checkpoints as JSON."""

from datetime import UTC, datetime
from threading import RLock

from pydantic import BaseModel, Field, PrivateAttr

from bionexus.contracts.errors import InvalidTransition
from bionexus.contracts.evidence import Claim, EvidenceRecord, Exclusion, Issue
from bionexus.contracts.investigation import (
    ALLOWED_TRANSITIONS,
    InvestigationRequest,
    InvestigationStatus,
)
from bionexus.contracts.invocation import Invocation
from bionexus.contracts.messages import AgentMessage
from bionexus.workflow.budget import Budget

MAX_NOTES_PER_AGENT = 20


class RunState(BaseModel):
    run_id: str
    tenant_id: str
    project_id: str
    created_by: str
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    request: InvestigationRequest
    release_id: str
    budget: Budget
    status: InvestigationStatus = InvestigationStatus.QUEUED
    stop_reason: str | None = None
    evidence: dict[str, EvidenceRecord] = Field(default_factory=dict)
    excluded: list[Exclusion] = Field(default_factory=list)
    messages: list[AgentMessage] = Field(default_factory=list)
    invocations: list[Invocation] = Field(default_factory=list)
    issues: list[Issue] = Field(default_factory=list)
    claims: list[Claim] = Field(default_factory=list)
    narrative: str = ""
    working_memory: dict[str, list[str]] = Field(default_factory=dict)
    report_id: str | None = None
    ranked_evidence_ids: list[str] = Field(default_factory=list)
    graph_context: list[str] = Field(default_factory=list)
    _lock: RLock = PrivateAttr(default_factory=RLock)

    @property
    def lock(self) -> RLock:
        """Guards shared mutation while specialists run in parallel."""
        return self._lock

    def transition(self, new_status: InvestigationStatus) -> None:
        if new_status not in ALLOWED_TRANSITIONS[self.status]:
            raise InvalidTransition(f"{self.status} -> {new_status} is not permitted")
        self.status = new_status

    def add_evidence(self, records: list[EvidenceRecord]) -> None:
        for record in records:
            self.evidence[record.evidence_id] = record

    def remember(self, agent: str, note: str) -> None:
        notes = self.working_memory.setdefault(agent, [])
        notes.append(note)
        del notes[:-MAX_NOTES_PER_AGENT]
