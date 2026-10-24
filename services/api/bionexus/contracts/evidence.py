"""Evidence, claims and issues: the vocabulary every agent shares."""

import hashlib
from datetime import date
from enum import StrEnum

from pydantic import BaseModel, ConfigDict, computed_field


class Stance(StrEnum):
    SUPPORTS = "supports"
    OPPOSES = "opposes"
    UNKNOWN = "unknown"


class ReviewState(StrEnum):
    PROVISIONAL = "provisional"
    REVIEWED = "reviewed"
    EXCLUDED = "excluded"


class EvidenceRecord(BaseModel):
    """One attributable finding. `study_family` groups the same study across aggregators."""

    # extra="ignore": derived fields (evidence_id, content_hash) are re-computed on reload.
    model_config = ConfigDict(frozen=True, extra="ignore")

    source: str
    source_id: str
    study_family: str
    target: str
    finding: str
    stance: Stance
    species: str
    context: str
    passage: str
    available_on: date
    license_ok: bool
    review_state: ReviewState = ReviewState.PROVISIONAL

    @computed_field
    @property
    def evidence_id(self) -> str:
        return f"{self.source}:{self.source_id}"

    @computed_field
    @property
    def content_hash(self) -> str:
        return hashlib.sha256(f"{self.finding}|{self.passage}".encode()).hexdigest()


class Exclusion(BaseModel):
    """Evidence that was found but kept out of model context, and why."""

    evidence_id: str
    reason: str


class IssueKind(StrEnum):
    MISSING_PASSAGE = "missing_passage"
    CONTRADICTION = "contradiction"
    SINGLE_FAMILY = "single_family"


class Issue(BaseModel):
    kind: IssueKind
    subject: str
    description: str

    @computed_field
    @property
    def issue_id(self) -> str:
        return f"{self.kind}:{self.subject}"


class Claim(BaseModel):
    claim_id: str
    text: str
    stance: Stance
    evidence_ids: tuple[str, ...]
