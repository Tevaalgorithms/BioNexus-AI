"""Scientist-requested revision: exclude evidence (with a reason) and regenerate the draft."""

from bionexus.agents.critic import find_issues
from bionexus.agents.synthesizer import SynthesizerAgent
from bionexus.contracts.errors import Conflict, InvalidRequest
from bionexus.contracts.evidence import Exclusion
from bionexus.contracts.investigation import InvestigationStatus
from bionexus.reporting.builder import ReportBuilder
from bionexus.reporting.models import Report
from bionexus.storage.ports import AuditStore, MemoryStore, ReportRepository, RunStore
from bionexus.workflow.state import RunState


def _revision_problems(state: RunState, evidence_ids: list[str], reason: str) -> list[str]:
    unknown = [e for e in evidence_ids if e not in state.evidence]
    checks = [
        (not reason.strip(), "A reason is required to exclude evidence"),
        (bool(unknown), f"Unknown evidence: {unknown}"),
    ]
    return [message for failed, message in checks if failed]


class RevisionService:
    def __init__(
        self,
        *,
        synthesizer: SynthesizerAgent,
        builder: ReportBuilder,
        reports: ReportRepository,
        runs: RunStore,
        memory: MemoryStore,
        audit: AuditStore,
    ) -> None:
        self._synthesizer = synthesizer
        self._builder = builder
        self._reports = reports
        self._runs = runs
        self._memory = memory
        self._audit = audit

    def exclude_evidence(
        self, state: RunState, reviewer: str, evidence_ids: list[str], reason: str
    ) -> Report:
        self._check_revisable(state, evidence_ids, reason)
        for evidence_id in evidence_ids:
            del state.evidence[evidence_id]
            state.excluded.append(
                Exclusion(evidence_id=evidence_id, reason=f"excluded by scientist: {reason}")
            )
            self._memory.exclude(state.tenant_id, state.project_id, evidence_id)
        state.issues = find_issues(list(state.evidence.values()))
        synthesis = self._synthesizer.write(state)
        state.claims, state.narrative = synthesis.claims, synthesis.narrative
        draft = self._new_draft(state)
        self._audit.record(
            reviewer, "evidence.excluded", f"{state.run_id}: {evidence_ids} ({reason})"
        )
        return draft

    @staticmethod
    def _check_revisable(state: RunState, evidence_ids: list[str], reason: str) -> None:
        if state.status is not InvestigationStatus.WAITING_FOR_REVIEW:
            raise Conflict("Only a run waiting for review can be revised")
        problems = _revision_problems(state, evidence_ids, reason)
        if problems:
            raise InvalidRequest("; ".join(problems))

    def _new_draft(self, state: RunState) -> Report:
        latest = self._reports.latest(state.run_id)
        draft = self._builder.build_draft(state, latest.version + 1, latest.version)
        self._reports.add_version(draft)
        state.report_id = draft.report_id
        self._runs.save(state)
        return draft
