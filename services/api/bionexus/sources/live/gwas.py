"""GWAS Catalog: genome-wide association variants."""

from datetime import date

from bionexus.contracts.evidence import EvidenceRecord, Stance
from bionexus.contracts.hints import HintKind, SearchHint
from bionexus.sources.live.common import (
    HUMAN,
    LiveSource,
    disease_words,
    normalise,
)


class GwasCatalogSource(LiveSource):
    name = "gwas"
    URL = "https://www.ebi.ac.uk/gwas/rest/api/v2/associations"

    def search(
        self, disease: str, targets: tuple[str, ...], hint: SearchHint | None = None
    ) -> list[EvidenceRecord]:
        names = [disease, hint.text] if hint and hint.kind is HintKind.DISEASE else [disease]
        word_sets = [disease_words(name) for name in names]
        genes = [(g, g) for g in targets]
        if hint and hint.kind is HintKind.GENE:  # look the alias up, but report it as the target
            genes += [(hint.text, g) for g in targets]
        records: list[EvidenceRecord] = []
        for symbol, target in genes:
            payload = self._http.get_json(self.URL, {"mapped_gene": symbol, "size": 200})
            rows = payload.get("_embedded", {}).get("associations", [])
            records.extend(self._to_record(r, target) for r in rows if self._matches(r, word_sets))
        return records

    @staticmethod
    def _matches(row: dict, word_sets: list[list[str]]) -> bool:
        """A trait matches when every word of any one accepted name appears in it."""
        traits = [t["efo_trait"] for t in row.get("efo_traits", [])] + row.get("reported_trait", [])
        return any(
            all(w in normalise(trait) for w in words) for words in word_sets for trait in traits
        )

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
