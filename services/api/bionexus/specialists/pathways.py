"""Pathways agent: pathway and mechanism context. Asked by genetics, never pre-planned."""

from typing import ClassVar

from bionexus.agents.base import SpecialistAgent
from bionexus.contracts.messages import AgentName


class PathwaysAgent(SpecialistAgent):
    name: ClassVar[AgentName] = AgentName.PATHWAYS
    skill_id: ClassVar[str] = "mechanism.context"
    source_names: ClassVar[tuple[str, ...]] = ("reactome", "monarch")
