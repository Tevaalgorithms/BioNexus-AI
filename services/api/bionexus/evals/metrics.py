"""Separate, individually reported metrics (EVAL-07). None of them is a single 'accuracy'."""

from dataclasses import dataclass

from bionexus.contracts.evidence import Claim, EvidenceRecord, Stance
from bionexus.evidence.matrix import build_matrix


@dataclass(frozen=True)
class Output:
    """What any system under test must hand to the metrics."""

    claims: list[Claim]
    evidence: dict[str, EvidenceRecord]  # evidence the system actually retrieved
    flagged_contradictions: set[str]  # targets the system reported as contradictory
    latency_s: float
    cost_usd: float
    ranked_ids: list[str]


def citation_presence(out: Output) -> float:
    cited = [c for c in out.claims if c.evidence_ids]
    return len(cited) / len(out.claims) if out.claims else 0.0


def fabricated_identifiers(out: Output) -> int:
    """Cited ids that were never retrieved: invented references."""
    return sum(1 for c in out.claims for e in c.evidence_ids if e not in out.evidence)


def citation_entailment_proxy(out: Output) -> float:
    """Automated proxy: does a claim's stance match the net stance of the evidence it cites?

    This is NOT expert entailment review; it only catches gross contradictions between a claim
    and its own citations.
    """
    if not out.claims:
        return 0.0
    agree = sum(1 for c in out.claims if _net(c, out) in (c.stance, Stance.UNKNOWN))
    return agree / len(out.claims)


def _net(claim: Claim, out: Output) -> Stance:
    cited = [out.evidence[e] for e in claim.evidence_ids if e in out.evidence]
    rows = build_matrix(cited)
    return rows[0].net_stance if rows else Stance.UNKNOWN


def essential_recall_at(out: Output, essential: list[str], k: int = 20) -> float:
    top = set(out.ranked_ids[:k]) if out.ranked_ids else set(out.evidence)
    return len(top & set(essential)) / len(essential)


def contradiction_recall(out: Output, known: list[str]) -> float:
    return len(out.flagged_contradictions & set(known)) / len(known) if known else 1.0


def excluded_leaks(out: Output, must_exclude: list[str]) -> int:
    return sum(1 for e in must_exclude if e in out.evidence)
