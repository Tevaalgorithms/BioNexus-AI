"""Versioned reports."""

from bionexus.contracts.errors import NotFound
from bionexus.reporting.models import Report
from bionexus.storage.postgres.database import Database, to_jsonb


class PostgresReports:
    def __init__(self, db: Database) -> None:
        self._db = db

    def save_draft(self, report: Report) -> Report:
        self._insert(report)
        return self.versions(report.run_id)[0]

    def add_version(self, report: Report) -> None:
        self._insert(report)

    def _insert(self, report: Report) -> None:
        self._db.execute(
            "INSERT INTO reports (report_id, run_id, version, payload) VALUES (%s, %s, %s, %s)"
            " ON CONFLICT (run_id, version) DO NOTHING",
            (report.report_id, report.run_id, report.version, to_jsonb(report)),
        )

    def versions(self, run_id: str) -> list[Report]:
        rows = self._db.fetch_all(
            "SELECT payload FROM reports WHERE run_id = %s ORDER BY version", (run_id,)
        )
        return [Report.model_validate(r["payload"]) for r in rows]

    def latest(self, run_id: str) -> Report:
        versions = self.versions(run_id)
        if not versions:
            raise NotFound(f"No report exists for run '{run_id}'")
        return versions[-1]
