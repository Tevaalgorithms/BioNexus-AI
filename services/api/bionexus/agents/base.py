"""Shared agent plumbing. Concrete agents mostly declare data; behaviour lives here once."""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import ClassVar

from pydantic import BaseModel, Field

from bionexus.agents.skills import SkillRegistry
from bionexus.contracts.evidence import EvidenceRecord, Exclusion, Issue
from bionexus.contracts.messages import AgentMessage, AgentName, MessageType
from bionexus.evidence.eligibility import partition_eligible
from bionexus.llm.gateway import ModelGateway
from bionexus.llm.release import ReleaseStore
from bionexus.messaging.envelope import new_message
from bionexus.sources.registry import SourceRegistry
from bionexus.workflow.state import RunState


@dataclass(frozen=True)
class AgentDeps:
    sources: SourceRegistry
    gateway: ModelGateway
    skills: SkillRegistry
    releases: ReleaseStore


MAX_PASSAGE_IN_PROMPT = 300


def evidence_block(records: list[EvidenceRecord]) -> str:
    """Source text enters prompts only in this delimited block, as data, never instructions."""
    lines = [
        f"[{r.evidence_id}] {r.finding} :: {r.passage[:MAX_PASSAGE_IN_PROMPT]}" for r in records
    ]
    return "<evidence_data>\n" + "\n".join(lines) + "\n</evidence_data>"


class AgentResult(BaseModel):
    evidence: list[EvidenceRecord] = Field(default_factory=list)
    excluded: list[Exclusion] = Field(default_factory=list)
    issues: list[Issue] = Field(default_factory=list)
    outgoing: list[AgentMessage] = Field(default_factory=list)
    assessment: str = ""
    abstained: bool = False


class Agent(ABC):
    name: ClassVar[AgentName]
    skill_id: ClassVar[str]

    def __init__(self, deps: AgentDeps) -> None:
        self.deps = deps

    def instructions(self, state: RunState) -> str:
        """The skill text pinned by the run's configuration release."""
        release = self.deps.releases.get(state.release_id)
        return self.deps.skills.get(
            self.skill_id, release.skill_versions[self.skill_id]
        ).instructions

    def ask_model(self, state: RunState, task_summary: str) -> str:
        prompt = f"{self.instructions(state)}\n{task_summary}"
        return self.deps.gateway.complete(state, self.name, prompt)

    @abstractmethod
    def handle(self, message: AgentMessage, state: RunState) -> AgentResult: ...


class SpecialistAgent(Agent):
    """Retrieves eligible evidence from its sources and summarises it with its own model."""

    source_names: ClassVar[tuple[str, ...]]

    def handle(self, message: AgentMessage, state: RunState) -> AgentResult:
        if message.type is MessageType.EVIDENCE_CHALLENGE:
            return self.answer_challenge(message, state)
        return self.assess(message, state)

    def assess(self, message: AgentMessage, state: RunState) -> AgentResult:
        targets = tuple(message.payload.get("targets") or state.request.targets)  # type: ignore[arg-type]
        found = self._search(state, targets)
        eligible, excluded = partition_eligible(found, state.request.evidence_cutoff)
        if not eligible:
            return AgentResult(
                excluded=excluded, abstained=True, assessment="No eligible evidence."
            )
        note = self.ask_model(state, self._summary(eligible))
        state.remember(self.name.value, note)
        return AgentResult(
            evidence=eligible,
            excluded=excluded,
            assessment=note,
            outgoing=self.follow_ups(eligible, message, state),
        )

    def _search(self, state: RunState, targets: tuple[str, ...]) -> list[EvidenceRecord]:
        records: list[EvidenceRecord] = []
        for source_name in self.source_names:
            source = self.deps.sources.get(source_name)
            records.extend(source.search(state.request.disease, targets))
        return records

    @staticmethod
    def _summary(records: list[EvidenceRecord]) -> str:
        return f"Summarise {len(records)} evidence items.\n{evidence_block(records)}"

    def follow_ups(
        self, evidence: list[EvidenceRecord], message: AgentMessage, state: RunState
    ) -> list[AgentMessage]:
        return []

    def answer_challenge(self, message: AgentMessage, state: RunState) -> AgentResult:
        return AgentResult(abstained=True, assessment="This agent does not handle challenges.")


def reply_to(parent: AgentMessage, result: AgentResult, kind: MessageType) -> AgentMessage:
    """The reply envelope for a handled message; the payload records the outcome."""
    return new_message(
        run_id=parent.run_id,
        sender=parent.recipient,
        recipient=parent.sender,
        kind=kind,
        payload={"in_reply_to": parent.message_id, "abstained": result.abstained},
        parent=parent,
        evidence_ids=tuple(r.evidence_id for r in result.evidence),
    )
