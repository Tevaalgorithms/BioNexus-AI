"""Europe PMC: published literature."""

from bionexus.contracts.evidence import EvidenceRecord, Stance
from bionexus.sources.live.common import HUMAN, LiveSource, parse_date, plain


class EuropePmcSource(LiveSource):
    name = "europe_pmc"
    URL = "https://www.ebi.ac.uk/europepmc/webservices/rest/search"

    def search(self, disease: str, targets: tuple[str, ...]) -> list[EvidenceRecord]:
        records: list[EvidenceRecord] = []
        for target in targets:
            query = f'"{target}" AND "{disease}" AND HAS_ABSTRACT:Y'
            params = {"query": query, "format": "json", "resultType": "core", "pageSize": 10}
            payload = self._http.get_json(self.URL, params)
            results = payload.get("resultList", {}).get("result", [])
            records.extend(self._to_record(row, target) for row in results)
        return records

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
