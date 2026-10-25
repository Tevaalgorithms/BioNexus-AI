"""Who is calling. Built only from verified server-side state, never from browser input."""

from enum import StrEnum

from pydantic import BaseModel, ConfigDict


class Role(StrEnum):
    PLATFORM_ADMIN = "platform_admin"
    SCIENTIST = "scientist"


class ClientKind(StrEnum):
    """Which login entry point issued the session. Necessary for admin APIs, never sufficient."""

    ADMIN = "admin"
    SCIENTIST = "scientist"
    UNSPECIFIED = "unspecified"


class UserRecord(BaseModel):
    """An account as an administrator sees it. The identity provider's subject is never shown."""

    user_id: str
    role: Role
    tenant_id: str
    active: bool = True


class Principal(BaseModel):
    model_config = ConfigDict(frozen=True)

    user_id: str
    role: Role
    tenant_id: str
    project_ids: frozenset[str] = frozenset()
    client_kind: ClientKind = ClientKind.UNSPECIFIED
