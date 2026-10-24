"""The per-run event log that feeds the live activity stream."""

from psycopg.types.json import Jsonb

from bionexus.storage.models import RunEvent
from bionexus.storage.postgres.database import Database


class PostgresEvents:
    def __init__(self, db: Database) -> None:
        self._db = db

    def append(self, run_id: str, kind: str, data: dict) -> RunEvent:
        row = self._db.fetch_one(
            "INSERT INTO run_events (run_id, kind, data) VALUES (%s, %s, %s) RETURNING seq",
            (run_id, kind, Jsonb(data)),
        )
        if row is None:
            raise RuntimeError("event was not stored")
        return RunEvent(run_id=run_id, seq=row["seq"], kind=kind, data=data)

    def since(self, run_id: str, after_seq: int) -> list[RunEvent]:
        rows = self._db.fetch_all(
            "SELECT seq, kind, data FROM run_events WHERE run_id = %s AND seq > %s ORDER BY seq",
            (run_id, after_seq),
        )
        return [RunEvent(run_id=run_id, **row) for row in rows]
