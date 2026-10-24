"""Project spaces: a private workspace per study or disease, with colleagues invited in."""

from bionexus.contracts.errors import AccessDenied, Conflict, InvalidRequest, NotFound
from bionexus.contracts.identity import Principal, Role
from bionexus.contracts.project import MAX_PROJECTS_PER_TENANT, Project, slugify
from bionexus.storage.ports import ProjectStore, UserDirectory

MIN_NAME, MAX_NAME = 3, 80


class ProjectService:
    def __init__(self, projects: ProjectStore, users: UserDirectory) -> None:
        self._projects = projects
        self._users = users

    def with_memberships(self, principal: Principal) -> Principal:
        """Fold self-service memberships into the principal on every request (always current)."""
        extra = self._projects.project_ids_for(principal.tenant_id, principal.user_id)
        return principal.model_copy(update={"project_ids": principal.project_ids | extra})

    def create(self, principal: Principal, name: str, description: str = "") -> Project:
        self._require_scientist(principal)
        problems = self._name_problems(name)
        if problems:
            raise InvalidRequest(problems)
        if self._projects.count(principal.tenant_id) >= MAX_PROJECTS_PER_TENANT:
            raise Conflict("Your organisation has reached its project limit")
        project = Project(
            project_id=slugify(name),
            tenant_id=principal.tenant_id,
            name=name.strip(),
            description=description.strip(),
            created_by=principal.user_id,
        )
        self._projects.add(project)  # raises Conflict if the id is taken
        self._projects.add_member(project.tenant_id, project.project_id, principal.user_id)
        return project

    @staticmethod
    def _name_problems(name: str) -> str:
        if not MIN_NAME <= len(name.strip()) <= MAX_NAME:
            return f"Project name must be {MIN_NAME}-{MAX_NAME} characters"
        return "" if slugify(name) else "Project name needs letters or numbers"

    def list_for(self, principal: Principal) -> list[dict]:
        """Every project the caller may open. Operator-assigned ones without a row get a default."""
        stored = {p.project_id: p for p in self._projects.all(principal.tenant_id)}
        return [
            self._summary(stored.get(pid), pid, principal) for pid in sorted(principal.project_ids)
        ]

    @staticmethod
    def _summary(project: Project | None, project_id: str, principal: Principal) -> dict:
        if project is None:
            return {"project_id": project_id, "name": project_id, "description": "", "owner": False}
        owner = project.created_by == principal.user_id
        return {
            "project_id": project_id,
            "name": project.name,
            "description": project.description,
            "owner": owner,
        }

    def members(self, principal: Principal, project_id: str) -> list[str]:
        self._require_member(principal, project_id)
        return self._projects.members(principal.tenant_id, project_id)

    def add_member(self, principal: Principal, project_id: str, user_id: str) -> list[str]:
        project = self._require_owner(principal, project_id)
        target = self._users.find_by_user_id(user_id.strip())
        if (
            target is None
            or target.tenant_id != project.tenant_id
            or target.role is not Role.SCIENTIST
        ):
            raise NotFound("No scientist with that user id exists in your organisation")
        self._projects.add_member(project.tenant_id, project_id, target.user_id)
        return self._projects.members(project.tenant_id, project_id)

    def _require_scientist(self, principal: Principal) -> None:
        if principal.role is not Role.SCIENTIST:
            raise AccessDenied("Only scientists create project spaces")

    def _require_member(self, principal: Principal, project_id: str) -> None:
        if project_id not in principal.project_ids:
            raise AccessDenied("Project membership required")

    def _require_owner(self, principal: Principal, project_id: str) -> Project:
        self._require_member(principal, project_id)
        project = next(
            (p for p in self._projects.all(principal.tenant_id) if p.project_id == project_id),
            None,
        )
        if project is None or project.created_by != principal.user_id:
            raise AccessDenied("Only the project owner can add members")
        return project
