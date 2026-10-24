from bionexus.container import build_container
from bionexus.contracts.investigation import InvestigationStatus
from bionexus.llm.clients import DeterministicModelClient
from tests.conftest import SCIENTIST, TOKENS, run_to_review


def test_fallback_model_is_used_and_the_reason_recorded(request_):
    flaky = {"fixture": DeterministicModelClient(failing_models=frozenset({"fixture-small"}))}
    state = run_to_review(build_container(TOKENS, clients=flaky), request_)
    assert state.status is InvestigationStatus.WAITING_FOR_REVIEW
    assert {i.model_id for i in state.invocations} == {"fixture-large"}
    assert all("unavailable" in i.fallback_reason for i in state.invocations)


def test_all_models_down_ends_incomplete(request_):
    down = {"fixture": DeterministicModelClient(frozenset({"fixture-small", "fixture-large"}))}
    state = run_to_review(build_container(TOKENS, clients=down), request_)
    assert state.status is InvestigationStatus.INCOMPLETE


def test_cost_in_manifest_matches_invocations(container, request_):
    state = run_to_review(container, request_)
    assert abs(state.budget.spent_usd - sum(i.cost_usd for i in state.invocations)) < 1e-9


def test_only_reviewed_evidence_is_reused_and_only_in_the_same_project(container, request_):
    first = run_to_review(container, request_, key="a")
    assert not container.storage.memory.recall(
        "org-a", "proj-1", ("NOD2",), request_.evidence_cutoff
    )

    report = container.investigations.report(SCIENTIST, first.run_id)
    container.investigations.approve(SCIENTIST, first.run_id, report.content_hash)

    recalled = container.storage.memory.recall(
        "org-a", "proj-1", ("NOD2",), request_.evidence_cutoff
    )
    assert recalled and all(r.review_state == "reviewed" for r in recalled)
    assert not container.storage.memory.recall(
        "org-a", "other-project", ("NOD2",), request_.evidence_cutoff
    )
    assert not container.storage.memory.recall(
        "org-b", "proj-1", ("NOD2",), request_.evidence_cutoff
    )


def test_a_scientist_exclusion_removes_an_item_from_reuse(container, request_):
    first = run_to_review(container, request_, key="a")
    report = container.investigations.report(SCIENTIST, first.run_id)
    container.investigations.approve(SCIENTIST, first.run_id, report.content_hash)
    container.storage.memory.exclude("org-a", "proj-1", "open_targets:OT-1")
    ids = {
        r.evidence_id
        for r in container.storage.memory.recall(
            "org-a", "proj-1", ("NOD2",), request_.evidence_cutoff
        )
    }
    assert "open_targets:OT-1" not in ids
