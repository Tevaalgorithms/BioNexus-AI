"""Cognito access-token verification (AUTH-09, 10, 14). Roles come from our database, not claims."""

from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any, Protocol

import jwt

from bionexus.contracts.errors import AccessDenied
from bionexus.contracts.identity import ClientKind, Principal
from bionexus.storage.ports import UserDirectory


@dataclass(frozen=True)
class CognitoConfig:
    region: str
    user_pool_id: str
    client_kinds: dict[str, ClientKind]  # app client id -> which login it belongs to
    required_scope: str = "openid"

    @property
    def issuer(self) -> str:
        return f"https://cognito-idp.{self.region}.amazonaws.com/{self.user_pool_id}"

    @property
    def jwks_url(self) -> str:
        return f"{self.issuer}/.well-known/jwks.json"


class KeyProvider(Protocol):
    def signing_key(self, token: str) -> Any: ...


class JwksKeyProvider:
    """Fetches and caches the pool's public keys (no AWS-signed calls needed, AWS-12)."""

    def __init__(self, jwks_url: str) -> None:
        self._client = jwt.PyJWKClient(jwks_url, cache_keys=True, lifespan=3600)

    def signing_key(self, token: str) -> Any:
        return self._client.get_signing_key_from_jwt(token).key


class CognitoTokenVerifier:
    ALGORITHMS = ["RS256"]

    def __init__(self, config: CognitoConfig, keys: KeyProvider, users: UserDirectory) -> None:
        self._config = config
        self._keys = keys
        self._users = users

    def verify(self, token: str) -> Principal:
        claims = self._decode(token)
        self._check_claims(claims)
        principal = self._users.find_by_subject(claims["sub"])
        if principal is None:
            raise AccessDenied("No active BioNexus account for this identity")
        self._check_not_revoked(claims)
        client_kind = self._config.client_kinds[claims["client_id"]]
        return principal.model_copy(update={"client_kind": client_kind})

    def _decode(self, token: str) -> dict:
        try:
            return jwt.decode(
                token,
                self._keys.signing_key(token),
                algorithms=self.ALGORITHMS,
                issuer=self._config.issuer,
                options={"require": ["exp", "iat", "sub", "iss"], "verify_aud": False},
            )
        except jwt.PyJWTError as error:
            raise AccessDenied("Invalid or expired token") from error

    def _check_claims(self, claims: dict) -> None:
        if claims.get("token_use") != "access":
            raise AccessDenied("An access token is required")
        if claims.get("client_id") not in self._config.client_kinds:
            raise AccessDenied("Token was issued to an unknown client")
        if self._config.required_scope not in claims.get("scope", "").split():
            raise AccessDenied("Required scope missing")

    def _check_not_revoked(self, claims: dict) -> None:
        cutoff = self._users.revoked_before(claims["sub"])
        issued_at = datetime.fromtimestamp(claims["iat"], UTC)
        if cutoff is not None and issued_at < cutoff:
            raise AccessDenied("Session was revoked")
