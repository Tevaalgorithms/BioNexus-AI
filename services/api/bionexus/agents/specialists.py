"""The four evidence specialists. Each is a source list plus, where needed, one extra behaviour."""

from typing import ClassVar

from bionexus.agents.base import AgentResult, SpecialistAgent, evidence_block
from bionexus.contracts.evidence import EvidenceRecord, Stance
from bionexus.contracts.messages import AgentMessage, AgentName, MessageType
from bionexus.messaging.envelope import new_message
from bionexus.workflow.state import RunState


class GeneticsAgent(SpecialistAgent):
    name: ClassVar[AgentName] = AgentName.GENETICS
    skill_id: ClassVar[str] = "genetics.assess"
    source_names: ClassVar[tuple[str, ...]] = ("open_targets", "gwas")

    def follow_ups(
        self, evidence: list[EvidenceRecord], message: AgentMessage, state: RunState
    ) -> list[AgentMessage]:
        """Ask pathways for context, but only on targets with genetic support."""
        supported = sorted({r.target for r in evidence if r.stance is Stance.SUPPORTS})
        if not supported:
            return []
        request = new_message(
            run_id=state.run_id,
            sender=self.name,
            recipient=AgentName.PATHWAYS,
            kind=MessageType.TASK_REQUEST,
            payload={"targets": supported},
            parent=message,
            evidence_ids=tuple(r.evidence_id for r in evidence),
        )
        return [request]


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


class PathwaysAgent(SpecialistAgent):
    name: ClassVar[AgentName] = AgentName.PATHWAYS
    skill_id: ClassVar[str] = "mechanism.context"
    source_names: ClassVar[tuple[str, ...]] = ("reactome", "monarch")


class ClinicalAgent(SpecialistAgent):
    name: ClassVar[AgentName] = AgentName.CLINICAL
    skill_id: ClassVar[str] = "trials.context"
    source_names: ClassVar[tuple[str, ...]] = ("clinicaltrials",)
