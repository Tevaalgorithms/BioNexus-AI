"""Inviting, listing and disabling users. Platform admins only.

An invitation creates the sign-in account in the identity provider, which emails the person a
temporary password (this code never sees it), and records the person's role here. The role is
decided here, by the server, and never by the browser or the identity provider.
"""

import re
from datetime import UTC, datetime, timedelta

from bionexus.auth.policy import require_admin
from bionexus.auth.provisioner import UserProvisioner
from bionexus.contracts.errors import (
    Conflict,
    InvalidRequest,
    NotFound,
    ProvisioningFailed,
    RateLimited,
)
from bionexus.contracts.identity import Principal, Role, UserRecord
from bionexus.storage.ports import AuditStore, UserDirectory

MAX_INVITES_PER_DAY = 25  # per administrator; also keeps within the identity provider's email limit
MAX_EMAIL_CHARS = 254
EMAIL = re.compile(r"^[^@\s\"'<>(),;:]{1,64}@[A-Za-z0-9.-]+\.[A-Za-z]{2,}$")


def clean_email(value: str) -> str:
    address = value.strip().lower()
    if len(address) > MAX_EMAIL_CHARS or not EMAIL.match(address):
        raise InvalidRequest("Enter a valid email address")
    return address


def parse_role(value: str) -> Role:
    try:
        return Role(value)
    except ValueError:
        allowed = ", ".join(r.value for r in Role)
        raise InvalidRequest(f"Role must be one of: {allowed}") from None


class UserService:
    def __init__(self, users: UserDirectory, provisioner: UserProvisioner, audit: AuditStore):
        self._users = users
        self._provisioner = provisioner
        self._audit = audit

    def list_users(self, principal: Principal) -> list[UserRecord]:
        require_admin(principal)
        return self._users.list_users(principal.tenant_id)

    def invite(self, principal: Principal, email: str, role: str) -> dict:
        require_admin(principal)
        address, chosen = clean_email(email), parse_role(role)
        if self._users.find_by_user_id(address) is not None:
            raise Conflict(f"{address} already has access")
        self._check_rate(principal)
        invitation = self._provisioner.invite(address, chosen)
        person = Principal(user_id=address, role=chosen, tenant_id=principal.tenant_id)
        self._users.upsert(invitation.subject, person)
        self._audit.record(principal.user_id, "user.invited", f"{address} as {chosen.value}")
        return {
            "user_id": address,
            "role": chosen.value,
            "emailed": invitation.emailed,
            "existing": invitation.existing,
        }

    def disable(self, principal: Principal, user_id: str) -> dict:
        require_admin(principal)
        target = self._target(principal, user_id)
        subject = self._users.subject_for(user_id)
        if subject is None:
            raise NotFound(f"No user '{user_id}'")
        self._users.disable(subject)
        self._users.revoke_sessions(
            subject, datetime.now(UTC)
        )  # tokens already issued stop working
        self._audit.record(principal.user_id, "user.disabled", f"{target.user_id}")
        return {
            "user_id": user_id,
            "disabled": True,
            "sign_in_disabled": self._sign_in_off(user_id),
        }

    def _target(self, principal: Principal, user_id: str) -> UserRecord:
        if user_id == principal.user_id:
            raise InvalidRequest("You cannot disable your own account")
        mine = self._users.list_users(principal.tenant_id)
        target = next((u for u in mine if u.user_id == user_id and u.active), None)
        if target is None:
            raise NotFound(f"No active user '{user_id}'")
        admins = [u for u in mine if u.role is Role.PLATFORM_ADMIN and u.active]
        if target.role is Role.PLATFORM_ADMIN and len(admins) <= 1:
            raise Conflict("The last platform admin cannot be disabled")
        return target

    def _sign_in_off(self, user_id: str) -> bool:
        """Also switch off the sign-in account when there is one. Access is already blocked."""
        if "@" not in user_id:  # an account made by hand, with no email to look up
            return False
        try:
            self._provisioner.disable(user_id)
        except ProvisioningFailed:
            return False
        return True

    def _check_rate(self, principal: Principal) -> None:
        since = datetime.now(UTC) - timedelta(days=1)
        recent = [
            e
            for e in self._audit.events()
            if e.actor == principal.user_id and e.action == "user.invited" and e.at >= since
        ]
        if len(recent) >= MAX_INVITES_PER_DAY:
            raise RateLimited(f"At most {MAX_INVITES_PER_DAY} invitations per day")
