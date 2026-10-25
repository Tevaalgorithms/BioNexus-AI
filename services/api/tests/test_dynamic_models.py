import pytest
from fastapi.testclient import TestClient

from bionexus.api.app import create_app
from bionexus.container import build_container
from bionexus.contracts.errors import InvalidRequest
from bionexus.contracts.investigation import InvestigationStatus
from bionexus.llm.clients import DeterministicModelClient
from bionexus.llm.factory import LazyClients
from bionexus.llm.models import AgentBinding
from bionexus.llm.registry import ModelSpec, ModelStatus, model_problems
from tests.conftest import ADMIN, SCIENTIST, TOKENS, run_to_review


def auth(token):
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def client(container):
    return TestClient(create_app(container))


FIXTURE_MODEL = {
    "model_id": "fixture-extra",
    "provider": "fixture",
    "supports_structured_output": True,
    "input_usd_per_million": 1,
    "output_usd_per_million": 2,
}


def test_model_registered_at_runtime_can_be_bound_and_used_without_restart(
    client, container, request_
):
    assert (
        client.post("/admin/models", json=FIXTURE_MODEL, headers=auth("admin")).status_code == 201
    )
    names = [m["model_id"] for m in client.get("/admin/models", headers=auth("admin")).json()]
    assert "fixture-extra" in names
    body = {"binding": {"model_id": "fixture-extra"}, "reason": "try it", "expected_revision": 1}
    assert (
        client.put(
            "/admin/agents/synthesizer/binding", json=body, headers=auth("admin")
        ).status_code
        == 200
    )
    state = run_to_review(container, request_)
    assert {i.model_id for i in state.invocations if i.agent == "synthesizer"} == {"fixture-extra"}


def test_scientist_cannot_register_models(client):
    assert client.post("/admin/models", json=FIXTURE_MODEL, headers=auth("sci")).status_code == 403


def test_duplicate_and_malformed_models_are_rejected(client):
    client.post("/admin/models", json=FIXTURE_MODEL, headers=auth("admin"))
    assert (
        client.post("/admin/models", json=FIXTURE_MODEL, headers=auth("admin")).status_code == 422
    )
    bad = {**FIXTURE_MODEL, "model_id": "bad id; drop"}
    assert client.post("/admin/models", json=bad, headers=auth("admin")).status_code == 422


def paid(**overrides):
    base = dict(
        model_id="m1",
        provider="anthropic",
        supports_structured_output=True,
        input_usd_per_million=1,
        output_usd_per_million=2,
        api_key_secret="ANTHROPIC_API_KEY",
        price_verified_on="2026-01-01",
    )
    return ModelSpec(**{**base, **overrides})


def test_paid_models_need_a_key_parameter_a_verified_price_and_a_known_provider(
    isolated_parameters,
):
    isolated_parameters.values["ANTHROPIC_API_KEY"] = "set"
    assert model_problems(paid(), production=True) == []
    assert any("not set" in p for p in model_problems(paid(api_key_secret="MISSING_KEY"), True))
    assert any(
        "API key parameter name" in p for p in model_problems(paid(api_key_secret=None), True)
    )
    assert any("prices" in p for p in model_problems(paid(input_usd_per_million=0), True))
    assert any("price_verified_on" in p for p in model_problems(paid(price_verified_on=None), True))
    assert any(
        "price_verified_on" in p for p in model_problems(paid(price_verified_on="2999-01-01"), True)
    )
    assert any("provider" in p for p in model_problems(paid(provider="evil-corp"), True))
    assert any(
        "provider" in p for p in model_problems(paid(provider="fixture"), True)
    )  # no fixtures in prod


def test_model_that_fails_its_smoke_test_is_not_registered(container):
    down = {"fixture": DeterministicModelClient(failing_models=frozenset({"fixture-extra"}))}
    app = build_container(TOKENS, clients=down)
    with pytest.raises(InvalidRequest):
        app.admin.register_model(ADMIN, ModelSpec(**FIXTURE_MODEL))
    assert "fixture-extra" not in [m.model_id for m in app.admin._registry.all()]


def test_deprecated_model_cannot_be_chosen_but_still_serves_pinned_runs(container, request_):
    app = container
    app.admin.register_model(ADMIN, ModelSpec(**FIXTURE_MODEL))
    app.admin.rebind_agent(
        ADMIN,
        "synthesizer",
        AgentBinding(model_id="fixture-extra"),
        "use",
        1,
    )
    pinned = app.investigations.submit(SCIENTIST, "proj-1", request_, "pinned")
    app.admin.set_model_status(ADMIN, "fixture-extra", ModelStatus.DEPRECATED, "retiring")
    check = app.admin.validate_binding(ADMIN, "critic", AgentBinding(model_id="fixture-extra"))
    assert not check.valid
    app.worker.run_pending()
    assert app.storage.runs.load(pinned.run_id).status is InvestigationStatus.WAITING_FOR_REVIEW


def test_disabled_model_falls_back_to_the_approved_fallback_and_records_why(container, request_):
    container.admin.rebind_agent(
        ADMIN,
        "synthesizer",
        AgentBinding(model_id="fixture-small", fallback_model_id="fixture-large"),
        "x",
        1,
    )
    container.admin.set_model_status(ADMIN, "fixture-small", ModelStatus.DISABLED, "bad outputs")
    state = run_to_review(container, request_)
    synthesizer = [i for i in state.invocations if i.agent == "synthesizer"]
    assert synthesizer and all(
        i.model_id == "fixture-large" and "disabled" in (i.fallback_reason or "")
        for i in synthesizer
    )


def test_status_change_needs_a_reason_and_is_audited(container):
    with pytest.raises(InvalidRequest):
        container.admin.set_model_status(ADMIN, "fixture-large", ModelStatus.DEPRECATED, "  ")
    container.admin.set_model_status(ADMIN, "fixture-large", ModelStatus.DEPRECATED, "retire")
    assert any(e.action == "model.deprecated" for e in container.storage.audit.events())


def test_lazy_clients_build_a_provider_only_when_first_used():
    clients = LazyClients()
    assert len(clients) == 0
    assert clients["fixture"] is clients["fixture"] and len(clients) == 1
    with pytest.raises(InvalidRequest):
        clients["unknown-provider"]
