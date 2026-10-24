"""The agent-to-agent message envelope (internal protocol, not the external A2A standard)."""

from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field


class AgentName(StrEnum):
    SUPERVISOR = "supervisor"
    GENETICS = "genetics"
    LITERATURE = "literature"
    PATHWAYS = "pathways"
    CLINICAL = "clinical"
    CRITIC = "critic"
    SYNTHESIZER = "synthesizer"


class MessageType(StrEnum):
    TASK_REQUEST = "task.request"
    TASK_RESULT = "task.result"
    EVIDENCE_CHALLENGE = "evidence.challenge"
    TASK_FAILED = "task.failed"


class AgentMessage(BaseModel):
    model_config = ConfigDict(frozen=True)

    message_id: str
    correlation_id: str
    parent_id: str | None
    run_id: str
    sender: AgentName
    recipient: AgentName
    type: MessageType
    payload: dict[str, object] = Field(default_factory=dict)
    evidence_ids: tuple[str, ...] = ()
    depth: int = 0
    idempotency_key: str
