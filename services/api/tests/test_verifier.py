"""The verifier withholds what the evidence does not support, and says what it could not check."""

import json
from datetime import date
from types import SimpleNamespace

import pytest

from bionexus.agents.optimization import AO_MAX_VERIFIED_SENTENCES
from bionexus.agents.synthesizer import make_claim
from bionexus.agents.verifier import (
    VerifierAgent,
    apply_verifications,
    check_claims,
    split_sentences,
)
from bionexus.container import build_container
from bionexus.contracts.errors import ModelUnavailable
from bionexus.contracts.evidence import EvidenceRecord, Stance
from bionexus.contracts.messages import AgentName, MessageType
from bionexus.contracts.review import VerificationKind, VerificationVerdict
from bionexus.evidence.matrix import build_matrix
from bionexus.llm.clients import DeterministicModelClient, ModelResponse
from bionexus.workflow.budget import Budget
from bionexus.workflow.state import RunState
from tests.conftest import SCIENTIST, TOKENS, run_to_review

HALLUCINATION = "Further trials are expected to confirm this."


def record(n: int, stance: Stance = Stance.SUPPORTS, licensed: bool = True) -> EvidenceRecord:
    return EvidenceRecord(
        source="gwas",
        source_id=f"V{n}",
        study_family=f"fam-{n}",
        target="NOD2",
        finding="NOD2 and Crohn's disease",
        stance=stance,
        species="human",
        context="context",
        passage="passage",
        available_on=date(2020, 1, 1),
        license_ok=licensed,
    )


@pytest.fixture
def state(request_):
    s = RunState(
        run_id="r",
        tenant_id="t",
        project_id="p",
        created_by="u",
        request=request_,
        release_id="rel-1",
        budget=Budget(max_cost_usd=1, max_calls=50),
    )
    s.add_evidence([record(1), record(2, Stance.OPPOSES)])
    row = build_matrix(list(s.evidence.values()))[0]
    s.claims = [make_claim(row, s.request.disease)]
    return s


class Gateway:
    def __init__(self, reply) -> None:
        self.reply, self.prompts = reply, []

    def complete(self, state, agent, prompt: str) -> str:
        self.prompts.append(prompt)
        if isinstance(self.reply, Exception):
            raise self.reply
        return self.reply(prompt) if callable(self.reply) else self.reply


def verifier(reply) -> tuple[VerifierAgent, Gateway]:
    gateway = Gateway(reply)
    agent = VerifierAgent(SimpleNamespace(gateway=gateway))
    agent.instructions = lambda state, skill_id=None: "skill"
    return agent, gateway


def verdicts(found):
    return {v.subject: v.verdict for v in found}


# ---- claims are rebuilt by plain code ---------------------------------------------------------


def test_a_claim_that_matches_its_citations_is_supported(state):
    [v] = check_claims(state)
    assert v.kind is VerificationKind.CLAIM and v.verdict is VerificationVerdict.SUPPORTED


def test_a_claim_with_changed_counts_is_withheld(state):
    state.claims = [state.claims[0].model_copy(update={"text": "NOD2: 9 supporting, 0 opposing."})]
    [v] = check_claims(state)
    assert v.verdict is VerificationVerdict.UNSUPPORTED and "does not match" in v.reason


def test_a_claim_citing_unknown_evidence_is_withheld(state):
    ids = (*state.claims[0].evidence_ids, "gwas:GHOST")
    state.claims = [state.claims[0].model_copy(update={"evidence_ids": ids})]
    [v] = check_claims(state)
    assert v.verdict is VerificationVerdict.UNSUPPORTED and "does not have" in v.reason


def test_a_claim_citing_evidence_that_is_not_accepted_is_withheld(state):
    state.add_evidence([record(3, licensed=False)])  # a licence that does not allow reuse
    ids = (*state.claims[0].evidence_ids, "gwas:V3")
    state.claims = [state.claims[0].model_copy(update={"evidence_ids": ids})]
    [v] = check_claims(state)
    assert v.verdict is VerificationVerdict.UNSUPPORTED and "not accepted" in v.reason


# ---- summary sentences are compared with the claims by a model --------------------------------


def verdict_for(sentence_text):
    """A scripted model: the hallucinated sentence is unsupported, everything else is supported."""

    def reply(prompt: str) -> str:
        bad = "unsupported" if "expected to confirm" in prompt else "supported"
        return json.dumps({"verdict": bad, "reason": "it adds a prediction"})

    return reply


def test_a_sentence_that_is_a_claim_word_for_word_needs_no_model(state):
    state.narrative = state.claims[0].text
    agent, gateway = verifier(verdict_for(None))
    found = agent._check_summary(state)
    assert [v.verdict for v in found] == [VerificationVerdict.SUPPORTED] and gateway.prompts == []


def test_an_added_sentence_is_unsupported_and_the_rest_is_kept(state):
    state.narrative = f"{state.claims[0].text} Both studies used cohorts. {HALLUCINATION}"
    agent, _ = verifier(verdict_for(None))
    found = agent._check_summary(state)
    assert [v.verdict.value for v in found] == ["supported", "supported", "unsupported"]
    assert found[2].text == HALLUCINATION and "prediction" in found[2].reason


@pytest.mark.parametrize("reply", ["no json", "{broken", '{"verdict": "maybe"}', "[]"])
def test_an_unclear_answer_keeps_the_sentence_and_says_it_was_not_checked(state, reply):
    state.narrative = "A sentence the claims do not mention."
    agent, _ = verifier(reply)
    [v] = agent._check_summary(state)
    assert v.verdict is VerificationVerdict.UNCHECKED


def test_without_a_model_nothing_is_withheld_and_nothing_is_pretended(state):
    state.narrative = "A sentence the claims do not mention."
    agent, _ = verifier(ModelUnavailable("none"))
    [v] = agent._check_summary(state)
    assert v.verdict is VerificationVerdict.UNCHECKED and "no model" in v.reason


def test_the_number_of_checked_sentences_is_capped(state):
    state.narrative = " ".join(f"Extra sentence {n}." for n in range(AO_MAX_VERIFIED_SENTENCES + 5))
    agent, gateway = verifier(verdict_for(None))
    found = agent._check_summary(state)
    assert len(found) == len(gateway.prompts) == AO_MAX_VERIFIED_SENTENCES


# ---- applying the verdicts --------------------------------------------------------------------


def apply(state, narrative: str, *, bad_claims=(), bad_sentences=()):
    state.narrative = narrative
    verdicts_ = [
        ("claim", c.claim_id, True) for c in state.claims if c.claim_id not in bad_claims
    ] + [("claim", c, False) for c in bad_claims]
    from bionexus.contracts.review import Verification

    state.verifications = [
        Verification(
            kind=VerificationKind(kind),
            subject=subject,
            verdict=VerificationVerdict.SUPPORTED if ok else VerificationVerdict.UNSUPPORTED,
        )
        for kind, subject, ok in verdicts_
    ] + [
        Verification(
            kind=VerificationKind.SENTENCE,
            subject=f"sentence-{n}",
            verdict=VerificationVerdict.UNSUPPORTED,
        )
        for n in bad_sentences
    ]
    apply_verifications(state)


def test_an_unsupported_sentence_is_removed_from_the_summary(state):
    apply(state, "First sentence. Second sentence. Third sentence.", bad_sentences=[1])
    assert state.narrative == "First sentence. Third sentence."


def test_if_every_sentence_is_removed_the_summary_falls_back_to_the_claims(state):
    apply(state, "Only sentence.", bad_sentences=[0])
    assert state.narrative == state.claims[0].text


def test_an_unsupported_claim_is_removed_from_the_findings(state):
    apply(state, "Summary.", bad_claims=[state.claims[0].claim_id])
    assert state.claims == []


def test_splitting_keeps_sentences_whole():
    assert split_sentences("One. Two? Three!  Four") == ["One.", "Two?", "Three!", "Four"]


# ---- the whole run -----------------------------------------------------------------------------


class ScriptedClient(DeterministicModelClient):
    """Writes a summary with one unsupported sentence, then judges sentences by that marker."""

    def generate(self, model_id, prompt, max_output_tokens, temperature=None, api_key_secret=None):
        if "<sentence>" in prompt:
            bad = "expected to confirm" in prompt
            verdict = {"verdict": "unsupported" if bad else "supported", "reason": "a prediction"}
            return ModelResponse(json.dumps(verdict), 60, 20)
        if prompt.strip().splitlines()[-1].startswith("Summarise:"):
            claims = prompt.strip().splitlines()[-1].removeprefix("Summarise: ")
            return ModelResponse(f"{claims} {HALLUCINATION}", 60, 40)
        return super().generate(model_id, prompt, max_output_tokens, temperature, api_key_secret)


def test_an_unsupported_sentence_never_reaches_the_report(request_):
    app = build_container(TOKENS, clients={"fixture": ScriptedClient()})
    state = run_to_review(app, request_)
    assert HALLUCINATION not in state.narrative
    report = app.investigations.report(SCIENTIST, state.run_id)
    assert HALLUCINATION not in report.markdown.split("## Limitations")[0]  # not in the findings
    assert "Withheld by the verifier" in report.markdown and HALLUCINATION in report.markdown
    pairs = [(m.sender, m.recipient, m.type) for m in state.messages]
    assert (AgentName.SUPERVISOR, AgentName.VERIFIER, MessageType.TASK_REQUEST) in pairs


def test_switching_the_verifier_off_lets_the_sentence_through(request_):
    app = build_container(
        TOKENS, clients={"fixture": ScriptedClient()}, disabled_steps=frozenset({"verify"})
    )
    state = run_to_review(app, request_)
    assert HALLUCINATION in state.narrative and state.verifications == []


def test_a_regenerated_draft_is_verified_too(request_):
    app = build_container(TOKENS, clients={"fixture": ScriptedClient()})
    state = run_to_review(app, request_)
    victim = next(e for e in state.evidence if e.startswith("reactome:"))
    app.investigations.exclude_evidence(SCIENTIST, state.run_id, [victim], "not relevant")
    after = app.investigations.get(SCIENTIST, state.run_id)
    assert HALLUCINATION not in after.narrative and after.verifications


def test_the_offline_model_keeps_every_sentence_and_says_so(container, request_):
    state = run_to_review(container, request_)
    assert state.verifications and not any(
        v.verdict is VerificationVerdict.UNSUPPORTED for v in state.verifications
    )
    assert state.narrative.startswith("[fixture")  # untouched
