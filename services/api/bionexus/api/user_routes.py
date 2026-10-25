"""Platform-admin routes for people: invite, list and disable. The service enforces the rules."""

from fastapi import APIRouter
from pydantic import BaseModel

from bionexus.api.deps import AppContainer, Caller

router = APIRouter(prefix="/admin/users")


class Invitation(BaseModel):
    email: str
    role: str = "scientist"


class Disabling(BaseModel):
    user_id: str


@router.get("")
def users(principal: Caller, app: AppContainer) -> list[dict]:
    return [u.model_dump(mode="json") for u in app.users.list_users(principal)]


@router.post("", status_code=201)
def invite(body: Invitation, principal: Caller, app: AppContainer) -> dict:
    return app.users.invite(principal, body.email, body.role)


@router.post("/disable")
def disable(body: Disabling, principal: Caller, app: AppContainer) -> dict:
    """The email travels in the body, not the URL: addresses may contain characters paths cannot."""
    return app.users.disable(principal, body.user_id)
