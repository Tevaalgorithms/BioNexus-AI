"""Shapes domain objects for the UI: evidence cards, completeness, timeline."""

from bionexus.agents.synthesizer import retained_evidence
from bionexus.evidence.matrix import build_matrix
from bionexus.reporting.next_steps import propose_next_steps
from bionexus.sources.registry import SOURCE_NAMES
from bionexus.workflow.state import RunState


def run_summary(state: RunState) -> dict:
    return {
        "run_id": state.run_id,
        "project_id": state.project_id,
        "status": state.status.value,
        "stop_reason": state.stop_reason,
        "release_id": state.release_id,
        "disease": state.request.disease,
        "targets": list(state.request.targets),
        "created_at": state.created_at.isoformat(),
        "cost_usd": round(state.budget.spent_usd, 6),
        "budget_warning": state.budget.warning,
    }


def _source_row(state: RunState, name: str) -> dict:
    retained = sum(1 for r in state.evidence.values() if r.source == name)
    excluded = sum(1 for e in state.excluded if e.evidence_id.startswith(f"{name}:"))
    status = "ok" if retained else "no_evidence"
    return {"source": name, "retained": retained, "excluded": excluded, "status": status}


def source_completeness(state: RunState) -> list[dict]:
    """Per-source counts so gaps are visible rather than silently hidden (SOURCE-12)."""
    return [_source_row(state, name) for name in SOURCE_NAMES]


def _evidence_cards(state: RunState) -> list[dict]:
    retained = {r.evidence_id for r in retained_evidence(state)}
    return [
        {**r.model_dump(mode="json"), "accepted": r.evidence_id in retained}
        for r in state.evidence.values()
    ]


def _dump(items) -> list[dict]:
    return [item.model_dump(mode="json") for item in items]


def run_detail(state: RunState) -> dict:
    cards = _evidence_cards(state)
    return {
        **run_summary(state),
        "question": state.request.question,
        "evidence_cutoff": str(state.request.evidence_cutoff),
        "matrix": [_row(r) for r in build_matrix(retained_evidence(state))],
        "evidence": cards,
        "unaccepted": [c["evidence_id"] for c in cards if not c["accepted"]],
        "claims": _dump(state.claims),
        "issues": _dump(state.issues),
        "excluded": _dump(state.excluded),
        "next_steps": propose_next_steps(state.issues, list(state.evidence.values())),
        "completeness": source_completeness(state),
        "graph_context": state.graph_context,
        "timeline": [timeline_entry(m) for m in state.messages],
        "analyses": _dump(state.analyses.values()),
        "verifications": _dump(state.verifications),
    }


def _row(row) -> dict:
    return {
        "target": row.target,
        "supporting_families": row.supporting_families,
        "opposing_families": row.opposing_families,
        "unknown_families": row.unknown_families,
        "net_stance": row.net_stance.value,
        "evidence_ids": list(row.evidence_ids),
    }


def timeline_entry(message) -> dict:
    """Concise handoff for scientists: who asked whom, what kind, never private reasoning."""
    return {
        "message_id": message.message_id,
        "correlation_id": message.correlation_id,
        "from": message.sender.value,
        "to": message.recipient.value,
        "type": message.type.value,
        "depth": message.depth,
        "evidence_ids": list(message.evidence_ids),
        "ask": message.payload.get("ask"),  # what a challenge asked for, else None
        "hint": message.payload.get("text"),  # the extra search a request asked for, else None
    }
