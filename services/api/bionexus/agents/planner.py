"""Planner: reviews what the specialists found and asks for more where coverage looks thin.

It reads a short coverage table (counts per gene and source), never the evidence itself. Its only
power is to ask a specialist to search again with a validated hint: an alternative disease name, a
gene alias or a qualifier. It cannot add, remove or judge evidence. The specialists answer with a
search, so a request costs no model call.
"""

from collections import Counter
from typing import ClassVar

from bionexus.agents.base import Agent, AgentResult
from bionexus.agents.evidence_requests import PlannedRequest, parse_request, request_message
from bionexus.agents.jsonreply import parse_json_object
from bionexus.agents.optimization import AO_MAX_PLANNER_REQUESTS
from bionexus.contracts.errors import ModelUnavailable
from bionexus.contracts.messages import AgentMessage, AgentName
from bionexus.evidence.matrix import build_matrix
from bionexus.messaging.router import exchanges_available
from bionexus.workflow.state import RunState

MESSAGE_RESERVE = 10  # room kept for the critic's rounds and the verifier


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


class PlannerAgent(Agent):
    name: ClassVar[AgentName] = AgentName.PLANNER
    skill_id: ClassVar[str] = "coverage.plan"

    def handle(self, message: AgentMessage, state: RunState) -> AgentResult:
        outgoing = [request_message(self.name, message, state, p) for p in self._plan(state)]
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
        planned = [p for p in (parse_request(row) for row in rows) if p is not None]
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
