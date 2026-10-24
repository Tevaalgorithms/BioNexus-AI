"""Live adapters. Each is a named BioNexus adapter (not an official MCP) returning EvidenceRecords.

Direction is never inferred by guesswork: where a source gives no direction the record is
`unknown`, and only an explicit literature extraction step may change that.
"""

import re
from datetime import date

from bionexus.contracts.evidence import EvidenceRecord, Stance
from bionexus.sources.http import GuardedHttp

MAX_PASSAGE_CHARS = 1500
HUMAN = "human"
TAG = re.compile(r"<[^>]+>")


def plain(text: str | None) -> str:
    return TAG.sub("", text or "").strip()[:MAX_PASSAGE_CHARS]


STOP_WORDS = frozenset({"disease", "syndrome", "disorder", "the", "of"})


def normalise(text: str) -> str:
    """Lower-case and drop possessives so "Crohn's disease" matches "Crohn disease"."""
    return re.sub(r"['’]s\b", "", text.lower())


def disease_words(disease: str) -> list[str]:
    """Every meaningful word of the disease name must appear in a trait (not just the first)."""
    words = [w for w in normalise(disease).split() if w not in STOP_WORDS]
    return words or normalise(disease).split()


def parse_date(value: str | None, fallback: date | None = None) -> date:
    """Accepts YYYY, YYYY-MM or YYYY-MM-DD; partial dates resolve to their first day."""
    parts = (value or "").split("-")
    try:
        numbers = [int(p) for p in parts[:3]] + [1] * (3 - len(parts))
        return date(*numbers[:3])
    except ValueError:
        return fallback or date.today()


class LiveSource:
    name: str

    def __init__(self, http: GuardedHttp) -> None:
        self._http = http

    def snapshot_id(self) -> str:
        return "live-api"

    def passage_for(self, source_id: str) -> str | None:
        return None


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


class ClinicalTrialsSource(LiveSource):
    name = "clinicaltrials"
    URL = "https://clinicaltrials.gov/api/v2/studies"

    def search(self, disease: str, targets: tuple[str, ...]) -> list[EvidenceRecord]:
        records: list[EvidenceRecord] = []
        for target in targets:
            params = {"query.cond": disease, "query.term": target, "pageSize": 10}
            studies = self._http.get_json(self.URL, params).get("studies", [])
            records.extend(self._to_record(study, target) for study in studies)
        return records

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


class ReactomeSource(LiveSource):
    name = "reactome"
    URL = "https://reactome.org/ContentService/search/query"

    def search(self, disease: str, targets: tuple[str, ...]) -> list[EvidenceRecord]:
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


class MonarchSource(LiveSource):
    name = "monarch"
    BASE = "https://api-v3.monarchinitiative.org/v3/api"

    def search(self, disease: str, targets: tuple[str, ...]) -> list[EvidenceRecord]:
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


class OpenTargetsSource(LiveSource):
    name = "open_targets"
    URL = "https://api.platform.opentargets.org/api/v4/graphql"
    LOOKUP = (
        "query($q:String!,$kind:[String!]){search(queryString:$q,entityNames:$kind,"
        "page:{index:0,size:1}){hits{id name}}}"
    )
    ASSOC = (
        "query($d:String!,$t:[String!]!){disease(efoId:$d){name associatedTargets(Bs:$t)"
        "{rows{target{id approvedSymbol} score datatypeScores{id score}}}}}"
    )

    def search(self, disease: str, targets: tuple[str, ...]) -> list[EvidenceRecord]:
        disease_hit = self._first_hit(disease, "disease")
        if disease_hit is None:
            return []
        records: list[EvidenceRecord] = []
        for target in targets:
            hit = self._first_hit(target, "target")
            records.extend(self._association(disease_hit, hit, target) if hit else [])
        return records

    def _first_hit(self, query: str, kind: str) -> dict | None:
        body = {"query": self.LOOKUP, "variables": {"q": query, "kind": [kind]}}
        hits = self._http.post_json(self.URL, body)["data"]["search"]["hits"]
        return hits[0] if hits else None

    def _association(self, disease: dict, hit: dict, target: str) -> list[EvidenceRecord]:
        body = {"query": self.ASSOC, "variables": {"d": disease["id"], "t": [hit["id"]]}}
        data = self._http.post_json(self.URL, body)["data"]["disease"]
        rows = data["associatedTargets"]["rows"] if data else []
        return [self._to_record(row, disease, target) for row in rows]

    @staticmethod
    def _to_record(row: dict, disease: dict, target: str) -> EvidenceRecord:
        genetic = next(
            (d["score"] for d in row["datatypeScores"] if d["id"] == "genetic_association"), 0
        )
        family = f"OPENTARGETS:{row['target']['id']}:{disease['id']}"
        return EvidenceRecord(
            source="open_targets",
            source_id=f"{row['target']['id']}-{disease['id']}",
            study_family=family,
            target=target,
            finding=(
                f"Open Targets association score {row['score']:.2f} "
                f"(genetic_association {genetic:.2f}); a ranking aid, not a probability"
            ),
            stance=Stance.SUPPORTS if genetic > 0 else Stance.UNKNOWN,
            species=HUMAN,
            context="aggregated platform association",
            passage=f"Datatype scores: {row['datatypeScores']}",
            available_on=date.today(),
            license_ok=True,  # CC0 per Open Targets terms; verify at release (SOURCE-10)
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


def live_sources(http: GuardedHttp) -> list[LiveSource]:
    return [
        OpenTargetsSource(http),
        GwasCatalogSource(http),
        EuropePmcSource(http),
        ReactomeSource(http),
        MonarchSource(http),
        ClinicalTrialsSource(http),
    ]
