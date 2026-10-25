"""Literature agent: published studies, with a model-extracted stance when the source has none."""

from concurrent.futures import ThreadPoolExecutor
from typing import ClassVar

from bionexus.agents.base import AgentResult, SpecialistAgent, evidence_block
from bionexus.agents.optimization import (
    AO_MAX_DIRECTION_CALLS,
    AO_MAX_PARALLEL_MODEL_CALLS,
    AO_RECHECK_PASSAGE_CHARS,
)
from bionexus.contracts.evidence import EvidenceRecord, Stance
from bionexus.contracts.messages import AgentMessage, AgentName, ChallengeAsk
from bionexus.evidence.stance import MODEL_STANCE_NOTE, RECHECKED_NOTE
from bionexus.workflow.state import RunState

STANCE_QUESTION = (
    "Does the evidence below support, oppose, or not clearly state an association between the "
    "gene and the disease? Answer with exactly one word: supports, opposes or unknown.\n"
)


def parse_stance(answer: str) -> Stance:
    """Anything other than a clear one-word verdict is treated as unknown."""
    words = answer.strip().lower().split()
    verdict = words[-1].strip(".") if words else ""
    return {"supports": Stance.SUPPORTS, "opposes": Stance.OPPOSES}.get(verdict, Stance.UNKNOWN)


def _needs_direction(record: EvidenceRecord) -> bool:
    """Only a paper that states no direction, and has a passage to read, is sent to a model."""
    return record.stance is Stance.UNKNOWN and bool(record.passage)


def _directions_read(state: RunState) -> int:
    """How many papers this run has already had read (first read, or re-checked)."""
    marks = (MODEL_STANCE_NOTE, RECHECKED_NOTE)
    return sum(any(m in r.context for m in marks) for r in state.evidence.values())


class LiteratureAgent(SpecialistAgent):
    name: ClassVar[AgentName] = AgentName.LITERATURE
    skill_id: ClassVar[str] = "literature.assess"
    source_names: ClassVar[tuple[str, ...]] = ("europe_pmc",)

    def assess(self, message: AgentMessage, state: RunState) -> AgentResult:
        result = super().assess(message, state)
        result.evidence = self._classified(result.evidence, state)
        return result

    def answer_request(self, message: AgentMessage, state: RunState) -> AgentResult:
        """New papers found with a hint get their direction read like the first ones."""
        result = super().answer_request(message, state)
        result.evidence = self._classified(result.evidence, state)
        return result

    def _classified(self, records: list[EvidenceRecord], state: RunState) -> list[EvidenceRecord]:
        """Read the direction of papers that state none, up to a limit for the whole run (AO-3)."""
        todo = [r for r in records if _needs_direction(r)]
        quota = max(0, AO_MAX_DIRECTION_CALLS - _directions_read(state))
        chosen = {r.evidence_id for r in todo[:quota]}
        read = self._with_stances([r for r in records if r.evidence_id in chosen], state)
        by_id = {r.evidence_id: r for r in read}
        return [by_id.get(r.evidence_id, r) for r in records]

    def _with_stances(self, records: list[EvidenceRecord], state: RunState) -> list[EvidenceRecord]:
        """AO-7: the direction calls are independent, so they run together; order is kept."""
        with ThreadPoolExecutor(max_workers=AO_MAX_PARALLEL_MODEL_CALLS) as pool:
            return list(pool.map(lambda record: self._with_stance(record, state), records))

    def _with_stance(self, record: EvidenceRecord, state: RunState) -> EvidenceRecord:
        """Only sources that give no direction are classified, from the passage, with a model."""
        if not _needs_direction(record):
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
        prompt = STANCE_QUESTION + evidence_block([with_passage], AO_RECHECK_PASSAGE_CHARS)
        stance = parse_stance(self.ask_model(state, prompt))
        context = original.context.replace(MODEL_STANCE_NOTE, RECHECKED_NOTE)
        updated = with_passage.model_copy(update={"stance": stance, "context": context})
        return AgentResult(
            evidence=[updated],
            assessment=f"Direction re-checked: {original.stance.value} -> {stance.value}.",
        )
