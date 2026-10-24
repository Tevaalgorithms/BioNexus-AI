"""What every evidence source (provider MCP or BioNexus adapter) must offer."""

from typing import Protocol

from bionexus.contracts.evidence import EvidenceRecord


class EvidenceSource(Protocol):
    name: str

    def search(self, disease: str, targets: tuple[str, ...]) -> list[EvidenceRecord]: ...

    def passage_for(self, source_id: str) -> str | None: ...

    def snapshot_id(self) -> str: ...
