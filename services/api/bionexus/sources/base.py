"""What every evidence source (provider MCP or BioNexus adapter) must offer."""

from typing import Protocol

from bionexus.contracts.evidence import EvidenceRecord
from bionexus.contracts.hints import SearchHint


class EvidenceSource(Protocol):
    name: str

    def search(
        self, disease: str, targets: tuple[str, ...], hint: SearchHint | None = None
    ) -> list[EvidenceRecord]:
        """`hint` may widen the search; a source that cannot use it ignores it."""
        ...

    def passage_for(self, source_id: str) -> str | None: ...

    def snapshot_id(self) -> str: ...
