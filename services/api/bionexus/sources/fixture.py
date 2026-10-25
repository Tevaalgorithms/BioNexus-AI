"""Offline source backed by a synthetic JSON fixture. Replace per source with a live adapter."""

import hashlib
import json
from pathlib import Path

from bionexus.contracts.evidence import EvidenceRecord
from bionexus.contracts.hints import SearchHint

FIXTURE_DIR = Path(__file__).parent / "fixtures"


class FixtureSource:
    def __init__(self, name: str, directory: Path = FIXTURE_DIR) -> None:
        self.name = name
        raw = (directory / f"{name}.json").read_bytes()
        self._snapshot = hashlib.sha256(raw).hexdigest()
        document = json.loads(raw)
        self._disease = document["disease"].lower()
        self._supplements: dict[str, str] = document.get("full_text_passages", {})
        self._records = [self._to_record(row) for row in document["records"]]

    def _to_record(self, row: dict) -> EvidenceRecord:
        return EvidenceRecord(source=self.name, **row)

    def disease_name(self) -> str:
        return self._disease

    def search(
        self, disease: str, targets: tuple[str, ...], hint: SearchHint | None = None
    ) -> list[EvidenceRecord]:
        if disease.lower() != self._disease:
            return []
        return [record for record in self._records if record.target in targets]

    def passage_for(self, source_id: str) -> str | None:
        return self._supplements.get(source_id)

    def snapshot_id(self) -> str:
        return self._snapshot
