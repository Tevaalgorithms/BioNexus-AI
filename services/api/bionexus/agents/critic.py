"""Evidence critic: finds problems and asks the right specialist for bounded repairs."""

from typing import ClassVar

from bionexus.agents.base import Agent, AgentResult
from bionexus.contracts.evidence import EvidenceRecord, Issue, IssueKind
from bionexus.contracts.messages import AgentMessage, AgentName, MessageType
from bionexus.evidence.matrix import build_matrix
from bionexus.messaging.envelope import new_message
from bionexus.workflow.state import RunState

CHALLENGEABLE_SOURCES = frozenset({"europe_pmc"})


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


def _already_challenged(issue: Issue, state: RunState) -> bool:
    return any(
        m.type is MessageType.EVIDENCE_CHALLENGE and issue.subject in m.evidence_ids
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
        challenges = [self._challenge(message, state, i) for i in self.repairable_issues(state)]
        return AgentResult(issues=issues, outgoing=challenges, assessment=note)

    def repairable_issues(self, state: RunState) -> list[Issue]:
        """Issues a specialist can still fix: not yet challenged, from a challengeable source."""
        issues = find_issues(list(state.evidence.values()))
        return [i for i in issues if self._is_repairable(i, state)]

    @staticmethod
    def _is_repairable(issue: Issue, state: RunState) -> bool:
        record = state.evidence.get(issue.subject)
        if issue.kind is not IssueKind.MISSING_PASSAGE or record is None:
            return False
        return record.source in CHALLENGEABLE_SOURCES and not _already_challenged(issue, state)

    def _challenge(self, parent: AgentMessage, state: RunState, issue: Issue) -> AgentMessage:
        return new_message(
            run_id=state.run_id,
            sender=self.name,
            recipient=AgentName.LITERATURE,
            kind=MessageType.EVIDENCE_CHALLENGE,
            payload={"evidence_id": issue.subject, "ask": "supply the supporting passage"},
            parent=parent,
            evidence_ids=(issue.subject,),
        )
