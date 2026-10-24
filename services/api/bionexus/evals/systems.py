"""Systems under test: two baselines and the multi-agent product, run on identical inputs."""

import time
from datetime import date

from bionexus.agents.critic import find_issues
from bionexus.container import Container, build_container
from bionexus.contracts.evidence import Claim
from bionexus.contracts.identity import ClientKind, Principal, Role
from bionexus.contracts.investigation import InvestigationRequest
from bionexus.evals.metrics import Output
from bionexus.evidence.eligibility import partition_eligible
from bionexus.evidence.matrix import build_matrix
from bionexus.sources.registry import SOURCE_NAMES, SourceRegistry

EVAL_USER = Principal(
    user_id="eval",
    role=Role.SCIENTIST,
    tenant_id="eval",
    project_ids=frozenset({"eval"}),
    client_kind=ClientKind.SCIENTIST,
)


def _request(case: dict) -> InvestigationRequest:
    return InvestigationRequest(
        disease=case["disease"],
        targets=tuple(case["targets"]),
        question=f"Evidence for {', '.join(case['targets'])} in {case['disease']}",
        evidence_cutoff=date.fromisoformat(case["cutoff"]),
    )


def deterministic_baseline(case: dict) -> Output:
    """Fixed queries to every source and a templated claim per target. No model, no critic."""
    started = time.monotonic()
    request, sources = _request(case), SourceRegistry.from_fixtures()
    found = [
        r for n in SOURCE_NAMES for r in sources.get(n).search(request.disease, request.targets)
    ]
    eligible, _ = partition_eligible(found, request.evidence_cutoff)
    evidence = {r.evidence_id: r for r in eligible}
    claims = [_claim(row) for row in build_matrix(eligible)]
    return Output(claims, evidence, set(), time.monotonic() - started, 0.0, [])


def _claim(row) -> Claim:
    return Claim(
        claim_id=f"claim-{row.target}",
        text=f"{row.target} evidence summary",
        stance=row.net_stance,
        evidence_ids=row.evidence_ids,
    )


def single_agent_baseline(case: dict) -> Output:
    """One agent, same sources/budget: retrieves and flags contradictions, but has no routed
    follow-ups, no passage repair and no critic challenges."""
    out = deterministic_baseline(case)
    issues = find_issues(list(out.evidence.values()))
    flagged = {i.subject for i in issues if i.kind == "contradiction"}
    return Output(out.claims, out.evidence, flagged, out.latency_s, out.cost_usd, [])


def _run_to_end(app: Container, case: dict):
    key = f"eval-{time.monotonic()}"
    run = app.investigations.submit(EVAL_USER, "eval", _request(case), key)
    app.worker.run_pending()
    return app.investigations.get(EVAL_USER, run.run_id)


def multi_agent(case: dict, *, critic: bool = True, container: Container | None = None) -> Output:
    disabled = frozenset() if critic else frozenset({"critique"})
    app = container or build_container({"eval": EVAL_USER}, disabled_steps=disabled)
    started = time.monotonic()
    state = _run_to_end(app, case)
    flagged = {i.subject for i in state.issues if i.kind == "contradiction"}
    return Output(
        state.claims,
        dict(state.evidence),
        flagged,
        time.monotonic() - started,
        state.budget.spent_usd,
        state.ranked_evidence_ids,
    )
