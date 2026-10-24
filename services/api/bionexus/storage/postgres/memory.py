"""Project memory: reviewed evidence promoted from earlier runs."""

from datetime import date

from bionexus.contracts.evidence import EvidenceRecord, ReviewState
from bionexus.storage.postgres.database import Database, to_jsonb


class PostgresMemory:
    def __init__(self, db: Database) -> None:
        self._db = db

    def promote(self, tenant_id: str, project_id: str, records: list[EvidenceRecord]) -> None:
        for record in records:
            reviewed = record.model_copy(update={"review_state": ReviewState.REVIEWED})
            self._db.execute(
                """INSERT INTO memory_items (tenant_id, project_id, evidence_id, target, record)
                   VALUES (%s, %s, %s, %s, %s)
                   ON CONFLICT (tenant_id, project_id, evidence_id)
                   DO UPDATE SET record = EXCLUDED.record""",
                (tenant_id, project_id, record.evidence_id, record.target, to_jsonb(reviewed)),
            )

    def exclude(self, tenant_id: str, project_id: str, evidence_id: str) -> None:
        self._db.execute(
            """UPDATE memory_items SET record = jsonb_set(record, '{review_state}', '"excluded"')
               WHERE tenant_id = %s AND project_id = %s AND evidence_id = %s""",
            (tenant_id, project_id, evidence_id),
        )

    def recall(
        self, tenant_id: str, project_id: str, targets: tuple[str, ...], cutoff: date
    ) -> list[EvidenceRecord]:
        rows = self._db.fetch_all(
            """SELECT record FROM memory_items
               WHERE tenant_id = %s AND project_id = %s AND target = ANY(%s)
                 AND record->>'review_state' = 'reviewed'
                 AND (record->>'license_ok')::boolean
                 AND (record->>'available_on')::date <= %s""",
            (tenant_id, project_id, list(targets), cutoff),
        )
        return [EvidenceRecord.model_validate(r["record"]) for r in rows]
