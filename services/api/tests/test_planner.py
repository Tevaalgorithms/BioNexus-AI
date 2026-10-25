"""The planner reviews coverage and may ask specialists to search again, within strict limits."""

import json
from datetime import UTC, date, datetime
from types import SimpleNamespace

import pytest

from bionexus.agents.optimization import AO_MAX_PLANNER_REQUESTS
from bionexus.agents.planner import PlannerAgent, coverage_summary
from bionexus.container import SKILL_VERSIONS, build_container
from bionexus.contracts.errors import ModelUnavailable
from bionexus.contracts.evidence import EvidenceRecord, Stance
from bionexus.contracts.messages import AgentName, MessageType
from bionexus.llm.clients import DeterministicModelClient, ModelResponse
from bionexus.llm.models import AgentBinding, ConfigRelease
from bionexus.messaging.envelope import new_message
from bionexus.sources.fixture import FixtureSource
from bionexus.sources.registry import SOURCE_NAMES, SourceRegistry
from bionexus.workflow.budget import Budget
from bionexus.workflow.state import RunState
from tests.conftest import SCIENTIST, TOKENS, run_to_review


def paper(n: int, source: str = "europe_pmc", stance: Stance = Stance.SUPPORTS) -> EvidenceRecord:
    return EvidenceRecord(
        source=source,
        source_id=f"X{n}",
        study_family=f"fam-{source}-{n}",
        target="NOD2",
        finding="NOD2 and Crohn's disease",
        stance=stance,
        species="human",
        context="context",
        passage="passage",
        available_on=date(2020, 1, 1),
        license_ok=True,
    )


@pytest.fixture
def state(request_):
    return RunState(
        run_id="r",
        tenant_id="t",
        project_id="p",
        created_by="u",
        request=request_,
        release_id="rel-1",
        budget=Budget(max_cost_usd=1, max_calls=50),
    )


def planner(reply: str | Exception) -> PlannerAgent:
    class Gateway:
        def complete(self, state, agent, prompt: str) -> str:
            if isinstance(reply, Exception):
                raise reply
            return reply

    agent = PlannerAgent(SimpleNamespace(gateway=Gateway()))
    agent.instructions = lambda state: "skill"
    return agent


def task(state):
    return new_message(
        run_id=state.run_id,
        sender=AgentName.SUPERVISOR,
        recipient=AgentName.PLANNER,
        kind=MessageType.TASK_REQUEST,
        payload={},
    )


def reply_with(*requests: dict) -> str:
    return "Here you go: " + json.dumps({"requests": list(requests)}) + " done"


LIT = {"agent": "literature", "kind": "disease", "text": "Crohn's"}


def test_a_valid_reply_becomes_recorded_requests_with_lineage(state):
    parent = task(state)
    result = planner(
        reply_with(LIT, {"agent": "genetics", "kind": "gene", "text": "CARD15"})
    ).handle(parent, state)
    assert [m.recipient for m in result.outgoing] == [AgentName.LITERATURE, AgentName.GENETICS]
    assert all(m.type is MessageType.EVIDENCE_REQUEST for m in result.outgoing)
    assert all(m.parent_id == parent.message_id for m in result.outgoing)
    assert result.outgoing[0].payload == {"kind": "disease", "text": "Crohn's"}


@pytest.mark.parametrize(
    "bad",
    [
        {"agent": "critic", "kind": "gene", "text": "CARD15"},  # not an agent it may ask
        {"agent": "pathways", "kind": "gene", "text": "CARD15"},  # its sources cannot use a hint
        {"agent": "literature", "kind": "gene", "text": 'x" OR "y'},  # not a plain phrase
        {"agent": "literature", "kind": "sql", "text": "CARD15"},  # not a hint kind
        {"agent": "literature"},
        "literature",
    ],
)
def test_unacceptable_requests_are_dropped(state, bad):
    assert planner(reply_with(bad)).handle(task(state), state).outgoing == []


def test_repeats_are_removed_and_the_number_is_capped(state):
    many = [{"agent": "literature", "kind": "context", "text": f"phrase {n}"} for n in range(9)]
    result = planner(reply_with(LIT, LIT, *many)).handle(task(state), state)
    assert len(result.outgoing) == AO_MAX_PLANNER_REQUESTS
    texts = [m.payload["text"] for m in result.outgoing]
    assert len(set(texts)) == len(texts)


@pytest.mark.parametrize("reply", ["no json here", "{not json}", "[1, 2]", '{"requests": "x"}'])
def test_a_reply_that_is_not_usable_asks_for_nothing(state, reply):
    result = planner(reply).handle(task(state), state)
    assert result.outgoing == [] and result.abstained


def test_without_a_model_the_planner_quietly_does_nothing(state):
    result = planner(ModelUnavailable("no model")).handle(task(state), state)
    assert result.outgoing == [] and result.abstained


def test_the_coverage_table_is_counts_only(state):
    state.add_evidence([paper(1), paper(2, "gwas"), paper(3, "gwas", Stance.OPPOSES)])
    text = coverage_summary(state)
    assert "NOD2: europe_pmc 1, gwas 2" in text
    assert "independent studies: 2 supporting, 1 opposing" in text
    assert "IL23R: nothing found" in text  # a requested gene with no records
    assert "passage" not in text  # the planner never sees the evidence text


# ---- the whole run: a hint finds evidence the first pass missed ----------------------------


class HintAwareLiterature(FixtureSource):
    """The offline Europe PMC sample, plus one extra paper that only an alias search finds."""

    def search(self, disease, targets, hint=None):
        found = super().search(disease, targets, hint)
        return [*found, paper(99)] if hint else found


class ScriptedClient(DeterministicModelClient):
    """Answers the planner with a fixed request; everything else behaves as the offline model."""

    def generate(self, model_id, prompt, max_output_tokens, temperature=None, api_key_secret=None):
        if "<coverage_data>" in prompt:
            return ModelResponse(reply_with(LIT), 50, 20)
        return super().generate(model_id, prompt, max_output_tokens, temperature, api_key_secret)


def scenario_sources() -> SourceRegistry:
    sources = [FixtureSource(n) for n in SOURCE_NAMES if n != "europe_pmc"]
    return SourceRegistry([*sources, HintAwareLiterature("europe_pmc")])


def test_a_planner_request_finds_extra_evidence_and_is_recorded(request_):
    app = build_container(TOKENS, clients={"fixture": ScriptedClient()}, sources=scenario_sources())
    state = run_to_review(app, request_)
    assert "europe_pmc:X99" in state.evidence  # found only by the hinted search
    pairs = [(m.sender, m.recipient, m.type) for m in state.messages]
    assert (AgentName.SUPERVISOR, AgentName.PLANNER, MessageType.TASK_REQUEST) in pairs
    assert (AgentName.PLANNER, AgentName.LITERATURE, MessageType.EVIDENCE_REQUEST) in pairs
    assert (AgentName.LITERATURE, AgentName.PLANNER, MessageType.TASK_RESULT) in pairs


def test_switching_the_coverage_step_off_loses_that_evidence(request_):
    app = build_container(
        TOKENS,
        clients={"fixture": ScriptedClient()},
        sources=scenario_sources(),
        disabled_steps=frozenset({"coverage"}),
    )
    state = run_to_review(app, request_)
    assert "europe_pmc:X99" not in state.evidence
    assert not any(m.sender is AgentName.PLANNER for m in state.messages)


def test_the_offline_model_is_harmless(container, request_):
    """With only placeholder models the planner's reply is unusable, so nothing changes."""
    state = run_to_review(container, request_)
    assert not any(m.type is MessageType.EVIDENCE_REQUEST for m in state.messages)
    assert state.status.value == "waiting_for_review"


# ---- an older saved release gains the new agents -------------------------------------------


def old_release() -> ConfigRelease:
    binding = AgentBinding(model_id="fixture-small")
    old_agents = [a for a in AgentName if a not in (AgentName.PLANNER, AgentName.VERIFIER)]
    return ConfigRelease(
        release_id="rel-1",
        revision=1,
        bindings={a: binding for a in old_agents},
        skill_versions={k: v for k, v in SKILL_VERSIONS.items() if k != "coverage.plan"},
        created_by="system",
        reason="initial release",
        parent_id=None,
        created_at=datetime.now(UTC),
    )


def test_a_release_saved_before_the_upgrade_gains_the_new_agents_and_keeps_its_history():
    app = build_container(TOKENS, initial=old_release())
    active = app.releases.active()
    assert AgentName.PLANNER in active.bindings and "coverage.plan" in active.skill_versions
    assert active.revision == 2 and active.parent_id == "rel-1"
    assert [r.revision for r in app.releases.history()] == [1, 2]  # nothing was rewritten
    assert app.releases.history()[0].reason == "initial release"


def test_the_upgrade_is_a_no_op_when_nothing_is_missing(container):
    assert container.releases.ensure_complete(AgentName.SYNTHESIZER, SKILL_VERSIONS) is None
    assert container.releases.active().revision == 1


def test_a_new_run_works_on_the_upgraded_release(request_):
    app = build_container(TOKENS, initial=old_release())
    state = run_to_review(app, request_)
    assert state.release_id == "rel-2" and state.status.value == "waiting_for_review"
    assert SCIENTIST.tenant_id == state.tenant_id
