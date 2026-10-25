"""Clinical agent: registered clinical trials for the target and disease."""

from typing import ClassVar

from bionexus.agents.base import SpecialistAgent
from bionexus.contracts.messages import AgentName


class ClinicalAgent(SpecialistAgent):
    name: ClassVar[AgentName] = AgentName.CLINICAL
    skill_id: ClassVar[str] = "trials.context"
    source_names: ClassVar[tuple[str, ...]] = ("clinicaltrials",)
