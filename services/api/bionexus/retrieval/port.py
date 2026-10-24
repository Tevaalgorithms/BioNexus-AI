from typing import Protocol

from bionexus.contracts.evidence import EvidenceRecord
from bionexus.retrieval.models import Edge, Scope


class RetrievalStore(Protocol):
    def add_chunks(
        self, scope: Scope, records: list[EvidenceRecord], vectors: list[list[float]], model: str
    ) -> None: ...

    def lexical(self, scope: Scope, query: str, limit: int) -> list[str]: ...

    def vector(self, scope: Scope, vector: list[float], model: str, limit: int) -> list[str]: ...

    def add_edges(self, scope: Scope, edges: list[Edge]) -> None: ...

    def edges_from(
        self, scope: Scope, nodes: list[str], relations: frozenset[str]
    ) -> list[Edge]: ...
