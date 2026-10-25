"""Evidence critic: finds problems, explains conflicts, and asks specialists for bounded repairs.

Plain code finds the problems (a missing passage, a conflict, one study family). A model then reads
each conflict and says whether it looks real or could be explained, and may ask a specialist for
more evidence. That explanation is unreviewed model text and is labelled so.
"""

from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from typing import ClassVar

from bionexus.agents.base import Agent, AgentResult
from bionexus.agents.conflict import conflict_prompt, read_analysis, sides
from bionexus.agents.evidence_requests import PlannedRequest, request_message
from bionexus.agents.optimization import (
    AO_MAX_CONFLICT_ANALYSES,
    AO_MAX_PARALLEL_MODEL_CALLS,
    AO_MAX_RECHECKS_PER_ROUND,
)
from bionexus.contracts.errors import ModelUnavailable
from bionexus.contracts.evidence import EvidenceRecord, Issue, IssueKind
from bionexus.contracts.messages import AgentMessage, AgentName, ChallengeAsk, MessageType
from bionexus.contracts.review import ConflictAnalysis
from bionexus.evidence.matrix import build_matrix
from bionexus.evidence.stance import is_model_read
from bionexus.messaging.envelope import new_message
from bionexus.messaging.router import exchanges_available
from bionexus.workflow.state import RunState

CHALLENGEABLE_SOURCES = frozenset({"europe_pmc"})
MESSAGE_RESERVE = 6  # room kept for the critic's own task and reply, and the verifier's
CONFLICT_SKILL = "conflict.analyse"  # the skill that guides the explanation


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
        challenges = [self._challenge(message, state, r) for r in self.pending_repairs(state)]
        room = self._room(state) - len(challenges)
        analyses, requests = self._analyse(message, state, issues, room)
        note = (
            f"{len(issues)} open issues; {len(challenges)} challenges and {len(requests)} requests."
        )
        return AgentResult(
            issues=issues, outgoing=[*challenges, *requests], analyses=analyses, assessment=note
        )

    def has_work(self, state: RunState) -> bool:
        """True while something can still be asked or explained (the repair loop's condition)."""
        issues = find_issues(list(state.evidence.values()))
        return bool(self.pending_repairs(state)) or bool(self._unanalysed(issues, state))

    @staticmethod
    def _unanalysed(issues: list[Issue], state: RunState) -> list[Issue]:
        """Conflicts not yet explained, a few per round."""
        new = [
            i
            for i in issues
            if i.kind is IssueKind.CONTRADICTION and i.subject not in state.analyses
        ]
        return new[:AO_MAX_CONFLICT_ANALYSES]

    def _analyse(
        self, parent: AgentMessage, state: RunState, issues: list[Issue], room: int
    ) -> tuple[list[ConflictAnalysis], list[AgentMessage]]:
        """A model reads each conflict (in parallel); any extra search it wants is requested."""
        pending = self._unanalysed(issues, state)
        if not pending:
            return [], []
        with ThreadPoolExecutor(max_workers=AO_MAX_PARALLEL_MODEL_CALLS) as pool:
            judged = list(pool.map(lambda issue: self._judge(state, issue.subject), pending))
        done = [j for j in judged if j is not None]
        wanted = [req for _, req in done if req is not None][: max(0, room)]
        requests = [request_message(self.name, parent, state, req) for req in wanted]
        return [analysis for analysis, _ in done], requests

    def _judge(
        self, state: RunState, target: str
    ) -> tuple[ConflictAnalysis, PlannedRequest | None] | None:
        supporting, opposing = sides(list(state.evidence.values()), target)
        try:
            reply = self.ask_model(
                state, conflict_prompt(target, supporting, opposing), CONFLICT_SKILL
            )
        except ModelUnavailable:  # the explanation is optional: no model, no explanation
            return None
        return read_analysis(reply, target)

    def pending_repairs(self, state: RunState) -> list[Repair]:
        """Challenges a specialist can act on, not yet sent, that fit the message budget."""
        issues = find_issues(list(state.evidence.values()))
        repairs = [r for issue in issues for r in self._repairs_for(issue, state)]
        return repairs[: self._room(state)]

    @staticmethod
    def _room(state: RunState) -> int:
        """A challenge costs two messages (ask and reply); the router caps the run."""
        return exchanges_available(state, MESSAGE_RESERVE)

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
        return [Repair(evidence_id, ask) for evidence_id in candidates[:AO_MAX_RECHECKS_PER_ROUND]]

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
