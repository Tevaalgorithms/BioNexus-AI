"""Genetics agent: human genetic evidence for a target-disease pair."""

from typing import ClassVar

from bionexus.agents.base import SpecialistAgent
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
