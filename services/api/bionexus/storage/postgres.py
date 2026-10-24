"""PostgreSQL adapters implementing the storage ports. Payloads are JSONB; hot columns are real."""

import uuid
from datetime import date, datetime

from langgraph.checkpoint.postgres import PostgresSaver
from psycopg.abc import Query
from psycopg.rows import dict_row
from psycopg.types.json import Jsonb
from psycopg_pool import ConnectionPool

from bionexus.contracts.errors import Conflict, NotFound
from bionexus.contracts.evidence import EvidenceRecord, ReviewState
from bionexus.contracts.identity import Principal, Role
from bionexus.contracts.project import Project
from bionexus.jobs.models import Job
from bionexus.llm.models import ConfigRelease
from bionexus.reporting.models import Report
from bionexus.storage.in_memory import LEASE_SECONDS, MAX_ATTEMPTS
from bionexus.storage.models import AuditEvent, RunEvent
from bionexus.storage.ports import Storage
from bionexus.workflow.state import RunState


class Database:
    """Thin wrapper so adapters stay free of connection handling."""

    def __init__(self, dsn: str) -> None:
        self._dsn = dsn
        self._checkpoint_pool: ConnectionPool | None = None
        self._pool = ConnectionPool(
            dsn, min_size=1, max_size=5, open=True, kwargs={"row_factory": dict_row}
        )

    def fetch_all(self, sql: Query, params: tuple | dict = ()) -> list[dict]:
        with self._pool.connection() as conn:
            return conn.execute(sql, params).fetchall()

    def fetch_one(self, sql: Query, params: tuple | dict = ()) -> dict | None:
        rows = self.fetch_all(sql, params)
        return rows[0] if rows else None

    def execute(self, sql: Query, params: tuple | dict = ()) -> None:
        with self._pool.connection() as conn:
            conn.execute(sql, params)

    def checkpoint_saver(self) -> PostgresSaver:
        """LangGraph's durable checkpoints. It needs its own autocommit connections."""
        self._checkpoint_pool = ConnectionPool(
            self._dsn,
            min_size=1,
            max_size=5,
            open=True,
            kwargs={"autocommit": True, "prepare_threshold": 0, "row_factory": dict_row},
        )
        saver = PostgresSaver(self._checkpoint_pool)
        saver.setup()  # creates/updates LangGraph's own tables
        return saver

    def close(self) -> None:
        self._pool.close()
        if self._checkpoint_pool is not None:
            self._checkpoint_pool.close()


def _json(model) -> Jsonb:
    return Jsonb(model.model_dump(mode="json"))


class PostgresRuns:
    def __init__(self, db: Database) -> None:
        self._db = db

    def save(self, state: RunState) -> None:
        self._db.execute(
            """INSERT INTO runs (run_id, tenant_id, project_id, status, state)
               VALUES (%s, %s, %s, %s, %s)
               ON CONFLICT (run_id) DO UPDATE
               SET status = EXCLUDED.status, state = EXCLUDED.state, updated_at = now()""",
            (state.run_id, state.tenant_id, state.project_id, state.status.value, _json(state)),
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


class PostgresJobs:
    def __init__(self, db: Database) -> None:
        self._db = db

    def find(self, idempotency_key: str) -> Job | None:
        row = self._db.fetch_one(
            "SELECT * FROM jobs WHERE idempotency_key = %s", (idempotency_key,)
        )
        return Job(**_job_fields(row)) if row else None

    def enqueue(self, run_id: str, idempotency_key: str) -> Job:
        job_id = uuid.uuid4().hex
        self._db.execute(
            "INSERT INTO jobs (job_id, run_id, idempotency_key) VALUES (%s, %s, %s)"
            " ON CONFLICT (idempotency_key) DO NOTHING",
            (job_id, run_id, idempotency_key),
        )
        found = self.find(idempotency_key)
        if found is None:
            raise RuntimeError("job was not stored")
        return found

    def lease(self, now: datetime) -> Job | None:
        """Atomic claim using SKIP LOCKED so concurrent workers never take the same job."""
        row = self._db.fetch_one(
            """UPDATE jobs SET attempts = attempts + 1,
                      lease_expires = %s + make_interval(secs => %s)
               WHERE job_id = (
                   SELECT job_id FROM jobs
                   WHERE NOT done AND attempts < %s
                     AND (lease_expires IS NULL OR lease_expires <= %s)
                   ORDER BY created_at FOR UPDATE SKIP LOCKED LIMIT 1)
               RETURNING *""",
            (now, LEASE_SECONDS, MAX_ATTEMPTS, now),
        )
        return Job(**_job_fields(row)) if row else None

    def complete(self, job: Job) -> None:
        self._db.execute(
            "UPDATE jobs SET done = true, lease_expires = NULL WHERE job_id = %s", (job.job_id,)
        )

    def depth(self) -> int:
        row = self._db.fetch_one("SELECT count(*) AS n FROM jobs WHERE NOT done")
        return int(row["n"]) if row else 0


def _job_fields(row: dict) -> dict:
    keys = ("job_id", "run_id", "idempotency_key", "done", "attempts", "lease_expires")
    return {k: row[k] for k in keys}


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
            (report.report_id, report.run_id, report.version, _json(report)),
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
                (tenant_id, project_id, record.evidence_id, record.target, _json(reviewed)),
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


class PostgresReleases:
    def __init__(self, db: Database) -> None:
        self._db = db

    def add(self, release: ConfigRelease, *, activate: bool) -> None:
        if activate:
            self._db.execute("UPDATE releases SET is_active = false WHERE is_active")
        try:
            self._db.execute(
                "INSERT INTO releases (release_id, revision, payload, is_active)"
                " VALUES (%s, %s, %s, %s)",
                (release.release_id, release.revision, _json(release), activate),
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


class PostgresUsers:
    def __init__(self, db: Database) -> None:
        self._db = db

    def find_by_subject(self, subject: str) -> Principal | None:
        user = self._db.fetch_one(
            "SELECT * FROM app_users WHERE subject = %s AND active", (subject,)
        )
        if user is None:
            return None
        rows = self._db.fetch_all(
            "SELECT project_id FROM memberships WHERE subject = %s", (subject,)
        )
        return Principal(
            user_id=user["user_id"],
            role=Role(user["role"]),
            tenant_id=user["tenant_id"],
            project_ids=frozenset(r["project_id"] for r in rows),
        )

    def find_by_user_id(self, user_id: str) -> Principal | None:
        row = self._db.fetch_one(
            "SELECT subject FROM app_users WHERE user_id = %s AND active", (user_id,)
        )
        return self.find_by_subject(row["subject"]) if row else None

    def revoked_before(self, subject: str) -> datetime | None:
        row = self._db.fetch_one(
            "SELECT revoked_before FROM app_users WHERE subject = %s", (subject,)
        )
        return row["revoked_before"] if row else None

    def revoke_sessions(self, subject: str, at: datetime) -> None:
        self._db.execute(
            "UPDATE app_users SET revoked_before = %s WHERE subject = %s", (at, subject)
        )

    def upsert(self, subject: str, principal: Principal) -> None:
        self._db.execute(
            """INSERT INTO app_users (subject, user_id, role, tenant_id, active)
               VALUES (%s, %s, %s, %s, true)
               ON CONFLICT (subject) DO UPDATE
               SET role = EXCLUDED.role, tenant_id = EXCLUDED.tenant_id, active = true""",
            (subject, principal.user_id, principal.role.value, principal.tenant_id),
        )
        self._db.execute("DELETE FROM memberships WHERE subject = %s", (subject,))
        for project_id in principal.project_ids:
            self._db.execute(
                "INSERT INTO memberships (subject, project_id) VALUES (%s, %s)",
                (subject, project_id),
            )

    def disable(self, subject: str) -> None:
        self._db.execute("UPDATE app_users SET active = false WHERE subject = %s", (subject,))


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


class PostgresProjects:
    def __init__(self, db: Database) -> None:
        self._db = db

    def add(self, project: Project) -> None:
        try:
            self._db.execute(
                """INSERT INTO projects
                   (tenant_id, project_id, name, description, created_by, created_at)
                   VALUES (%s, %s, %s, %s, %s, %s)""",
                (
                    project.tenant_id,
                    project.project_id,
                    project.name,
                    project.description,
                    project.created_by,
                    project.created_at,
                ),
            )
        except Exception as error:  # primary-key violation: the id is taken in this tenant
            raise Conflict(f"A project named '{project.project_id}' already exists") from error

    def list(self, tenant_id: str) -> list[Project]:
        rows = self._db.fetch_all(
            "SELECT * FROM projects WHERE tenant_id = %s ORDER BY created_at", (tenant_id,)
        )
        return [Project(**row) for row in rows]

    def count(self, tenant_id: str) -> int:
        row = self._db.fetch_one(
            "SELECT count(*) AS n FROM projects WHERE tenant_id = %s", (tenant_id,)
        )
        return int(row["n"]) if row else 0

    def add_member(self, tenant_id: str, project_id: str, user_id: str) -> None:
        self._db.execute(
            "INSERT INTO project_members (tenant_id, project_id, user_id)"
            " VALUES (%s, %s, %s) ON CONFLICT DO NOTHING",
            (tenant_id, project_id, user_id),
        )

    def members(self, tenant_id: str, project_id: str) -> list[str]:
        rows = self._db.fetch_all(
            "SELECT user_id FROM project_members"
            " WHERE tenant_id = %s AND project_id = %s ORDER BY user_id",
            (tenant_id, project_id),
        )
        return [r["user_id"] for r in rows]

    def project_ids_for(self, tenant_id: str, user_id: str) -> frozenset[str]:
        rows = self._db.fetch_all(
            "SELECT project_id FROM project_members WHERE tenant_id = %s AND user_id = %s",
            (tenant_id, user_id),
        )
        return frozenset(r["project_id"] for r in rows)


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


def postgres_storage(db: Database, embedding_dim: int = 64) -> Storage:
    return Storage(
        runs=PostgresRuns(db),
        jobs=PostgresJobs(db),
        reports=PostgresReports(db),
        audit=PostgresAudit(db),
        memory=PostgresMemory(db),
        releases=PostgresReleases(db),
        users=PostgresUsers(db),
        events=PostgresEvents(db),
        flags=PostgresFlags(db),
        catalog=PostgresCatalog(db),
        checkpointer=db.checkpoint_saver(),
        projects=PostgresProjects(db),
        retrieval=PostgresRetrieval(db, embedding_dim),
    )


from bionexus.retrieval.postgres import PostgresRetrieval  # noqa: E402  (avoids an import cycle)
