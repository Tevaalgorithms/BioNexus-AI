"""Proposed next experiments, derived deterministically from open issues (never from a model)."""

from bionexus.contracts.evidence import EvidenceRecord, Issue, IssueKind, Stance

_BY_KIND = {
    IssueKind.CONTRADICTION: "Compare cohort ancestry, tissue and assay design across the opposing "
    "studies for {subject}; consider a stratified re-analysis.",
    IssueKind.MISSING_PASSAGE: "Obtain the full text for {subject} and confirm the finding "
    "before it is relied upon.",
    IssueKind.SINGLE_FAMILY: "Seek an independent replication for {subject}; current support comes "
    "from one study family.",
}


def propose_next_steps(issues: list[Issue], evidence: list[EvidenceRecord]) -> list[str]:
    steps = [_BY_KIND[issue.kind].format(subject=issue.subject) for issue in issues]
    steps.extend(_trial_steps(evidence))
    return steps


def _trial_steps(evidence: list[EvidenceRecord]) -> list[str]:
    registered = [
        e for e in evidence if e.source == "clinicaltrials" and e.stance is Stance.UNKNOWN
    ]
    return [
        f"Check whether results have been posted for {e.source_id}; registration alone does not "
        "show efficacy."
        for e in registered
    ]
