"""Evidence critic: finds problems and asks the right specialist for bounded repairs."""

from dataclasses import dataclass
from typing import ClassVar

from bionexus.agents.base import Agent, AgentResult
from bionexus.contracts.evidence import EvidenceRecord, Issue, IssueKind
from bionexus.contracts.messages import AgentMessage, AgentName, ChallengeAsk, MessageType
from bionexus.evidence.matrix import build_matrix
from bionexus.evidence.stance import is_model_read
from bionexus.messaging.envelope import new_message
from bionexus.messaging.router import MAX_MESSAGES_PER_RUN
from bionexus.workflow.state import RunState

CHALLENGEABLE_SOURCES = frozenset({"europe_pmc"})
MAX_RECHECKS_PER_ROUND = 3  # each re-check is one model call, so a conflict cannot fan out
MESSAGE_RESERVE = 4  # room kept for the critic's own task and reply


@dataclass(frozen=True)
class Repair:
    """One challenge the critic will send: this record, this request."""

    evidence_id: str
    ask: ChallengeAsk


def find_issues(evidence: list[EvidenceRecord]) -> list[Issue]:
    """Pure function, so the workflow can re-run it after repairs to see what remains."""
    return [*_missing_passages(evidence), *_matrix_issues(evidence)]


def _missing_passages(evidence: list[EvidenceRecord]) -> list[Issue]:
    return [
        Issue(
            kind=IssueKind.MISSING_PASSAGE,
            subject=r.evidence_id,
            description=f"{r.evidence_id} has no supporting passage.",
        )
        for r in evidence
        if not r.passage
    ]


def _matrix_issues(evidence: list[EvidenceRecord]) -> list[Issue]:
    issues: list[Issue] = []
    for row in build_matrix(evidence):
        issue = _row_issue(row)
        if issue:
            issues.append(issue)
    return issues


def _row_issue(row) -> Issue | None:
    if row.supporting_families and row.opposing_families:
        return _issue(IssueKind.CONTRADICTION, row.target, "supported and opposed")
    if row.supporting_families == 1 and not row.opposing_families:
        return _issue(IssueKind.SINGLE_FAMILY, row.target, "rests on one study family")
    return None


def _challenged(state: RunState, evidence_id: str, ask: ChallengeAsk) -> bool:
    return any(
        m.type is MessageType.EVIDENCE_CHALLENGE
        and evidence_id in m.evidence_ids
        and m.payload.get("ask") == ask
        for m in state.messages
    )


def _issue(kind: IssueKind, target: str, detail: str) -> Issue:
    return Issue(kind=kind, subject=target, description=f"{target}: {detail}.")


class CriticAgent(Agent):
    name: ClassVar[AgentName] = AgentName.CRITIC
    skill_id: ClassVar[str] = "evidence.critique"

    def handle(self, message: AgentMessage, state: RunState) -> AgentResult:
        issues = find_issues(list(state.evidence.values()))
        note = self.ask_model(state, f"Review {len(issues)} issues.")
        challenges = [self._challenge(message, state, r) for r in self.pending_repairs(state)]
        return AgentResult(issues=issues, outgoing=challenges, assessment=note)

    def pending_repairs(self, state: RunState) -> list[Repair]:
        """Challenges a specialist can act on, not yet sent, that fit the message budget."""
        issues = find_issues(list(state.evidence.values()))
        repairs = [r for issue in issues for r in self._repairs_for(issue, state)]
        return repairs[: self._room(state)]

    @staticmethod
    def _room(state: RunState) -> int:
        """A challenge costs two messages (ask and reply); the router caps a run at 40."""
        return max(0, (MAX_MESSAGES_PER_RUN - len(state.messages) - MESSAGE_RESERVE) // 2)

    def _repairs_for(self, issue: Issue, state: RunState) -> list[Repair]:
        if issue.kind is IssueKind.MISSING_PASSAGE:
            return self._passage_repairs(issue, state)
        if issue.kind is IssueKind.CONTRADICTION:
            return self._recheck_repairs(issue, state)
        return []  # one study family cannot be repaired, only reported

    @staticmethod
    def _passage_repairs(issue: Issue, state: RunState) -> list[Repair]:
        record = state.evidence.get(issue.subject)
        ask = ChallengeAsk.SUPPLY_PASSAGE
        if record is None or record.source not in CHALLENGEABLE_SOURCES:
            return []
        return [] if _challenged(state, record.evidence_id, ask) else [Repair(issue.subject, ask)]

    @staticmethod
    def _recheck_repairs(issue: Issue, state: RunState) -> list[Repair]:
        """Only a direction a model read can be re-read; database records are only reported."""
        ask = ChallengeAsk.RECHECK_DIRECTION
        candidates = [
            r.evidence_id
            for r in state.evidence.values()
            if r.target == issue.subject
            and is_model_read(r)
            and not _challenged(state, r.evidence_id, ask)
        ]
        return [Repair(evidence_id, ask) for evidence_id in candidates[:MAX_RECHECKS_PER_ROUND]]

    def _challenge(self, parent: AgentMessage, state: RunState, repair: Repair) -> AgentMessage:
        return new_message(
            run_id=state.run_id,
            sender=self.name,
            recipient=AgentName.LITERATURE,
            kind=MessageType.EVIDENCE_CHALLENGE,
            payload={"evidence_id": repair.evidence_id, "ask": repair.ask},
            parent=parent,
            evidence_ids=(repair.evidence_id,),
        )
