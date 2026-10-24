"""Pre-export checks (REPORT-04): every claim resolves to evidence and limitations are present."""

from bionexus.contracts.errors import InvalidRequest
from bionexus.workflow.state import RunState


def validate_for_export(state: RunState) -> None:
    problems = [*_claim_problems(state), *_limitation_problems(state)]
    if problems:
        raise InvalidRequest("Report failed validation: " + "; ".join(problems))


def _claim_problems(state: RunState) -> list[str]:
    return [problem for claim in state.claims for problem in _one_claim(claim, state)]


def _one_claim(claim, state: RunState) -> list[str]:
    problems = [] if claim.evidence_ids else [f"{claim.claim_id} cites no evidence"]
    missing = [e for e in claim.evidence_ids if e not in state.evidence]
    return problems + [f"{claim.claim_id} cites unknown {e}" for e in missing]


def _limitation_problems(state: RunState) -> list[str]:
    unresolved = [i for i in state.issues if i.kind == "missing_passage"]
    return [] if state.narrative or not unresolved else ["narrative missing despite open issues"]
