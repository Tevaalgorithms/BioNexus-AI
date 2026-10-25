"""Asking a specialist to search again: who may be asked, and the validated request.

Used by every agent that can send an `evidence.request` (the planner and the critic), so the rules
are written once.
"""

from dataclasses import dataclass

from bionexus.contracts.hints import SearchHint, clean_hint
from bionexus.contracts.messages import AgentMessage, AgentName, MessageType
from bionexus.messaging.envelope import new_message
from bionexus.workflow.state import RunState

# Only specialists whose sources can use a hint are worth asking (pathways sources cannot).
ASKABLE = {
    "genetics": AgentName.GENETICS,
    "literature": AgentName.LITERATURE,
    "clinical": AgentName.CLINICAL,
}


@dataclass(frozen=True)
class PlannedRequest:
    agent: AgentName
    hint: SearchHint


def parse_request(row: object) -> PlannedRequest | None:
    """One requested search from a model's reply, or None if it is not acceptable."""
    if not isinstance(row, dict):
        return None
    agent = ASKABLE.get(str(row.get("agent", "")).lower())
    hint = clean_hint(row.get("kind"), row.get("text"))
    return PlannedRequest(agent, hint) if agent and hint else None


def request_message(
    sender: AgentName, parent: AgentMessage, state: RunState, planned: PlannedRequest
) -> AgentMessage:
    return new_message(
        run_id=state.run_id,
        sender=sender,
        recipient=planned.agent,
        kind=MessageType.EVIDENCE_REQUEST,
        payload={"kind": planned.hint.kind.value, "text": planned.hint.text},
        parent=parent,
    )
