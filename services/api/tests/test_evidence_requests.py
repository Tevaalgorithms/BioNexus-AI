"""`evidence.request`: one agent asks a specialist to search again with a validated hint."""

from datetime import date
from types import SimpleNamespace

import httpx
import pytest

from bionexus.agents.base import AgentResult
from bionexus.agents.genetics import GeneticsAgent
from bionexus.agents.literature import LiteratureAgent
from bionexus.contracts.errors import RouteRejected, SourceUnavailable
from bionexus.contracts.evidence import EvidenceRecord, Stance
from bionexus.contracts.hints import HintKind, SearchHint, clean_hint
from bionexus.contracts.messages import AgentName, MessageType
from bionexus.messaging.envelope import new_message
from bionexus.messaging.router import MAX_MESSAGES_PER_RUN, MessageRouter, exchanges_available
from bionexus.sources.http import GuardedHttp
from bionexus.sources.live.clinical_trials import ClinicalTrialsSource
from bionexus.sources.live.europe_pmc import EuropePmcSource
from bionexus.sources.live.gwas import GwasCatalogSource
from bionexus.workflow.budget import Budget
from bionexus.workflow.state import RunState


def http_with(handler) -> GuardedHttp:
    return GuardedHttp(transport=httpx.MockTransport(handler), sleep=lambda _: None)


# ---- a hint is untrusted model output ------------------------------------------------------


@pytest.mark.parametrize(
    ("kind", "text"),
    [
        ("disease", "Crohn's"),
        ("gene", "CARD15"),
        ("context", "East Asian ancestry"),
        ("disease", "  inflammatory   bowel disease  "),
    ],
)
def test_a_plain_phrase_is_a_valid_hint(kind, text):
    hint = clean_hint(kind, text)
    assert hint is not None and hint.text == " ".join(text.split())


@pytest.mark.parametrize(
    ("kind", "text"),
    [
        ("disease", 'x" OR "y'),  # a quote could rewrite the query
        ("gene", "NOD2; DROP TABLE"),
        ("gene", "a"),  # too short
        ("context", "x" * 61),  # too long
        ("shell", "ok phrase"),  # not a known kind
        ("gene", None),
        (None, "CARD15"),
        ("gene", "<script>"),
    ],
)
def test_anything_else_is_dropped(kind, text):
    assert clean_hint(kind, text) is None


# ---- sources use a hint only to widen a search ---------------------------------------------


def test_europe_pmc_without_a_hint_sends_the_plain_query():
    seen = []

    def handler(request):
        seen.append(request.url.params["query"])
        return httpx.Response(200, json={"resultList": {"result": []}})

    EuropePmcSource(http_with(handler)).search("Crohn disease", ("NOD2",))
    assert seen == ['"NOD2" AND "Crohn disease" AND HAS_ABSTRACT:Y']


@pytest.mark.parametrize(
    ("hint", "expected"),
    [
        (
            SearchHint(kind=HintKind.DISEASE, text="Crohn's"),
            '"NOD2" AND ("Crohn disease" OR "Crohn\'s") AND HAS_ABSTRACT:Y',
        ),
        (
            SearchHint(kind=HintKind.GENE, text="CARD15"),
            '("NOD2" OR "CARD15") AND "Crohn disease" AND HAS_ABSTRACT:Y',
        ),
        (
            SearchHint(kind=HintKind.CONTEXT, text="East Asian"),
            '"NOD2" AND "Crohn disease" AND HAS_ABSTRACT:Y AND "East Asian"',
        ),
    ],
)
def test_europe_pmc_widens_its_query_with_a_hint(hint, expected):
    seen = []

    def handler(request):
        seen.append(request.url.params["query"])
        return httpx.Response(200, json={"resultList": {"result": []}})

    EuropePmcSource(http_with(handler)).search("Crohn disease", ("NOD2",), hint)
    assert seen == [expected]


def test_clinical_trials_widens_the_condition_or_the_term():
    seen = []

    def handler(request):
        seen.append(dict(request.url.params))
        return httpx.Response(200, json={"studies": []})

    source = ClinicalTrialsSource(http_with(handler))
    source.search("Crohn disease", ("NOD2",))
    source.search("Crohn disease", ("NOD2",), SearchHint(kind=HintKind.DISEASE, text="ileitis"))
    source.search("Crohn disease", ("NOD2",), SearchHint(kind=HintKind.GENE, text="CARD15"))
    assert seen[0]["query.cond"] == "Crohn disease" and seen[0]["query.term"] == "NOD2"
    assert seen[1]["query.cond"] == '"Crohn disease" OR "ileitis"'
    assert seen[2]["query.term"] == '"NOD2" OR "CARD15"'


def gwas_row(n: int, trait: str) -> dict:
    return {
        "association_id": n,
        "accession_id": f"GCST{n}",
        "pubmed_id": str(n),
        "p_value": 1e-9,
        "efo_traits": [{"efo_trait": trait}],
        "reported_trait": [trait],
    }


def test_gwas_accepts_a_disease_synonym_and_looks_up_a_gene_alias():
    asked = []

    def handler(request):
        asked.append(request.url.params["mapped_gene"])
        return httpx.Response(
            200, json={"_embedded": {"associations": [gwas_row(1, "inflammatory bowel disease")]}}
        )

    source = GwasCatalogSource(http_with(handler))
    assert source.search("Crohn disease", ("NOD2",)) == []  # the trait is not named "Crohn"
    synonym = SearchHint(kind=HintKind.DISEASE, text="inflammatory bowel disease")
    assert [r.target for r in source.search("Crohn disease", ("NOD2",), synonym)] == ["NOD2"]
    asked.clear()
    alias = SearchHint(kind=HintKind.GENE, text="CARD15")
    source.search("inflammatory bowel disease", ("NOD2",), alias)
    assert asked == ["NOD2", "CARD15"]  # the alias is looked up, and reported as NOD2


# ---- a specialist answers a request without a model ----------------------------------------


def paper(n: int, stance: Stance = Stance.SUPPORTS) -> EvidenceRecord:
    return EvidenceRecord(
        source="europe_pmc",
        source_id=f"P{n}",
        study_family=f"fam-{n}",
        target="NOD2",
        finding="NOD2 and Crohn's disease",
        stance=stance,
        species="human",
        context="context",
        passage="passage",
        available_on=date(2020, 1, 1),
        license_ok=True,
    )


@pytest.fixture
def state(request_):
    return RunState(
        run_id="r",
        tenant_id="t",
        project_id="p",
        created_by="u",
        request=request_,
        release_id="rel-1",
        budget=Budget(max_cost_usd=1, max_calls=50),
    )


def request_message(state, **payload):
    return new_message(
        run_id=state.run_id,
        sender=AgentName.PLANNER,
        recipient=AgentName.GENETICS,
        kind=MessageType.EVIDENCE_REQUEST,
        payload=payload,
    )


class HintAwareSource:
    """Returns one extra paper only when it is asked with the alias hint."""

    name = "europe_pmc"

    def __init__(self):
        self.hints = []

    def search(self, disease, targets, hint=None):
        self.hints.append(hint)
        return [paper(1), *([paper(2)] if hint else [])]


def specialist(cls, source) -> object:
    agent = cls(SimpleNamespace(sources=SimpleNamespace(get=lambda n: source), gateway=None))
    agent.source_names = ("europe_pmc",)
    return agent


def test_a_request_returns_only_evidence_the_run_does_not_have(state):
    source = HintAwareSource()
    state.add_evidence([paper(1)])
    result = specialist(GeneticsAgent, source).handle(
        request_message(state, kind="gene", text="CARD15"), state
    )
    assert [r.evidence_id for r in result.evidence] == ["europe_pmc:P2"]
    assert source.hints == [SearchHint(kind=HintKind.GENE, text="CARD15")]


def test_a_request_with_an_invalid_hint_makes_no_search(state):
    source = HintAwareSource()
    result = specialist(GeneticsAgent, source).handle(
        request_message(state, kind="gene", text='x" OR "y'), state
    )
    assert result.abstained and source.hints == []


def test_a_failing_source_does_not_end_the_run(state):
    class Down:
        def search(self, disease, targets, hint=None):
            raise SourceUnavailable("down")

    result = specialist(GeneticsAgent, Down()).handle(
        request_message(state, kind="gene", text="CARD15"), state
    )
    assert result.abstained and result.evidence == []


def test_literature_reads_the_direction_of_papers_found_with_a_hint(state):
    class Gateway:
        def __init__(self):
            self.calls = 0

        def complete(self, state, agent, prompt):
            self.calls += 1
            return "opposes"

    gateway = Gateway()
    source = SimpleNamespace(search=lambda d, t, hint=None: [paper(5, Stance.UNKNOWN)])
    agent = LiteratureAgent(
        SimpleNamespace(sources=SimpleNamespace(get=lambda n: source), gateway=gateway)
    )
    agent.instructions = lambda s, skill_id=None: "skill"
    result = agent.handle(request_message(state, kind="context", text="East Asian"), state)
    assert [r.stance for r in result.evidence] == [Stance.OPPOSES] and gateway.calls == 1
    assert isinstance(result, AgentResult)


# ---- the router ----------------------------------------------------------------------------


def test_the_planner_may_ask_a_specialist_but_not_the_critic(state):
    router = MessageRouter()
    ok = request_message(state, kind="gene", text="CARD15")
    assert router.accept(state, ok)
    wrong = new_message(
        run_id=state.run_id,
        sender=AgentName.PLANNER,
        recipient=AgentName.CRITIC,
        kind=MessageType.EVIDENCE_REQUEST,
        payload={"kind": "gene", "text": "CARD15"},
    )
    with pytest.raises(RouteRejected):
        router.accept(state, wrong)


def test_exchanges_available_keeps_a_reserve(state):
    assert exchanges_available(state, reserve=4) == (MAX_MESSAGES_PER_RUN - 4) // 2
    state.messages.extend([request_message(state, n=i) for i in range(MAX_MESSAGES_PER_RUN)])
    assert exchanges_available(state, reserve=4) == 0
