"""The critic asks for a second opinion on a contested, model-read direction (and only that)."""

from datetime import date
from types import SimpleNamespace

import pytest

from bionexus.agents.critic import CriticAgent
from bionexus.agents.literature import LiteratureAgent
from bionexus.agents.optimization import AO_MAX_RECHECKS_PER_ROUND
from bionexus.contracts.evidence import EvidenceRecord, IssueKind, Stance
from bionexus.contracts.messages import AgentName, ChallengeAsk, MessageType
from bionexus.evidence.stance import MODEL_STANCE_NOTE, RECHECKED_NOTE
from bionexus.messaging.envelope import new_message
from bionexus.messaging.router import MAX_MESSAGES_PER_RUN
from bionexus.workflow.budget import Budget
from bionexus.workflow.state import RunState

LONG_PASSAGE = "Opening sentence. " + "Filler text. " * 40 + "DECISIVE SENTENCE at the very end."


class FakeGateway:
    def __init__(self, answer: str = "ok") -> None:
        self.answer, self.prompts = answer, []

    def complete(self, state, agent, prompt: str) -> str:
        self.prompts.append(prompt)
        return self.answer


class FakeSources:
    def __init__(self, passage: str | None) -> None:
        self._passage = passage

    def get(self, name: str):
        return SimpleNamespace(passage_for=lambda source_id: self._passage)


def record(source, source_id, family, stance, *, model_read=False, passage="short passage"):
    return EvidenceRecord(
        source=source,
        source_id=source_id,
        study_family=family,
        target="NOD2",
        finding="NOD2 and Crohn's disease",
        stance=stance,
        species="human",
        context=f"context; {MODEL_STANCE_NOTE}" if model_read else "context",
        passage=passage,
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
        budget=Budget(max_cost_usd=1, max_calls=5),
    )


def critic(gateway=None) -> CriticAgent:
    agent = CriticAgent(SimpleNamespace(gateway=gateway or FakeGateway()))
    agent.instructions = lambda state, skill_id=None: "skill"
    return agent


def literature(passage: str | None, answer: str) -> tuple[LiteratureAgent, FakeGateway]:
    gateway = FakeGateway(answer)
    agent = LiteratureAgent(SimpleNamespace(sources=FakeSources(passage), gateway=gateway))
    agent.instructions = lambda state, skill_id=None: "skill"
    return agent, gateway


def critic_task(state):
    return new_message(
        run_id=state.run_id,
        sender=AgentName.SUPERVISOR,
        recipient=AgentName.CRITIC,
        kind=MessageType.TASK_REQUEST,
        payload={"repair_round": 0},
    )


def contested(state, *, model_read=True):
    """A database study supports NOD2; a model read one paper as opposing."""
    state.add_evidence(
        [
            record("open_targets", "OT-1", "fam-db", Stance.SUPPORTS),
            record("europe_pmc", "PMC-9", "fam-lit", Stance.OPPOSES, model_read=model_read),
        ]
    )


def test_a_contradiction_with_a_model_read_direction_is_challenged(state):
    contested(state)
    result = critic().handle(critic_task(state), state)
    assert any(i.kind is IssueKind.CONTRADICTION for i in result.issues)
    [challenge] = result.outgoing
    assert challenge.type is MessageType.EVIDENCE_CHALLENGE
    assert challenge.recipient is AgentName.LITERATURE
    assert challenge.payload["ask"] == ChallengeAsk.RECHECK_DIRECTION
    assert challenge.evidence_ids == ("europe_pmc:PMC-9",)


def test_database_records_are_never_re_read(state):
    contested(state, model_read=False)  # both directions came from the sources themselves
    result = critic().handle(critic_task(state), state)
    assert any(i.kind is IssueKind.CONTRADICTION for i in result.issues)  # still reported
    assert result.outgoing == []


def test_a_handoff_says_what_the_challenge_asked_for(state):
    from bionexus.application.presentation import timeline_entry

    contested(state)
    challenge = critic().handle(critic_task(state), state).outgoing[0]
    assert timeline_entry(challenge)["ask"] == ChallengeAsk.RECHECK_DIRECTION
    assert timeline_entry(critic_task(state))["ask"] is None


def test_the_meta_payload_reports_the_real_run_limits():
    from bionexus.config import Settings
    from bionexus.container import build_container
    from bionexus.workflow.nodes import MAX_REPAIR_ROUNDS

    app = build_container({}, settings=Settings(run_budget_usd=0.5, run_warn_usd=0.25))
    assert app.meta()["limits"] == {
        "run_budget_usd": 0.5,
        "run_warn_usd": 0.25,
        "max_repair_rounds": MAX_REPAIR_ROUNDS,
    }


def test_the_same_record_is_challenged_only_once(state):
    contested(state)
    first = critic().handle(critic_task(state), state).outgoing
    state.messages.extend(first)
    assert critic().handle(critic_task(state), state).outgoing == []


def test_rechecks_per_round_are_capped(state):
    state.add_evidence([record("open_targets", "OT-1", "fam-db", Stance.SUPPORTS)])
    for n in range(AO_MAX_RECHECKS_PER_ROUND + 3):
        state.add_evidence(
            [record("europe_pmc", f"P{n}", f"fam-{n}", Stance.OPPOSES, model_read=True)]
        )
    assert len(critic().pending_repairs(state)) == AO_MAX_RECHECKS_PER_ROUND


def test_no_challenge_is_sent_when_the_message_budget_is_nearly_spent(state):
    contested(state)
    filler = new_message(
        run_id="r",
        sender=AgentName.SUPERVISOR,
        recipient=AgentName.GENETICS,
        kind=MessageType.TASK_REQUEST,
        payload={},
    )
    state.messages.extend([filler] * (MAX_MESSAGES_PER_RUN - 3))
    assert critic().pending_repairs(state) == []


def test_literature_re_reads_the_full_passage_and_updates_the_direction(state):
    contested(state)
    agent, gateway = literature(LONG_PASSAGE, "supports")
    challenge = critic().handle(critic_task(state), state).outgoing[0]
    result = agent.handle(challenge, state)
    [updated] = result.evidence
    assert updated.stance is Stance.SUPPORTS
    assert RECHECKED_NOTE in updated.context and MODEL_STANCE_NOTE not in updated.context
    assert "DECISIVE SENTENCE" in gateway.prompts[0]  # the end of the passage reached the model
    assert result.assessment == "Direction re-checked: opposes -> supports."


def test_a_re_check_that_cannot_tell_says_unknown_and_resolves_the_conflict(state):
    contested(state)
    agent, _ = literature(LONG_PASSAGE, "I cannot tell from this text")
    challenge = critic().handle(critic_task(state), state).outgoing[0]
    state.add_evidence(agent.handle(challenge, state).evidence)
    assert state.evidence["europe_pmc:PMC-9"].stance is Stance.UNKNOWN
    assert critic().pending_repairs(state) == []


def test_without_a_passage_the_agent_abstains_and_changes_nothing(state):
    contested(state)
    agent, gateway = literature(None, "supports")
    challenge = critic().handle(critic_task(state), state).outgoing[0]
    result = agent.handle(challenge, state)
    assert result.abstained and result.evidence == [] and gateway.prompts == []
