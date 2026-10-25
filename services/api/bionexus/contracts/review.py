"""What the review agents (critic and verifier) record about a run. Model text is labelled."""

from enum import StrEnum

from pydantic import BaseModel


class ConflictVerdict(StrEnum):
    REAL = "real"  # the studies appear to disagree
    EXPLAINED = "explained"  # the studies differ in a way that may explain the disagreement
    UNCLEAR = "unclear"


class ConflictAnalysis(BaseModel):
    """The critic's reading of one gene's conflict. A model wrote it; no one has reviewed it."""

    target: str
    verdict: ConflictVerdict
    explanation: str = ""


class VerificationKind(StrEnum):
    CLAIM = "claim"  # a claim in the findings, checked by plain code
    SENTENCE = "sentence"  # a sentence of the summary, checked by a model


class VerificationVerdict(StrEnum):
    SUPPORTED = "supported"
    UNSUPPORTED = "unsupported"  # withheld from the report
    UNCHECKED = "unchecked"  # could not be checked; kept, and said so


class Verification(BaseModel):
    kind: VerificationKind
    subject: str  # the claim id, or the sentence number
    text: str = ""
    verdict: VerificationVerdict
    reason: str = ""
