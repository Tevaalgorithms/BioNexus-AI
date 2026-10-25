from bionexus.contracts.investigation import InvestigationStatus
from bionexus.contracts.messages import AgentName, MessageType
from tests.conftest import run_to_review


def test_run_reaches_review_and_is_a_draft(container, request_):
    state = run_to_review(container, request_)
    assert state.status is InvestigationStatus.WAITING_FOR_REVIEW
    assert container.investigations.report(*_sci(state)).status == "draft"


def _sci(state):
    from tests.conftest import SCIENTIST

    return SCIENTIST, state.run_id


def test_same_study_across_sources_counts_once(container, request_):
    state = run_to_review(container, request_)
    nod2 = [c for c in state.claims if c.claim_id == "claim-NOD2"][0]
    assert "open_targets:OT-1" in nod2.evidence_ids and "gwas:GWAS-1" in nod2.evidence_ids
    assert "3 supporting" in nod2.text  # four NOD2 records, but OT-1 and GWAS-1 are one study


def test_post_cutoff_and_unlicensed_evidence_never_enter_context(container, request_):
    state = run_to_review(container, request_)
    reasons = {e.evidence_id: e.reason for e in state.excluded}
    assert "gwas:GWAS-3" in reasons and "europe_pmc:PMC-3" in reasons
    assert "gwas:GWAS-3" not in state.evidence and "europe_pmc:PMC-3" not in state.evidence


def test_genetics_asks_pathways_through_the_router(container, request_):
    state = run_to_review(container, request_)
    handoff = [
        m
        for m in state.messages
        if m.sender is AgentName.GENETICS and m.recipient is AgentName.PATHWAYS
    ]
    assert len(handoff) == 1 and handoff[0].type is MessageType.TASK_REQUEST
    assert any(e.startswith("reactome:") for e in state.evidence)


def test_critic_challenge_resolves_one_passage_and_reports_the_other(container, request_):
    state = run_to_review(container, request_)
    assert state.evidence["europe_pmc:PMC-1"].passage  # repaired through literature
    unresolved = [i.subject for i in state.issues if i.kind == "missing_passage"]
    assert unresolved == ["europe_pmc:PMC-4"]  # honest: still reported, never claimed


def test_unsupported_evidence_is_not_cited_in_claims(container, request_):
    state = run_to_review(container, request_)
    cited = {e for claim in state.claims for e in claim.evidence_ids}
    assert "europe_pmc:PMC-4" not in cited


def test_every_message_has_correlated_lineage(container, request_):
    state = run_to_review(container, request_)
    replies = [m for m in state.messages if m.type is MessageType.TASK_RESULT]
    assert replies and all(m.parent_id for m in replies)
    assert len({m.idempotency_key for m in state.messages}) == len(state.messages)


def test_budget_exhaustion_ends_incomplete_not_failed(container, request_):
    from bionexus.config import Settings
    from bionexus.container import build_container
    from tests.conftest import TOKENS

    tight = build_container(TOKENS, Settings(run_budget_usd=10.0, run_max_model_calls=0))
    state = run_to_review(tight, request_)
    assert state.status is InvestigationStatus.INCOMPLETE
    assert "Call limit" in state.stop_reason
