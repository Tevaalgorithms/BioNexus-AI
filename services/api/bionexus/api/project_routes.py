"""Project spaces: create, list, and invite colleagues."""

from fastapi import APIRouter
from pydantic import BaseModel

from bionexus.api.deps import AppContainer, Caller

router = APIRouter(prefix="/projects")


class NewProject(BaseModel):
    name: str
    description: str = ""


class NewMember(BaseModel):
    user_id: str


@router.get("")
def list_projects(principal: Caller, app: AppContainer) -> list[dict]:
    return app.projects.list_for(principal)


@router.post("", status_code=201)
def create_project(body: NewProject, principal: Caller, app: AppContainer) -> dict:
    project = app.projects.create(principal, body.name, body.description)
    return {
        "project_id": project.project_id,
        "name": project.name,
        "description": project.description,
    }


@router.get("/{project_id}/members")
def members(project_id: str, principal: Caller, app: AppContainer) -> list[str]:
    return app.projects.members(principal, project_id)


@router.post("/{project_id}/members", status_code=201)
def add_member(project_id: str, body: NewMember, principal: Caller, app: AppContainer) -> list[str]:
    return app.projects.add_member(principal, project_id, body.user_id)
