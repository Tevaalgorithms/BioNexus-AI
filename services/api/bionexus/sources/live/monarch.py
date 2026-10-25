"""Monarch Initiative: gene-disease and phenotype associations."""

from datetime import date

from bionexus.contracts.evidence import EvidenceRecord, Stance
from bionexus.contracts.hints import SearchHint
from bionexus.sources.live.common import (
    HUMAN,
    LiveSource,
)


class MonarchSource(LiveSource):
    name = "monarch"
    BASE = "https://api-v3.monarchinitiative.org/v3/api"

    def search(
        self, disease: str, targets: tuple[str, ...], hint: SearchHint | None = None
    ) -> list[EvidenceRecord]:
        records: list[EvidenceRecord] = []
        for target in targets:
            gene_id = self._gene_id(target)
            records.extend(self._phenotypes(gene_id, target) if gene_id else [])
        return records

    def _gene_id(self, symbol: str) -> str | None:
        params = {"q": symbol, "category": "biolink:Gene", "limit": 5}
        items = self._http.get_json(f"{self.BASE}/search", params).get("items", [])
        exact = [item for item in items if item.get("name") == symbol]
        return exact[0]["id"] if exact else None

    def _phenotypes(self, gene_id: str, target: str) -> list[EvidenceRecord]:
        params = {
            "subject": gene_id,
            "category": "biolink:GeneToPhenotypicFeatureAssociation",
            "limit": 5,
        }
        items = self._http.get_json(f"{self.BASE}/association", params).get("items", [])
        return [self._to_record(item, target) for item in items]

    @staticmethod
    def _to_record(item: dict, target: str) -> EvidenceRecord:
        phenotype = item.get("object_label") or item["object"]
        return EvidenceRecord(
            source="monarch",
            source_id=item["id"],
            study_family=f"MONARCH:{item['id']}",
            target=target,
            finding=f"Gene-phenotype association: {phenotype}",
            stance=Stance.UNKNOWN,
            species=HUMAN,
            context=f"upstream: {item.get('primary_knowledge_source', 'unknown')}",
            passage=f"{item.get('subject_label', target)} {item.get('predicate', '')} {phenotype}",
            available_on=date.today(),
            license_ok=True,  # upstream terms vary; confirm per knowledge source (SOURCE-10)
        )
