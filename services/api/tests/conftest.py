import os
from datetime import date
from functools import cache

import psycopg
import pytest

from bionexus.container import Container, build_container
from bionexus.contracts.identity import ClientKind, Principal, Role
from bionexus.contracts.investigation import InvestigationRequest
from bionexus.params import DotEnvSource, Parameters, set_parameters
from bionexus.storage.in_memory import in_memory_storage
from bionexus.storage.migrate import migrate
from bionexus.storage.postgres import Database, postgres_storage

ADMIN = Principal(
    user_id="admin-1",
    role=Role.PLATFORM_ADMIN,
    tenant_id="org-a",
    client_kind=ClientKind.ADMIN,
)
SCIENTIST = Principal(
    user_id="sci-1", role=Role.SCIENTIST, tenant_id="org-a", project_ids=frozenset({"proj-1"})
)
OUTSIDER = Principal(
    user_id="sci-2", role=Role.SCIENTIST, tenant_id="org-b", project_ids=frozenset({"proj-1"})
)
TOKENS = {"admin": ADMIN, "sci": SCIENTIST, "outsider": OUTSIDER}


TEST_DSN = os.getenv("BIONEXUS_TEST_DSN") or DotEnvSource().load().get("BIONEXUS_TEST_DSN", "")


@cache
def postgres_unreachable() -> str:
    """Why there is no database ('' when there is one). Asked once: 2 s, not 30 s a test."""
    if not TEST_DSN:
        return "BIONEXUS_TEST_DSN is not set"
    try:
        psycopg.connect(TEST_DSN, connect_timeout=2).close()
    except psycopg.Error as error:
        return f"PostgreSQL unavailable: {error}"
    return ""


def fresh_postgres_storage():
    """A clean, migrated database per test; skips when no PostgreSQL is reachable."""
    if reason := postgres_unreachable():
        pytest.skip(reason)
    try:
        db = Database(TEST_DSN)
        db.execute("DROP SCHEMA public CASCADE; CREATE SCHEMA public")
    except Exception as error:
        pytest.skip(f"PostgreSQL unavailable: {error}")
    migrate(db)
    return postgres_storage(db), db


class DictSource:
    """A parameter source tests can edit to simulate SSM changes."""

    def __init__(self, values: dict[str, str] | None = None) -> None:
        self.values = dict(values or {})
        self.fail = False

    def load(self) -> dict[str, str]:
        if self.fail:
            raise RuntimeError("source down")
        return dict(self.values)


@pytest.fixture(autouse=True)
def isolated_parameters():
    """Every test gets its own non-production parameter set; nothing leaks from a real .env."""
    source = DictSource()
    set_parameters(Parameters(source, ttl=0))
    yield source
    set_parameters(None)


@pytest.fixture(params=["memory", "postgres"])
def storage(request):
    if request.param == "memory":
        yield in_memory_storage(TOKENS)
        return
    storage, db = fresh_postgres_storage()
    yield storage
    db.close()


@pytest.fixture
def container(storage) -> Container:
    return build_container(TOKENS, storage=storage)


@pytest.fixture
def request_() -> InvestigationRequest:
    return InvestigationRequest(
        disease="Crohn's disease",
        targets=("NOD2", "IL23R"),
        question="Compare NOD2 sensing and IL-23 signalling evidence.",
        evidence_cutoff=date(2026, 1, 1),
    )


def run_to_review(container: Container, request: InvestigationRequest, key: str = "k1"):
    run = container.investigations.submit(SCIENTIST, "proj-1", request, key)
    container.worker.run_pending()
    return container.investigations.get(SCIENTIST, run.run_id)
