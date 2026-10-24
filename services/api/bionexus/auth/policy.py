"""Authorization rules. The server decides; role or tenant claims from the browser are ignored."""

from typing import Protocol

from bionexus.contracts.errors import AccessDenied
from bionexus.contracts.identity import ClientKind, Principal, Role


class TokenVerifier(Protocol):
    """Turns a bearer token into a Principal. The production adapter validates Cognito JWTs."""

    def verify(self, token: str) -> Principal: ...


class StaticTokenVerifier:
    """Development and test verifier backed by a fixed token table."""

    def __init__(self, principals: dict[str, Principal]) -> None:
        self._principals = principals

    def verify(self, token: str) -> Principal:
        principal = self._principals.get(token)
        if principal is None:
            raise AccessDenied("Unknown or expired credentials")
        return principal


def require_admin(principal: Principal) -> None:
    """Admin APIs need the admin role (server-side) AND the admin login client."""
    if principal.role is not Role.PLATFORM_ADMIN:
        raise AccessDenied("Platform admin role required")
    if principal.client_kind is not ClientKind.ADMIN:
        raise AccessDenied("Admin operations require the admin sign-in")


def require_project_member(principal: Principal, tenant_id: str, project_id: str) -> None:
    """Admins get no implicit access to scientific data (AUTH-12)."""
    same_tenant = principal.tenant_id == tenant_id
    if not (same_tenant and project_id in principal.project_ids):
        raise AccessDenied("Project membership required")
