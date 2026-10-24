"""Gate applied before evidence may reach any model: license, cutoff, and review exclusions."""

from datetime import date

from bionexus.contracts.evidence import EvidenceRecord, Exclusion, ReviewState


def exclusion_reason(record: EvidenceRecord, cutoff: date) -> str | None:
    if not record.license_ok:
        return "license does not permit use"
    if record.available_on > cutoff:
        return f"available {record.available_on}, after cutoff {cutoff}"
    if record.review_state is ReviewState.EXCLUDED:
        return "excluded by scientist review"
    return None


def partition_eligible(
    records: list[EvidenceRecord], cutoff: date
) -> tuple[list[EvidenceRecord], list[Exclusion]]:
    eligible: list[EvidenceRecord] = []
    excluded: list[Exclusion] = []
    for record in records:
        reason = exclusion_reason(record, cutoff)
        if reason:
            excluded.append(Exclusion(evidence_id=record.evidence_id, reason=reason))
        else:
            eligible.append(record)
    return eligible, excluded


def accepted_evidence(records: list[EvidenceRecord]) -> list[EvidenceRecord]:
    """Accepted = eligible and backed by a passage. Unsupported items never reach a claim."""
    return [record for record in records if record.passage]
