import httpx
import pytest

from bionexus.contracts.errors import SourceUnavailable
from bionexus.contracts.evidence import Stance
from bionexus.sources.http import GuardedHttp
from bionexus.sources.live import (
    ClinicalTrialsSource,
    EuropePmcSource,
    GwasCatalogSource,
    MonarchSource,
    OpenTargetsSource,
    ReactomeSource,
    parse_date,
)


def http_with(handler) -> GuardedHttp:
    return GuardedHttp(transport=httpx.MockTransport(handler), sleep=lambda _: None)


def test_europe_pmc_maps_open_access_and_family():
    payload = {
        "resultList": {
            "result": [
                {
                    "id": "1",
                    "pmid": "111",
                    "title": "<b>NOD2</b> study",
                    "abstractText": "Text",
                    "isOpenAccess": "Y",
                    "firstPublicationDate": "2020-05-01",
                },
                {
                    "id": "2",
                    "pmid": "222",
                    "title": "Closed",
                    "abstractText": "X",
                    "isOpenAccess": "N",
                    "firstPublicationDate": "2021",
                },
            ]
        }
    }
    source = EuropePmcSource(http_with(lambda r: httpx.Response(200, json=payload)))
    open_, closed = source.search("Crohn disease", ("NOD2",))
    assert open_.study_family == "PMID:111" and open_.license_ok and open_.finding == "NOD2 study"
    assert not closed.license_ok and str(closed.available_on) == "2021-01-01"
    assert open_.stance is Stance.UNKNOWN


def test_clinical_trials_never_infers_efficacy():
    payload = {
        "studies": [
            {
                "hasResults": False,
                "protocolSection": {
                    "identificationModule": {"nctId": "NCT1", "briefTitle": "Trial"},
                    "statusModule": {
                        "overallStatus": "RECRUITING",
                        "studyFirstSubmitDate": "2025-09-17",
                    },
                    "descriptionModule": {"briefSummary": "Summary"},
                },
            }
        ]
    }
    record = ClinicalTrialsSource(http_with(lambda r: httpx.Response(200, json=payload))).search(
        "Crohn disease", ("IL23R",)
    )[0]
    assert record.stance is Stance.UNKNOWN and "no posted results" in record.context


def test_reactome_annotation_is_not_a_demonstrated_mechanism():
    payload = {
        "results": [
            {
                "entries": [
                    {
                        "stId": "R-HSA-1",
                        "name": "NOD1/2 Signaling",
                        "summation": "text <span>NOD2</span>",
                    }
                ]
            }
        ]
    }
    record = ReactomeSource(http_with(lambda r: httpx.Response(200, json=payload))).search(
        "Crohn disease", ("NOD2",)
    )[0]
    assert record.stance is Stance.UNKNOWN and record.passage == "text NOD2"


def test_monarch_resolves_exact_gene_symbol_first():
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith("/search"):
            return httpx.Response(
                200,
                json={
                    "items": [
                        {"id": "HGNC:1", "name": "NOD22"},
                        {"id": "HGNC:5331", "name": "NOD2"},
                    ]
                },
            )
        assert request.url.params["subject"] == "HGNC:5331"
        return httpx.Response(
            200, json={"items": [{"id": "uuid:1", "object": "HP:1", "object_label": "Diarrhea"}]}
        )

    records = MonarchSource(http_with(handler)).search("Crohn disease", ("NOD2",))
    assert [r.source_id for r in records] == ["uuid:1"]


def test_open_targets_score_is_not_presented_as_probability():
    def handler(request: httpx.Request) -> httpx.Response:
        body = request.read().decode()
        if "associatedTargets" in body:
            return httpx.Response(
                200,
                json={
                    "data": {
                        "disease": {
                            "name": "CD",
                            "associatedTargets": {
                                "rows": [
                                    {
                                        "target": {"id": "ENSG1", "approvedSymbol": "NOD2"},
                                        "score": 0.77,
                                        "datatypeScores": [
                                            {"id": "genetic_association", "score": 0.9}
                                        ],
                                    }
                                ]
                            },
                        }
                    }
                },
            )
        return httpx.Response(
            200, json={"data": {"search": {"hits": [{"id": "X_1", "name": "n"}]}}}
        )

    record = OpenTargetsSource(http_with(handler)).search("Crohn disease", ("NOD2",))[0]
    assert "not a probability" in record.finding and record.stance is Stance.SUPPORTS


def test_gwas_filters_by_disease_and_shares_family_with_literature():
    rows = [
        {
            "association_id": 1,
            "accession_id": "GCST1",
            "pubmed_id": "111",
            "p_value": 1e-9,
            "efo_traits": [{"efo_trait": "Crohn's disease"}],
            "reported_trait": ["Crohn's disease"],
        },
        {
            "association_id": 2,
            "accession_id": "GCST2",
            "pubmed_id": "222",
            "efo_traits": [{"efo_trait": "height"}],
            "reported_trait": ["Height"],
        },
    ]
    source = GwasCatalogSource(
        http_with(lambda r: httpx.Response(200, json={"_embedded": {"associations": rows}}))
    )
    records = source.search("Crohn disease", ("NOD2",))
    assert [r.study_family for r in records] == ["PMID:111"]


def test_disallowed_host_and_plain_http_are_refused():
    guard = http_with(lambda r: httpx.Response(200, json={}))
    with pytest.raises(SourceUnavailable):
        guard.get_json("https://evil.example.com/x")
    with pytest.raises(SourceUnavailable):
        guard.get_json("http://reactome.org/x")


def test_transient_errors_are_retried_then_succeed_or_fail_cleanly():
    calls = []

    def flaky(request):
        calls.append(1)
        return httpx.Response(503) if len(calls) < 3 else httpx.Response(200, json={"ok": 1})

    assert http_with(flaky).get_json("https://reactome.org/x") == {"ok": 1}
    always_down = http_with(lambda r: httpx.Response(503))
    with pytest.raises(SourceUnavailable):
        always_down.get_json("https://reactome.org/x")


def test_client_errors_are_not_retried_and_oversize_is_refused():
    calls = []

    def not_found(request):
        calls.append(1)
        return httpx.Response(404)

    with pytest.raises(SourceUnavailable):
        http_with(not_found).get_json("https://reactome.org/x")
    assert len(calls) == 1
    big = http_with(lambda r: httpx.Response(200, content=b'{"a":"' + b"x" * 2_100_000 + b'"}'))
    with pytest.raises(SourceUnavailable):
        big.get_json("https://reactome.org/x")


def test_partial_dates_resolve_to_first_day():
    assert str(parse_date("2020")) == "2020-01-01"
    assert str(parse_date("2020-03")) == "2020-03-01"


def test_disease_matching_needs_every_meaningful_word_not_just_the_first():
    from bionexus.sources.live import disease_words, normalise

    assert disease_words("Type 2 diabetes") == ["type", "2", "diabetes"]
    assert disease_words("Crohn's disease") == ["crohn"]
    assert normalise("Crohn’s Disease") == "crohn disease"
    rows = [
        {
            "association_id": 1,
            "accession_id": "G1",
            "pubmed_id": "1",
            "efo_traits": [{"efo_trait": "type 2 diabetes mellitus"}],
            "reported_trait": [],
        },
        {
            "association_id": 2,
            "accession_id": "G2",
            "pubmed_id": "2",
            "efo_traits": [{"efo_trait": "type 1 diabetes"}],
            "reported_trait": [],
        },
    ]
    source = GwasCatalogSource(
        http_with(lambda r: httpx.Response(200, json={"_embedded": {"associations": rows}}))
    )
    assert [r.source_id for r in source.search("Type 2 diabetes", ("TCF7L2",))] == ["1"]
    assert source.search("Alzheimer's disease", ("APOE",)) == []


def test_meta_endpoint_reports_demo_mode_and_covered_diseases(container):
    meta = container.meta()
    assert meta["data_mode"] == "demo" and "crohn's disease" in meta["demo_diseases"]
    assert meta["model_mode"] == "demo"
