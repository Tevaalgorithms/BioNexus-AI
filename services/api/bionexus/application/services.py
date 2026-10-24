"""Scientist-facing application services: authorization meets business operations here."""

import uuid
from collections.abc import Callable
from datetime import UTC, datetime

from bionexus.auth.policy import require_project_member
from bionexus.config import Settings
from bionexus.contracts.errors import BudgetExceeded, Conflict
from bionexus.contracts.identity import Principal
from bionexus.contracts.investigation import (
    ALLOWED_TRANSITIONS,
    InvestigationRequest,
    InvestigationStatus,
)
from bionexus.llm.release import ReleaseStore
from bionexus.reporting.docx_export import render_docx
from bionexus.reporting.models import Report
from bionexus.reporting.review import ReviewService
from bionexus.reporting.revision import RevisionService
from bionexus.reporting.validation import validate_for_export
from bionexus.storage.models import RunEvent
from bionexus.storage.ports import EventStore, JobStore, ReportRepository, RunStore
from bionexus.workflow.budget import Budget
from bionexus.workflow.state import RunState

TERMINAL = frozenset({InvestigationStatus.COMPLETED, InvestigationStatus.CANCELLED})


class InvestigationService:
    def __init__(
        self,
        *,
        settings: Callable[[], Settings],
        runs: RunStore,
        queue: JobStore,
        releases: ReleaseStore,
        reports: ReportRepository,
        review: ReviewService,
        revision: RevisionService,
        events: EventStore,
    ) -> None:
        self._settings = settings
        self._runs = runs
        self._queue = queue
        self._releases = releases
        self._reports = reports
        self._review = review
        self._revision = revision
        self._events = events

    def submit(
        self,
        principal: Principal,
        project_id: str,
        request: InvestigationRequest,
        idempotency_key: str,
    ) -> RunState:
        require_project_member(principal, principal.tenant_id, project_id)
        key = f"{principal.user_id}:{idempotency_key}"
        existing = self._queue.find(key)
        if existing:
            return self._runs.load(existing.run_id)
        settings = self._settings()  # read once per submission; SSM edits apply live
        self._check_tenant_budget(principal.tenant_id, settings)
        state = self._new_run(principal, project_id, request, settings)
        self._runs.save(state)
        self._queue.enqueue(state.run_id, key)
        return state

    def _new_run(
        self,
        principal: Principal,
        project_id: str,
        request: InvestigationRequest,
        settings: Settings,
    ) -> RunState:
        return RunState(
            run_id=f"run-{uuid.uuid4().hex[:12]}",
            tenant_id=principal.tenant_id,
            project_id=project_id,
            created_by=principal.user_id,
            request=request,
            release_id=self._releases.active().release_id,  # pinned for the life of the run
            budget=Budget(
                max_cost_usd=settings.run_budget_usd,
                max_calls=settings.run_max_model_calls,
                warn_usd=settings.run_warn_usd,
            ),
        )

    def _check_tenant_budget(self, tenant_id: str, settings: Settings) -> None:
        now = datetime.now(UTC)
        spent = sum(
            run.budget.spent_usd
            for run in self._runs.list_all()
            if run.tenant_id == tenant_id
            and (run.created_at.year, run.created_at.month) == (now.year, now.month)
        )
        if spent >= settings.tenant_monthly_budget_usd:
            raise BudgetExceeded("The organisation's monthly model budget is used up")

    def get(self, principal: Principal, run_id: str) -> RunState:
        state = self._runs.load(run_id)
        require_project_member(principal, state.tenant_id, state.project_id)
        return state

    def history(self, principal: Principal, project_id: str) -> list[RunState]:
        require_project_member(principal, principal.tenant_id, project_id)
        return self._runs.list_for_project(principal.tenant_id, project_id)

    def report(self, principal: Principal, run_id: str) -> Report:
        self.get(principal, run_id)
        return self._reports.latest(run_id)

    def report_versions(self, principal: Principal, run_id: str) -> list[Report]:
        self.get(principal, run_id)
        return self._reports.versions(run_id)

    def export_docx(self, principal: Principal, run_id: str) -> bytes:
        state = self.get(principal, run_id)
        validate_for_export(state)
        return render_docx(state, self._reports.latest(run_id))

    def approve(self, principal: Principal, run_id: str, expected_hash: str) -> Report:
        state = self.get(principal, run_id)
        return self._review.approve(state, principal.user_id, expected_hash)

    def exclude_evidence(
        self, principal: Principal, run_id: str, evidence_ids: list[str], reason: str
    ) -> Report:
        state = self.get(principal, run_id)
        return self._revision.exclude_evidence(state, principal.user_id, evidence_ids, reason)

    def cancel(self, principal: Principal, run_id: str) -> RunState:
        state = self.get(principal, run_id)
        if InvestigationStatus.CANCELLED not in ALLOWED_TRANSITIONS[state.status]:
            raise Conflict(f"A run that is {state.status} cannot be cancelled")
        self._runs.request_cancel(run_id)
        return state

    def events(self, principal: Principal, run_id: str, after_seq: int) -> list[RunEvent]:
        self.get(principal, run_id)
        return self._events.since(run_id, after_seq)

    def is_finished(self, principal: Principal, run_id: str) -> bool:
        status = self.get(principal, run_id).status
        return status in TERMINAL or status in {
            InvestigationStatus.WAITING_FOR_REVIEW,
            InvestigationStatus.INCOMPLETE,
            InvestigationStatus.FAILED,
        }
