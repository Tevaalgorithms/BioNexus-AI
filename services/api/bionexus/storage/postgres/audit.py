"""The append-only audit trail."""

from bionexus.storage.models import AuditEvent
from bionexus.storage.postgres.database import Database


class PostgresAudit:
    def __init__(self, db: Database) -> None:
        self._db = db

    def record(self, actor: str, action: str, detail: str) -> None:
        self._db.execute(
            "INSERT INTO audit_events (actor, action, detail) VALUES (%s, %s, %s)",
            (actor, action, detail),
        )

    def events(self) -> list[AuditEvent]:
        rows = self._db.fetch_all("SELECT actor, action, detail, at FROM audit_events ORDER BY id")
        return [AuditEvent(**row) for row in rows]
