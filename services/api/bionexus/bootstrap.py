"""Builds the production container from environment variables. Fails loudly if misconfigured."""

from bionexus.auth.cognito import CognitoConfig, CognitoTokenVerifier, JwksKeyProvider
from bionexus.container import Container, build_container
from bionexus.contracts.errors import InvalidRequest
from bionexus.contracts.identity import ClientKind
from bionexus.params import parameters
from bionexus.storage.migrate import migrate
from bionexus.storage.postgres import Database, postgres_storage

REQUIRED = (
    "BIONEXUS_DATABASE_URL",
    "COGNITO_REGION",
    "COGNITO_USER_POOL_ID",
    "COGNITO_ADMIN_CLIENT_ID",
    "COGNITO_SCIENTIST_CLIENT_ID",
)


def missing_settings() -> list[str]:
    return [name for name in REQUIRED if not parameters().has(name)]


def cognito_config() -> CognitoConfig:
    return CognitoConfig(
        region=parameters().require("COGNITO_REGION"),
        user_pool_id=parameters().require("COGNITO_USER_POOL_ID"),
        client_kinds={
            parameters().require("COGNITO_ADMIN_CLIENT_ID"): ClientKind.ADMIN,
            parameters().require("COGNITO_SCIENTIST_CLIENT_ID"): ClientKind.SCIENTIST,
        },
    )


def production_container() -> Container:
    missing = missing_settings()
    if missing:
        raise InvalidRequest(f"Missing required settings: {', '.join(missing)}")
    db = Database(parameters().require("BIONEXUS_DATABASE_URL"))
    migrate(db)
    storage = postgres_storage(db)
    config = cognito_config()
    verifier = CognitoTokenVerifier(config, JwksKeyProvider(config.jwks_url), storage.users)
    return build_container(storage=storage, verifier=verifier)
