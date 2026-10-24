"""Projects and their members."""

from bionexus.contracts.errors import Conflict
from bionexus.contracts.project import Project
from bionexus.storage.postgres.database import Database


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

    def all(self, tenant_id: str) -> list[Project]:
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
