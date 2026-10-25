"""Immutable configuration releases."""

from bionexus.contracts.errors import Conflict, NotFound
from bionexus.llm.models import ConfigRelease
from bionexus.storage.postgres.database import Database, to_jsonb


class PostgresReleases:
    def __init__(self, db: Database) -> None:
        self._db = db

    def add(self, release: ConfigRelease, *, activate: bool) -> None:
        try:
            # One transaction: if the insert fails, the old release stays active. Without it a
            # failed insert would leave the system with no active release.
            with self._db.transaction() as conn:
                if activate:
                    conn.execute("UPDATE releases SET is_active = false WHERE is_active")
                conn.execute(
                    "INSERT INTO releases (release_id, revision, payload, is_active)"
                    " VALUES (%s, %s, %s, %s)",
                    (release.release_id, release.revision, to_jsonb(release), activate),
                )
        except Exception as error:  # unique revision violated by a concurrent admin edit
            raise Conflict("Another admin changed the configuration first") from error

    def get(self, release_id: str) -> ConfigRelease | None:
        row = self._db.fetch_one(
            "SELECT payload FROM releases WHERE release_id = %s", (release_id,)
        )
        return ConfigRelease.model_validate(row["payload"]) if row else None

    def active(self) -> ConfigRelease:
        row = self._db.fetch_one("SELECT payload FROM releases WHERE is_active")
        if row is None:
            raise NotFound("No active configuration release")
        return ConfigRelease.model_validate(row["payload"])

    def history(self) -> list[ConfigRelease]:
        rows = self._db.fetch_all("SELECT payload FROM releases ORDER BY revision")
        return [ConfigRelease.model_validate(r["payload"]) for r in rows]
