"""GWAS Catalog: genome-wide association variants."""

from datetime import date

from bionexus.contracts.evidence import EvidenceRecord, Stance
from bionexus.sources.live.common import (
    HUMAN,
    LiveSource,
    disease_words,
    normalise,
)


class GwasCatalogSource(LiveSource):
    name = "gwas"
    URL = "https://www.ebi.ac.uk/gwas/rest/api/v2/associations"

    def search(self, disease: str, targets: tuple[str, ...]) -> list[EvidenceRecord]:
        words = disease_words(disease)
        records: list[EvidenceRecord] = []
        for target in targets:
            params = {"mapped_gene": target, "size": 200}
            payload = self._http.get_json(self.URL, params)
            rows = payload.get("_embedded", {}).get("associations", [])
            records.extend(self._to_record(r, target) for r in rows if self._matches(r, words))
        return records

    @staticmethod
    def _matches(row: dict, words: list[str]) -> bool:
        traits = [t["efo_trait"] for t in row.get("efo_traits", [])] + row.get("reported_trait", [])
        return any(all(w in normalise(trait) for w in words) for trait in traits)

    @staticmethod
    def _to_record(row: dict, target: str) -> EvidenceRecord:
        pmid = row.get("pubmed_id", row["accession_id"])
        return EvidenceRecord(
            source="gwas",
            source_id=str(row["association_id"]),
            study_family=f"PMID:{pmid}",  # same family as the literature record for this paper
            target=target,
            finding=f"GWAS association (p={row.get('p_value')}) with {row.get('reported_trait')}",
            stance=Stance.SUPPORTS,  # an association, not functional evidence
            species=HUMAN,
            context=f"{row.get('accession_id')}; effect alleles {row.get('snp_effect_allele')}",
            passage=f"Variant(s) {row.get('locations')} mapped to {row.get('mapped_genes')}",
            available_on=date.today(),
            license_ok=True,  # GWAS Catalog is open; check exceptions (SOURCE-10)
        )
