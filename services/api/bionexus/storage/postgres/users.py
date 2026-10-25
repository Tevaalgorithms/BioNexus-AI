"""Application accounts: roles, tenants, project membership and session revocation."""

from datetime import datetime

from bionexus.contracts.identity import Principal, Role, UserRecord
from bionexus.storage.postgres.database import Database


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

    def list_users(self, tenant_id: str) -> list[UserRecord]:
        rows = self._db.fetch_all(
            "SELECT user_id, role, tenant_id, active FROM app_users"
            " WHERE tenant_id = %s ORDER BY user_id",
            (tenant_id,),
        )
        return [UserRecord(**row) for row in rows]

    def subject_for(self, user_id: str) -> str | None:
        row = self._db.fetch_one("SELECT subject FROM app_users WHERE user_id = %s", (user_id,))
        return row["subject"] if row else None

    def disable(self, subject: str) -> None:
        self._db.execute("UPDATE app_users SET active = false WHERE subject = %s", (subject,))
