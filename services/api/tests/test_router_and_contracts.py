import pytest
from pydantic import ValidationError

from bionexus.contracts.errors import InvalidTransition, RouteRejected
from bionexus.contracts.investigation import InvestigationRequest, InvestigationStatus
from bionexus.contracts.messages import AgentName, MessageType
from bionexus.messaging.envelope import new_message
from bionexus.messaging.router import MAX_DEPTH, MessageRouter
from bionexus.workflow.budget import Budget
from bionexus.workflow.state import RunState


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


def msg(sender, recipient, kind=MessageType.TASK_REQUEST, parent=None, **payload):
    return new_message(
        run_id="r", sender=sender, recipient=recipient, kind=kind, payload=payload, parent=parent
    )


def test_unlisted_routes_are_rejected(state):
    with pytest.raises(RouteRejected):
        MessageRouter().accept(state, msg(AgentName.LITERATURE, AgentName.GENETICS))


def test_duplicate_delivery_is_ignored(state):
    router, m = MessageRouter(), msg(AgentName.SUPERVISOR, AgentName.GENETICS)
    assert router.accept(state, m) and not router.accept(state, m)
    assert len(state.messages) == 1


def test_reply_must_answer_a_real_request(state):
    forged = msg(AgentName.LITERATURE, AgentName.SUPERVISOR, MessageType.TASK_RESULT)
    with pytest.raises(RouteRejected):
        MessageRouter().accept(state, forged)


def test_handoff_depth_is_capped(state):
    parent = msg(AgentName.SUPERVISOR, AgentName.GENETICS)
    for _ in range(MAX_DEPTH + 1):
        parent = new_message(
            run_id="r",
            sender=AgentName.SUPERVISOR,
            recipient=AgentName.GENETICS,
            kind=MessageType.TASK_REQUEST,
            payload={"n": parent.depth},
            parent=parent,
        )
    with pytest.raises(RouteRejected):
        MessageRouter().accept(state, parent)


def test_invalid_status_transition_is_refused(state):
    with pytest.raises(InvalidTransition):
        state.transition(InvestigationStatus.COMPLETED)


def test_request_contract_rejects_bad_input():
    base = dict(
        disease="Crohn's disease", question="a valid question", evidence_cutoff="2026-01-01"
    )
    with pytest.raises(ValidationError):
        InvestigationRequest(targets=[], **base)
    with pytest.raises(ValidationError):
        InvestigationRequest(targets=list("ABCDEF"), **base)
    with pytest.raises(ValidationError):
        InvestigationRequest(targets=["NOD2"], unexpected="x", **base)
