"""Verifier: checks the findings before they go into a report.

Two checks, one by plain code and one by a model:

1. Each claim is rebuilt from the evidence it cites. If the claim does not match, cites evidence the
   run does not have, or cites evidence that is not accepted, it is withheld.
2. Each sentence of the written summary is compared with the claims by a model. A sentence the
   claims do not support (anything added, stronger or causal) is withheld.

Nothing is invented to fill a gap. If the model cannot be reached, a sentence is kept and marked
"unchecked", so the report says what was and was not verified.
"""

import re
from concurrent.futures import ThreadPoolExecutor
from typing import ClassVar

from bionexus.agents.base import Agent, AgentResult
from bionexus.agents.jsonreply import parse_json_object
from bionexus.agents.optimization import AO_MAX_PARALLEL_MODEL_CALLS, AO_MAX_VERIFIED_SENTENCES
from bionexus.agents.synthesizer import make_claim
from bionexus.contracts.errors import ModelUnavailable
from bionexus.contracts.evidence import Claim, EvidenceRecord
from bionexus.contracts.messages import AgentMessage, AgentName
from bionexus.contracts.review import Verification, VerificationKind, VerificationVerdict
from bionexus.evidence.eligibility import exclusion_reason
from bionexus.evidence.matrix import build_matrix
from bionexus.workflow.state import RunState

SENTENCE_BREAK = re.compile(r"(?<=[.!?])\s+")
MAX_REASON_CHARS = 200


def split_sentences(text: str) -> list[str]:
    return [s.strip() for s in SENTENCE_BREAK.split(text.strip()) if s.strip()]


def _verdict(kind, subject: str, text: str, ok: bool, reason: str = "") -> Verification:
    verdict = VerificationVerdict.SUPPORTED if ok else VerificationVerdict.UNSUPPORTED
    return Verification(kind=kind, subject=subject, text=text, verdict=verdict, reason=reason)


def _not_accepted(record: EvidenceRecord, state: RunState) -> bool:
    """Evidence a claim may cite has a passage and is still licensed, in date and not excluded."""
    cutoff = state.request.evidence_cutoff
    return not record.passage or exclusion_reason(record, cutoff) is not None


def _claim_problem(claim: Claim, state: RunState) -> str:
    """Why a claim cannot stand, or an empty string if it can."""
    cited = [state.evidence[e] for e in claim.evidence_ids if e in state.evidence]
    if len(cited) != len(claim.evidence_ids):
        return "it cites evidence this run does not have"
    if any(_not_accepted(r, state) for r in cited):
        return "it cites evidence that is not accepted"
    rows = build_matrix(cited)
    expected = make_claim(rows[0], state.request.disease) if rows else None
    if expected is None or (expected.text, expected.stance) != (claim.text, claim.stance):
        return "it does not match the evidence it cites"
    return ""


def check_claims(state: RunState) -> list[Verification]:
    """Plain code: every claim is rebuilt from its own citations."""
    results = []
    for claim in state.claims:
        problem = _claim_problem(claim, state)
        results.append(
            _verdict(VerificationKind.CLAIM, claim.claim_id, claim.text, not problem, problem)
        )
    return results


def apply_verifications(state: RunState) -> None:
    """Withhold what failed: drop unsupported claims and unsupported summary sentences."""
    bad = {v.subject for v in state.verifications if v.verdict is VerificationVerdict.UNSUPPORTED}
    state.claims = [c for c in state.claims if c.claim_id not in bad]
    sentences = split_sentences(state.narrative)
    kept = [s for n, s in enumerate(sentences) if f"sentence-{n}" not in bad]
    state.narrative = " ".join(kept) or " ".join(c.text for c in state.claims)


class VerifierAgent(Agent):
    name: ClassVar[AgentName] = AgentName.VERIFIER
    skill_id: ClassVar[str] = "claims.verify"

    def handle(self, message: AgentMessage, state: RunState) -> AgentResult:
        found = self.verify(state)
        withheld = sum(v.verdict is VerificationVerdict.UNSUPPORTED for v in found)
        return AgentResult(
            verifications=found,
            assessment=f"{len(found)} checks, {withheld} withheld.",
        )

    def review(self, state: RunState) -> None:
        """Verify and apply in one step (used when an exclusion regenerates the draft)."""
        state.verifications = self.verify(state)
        apply_verifications(state)

    def verify(self, state: RunState) -> list[Verification]:
        return [*check_claims(state), *self._check_summary(state)]

    def _check_summary(self, state: RunState) -> list[Verification]:
        sentences = split_sentences(state.narrative)[:AO_MAX_VERIFIED_SENTENCES]
        with ThreadPoolExecutor(max_workers=AO_MAX_PARALLEL_MODEL_CALLS) as pool:
            return list(
                pool.map(lambda item: self._check_sentence(state, *item), enumerate(sentences))
            )

    def _check_sentence(self, state: RunState, number: int, sentence: str) -> Verification:
        subject = f"sentence-{number}"
        if any(sentence == c.text for c in state.claims):  # a claim word for word needs no model
            return _verdict(VerificationKind.SENTENCE, subject, sentence, True, "it is a claim")
        try:
            reply = self.ask_model(state, self._prompt(state, sentence))
        except ModelUnavailable:
            return self._unchecked(subject, sentence, "no model was available")
        return self._read(subject, sentence, parse_json_object(reply))

    @staticmethod
    def _prompt(state: RunState, sentence: str) -> str:
        claims = "\n".join(c.text for c in state.claims)
        return (
            f"<claims_data>\n{claims}\n</claims_data>\n<sentence>{sentence}</sentence>\n"
            "Is the sentence fully supported by the claims, with nothing added or stronger? "
            'Reply with JSON only: {"verdict": "supported|unsupported", "reason": "<short>"}'
        )

    def _read(self, subject: str, sentence: str, payload: dict | None) -> Verification:
        verdict = str((payload or {}).get("verdict", "")).strip().lower()
        if verdict not in {"supported", "unsupported"}:
            return self._unchecked(subject, sentence, "the check gave no clear answer")
        reason = " ".join(str((payload or {}).get("reason", "")).split())[:MAX_REASON_CHARS]
        return _verdict(
            VerificationKind.SENTENCE, subject, sentence, verdict == "supported", reason
        )

    @staticmethod
    def _unchecked(subject: str, sentence: str, reason: str) -> Verification:
        return Verification(
            kind=VerificationKind.SENTENCE,
            subject=subject,
            text=sentence,
            verdict=VerificationVerdict.UNCHECKED,
            reason=reason,
        )
