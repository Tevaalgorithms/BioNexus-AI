"""Europe PMC: published literature."""

from bionexus.contracts.evidence import EvidenceRecord, Stance
from bionexus.contracts.hints import HintKind, SearchHint
from bionexus.sources.live.common import HUMAN, LiveSource, parse_date, plain


def _any_of(terms: list[str]) -> str:
    quoted = [f'"{t}"' for t in terms]
    return quoted[0] if len(quoted) == 1 else "(" + " OR ".join(quoted) + ")"


class EuropePmcSource(LiveSource):
    name = "europe_pmc"
    URL = "https://www.ebi.ac.uk/europepmc/webservices/rest/search"

    def search(
        self, disease: str, targets: tuple[str, ...], hint: SearchHint | None = None
    ) -> list[EvidenceRecord]:
        records: list[EvidenceRecord] = []
        for target in targets:
            query = self._query(disease, target, hint)
            params = {"query": query, "format": "json", "resultType": "core", "pageSize": 10}
            payload = self._http.get_json(self.URL, params)
            results = payload.get("resultList", {}).get("result", [])
            records.extend(self._to_record(row, target) for row in results)
        return records

    @staticmethod
    def _query(disease: str, target: str, hint: SearchHint | None) -> str:
        """No hint: the plain query. A hint adds an alternative name or a qualifier."""
        genes, diseases = [target], [disease]
        if hint and hint.kind is HintKind.GENE:
            genes.append(hint.text)
        if hint and hint.kind is HintKind.DISEASE:
            diseases.append(hint.text)
        query = f"{_any_of(genes)} AND {_any_of(diseases)} AND HAS_ABSTRACT:Y"
        if hint and hint.kind is HintKind.CONTEXT:
            query += f' AND "{hint.text}"'
        return query

    @staticmethod
    def _to_record(row: dict, target: str) -> EvidenceRecord:
        pmid = row.get("pmid") or row["id"]
        return EvidenceRecord(
            source="europe_pmc",
            source_id=str(pmid),
            study_family=f"PMID:{pmid}",
            target=target,
            finding=plain(row.get("title")),
            stance=Stance.UNKNOWN,
            species=HUMAN,
            context=plain(row.get("journalTitle")) or "literature",
            passage=plain(row.get("abstractText")),
            available_on=parse_date(row.get("firstPublicationDate")),
            # Conservative item-level rights decision: only open-access articles are reusable.
            license_ok=row.get("isOpenAccess") == "Y",
        )

    def passage_for(self, source_id: str) -> str | None:
        params = {"query": f"EXT_ID:{source_id}", "format": "json", "resultType": "core"}
        results = self._http.get_json(self.URL, params).get("resultList", {}).get("result", [])
        return plain(results[0].get("abstractText")) if results else None
