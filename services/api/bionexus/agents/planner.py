"""Planner: reviews what the specialists found and asks for more where coverage looks thin.

It reads a short coverage table (counts per gene and source), never the evidence itself. Its only
power is to ask a specialist to search again with a validated hint: an alternative disease name, a
gene alias or a qualifier. It cannot add, remove or judge evidence. The specialists answer with a
search, so a request costs no model call.
"""

from collections import Counter
from dataclasses import dataclass
from typing import ClassVar

from bionexus.agents.base import Agent, AgentResult
from bionexus.agents.jsonreply import parse_json_object
from bionexus.agents.optimization import AO_MAX_PLANNER_REQUESTS
from bionexus.contracts.errors import ModelUnavailable
from bionexus.contracts.hints import SearchHint, clean_hint
from bionexus.contracts.messages import AgentMessage, AgentName, MessageType
from bionexus.evidence.matrix import build_matrix
from bionexus.messaging.envelope import new_message
from bionexus.messaging.router import exchanges_available
from bionexus.workflow.state import RunState

# Only specialists whose sources can use a hint are worth asking (pathways sources cannot).
ASKABLE = {
    "genetics": AgentName.GENETICS,
    "literature": AgentName.LITERATURE,
    "clinical": AgentName.CLINICAL,
}
MESSAGE_RESERVE = 10  # room kept for the critic's rounds and the verifier


@dataclass(frozen=True)
class PlannedRequest:
    agent: AgentName
    hint: SearchHint


def coverage_summary(state: RunState) -> str:
    """One line per gene: records per source, and how many independent studies point which way."""
    lines = []
    for target in state.request.targets:
        records = [r for r in state.evidence.values() if r.target == target]
        by_source = Counter(r.source for r in records)
        found = ", ".join(f"{s} {n}" for s, n in sorted(by_source.items())) or "nothing found"
        lines.append(f"{target}: {found}{_studies(records)}")
    return "\n".join(lines)


def _studies(records: list) -> str:
    row = next(iter(build_matrix(records)), None)
    if row is None:
        return ""
    return (
        f" | independent studies: {row.supporting_families} supporting, "
        f"{row.opposing_families} opposing, {row.unknown_families} no direction"
    )


def _planned(row: object) -> PlannedRequest | None:
    """One requested search from the model's reply, or None if it is not acceptable."""
    if not isinstance(row, dict):
        return None
    agent = ASKABLE.get(str(row.get("agent", "")).lower())
    hint = clean_hint(row.get("kind"), row.get("text"))
    return PlannedRequest(agent, hint) if agent and hint else None


class PlannerAgent(Agent):
    name: ClassVar[AgentName] = AgentName.PLANNER
    skill_id: ClassVar[str] = "coverage.plan"

    def handle(self, message: AgentMessage, state: RunState) -> AgentResult:
        outgoing = [self._request(message, state, p) for p in self._plan(state)]
        return AgentResult(
            outgoing=outgoing,
            abstained=not outgoing,
            assessment=f"{len(outgoing)} extra searches requested.",
        )

    def _plan(self, state: RunState) -> list[PlannedRequest]:
        try:
            reply = self.ask_model(state, self._prompt(state))
        except ModelUnavailable:  # the planner is optional: no model, no extra searches
            return []
        limit = min(AO_MAX_PLANNER_REQUESTS, exchanges_available(state, MESSAGE_RESERVE))
        return self._validated(parse_json_object(reply), limit)

    @staticmethod
    def _validated(payload: dict | None, limit: int) -> list[PlannedRequest]:
        rows = payload.get("requests") if payload else None
        if not isinstance(rows, list):
            return []
        planned = [p for p in (_planned(row) for row in rows) if p is not None]
        return list(dict.fromkeys(planned))[:limit]  # no repeats, at most `limit`

    @staticmethod
    def _prompt(state: RunState) -> str:
        request = state.request
        return (
            f"<request_data>\nDisease: {request.disease}\nGenes: {', '.join(request.targets)}\n"
            f"</request_data>\n<coverage_data>\n{coverage_summary(state)}\n</coverage_data>\n"
            f"Propose at most {AO_MAX_PLANNER_REQUESTS} extra searches, using only alternative "
            'names or short qualifiers. Reply with JSON only: {"requests": [{"agent": '
            '"literature|genetics|clinical", "kind": "disease|gene|context", "text": "<phrase>"}]}'
        )

    def _request(
        self, parent: AgentMessage, state: RunState, planned: PlannedRequest
    ) -> AgentMessage:
        return new_message(
            run_id=state.run_id,
            sender=self.name,
            recipient=planned.agent,
            kind=MessageType.EVIDENCE_REQUEST,
            payload={"kind": planned.hint.kind.value, "text": planned.hint.text},
            parent=parent,
        )
