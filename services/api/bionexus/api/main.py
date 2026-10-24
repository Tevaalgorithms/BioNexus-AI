"""API entrypoint: `uvicorn bionexus.api.main:app`.

APP_ENV=production wires PostgreSQL, Cognito and SSM; anything else is a local dev setup
(.env file, in-memory storage, dev tokens) and must never face the internet.
"""

from bionexus.api.app import create_app
from bionexus.bootstrap import production_container
from bionexus.container import build_container
from bionexus.contracts.identity import ClientKind, Principal, Role
from bionexus.observability import configure_logging
from bionexus.params import parameters


def dev_principals() -> dict[str, Principal]:
    """Local-only sign-in identities. The tokens are random values from your own `.env`."""
    p = parameters()
    people = {
        p.require("DEV_ADMIN_TOKEN"): Principal(
            user_id="dev-admin",
            role=Role.PLATFORM_ADMIN,
            tenant_id="dev-org",
            client_kind=ClientKind.ADMIN,
        ),
        p.require("DEV_SCIENTIST_TOKEN"): Principal(
            user_id="dev-scientist",
            role=Role.SCIENTIST,
            tenant_id="dev-org",
            project_ids=frozenset({"general-research", "crohns"}),
            client_kind=ClientKind.SCIENTIST,
        ),
    }
    colleague = p.get("DEV_COLLEAGUE_TOKEN")
    if colleague:  # optional second scientist, to try inviting someone to a project
        people[colleague] = Principal(
            user_id="dev-colleague",
            role=Role.SCIENTIST,
            tenant_id="dev-org",
            client_kind=ClientKind.SCIENTIST,
        )
    return people


def build_app():
    configure_logging()
    if parameters().is_production():
        return create_app(production_container())
    return create_app(build_container(dev_principals()))


app = build_app()
