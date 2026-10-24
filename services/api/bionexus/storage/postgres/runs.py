"""Run state persistence."""

from bionexus.contracts.errors import NotFound
from bionexus.storage.postgres.database import Database, to_jsonb
from bionexus.workflow.state import RunState


class PostgresRuns:
    def __init__(self, db: Database) -> None:
        self._db = db

    def save(self, state: RunState) -> None:
        self._db.execute(
            """INSERT INTO runs (run_id, tenant_id, project_id, status, state)
               VALUES (%s, %s, %s, %s, %s)
               ON CONFLICT (run_id) DO UPDATE
               SET status = EXCLUDED.status, state = EXCLUDED.state, updated_at = now()""",
            (state.run_id, state.tenant_id, state.project_id, state.status.value, to_jsonb(state)),
        )

    def load(self, run_id: str) -> RunState:
        row = self._db.fetch_one("SELECT state FROM runs WHERE run_id = %s", (run_id,))
        if row is None:
            raise NotFound(f"Run '{run_id}' does not exist")
        return RunState.model_validate(row["state"])

    def request_cancel(self, run_id: str) -> None:
        self._db.execute("UPDATE runs SET cancel_requested = true WHERE run_id = %s", (run_id,))

    def cancel_requested(self, run_id: str) -> bool:
        row = self._db.fetch_one("SELECT cancel_requested FROM runs WHERE run_id = %s", (run_id,))
        return bool(row and row["cancel_requested"])

    def list_all(self) -> list[RunState]:
        rows = self._db.fetch_all("SELECT state FROM runs ORDER BY updated_at DESC")
        return [RunState.model_validate(r["state"]) for r in rows]

    def list_for_project(self, tenant_id: str, project_id: str) -> list[RunState]:
        rows = self._db.fetch_all(
            "SELECT state FROM runs WHERE tenant_id = %s AND project_id = %s"
            " ORDER BY updated_at DESC",
            (tenant_id, project_id),
        )
        return [RunState.model_validate(r["state"]) for r in rows]
