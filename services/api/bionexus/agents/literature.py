"""Literature agent: published studies, with a model-extracted stance when the source has none."""

from typing import ClassVar

from bionexus.agents.base import (
    RECHECK_PASSAGE_IN_PROMPT,
    AgentResult,
    SpecialistAgent,
    evidence_block,
)
from bionexus.contracts.evidence import EvidenceRecord, Stance
from bionexus.contracts.messages import AgentMessage, AgentName, ChallengeAsk
from bionexus.evidence.stance import MODEL_STANCE_NOTE, RECHECKED_NOTE
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
        context = f"{record.context}; {MODEL_STANCE_NOTE}"
        return record.model_copy(update={"stance": parse_stance(answer), "context": context})

    def answer_challenge(self, message: AgentMessage, state: RunState) -> AgentResult:
        """Answer the critic: fetch the full passage, and re-read the direction if asked to."""
        record = state.evidence[str(message.payload["evidence_id"])]
        passage = self.deps.sources.get(record.source).passage_for(record.source_id)
        if not passage:
            return AgentResult(abstained=True, assessment="Supporting passage not found.")
        with_passage = record.model_copy(update={"passage": passage})
        if message.payload.get("ask") == ChallengeAsk.RECHECK_DIRECTION:
            return self._recheck_direction(record, with_passage, state)
        return AgentResult(evidence=[with_passage], assessment="Passage retrieved from source.")

    def _recheck_direction(
        self, original: EvidenceRecord, with_passage: EvidenceRecord, state: RunState
    ) -> AgentResult:
        """A second opinion: the model reads the whole passage, not the excerpt it saw before."""
        prompt = STANCE_QUESTION + evidence_block([with_passage], RECHECK_PASSAGE_IN_PROMPT)
        stance = parse_stance(self.ask_model(state, prompt))
        context = original.context.replace(MODEL_STANCE_NOTE, RECHECKED_NOTE)
        updated = with_passage.model_copy(update={"stance": stance, "context": context})
        return AgentResult(
            evidence=[updated],
            assessment=f"Direction re-checked: {original.stance.value} -> {stance.value}.",
        )
