"""Hybrid retrieval: lexical + vector fused deterministically, then bounded graph expansion."""

from bionexus.contracts.evidence import EvidenceRecord, Stance
from bionexus.retrieval.embedder import Embedder
from bionexus.retrieval.fusion import fuse
from bionexus.retrieval.models import ALLOWED_RELATIONS, MAX_EDGES, MAX_HOPS, Edge, RankedHit, Scope
from bionexus.retrieval.port import RetrievalStore

CANDIDATES = 200  # SCOPE-06: at most 200 retrieved candidates per investigation
PATHWAY_SOURCES = frozenset({"reactome", "monarch"})


class RetrievalService:
    def __init__(self, store: RetrievalStore, embedder: Embedder) -> None:
        self._store = store
        self._embedder = embedder

    def index(self, scope: Scope, records: list[EvidenceRecord], disease: str) -> None:
        vectors = self._embedder.embed([f"{r.finding} {r.passage}" for r in records])
        self._store.add_chunks(scope, records, vectors, self._embedder.model_id)
        self._store.add_edges(scope, [edge for r in records for edge in edges_for(r, disease)])

    def search(self, scope: Scope, query: str, limit: int = CANDIDATES) -> list[RankedHit]:
        lexical = self._store.lexical(scope, query, limit)
        query_vector = self._embedder.embed([query])[0]
        vector = self._store.vector(scope, query_vector, self._embedder.model_id, limit)
        return [RankedHit(evidence_id=i, score=s) for i, s in fuse([lexical, vector])][:limit]

    def expand(self, scope: Scope, seeds: list[str]) -> list[Edge]:
        """Breadth-first over approved relations only: <= 2 hops and <= 100 edges."""
        seen: dict[tuple, Edge] = {}
        frontier = list(seeds)
        for _ in range(MAX_HOPS):
            fresh = self._take_new_edges(scope, frontier, seen)
            frontier = sorted({e.object for e in fresh})
            if not frontier or len(seen) >= MAX_EDGES:
                break
        return list(seen.values())

    def _take_new_edges(self, scope: Scope, frontier: list[str], seen: dict) -> list[Edge]:
        found = self._store.edges_from(scope, frontier, ALLOWED_RELATIONS)
        fresh = [e for e in found if _key(e) not in seen]
        for edge in fresh[: MAX_EDGES - len(seen)]:
            seen[_key(edge)] = edge
        return fresh


def _key(edge: Edge) -> tuple:
    return (edge.subject, edge.relation, edge.object, edge.evidence_id)


def edges_for(record: EvidenceRecord, disease: str) -> list[Edge]:
    """Typed edges from a record; the relation reflects what the source actually shows."""
    if record.source in PATHWAY_SOURCES:
        pathway = record.finding.split(": ")[-1]
        return [_edge(record, record.target, "annotated_in", pathway, "none")]
    direction = record.stance.value if record.stance is not Stance.UNKNOWN else "none"
    return [
        _edge(record, record.target, "associated_with", disease, direction),
        _edge(record, disease, "associated_with", record.target, direction),
    ]


def _edge(record: EvidenceRecord, subject: str, relation: str, obj: str, direction: str) -> Edge:
    return Edge(
        subject=subject,
        relation=relation,
        object=obj,
        evidence_id=record.evidence_id,
        species=record.species,
        direction=direction,
    )
