import time
from datetime import UTC, datetime, timedelta

import jwt
import pytest
from cryptography.hazmat.primitives.asymmetric import rsa

from bionexus.auth.cognito import CognitoConfig, CognitoTokenVerifier
from bionexus.auth.policy import require_admin, require_project_member
from bionexus.contracts.errors import AccessDenied
from bionexus.contracts.identity import ClientKind, Principal, Role
from bionexus.storage.in_memory import InMemoryUsers

POOL = "us-east-1_TESTPOOL"
CONFIG = CognitoConfig(
    region="us-east-1",
    user_pool_id=POOL,
    client_kinds={"admin-client": ClientKind.ADMIN, "sci-client": ClientKind.SCIENTIST},
)
KEY = rsa.generate_private_key(public_exponent=65537, key_size=2048)
OTHER_KEY = rsa.generate_private_key(public_exponent=65537, key_size=2048)


class FixedKeys:
    def signing_key(self, token):
        return KEY.public_key()


def mint(sub="sub-sci", client="sci-client", key=KEY, algorithm="RS256", **overrides):
    now = int(time.time())
    claims = {
        "sub": sub,
        "iss": CONFIG.issuer,
        "token_use": "access",
        "client_id": client,
        "scope": "openid",
        "iat": now,
        "exp": now + 600,
    }
    claims.update(overrides)
    return jwt.encode({k: v for k, v in claims.items() if v is not None}, key, algorithm=algorithm)


@pytest.fixture
def users():
    return InMemoryUsers(
        {
            "sub-sci": Principal(
                user_id="u1", role=Role.SCIENTIST, tenant_id="org-a", project_ids=frozenset({"p1"})
            ),
            "sub-admin": Principal(user_id="a1", role=Role.PLATFORM_ADMIN, tenant_id="org-a"),
        }
    )


@pytest.fixture
def verifier(users):
    return CognitoTokenVerifier(CONFIG, FixedKeys(), users)


def test_valid_scientist_token_maps_to_database_principal(verifier):
    principal = verifier.verify(mint())
    assert (principal.user_id, principal.role, principal.client_kind) == (
        "u1",
        Role.SCIENTIST,
        ClientKind.SCIENTIST,
    )


@pytest.mark.parametrize(
    "bad",
    [
        lambda: "not-a-jwt",
        lambda: mint(exp=int(time.time()) - 10),
        lambda: mint(iss="https://cognito-idp.us-east-1.amazonaws.com/other_pool"),
        lambda: mint(client="stranger-client"),
        lambda: mint(token_use="id"),
        lambda: mint(scope="profile"),
        lambda: mint(key=OTHER_KEY),
        lambda: mint(sub="sub-unknown"),
        lambda: jwt.encode({"sub": "sub-sci", "iss": CONFIG.issuer}, "secret", algorithm="HS256"),
    ],
)
def test_invalid_tokens_are_denied(verifier, bad):
    with pytest.raises(AccessDenied):
        verifier.verify(bad())


def test_disabled_user_is_denied(verifier, users):
    users.disable("sub-sci")
    with pytest.raises(AccessDenied):
        verifier.verify(mint())


def test_tokens_issued_before_revocation_are_denied(verifier, users):
    token = mint(iat=int(time.time()) - 100)
    users.revoke_sessions("sub-sci", datetime.now(UTC) - timedelta(seconds=10))
    with pytest.raises(AccessDenied):
        verifier.verify(token)


def test_scientist_through_admin_client_still_cannot_administer(verifier):
    principal = verifier.verify(mint(client="admin-client"))
    with pytest.raises(AccessDenied):
        require_admin(principal)


def test_admin_role_through_scientist_client_cannot_administer(verifier):
    principal = verifier.verify(mint(sub="sub-admin", client="sci-client"))
    with pytest.raises(AccessDenied):
        require_admin(principal)


def test_admin_through_admin_client_can_administer_but_not_read_projects(verifier):
    principal = verifier.verify(mint(sub="sub-admin", client="admin-client"))
    require_admin(principal)
    with pytest.raises(AccessDenied):
        require_project_member(principal, "org-a", "p1")


def test_cross_tenant_membership_is_denied(verifier):
    principal = verifier.verify(mint())
    with pytest.raises(AccessDenied):
        require_project_member(principal, "org-b", "p1")
