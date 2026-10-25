"""Reactome: curated biological pathways."""

from datetime import date

from bionexus.contracts.evidence import EvidenceRecord, Stance
from bionexus.contracts.hints import SearchHint
from bionexus.sources.live.common import (
    HUMAN,
    LiveSource,
    plain,
)


class ReactomeSource(LiveSource):
    name = "reactome"
    URL = "https://reactome.org/ContentService/search/query"

    def search(
        self, disease: str, targets: tuple[str, ...], hint: SearchHint | None = None
    ) -> list[EvidenceRecord]:
        records: list[EvidenceRecord] = []
        for target in targets:
            params = {"query": target, "species": "Homo sapiens", "types": "Pathway"}
            groups = self._http.get_json(self.URL, params).get("results", [])
            entries = [entry for group in groups for entry in group.get("entries", [])]
            records.extend(self._to_record(entry, target) for entry in entries[:5])
        return records

    @staticmethod
    def _to_record(entry: dict, target: str) -> EvidenceRecord:
        return EvidenceRecord(
            source="reactome",
            source_id=entry["stId"],
            study_family=f"REACTOME:{entry['stId']}",
            target=target,
            finding=f"Curated pathway annotation: {plain(entry.get('name'))}",
            stance=Stance.UNKNOWN,  # an annotation is not an experimentally shown mechanism
            species=HUMAN,
            context="curated pathway annotation",
            passage=plain(entry.get("summation")),
            available_on=date.today(),
            license_ok=True,  # Reactome content is CC0/CC-BY; confirm per category (SOURCE-10)
        )
