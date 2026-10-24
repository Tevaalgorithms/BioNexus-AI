"""The approved-model catalogue."""

from psycopg.types.json import Jsonb

from bionexus.storage.postgres.database import Database


class PostgresCatalog:
    def __init__(self, db: Database) -> None:
        self._db = db

    def get(self, model_id: str) -> dict | None:
        row = self._db.fetch_one("SELECT payload FROM model_specs WHERE model_id = %s", (model_id,))
        return row["payload"] if row else None

    def put(self, row: dict) -> None:
        self._db.execute(
            """INSERT INTO model_specs (model_id, payload) VALUES (%s, %s)
               ON CONFLICT (model_id)
               DO UPDATE SET payload = EXCLUDED.payload, updated_at = now()""",
            (row["model_id"], Jsonb(row)),
        )

    def list(self) -> list[dict]:
        return [
            r["payload"]
            for r in self._db.fetch_all("SELECT payload FROM model_specs ORDER BY model_id")
        ]
