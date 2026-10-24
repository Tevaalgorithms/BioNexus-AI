from datetime import date

from pydantic import BaseModel, ConfigDict

ALLOWED_RELATIONS = frozenset({"associated_with", "annotated_in", "studied_in"})
MAX_HOPS = 2
MAX_EDGES = 100


class Scope(BaseModel):
    """Every retrieval is bound to tenant, project, run and evidence cutoff."""

    model_config = ConfigDict(frozen=True)

    tenant_id: str
    project_id: str
    run_id: str
    cutoff: date


class Edge(BaseModel):
    model_config = ConfigDict(frozen=True)

    subject: str
    relation: str
    object: str
    evidence_id: str
    species: str
    direction: str


class RankedHit(BaseModel):
    evidence_id: str
    score: float
