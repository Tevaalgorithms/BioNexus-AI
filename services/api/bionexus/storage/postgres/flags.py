"""System flags, such as the kill switch."""

from bionexus.storage.postgres.database import Database


class PostgresFlags:
    def __init__(self, db: Database) -> None:
        self._db = db

    def is_set(self, name: str) -> bool:
        row = self._db.fetch_one("SELECT value FROM system_flags WHERE name = %s", (name,))
        return bool(row and row["value"])

    def set(self, name: str, value: bool) -> None:
        self._db.execute(
            """INSERT INTO system_flags (name, value) VALUES (%s, %s)
               ON CONFLICT (name) DO UPDATE SET value = EXCLUDED.value""",
            (name, value),
        )
