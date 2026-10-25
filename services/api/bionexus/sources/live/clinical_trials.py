"""ClinicalTrials.gov: registered trials."""

from bionexus.contracts.evidence import EvidenceRecord, Stance
from bionexus.contracts.hints import HintKind, SearchHint
from bionexus.sources.live.common import HUMAN, LiveSource, parse_date, plain


class ClinicalTrialsSource(LiveSource):
    name = "clinicaltrials"
    URL = "https://clinicaltrials.gov/api/v2/studies"

    def search(
        self, disease: str, targets: tuple[str, ...], hint: SearchHint | None = None
    ) -> list[EvidenceRecord]:
        records: list[EvidenceRecord] = []
        for target in targets:
            params = self._params(disease, target, hint)
            studies = self._http.get_json(self.URL, params).get("studies", [])
            records.extend(self._to_record(study, target) for study in studies)
        return records

    @staticmethod
    def _params(disease: str, target: str, hint: SearchHint | None) -> dict[str, object]:
        """The plain query, widened by a hint: an alternative name, or an extra qualifier."""
        condition, term = disease, target
        if hint and hint.kind is HintKind.DISEASE:
            condition = f'"{disease}" OR "{hint.text}"'
        if hint and hint.kind is HintKind.GENE:
            term = f'"{target}" OR "{hint.text}"'
        if hint and hint.kind is HintKind.CONTEXT:
            term = f'{target} AND "{hint.text}"'
        return {"query.cond": condition, "query.term": term, "pageSize": 10}

    @staticmethod
    def _to_record(study: dict, target: str) -> EvidenceRecord:
        protocol = study["protocolSection"]
        ident, status = protocol["identificationModule"], protocol["statusModule"]
        results = "results posted" if study.get("hasResults") else "no posted results"
        return EvidenceRecord(
            source="clinicaltrials",
            source_id=ident["nctId"],
            study_family=ident["nctId"],
            target=target,
            finding=plain(ident.get("briefTitle")),
            stance=Stance.UNKNOWN,  # registration is not evidence of efficacy
            species=HUMAN,
            context=f"{status.get('overallStatus', 'UNKNOWN')}; {results}",
            passage=plain(protocol.get("descriptionModule", {}).get("briefSummary")),
            available_on=parse_date(status.get("studyFirstSubmitDate")),
            license_ok=True,
        )
