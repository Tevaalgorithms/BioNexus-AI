"""The critic explains each conflict once and may ask a specialist for more evidence."""

import json
from datetime import date
from types import SimpleNamespace

import pytest

from bionexus.agents.conflict import MAX_EXPLANATION_CHARS, conflict_prompt, read_analysis, sides
from bionexus.agents.critic import CriticAgent
from bionexus.agents.optimization import AO_MAX_CONFLICT_RECORDS
from bionexus.container import build_container
from bionexus.contracts.errors import ModelUnavailable
from bionexus.contracts.evidence import EvidenceRecord, Stance
from bionexus.contracts.hints import HintKind
from bionexus.contracts.messages import AgentName, MessageType
from bionexus.contracts.review import ConflictVerdict
from bionexus.llm.clients import DeterministicModelClient, ModelResponse
from bionexus.messaging.envelope import new_message
from bionexus.messaging.router import MAX_MESSAGES_PER_RUN
from bionexus.sources.fixture import FixtureSource
from bionexus.sources.registry import SOURCE_NAMES, SourceRegistry
from bionexus.workflow.budget import Budget
from bionexus.workflow.state import RunState
from tests.conftest import TOKENS, run_to_review


def record(source: str, n: int, stance: Stance, target: str = "NOD2") -> EvidenceRecord:
    return EvidenceRecord(
        source=source,
        source_id=f"R{n}",
        study_family=f"fam-{source}-{n}",
        target=target,
        finding=f"{target} study {n}",
        stance=stance,
        species="human",
        context="European ancestry cohort"
        if stance is Stance.SUPPORTS
        else "Asian ancestry cohort",
        passage=f"Passage {n}. " + "x" * 500,
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


def conflicted(state):
    state.add_evidence(
        [record("gwas", 1, Stance.SUPPORTS), record("open_targets", 2, Stance.OPPOSES)]
    )


class Gateway:
    def __init__(self, reply: str | Exception) -> None:
        self.reply, self.prompts = reply, []

    def complete(self, state, agent, prompt: str) -> str:
        self.prompts.append(prompt)
        if isinstance(self.reply, Exception):
            raise self.reply
        return self.reply


def critic(reply: str | Exception) -> tuple[CriticAgent, Gateway]:
    gateway = Gateway(reply)
    agent = CriticAgent(SimpleNamespace(gateway=gateway))
    agent.instructions = lambda state, skill_id=None: "skill"
    return agent, gateway


def task(state):
    return new_message(
        run_id=state.run_id,
        sender=AgentName.SUPERVISOR,
        recipient=AgentName.CRITIC,
        kind=MessageType.TASK_REQUEST,
        payload={"repair_round": 0},
    )


GOOD = json.dumps(
    {
        "verdict": "explained",
        "explanation": "The opposing study is in a different ancestry.",
        "request": {"agent": "genetics", "kind": "context", "text": "Asian ancestry"},
    }
)


# ---- reading a reply defensively ------------------------------------------------------------


def test_a_good_reply_gives_an_explained_conflict_and_a_valid_request():
    analysis, request = read_analysis("Sure: " + GOOD, "NOD2")
    assert analysis.verdict is ConflictVerdict.EXPLAINED and "ancestry" in analysis.explanation
    assert request is not None and request.agent is AgentName.GENETICS
    assert request.hint.kind is HintKind.CONTEXT


@pytest.mark.parametrize("reply", ["no json", "{broken", "[]", ""])
def test_an_unusable_reply_is_an_unclear_conflict_with_no_text_and_no_request(reply):
    analysis, request = read_analysis(reply, "NOD2")
    assert analysis.verdict is ConflictVerdict.UNCLEAR and analysis.explanation == ""
    assert request is None


def test_an_unknown_verdict_is_unclear():
    analysis, _ = read_analysis(json.dumps({"verdict": "definitely", "explanation": "x"}), "NOD2")
    assert analysis.verdict is ConflictVerdict.UNCLEAR


def test_causal_wording_in_an_explanation_is_dropped():
    reply = json.dumps({"verdict": "real", "explanation": "NOD2 causes Crohn's disease."})
    analysis, _ = read_analysis(reply, "NOD2")
    assert analysis.verdict is ConflictVerdict.REAL and analysis.explanation == ""


def test_an_explanation_is_trimmed_and_a_bad_request_is_ignored():
    reply = json.dumps(
        {
            "verdict": "explained",
            "explanation": "word " * 200,
            "request": {"agent": "critic", "kind": "gene", "text": "CARD15"},
        }
    )
    analysis, request = read_analysis(reply, "NOD2")
    assert len(analysis.explanation) <= MAX_EXPLANATION_CHARS and request is None


def test_the_model_sees_both_sides_but_only_a_few_records_each():
    records = [record("gwas", n, Stance.SUPPORTS) for n in range(10)] + [
        record("monarch", 50, Stance.OPPOSES)
    ]
    supporting, opposing = sides(records, "NOD2")
    assert len(supporting) == AO_MAX_CONFLICT_RECORDS and len(opposing) == 1
    prompt = conflict_prompt("NOD2", supporting, opposing)
    assert prompt.count("[gwas:") == AO_MAX_CONFLICT_RECORDS and "[monarch:R50]" in prompt
    assert "European ancestry" in prompt and "Asian ancestry" in prompt  # the context matters


# ---- the critic ------------------------------------------------------------------------------


def test_the_critic_explains_a_conflict_and_asks_a_specialist_for_more(state):
    conflicted(state)
    agent, gateway = critic(GOOD)
    result = agent.handle(task(state), state)
    assert [a.target for a in result.analyses] == ["NOD2"]
    [request] = [m for m in result.outgoing if m.type is MessageType.EVIDENCE_REQUEST]
    assert request.recipient is AgentName.GENETICS and request.sender is AgentName.CRITIC
    assert len(gateway.prompts) == 1  # one call for one conflict


def test_each_conflict_is_explained_only_once(state):
    conflicted(state)
    agent, gateway = critic(GOOD)
    first = agent.handle(task(state), state)
    state.analyses.update({a.target: a for a in first.analyses})
    again = agent.handle(task(state), state)
    assert again.analyses == [] and len(gateway.prompts) == 1


def test_the_loop_has_no_work_left_once_the_conflict_is_explained(state):
    conflicted(state)
    agent, _ = critic(GOOD)
    assert agent.has_work(state)
    state.analyses["NOD2"] = agent.handle(task(state), state).analyses[0]
    assert not agent.has_work(state)


def test_without_a_model_the_critic_still_reports_the_conflict(state):
    conflicted(state)
    agent, _ = critic(ModelUnavailable("none"))
    result = agent.handle(task(state), state)
    assert result.analyses == [] and result.outgoing == []
    assert any(i.kind.value == "contradiction" for i in result.issues)


def test_an_unusable_reply_is_recorded_so_it_is_not_asked_again(state):
    conflicted(state)
    agent, gateway = critic("I am not sure")
    state.analyses.update({a.target: a for a in agent.handle(task(state), state).analyses})
    assert state.analyses["NOD2"].verdict is ConflictVerdict.UNCLEAR
    agent.handle(task(state), state)
    assert len(gateway.prompts) == 1


def test_no_request_is_sent_when_the_message_cap_is_nearly_reached(state):
    conflicted(state)
    filler = task(state)
    state.messages.extend([filler] * (MAX_MESSAGES_PER_RUN - 3))
    agent, _ = critic(GOOD)
    result = agent.handle(task(state), state)
    assert result.analyses and not [
        m for m in result.outgoing if m.type is MessageType.EVIDENCE_REQUEST
    ]


# ---- the whole run: the explanation is kept and the request finds more -----------------------


class ConflictedGwas(FixtureSource):
    """The offline GWAS sample, plus one opposing study, so NOD2 has a conflict to explain."""

    def search(self, disease, targets, hint=None):
        found = super().search(disease, targets, hint)
        return [*found, record("gwas", 77, Stance.OPPOSES)] if "NOD2" in targets else found


class HintAwareLiterature(FixtureSource):
    def search(self, disease, targets, hint=None):
        found = super().search(disease, targets, hint)
        return [*found, record("europe_pmc", 88, Stance.SUPPORTS)] if hint else found


class ScriptedClient(DeterministicModelClient):
    def generate(self, model_id, prompt, max_output_tokens, temperature=None, api_key_secret=None):
        if "<conflict_data>" in prompt:
            reply = json.dumps(
                {
                    "verdict": "explained",
                    "explanation": "The opposing study is in a different ancestry.",
                    "request": {"agent": "literature", "kind": "context", "text": "Asian ancestry"},
                }
            )
            return ModelResponse(reply, 80, 40)
        return super().generate(model_id, prompt, max_output_tokens, temperature, api_key_secret)


def scenario(**kwargs):
    kept = {"gwas", "europe_pmc"}
    sources = [FixtureSource(n) for n in SOURCE_NAMES if n not in kept]
    registry = SourceRegistry([*sources, ConflictedGwas("gwas"), HintAwareLiterature("europe_pmc")])
    return build_container(
        TOKENS, clients={"fixture": ScriptedClient()}, sources=registry, **kwargs
    )


def test_a_conflict_is_explained_and_the_request_finds_more_evidence(request_):
    state = run_to_review(scenario(), request_)
    assert state.analyses["NOD2"].verdict is ConflictVerdict.EXPLAINED
    assert "ancestry" in state.analyses["NOD2"].explanation
    assert "europe_pmc:R88" in state.evidence  # found by the critic's request
    pairs = [(m.sender, m.recipient, m.type) for m in state.messages]
    assert (AgentName.CRITIC, AgentName.LITERATURE, MessageType.EVIDENCE_REQUEST) in pairs
    assert state.status.value == "waiting_for_review"


def test_switching_the_critic_off_removes_the_explanation_and_the_request(request_):
    state = run_to_review(scenario(disabled_steps=frozenset({"critique"})), request_)
    assert state.analyses == {} and "europe_pmc:R88" not in state.evidence
