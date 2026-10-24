"""In-memory retrieval store for tests; mirrors the SQL filters exactly."""

import re

from bionexus.contracts.evidence import EvidenceRecord
from bionexus.evidence.eligibility import exclusion_reason
from bionexus.retrieval.models import Edge, Scope

TOKEN = re.compile(r"[a-z0-9]+")


def _visible(scope: Scope, chunk_scope: Scope, record: EvidenceRecord) -> bool:
    same = (chunk_scope.tenant_id, chunk_scope.project_id, chunk_scope.run_id) == (
        scope.tenant_id,
        scope.project_id,
        scope.run_id,
    )
    return same and exclusion_reason(record, scope.cutoff) is None


def _edge_matches(edge: Edge, nodes: list[str], relations: frozenset[str], allowed: set) -> bool:
    return edge.subject in nodes and edge.relation in relations and edge.evidence_id in allowed


def _text(record: EvidenceRecord) -> str:
    return f"{record.finding} {record.passage} {record.target}"


class InMemoryRetrieval:
    def __init__(self) -> None:
        self._chunks: list[tuple[Scope, EvidenceRecord, list[float], str]] = []
        self._edges: list[tuple[Scope, Edge]] = []

    def add_chunks(self, scope, records, vectors, model) -> None:
        for record, vector in zip(records, vectors, strict=True):
            self._chunks.append((scope, record, vector, model))

    def _eligible(self, scope: Scope, model: str | None = None):
        for chunk_scope, record, vector, chunk_model in self._chunks:
            if _visible(scope, chunk_scope, record) and model in (None, chunk_model):
                yield record, vector

    def lexical(self, scope: Scope, query: str, limit: int) -> list[str]:
        terms = set(TOKEN.findall(query.lower()))
        scored = [
            (len(terms & set(TOKEN.findall(_text(r).lower()))), r.evidence_id)
            for r, _ in self._eligible(scope)
        ]
        ranked = sorted((s for s in scored if s[0] > 0), key=lambda s: (-s[0], s[1]))
        return [evidence_id for _, evidence_id in ranked[:limit]]

    def vector(self, scope: Scope, vector: list[float], model: str, limit: int) -> list[str]:
        scored = [
            (sum(a * b for a, b in zip(vector, v, strict=True)), r.evidence_id)
            for r, v in self._eligible(scope, model)
        ]
        ranked = sorted(scored, key=lambda s: (-s[0], s[1]))
        return [evidence_id for _, evidence_id in ranked[:limit]]

    def add_edges(self, scope: Scope, edges: list[Edge]) -> None:
        self._edges.extend((scope, edge) for edge in edges)

    def edges_from(self, scope: Scope, nodes: list[str], relations: frozenset[str]) -> list[Edge]:
        allowed = {r.evidence_id for r, _ in self._eligible(scope)}
        in_scope = [edge for edge_scope, edge in self._edges if edge_scope == scope]
        return [e for e in in_scope if _edge_matches(e, nodes, relations, allowed)]
