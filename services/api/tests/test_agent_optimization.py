"""Agent optimizations (AO-n, see bionexus/agents/optimization.py): calls, parallelism, cache."""

import threading
from datetime import date
from types import SimpleNamespace

import pytest

from bionexus.agents.literature import LiteratureAgent
from bionexus.agents.optimization import AO_MAX_DIRECTION_CALLS
from bionexus.container import build_container
from bionexus.contracts.evidence import EvidenceRecord, Stance
from bionexus.contracts.messages import AgentName
from bionexus.llm.cache import CachedAnswer, ResponseCache
from bionexus.llm.clients import ModelResponse
from bionexus.llm.models import AgentBinding
from bionexus.workflow.budget import Budget
from bionexus.workflow.state import RunState
from tests.conftest import run_to_review


def paper(n: int, stance: Stance = Stance.UNKNOWN) -> EvidenceRecord:
    return EvidenceRecord(
        source="europe_pmc",
        source_id=f"P{n}",
        study_family=f"fam-{n}",
        target="NOD2",
        finding="NOD2 and Crohn's disease",
        stance=stance,
        species="human",
        context="context",
        passage="NOD2 variants are associated with Crohn's disease.",
        available_on=date(2020, 1, 1),
        license_ok=True,
    )


@pytest.fixture
def state(request_):
    return RunState(
        run_id="r",
        tenant_id="org-a",
        project_id="p",
        created_by="u",
        request=request_,
        release_id="rel-1",
        budget=Budget(max_cost_usd=1, max_calls=50),
    )


def literature(gateway, records=()) -> LiteratureAgent:
    sources = SimpleNamespace(
        get=lambda name: SimpleNamespace(search=lambda d, t, hint=None: list(records))
    )
    agent = LiteratureAgent(SimpleNamespace(gateway=gateway, sources=sources))
    agent.instructions = lambda state: "skill"
    return agent


class CountingGateway:
    def __init__(self, answer: str = "supports") -> None:
        self.answer, self.prompts, self._lock = answer, [], threading.Lock()

    def complete(self, state, agent, prompt: str) -> str:
        with self._lock:
            self.prompts.append(prompt)
        return self.answer


# AO-1: an agent whose output is retrieved evidence makes no model call --------------------------


def test_retrieval_agents_and_the_supervisor_make_no_model_call(container, request_):
    state = run_to_review(container, request_)
    callers = {i.agent for i in state.invocations}
    plain_code = {AgentName.SUPERVISOR, AgentName.GENETICS, AgentName.PATHWAYS, AgentName.CLINICAL}
    assert callers and callers.isdisjoint(plain_code)


# AO-3: the direction calls are capped ---------------------------------------------------------


def test_direction_calls_are_capped(state):
    gateway = CountingGateway()
    records = [paper(n) for n in range(AO_MAX_DIRECTION_CALLS + 2)]
    result = literature(gateway, records).assess(
        SimpleNamespace(payload={}),
        state,  # no targets in the message: the request's are used
    )
    assert len(gateway.prompts) == AO_MAX_DIRECTION_CALLS
    unread = [r for r in result.evidence if r.stance is Stance.UNKNOWN]
    assert len(unread) == 2  # the papers beyond the cap keep "no stated direction"


# AO-7: the direction calls run together -------------------------------------------------------


def test_direction_calls_run_at_the_same_time_and_keep_their_order(state):
    meet = threading.Barrier(2, timeout=5)  # both calls must be in flight together to pass

    class Gateway:
        def complete(self, state, agent, prompt: str) -> str:
            meet.wait()
            return "supports"

    records = [paper(1), paper(2)]
    out = literature(Gateway())._with_stances(records, state)
    assert [r.evidence_id for r in out] == [r.evidence_id for r in records]
    assert all(r.stance is Stance.SUPPORTS for r in out)


# AO-5: an identical prompt is paid for once ---------------------------------------------------


class CountingClient:
    def __init__(self) -> None:
        self.calls = 0

    def generate(self, model_id, prompt, max_output_tokens, temperature=None, api_key_secret=None):
        self.calls += 1
        return ModelResponse("answer", 10, 5)


@pytest.fixture
def gateway_and_client():
    client = CountingClient()
    app = build_container({}, clients={"fixture": client})
    return app, client


def run_state(app, request, tenant="org-a") -> RunState:
    return RunState(
        run_id=f"r-{tenant}",
        tenant_id=tenant,
        project_id="p",
        created_by="u",
        request=request,
        release_id=app.releases.active().release_id,
        budget=Budget(max_cost_usd=1, max_calls=50),
    )


def test_an_identical_prompt_is_answered_from_the_cache(gateway_and_client, request_):
    app, client = gateway_and_client
    state = run_state(app, request_)
    first = app.gateway.complete(state, AgentName.LITERATURE, "same prompt")
    again = app.gateway.complete(state, AgentName.LITERATURE, "same prompt")
    assert first == again == "answer" and client.calls == 1
    hit = state.invocations[-1]
    assert hit.cached and hit.cost_usd == 0 and hit.input_tokens == 0
    assert state.budget.calls == 1  # a hit does not use the call allowance
    assert state.budget.spent_usd == pytest.approx(sum(i.cost_usd for i in state.invocations))


def test_a_different_prompt_or_organisation_is_never_served_from_the_cache(
    gateway_and_client, request_
):
    app, client = gateway_and_client
    app.gateway.complete(run_state(app, request_), AgentName.LITERATURE, "same prompt")
    app.gateway.complete(run_state(app, request_), AgentName.LITERATURE, "another prompt")
    app.gateway.complete(run_state(app, request_, "org-b"), AgentName.LITERATURE, "same prompt")
    assert client.calls == 3


def test_the_cache_is_bounded_and_forgets_the_least_recently_used():
    cache, binding = ResponseCache(2), AgentBinding(model_id="m")
    keys = [cache.key("t", binding, p) for p in ("a", "b", "c")]
    cache.put(keys[0], CachedAnswer("A", "m"))
    cache.put(keys[1], CachedAnswer("B", "m"))
    cache.get(keys[0])  # "a" is now the most recently used
    cache.put(keys[2], CachedAnswer("C", "m"))  # evicts "b"
    assert cache.get(keys[0]) and cache.get(keys[2]) and cache.get(keys[1]) is None


def test_a_cache_of_zero_remembers_nothing():
    cache, binding = ResponseCache(0), AgentBinding(model_id="m")
    key = cache.key("t", binding, "p")
    cache.put(key, CachedAnswer("A", "m"))
    assert cache.get(key) is None


def test_the_key_changes_with_the_model_setup():
    a = ResponseCache.key("t", AgentBinding(model_id="m1"), "p")
    b = ResponseCache.key("t", AgentBinding(model_id="m2"), "p")
    c = ResponseCache.key("t", AgentBinding(model_id="m1", max_output_tokens=50), "p")
    assert len({a, b, c}) == 3
