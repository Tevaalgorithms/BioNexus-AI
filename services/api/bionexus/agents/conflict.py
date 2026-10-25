"""The critic's judgement of a conflict: what it shows a model, and how the reply is read.

A model's reply is untrusted. It is read defensively: a verdict outside the three allowed ones is
"unclear", an explanation with causal or treatment wording is dropped, and a requested search is
only used if it passes the same checks as any other request.
"""

from bionexus.agents.evidence_requests import PlannedRequest, parse_request
from bionexus.agents.jsonreply import parse_json_object
from bionexus.agents.optimization import AO_MAX_CONFLICT_RECORDS, AO_PASSAGE_CHARS
from bionexus.agents.synthesizer import language_violations
from bionexus.contracts.evidence import EvidenceRecord, Stance
from bionexus.contracts.review import ConflictAnalysis, ConflictVerdict

MAX_EXPLANATION_CHARS = 300


def sides(
    records: list[EvidenceRecord], target: str
) -> tuple[list[EvidenceRecord], list[EvidenceRecord]]:
    """The supporting and the opposing records for one gene, a few of each."""
    mine = [r for r in records if r.target == target]
    supporting = [r for r in mine if r.stance is Stance.SUPPORTS]
    opposing = [r for r in mine if r.stance is Stance.OPPOSES]
    return supporting[:AO_MAX_CONFLICT_RECORDS], opposing[:AO_MAX_CONFLICT_RECORDS]


def _line(r: EvidenceRecord) -> str:
    where = f"{r.source}; {r.species}; {r.context}"
    return f"[{r.evidence_id}] ({where}) {r.finding} :: {r.passage[:AO_PASSAGE_CHARS]}"


def conflict_prompt(
    target: str, supporting: list[EvidenceRecord], opposing: list[EvidenceRecord]
) -> str:
    lines = [f"Gene: {target}", "SUPPORTING:", *map(_line, supporting)]
    lines += ["OPPOSING:", *map(_line, opposing)]
    return (
        "<conflict_data>\n" + "\n".join(lines) + "\n</conflict_data>\n"
        "Do these studies truly conflict, or could they differ in population, tissue, assay or "
        "design? Reply with JSON only: "
        '{"verdict": "real|explained|unclear", "explanation": "<one or two sentences>", '
        '"request": null or {"agent": "literature|genetics|clinical", '
        '"kind": "disease|gene|context", "text": "<phrase>"}}'
    )


def _verdict(value: object) -> ConflictVerdict:
    allowed = {v.value: v for v in ConflictVerdict}
    return allowed.get(str(value).strip().lower(), ConflictVerdict.UNCLEAR)


def _explanation(value: object) -> str:
    if not isinstance(value, str):
        return ""
    text = " ".join(value.split())[:MAX_EXPLANATION_CHARS]
    return "" if language_violations(text) else text  # causal or treatment wording is dropped


def read_analysis(reply: str, target: str) -> tuple[ConflictAnalysis, PlannedRequest | None]:
    """The analysis and the optional search the critic wants, from one model reply."""
    payload = parse_json_object(reply) or {}
    analysis = ConflictAnalysis(
        target=target,
        verdict=_verdict(payload.get("verdict")),
        explanation=_explanation(payload.get("explanation")),
    )
    return analysis, parse_request(payload.get("request"))
