"""Literature agent: published studies, with a model-extracted stance when the source has none."""

from typing import ClassVar

from bionexus.agents.base import AgentResult, SpecialistAgent, evidence_block
from bionexus.contracts.evidence import EvidenceRecord, Stance
from bionexus.contracts.messages import AgentMessage, AgentName
from bionexus.workflow.state import RunState

MAX_STANCE_EXTRACTIONS = 10
STANCE_QUESTION = (
    "Does the evidence below support, oppose, or not clearly state an association between the "
    "gene and the disease? Answer with exactly one word: supports, opposes or unknown.\n"
)


def parse_stance(answer: str) -> Stance:
    """Anything other than a clear one-word verdict is treated as unknown."""
    words = answer.strip().lower().split()
    verdict = words[-1].strip(".") if words else ""
    return {"supports": Stance.SUPPORTS, "opposes": Stance.OPPOSES}.get(verdict, Stance.UNKNOWN)


class LiteratureAgent(SpecialistAgent):
    name: ClassVar[AgentName] = AgentName.LITERATURE
    skill_id: ClassVar[str] = "literature.assess"
    source_names: ClassVar[tuple[str, ...]] = ("europe_pmc",)

    def assess(self, message: AgentMessage, state: RunState) -> AgentResult:
        result = super().assess(message, state)
        result.evidence = [
            self._with_stance(r, state) for r in result.evidence[:MAX_STANCE_EXTRACTIONS]
        ] + result.evidence[MAX_STANCE_EXTRACTIONS:]
        return result

    def _with_stance(self, record: EvidenceRecord, state: RunState) -> EvidenceRecord:
        """Only sources that give no direction are classified, from the passage, with a model."""
        if record.stance is not Stance.UNKNOWN or not record.passage:
            return record
        answer = self.ask_model(state, STANCE_QUESTION + evidence_block([record]))
        context = f"{record.context}; stance extracted by model (unreviewed)"
        return record.model_copy(update={"stance": parse_stance(answer), "context": context})

    def answer_challenge(self, message: AgentMessage, state: RunState) -> AgentResult:
        """Return the supporting passage if the source has one; otherwise say so plainly."""
        record = state.evidence[str(message.payload["evidence_id"])]
        passage = self.deps.sources.get(record.source).passage_for(record.source_id)
        if not passage:
            return AgentResult(abstained=True, assessment="Supporting passage not found.")
        return AgentResult(
            evidence=[record.model_copy(update={"passage": passage})],
            assessment="Passage retrieved from source.",
        )
