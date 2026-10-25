"""Open Targets: genetic association scores."""

from datetime import date

from bionexus.contracts.evidence import EvidenceRecord, Stance
from bionexus.contracts.hints import SearchHint
from bionexus.sources.live.common import (
    HUMAN,
    LiveSource,
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

    def search(
        self, disease: str, targets: tuple[str, ...], hint: SearchHint | None = None
    ) -> list[EvidenceRecord]:
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
