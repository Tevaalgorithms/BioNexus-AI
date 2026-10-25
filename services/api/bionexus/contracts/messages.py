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
    PLANNER = "planner"
    VERIFIER = "verifier"


class MessageType(StrEnum):
    TASK_REQUEST = "task.request"
    TASK_RESULT = "task.result"
    EVIDENCE_CHALLENGE = "evidence.challenge"
    EVIDENCE_REQUEST = "evidence.request"  # "search again with this hint"
    TASK_FAILED = "task.failed"


class ChallengeAsk(StrEnum):
    """What an `evidence.challenge` asks the receiving specialist to do."""

    SUPPLY_PASSAGE = "supply the supporting passage"
    RECHECK_DIRECTION = "recheck the direction against the full passage"


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
