"""Scientist approval of one exact report version, identified by its content hash."""

from collections.abc import Callable

from bionexus.contracts.errors import Conflict
from bionexus.reporting.models import Report, ReportStatus
from bionexus.storage.ports import ReportRepository
from bionexus.workflow.state import RunState


class ReviewService:
    def __init__(self, reports: ReportRepository, resume: Callable[[str, str], None]) -> None:
        self._reports = reports
        self._resume = resume  # continues the paused graph: complete the run, promote memory

    def approve(self, state: RunState, reviewer: str, expected_hash: str) -> Report:
        latest = self._reports.latest(state.run_id)
        self._check_approvable(latest, expected_hash)
        approved = latest.model_copy(
            update={
                "report_id": f"{state.run_id}-v{latest.version + 1}",
                "version": latest.version + 1,
                "status": ReportStatus.APPROVED,
                "parent_version": latest.version,
                "approved_by": reviewer,
            }
        )
        self._reports.add_version(approved)
        self._resume(state.run_id, reviewer)
        return approved

    @staticmethod
    def _check_approvable(latest: Report, expected_hash: str) -> None:
        if latest.status is ReportStatus.APPROVED:
            raise Conflict("This report is already approved")
        if latest.content_hash != expected_hash:
            raise Conflict("The report changed since you opened it; reload and review again")
