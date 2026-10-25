"""Synthesizer: writes claims from accepted evidence only, and guards the language it emits."""

from dataclasses import dataclass
from typing import ClassVar

from bionexus.agents.base import Agent, AgentResult
from bionexus.agents.optimization import AO_MAX_RETAINED_EVIDENCE
from bionexus.contracts.evidence import Claim, EvidenceRecord
from bionexus.contracts.messages import AgentMessage, AgentName
from bionexus.evidence.eligibility import accepted_evidence
from bionexus.evidence.matrix import MatrixRow, build_matrix
from bionexus.workflow.state import RunState

BLOCKED_PHRASES = ("causes", "cures", "proves", "should take", "recommend treatment")


@dataclass(frozen=True)
class Synthesis:
    claims: list[Claim]
    narrative: str


def retained_evidence(state: RunState) -> list[EvidenceRecord]:
    """Accepted evidence, best-ranked first, capped at the pilot's retention limit."""
    accepted = {r.evidence_id: r for r in accepted_evidence(list(state.evidence.values()))}
    ranked = [i for i in state.ranked_evidence_ids if i in accepted]
    unranked = sorted(set(accepted) - set(ranked))
    return [accepted[i] for i in [*ranked, *unranked][:AO_MAX_RETAINED_EVIDENCE]]


def language_violations(text: str) -> list[str]:
    lowered = text.lower()
    return [phrase for phrase in BLOCKED_PHRASES if phrase in lowered]


class SynthesizerAgent(Agent):
    name: ClassVar[AgentName] = AgentName.SYNTHESIZER
    skill_id: ClassVar[str] = "report.synthesize"

    def write(self, state: RunState) -> Synthesis:
        rows = build_matrix(retained_evidence(state))
        claims = [self._claim(row, state.request.disease) for row in rows]
        return Synthesis(claims=claims, narrative=self._narrative(state, claims))

    @staticmethod
    def _claim(row: MatrixRow, disease: str) -> Claim:
        text = (
            f"{row.target} and {disease} (independent study families): "
            f"{row.supporting_families} supporting, {row.opposing_families} opposing, "
            f"{row.unknown_families} with no stated direction."
        )
        return Claim(
            claim_id=f"claim-{row.target}",
            text=text,
            stance=row.net_stance,
            evidence_ids=row.evidence_ids,
        )

    def _narrative(self, state: RunState, claims: list[Claim]) -> str:
        draft = self.ask_model(state, "Summarise: " + " ".join(c.text for c in claims))
        if language_violations(draft):
            return " ".join(c.text for c in claims)
        return draft

    def handle(self, message: AgentMessage, state: RunState) -> AgentResult:
        return AgentResult(abstained=True, assessment="Use write() to synthesise.")
