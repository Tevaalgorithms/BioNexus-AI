"""Composition root: the one place that wires every component. Read this to see the whole system."""

from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import UTC, date, datetime
from pathlib import Path

from langgraph.graph.state import CompiledStateGraph

from bionexus.agents.base import AgentDeps
from bionexus.agents.clinical import ClinicalAgent
from bionexus.agents.critic import CriticAgent
from bionexus.agents.genetics import GeneticsAgent
from bionexus.agents.literature import LiteratureAgent
from bionexus.agents.optimization import AO_RESPONSE_CACHE_ENTRIES
from bionexus.agents.pathways import PathwaysAgent
from bionexus.agents.planner import PlannerAgent
from bionexus.agents.skills import SkillRegistry
from bionexus.agents.supervisor import SupervisorAgent
from bionexus.agents.synthesizer import SynthesizerAgent
from bionexus.application.admin import AdminService
from bionexus.application.projects import ProjectService
from bionexus.application.services import InvestigationService
from bionexus.auth.policy import StaticTokenVerifier, TokenVerifier
from bionexus.config import Settings
from bionexus.contracts.identity import ClientKind, Principal, Role
from bionexus.contracts.investigation import InvestigationRequest
from bionexus.contracts.messages import AgentName
from bionexus.jobs.worker import Worker
from bionexus.llm.cache import ResponseCache
from bionexus.llm.clients import ModelClient
from bionexus.llm.factory import LazyClients
from bionexus.llm.gateway import ModelGateway
from bionexus.llm.models import AgentBinding, ConfigRelease
from bionexus.llm.registry import ModelRegistry, ModelSpec, load_specs, specs_from_json
from bionexus.llm.release import ReleaseStore
from bionexus.messaging.router import MessageRouter
from bionexus.params import parameters
from bionexus.reporting.builder import ReportBuilder
from bionexus.reporting.review import ReviewService
from bionexus.reporting.revision import RevisionService
from bionexus.retrieval.embedder import HashingEmbedder
from bionexus.retrieval.service import RetrievalService
from bionexus.sources.http import GuardedHttp
from bionexus.sources.live import live_sources
from bionexus.sources.registry import SourceRegistry
from bionexus.storage.in_memory import in_memory_storage
from bionexus.storage.ports import Storage
from bionexus.workflow.dispatcher import Dispatcher
from bionexus.workflow.events import EventPublisher
from bionexus.workflow.graph import build_graph
from bionexus.workflow.nodes import MAX_REPAIR_ROUNDS, InvestigationNodes
from bionexus.workflow.runner import RunExecutor

SKILL_VERSIONS = {
    "investigation.plan": "1.0.0",
    "genetics.assess": "1.0.0",
    "literature.assess": "1.0.0",
    "mechanism.context": "1.0.0",
    "trials.context": "1.0.0",
    "evidence.critique": "1.0.0",
    "report.synthesize": "1.0.0",
    "coverage.plan": "1.0.0",
    "conflict.analyse": "1.0.0",
    "claims.verify": "1.0.0",
}

FIXTURE_MODELS = [
    ModelSpec(
        model_id="fixture-small",
        provider="fixture",
        supports_structured_output=True,
        input_usd_per_million=0.5,
        output_usd_per_million=2.0,
    ),
    ModelSpec(
        model_id="fixture-large",
        provider="fixture",
        supports_structured_output=True,
        input_usd_per_million=3.0,
        output_usd_per_million=15.0,
    ),
]


def initial_release(
    default_model: str = "fixture-small", fallback: str | None = "fixture-large"
) -> ConfigRelease:
    binding = AgentBinding(model_id=default_model, fallback_model_id=fallback)
    return ConfigRelease(
        release_id="rel-1",
        revision=1,
        bindings={agent: binding for agent in AgentName},
        skill_versions=SKILL_VERSIONS,
        created_by="system",
        reason="initial release",
        parent_id=None,
        created_at=datetime.now(UTC),
    )


@dataclass
class Container:
    verifier: TokenVerifier
    investigations: InvestigationService
    admin: AdminService
    worker: Worker
    releases: ReleaseStore
    storage: Storage
    graph: CompiledStateGraph
    nodes: InvestigationNodes
    gateway: ModelGateway
    projects: ProjectService
    inline_worker: bool = True
    meta: Callable[[], dict] = field(default=dict)


def build_registry(storage: Storage, settings: Settings) -> ModelRegistry:
    """Catalogue lives in the database; the seed file and fixtures only fill in what is missing."""
    registry = ModelRegistry(storage.catalog)
    if not parameters().is_production():
        registry.seed(FIXTURE_MODELS)
    if settings.models_file:
        registry.seed(load_specs(Path(settings.models_file)))
    if settings.models_json:
        registry.seed(specs_from_json(settings.models_json))
    return registry


def default_release() -> ConfigRelease:
    """First-ever release. Production names its models in SSM; local development uses fixtures."""
    p = parameters()
    if p.is_production():
        return initial_release(
            p.require("BIONEXUS_DEFAULT_MODEL"), p.get("BIONEXUS_FALLBACK_MODEL")
        )
    return initial_release()


def build_sources(live: bool) -> SourceRegistry:
    return SourceRegistry(live_sources(GuardedHttp())) if live else SourceRegistry.from_fixtures()


def build_agents(deps: AgentDeps) -> tuple[SupervisorAgent, CriticAgent, SynthesizerAgent, dict]:
    supervisor, critic, synthesizer = (
        SupervisorAgent(deps),
        CriticAgent(deps),
        SynthesizerAgent(deps),
    )
    handlers = {
        AgentName.GENETICS: GeneticsAgent(deps),
        AgentName.LITERATURE: LiteratureAgent(deps),
        AgentName.PATHWAYS: PathwaysAgent(deps),
        AgentName.CLINICAL: ClinicalAgent(deps),
        AgentName.CRITIC: critic,
        AgentName.PLANNER: PlannerAgent(deps),
    }
    return supervisor, critic, synthesizer, handlers


def build_nodes(storage: Storage, deps: AgentDeps, releases: ReleaseStore) -> tuple:
    supervisor, critic, synthesizer, handlers = build_agents(deps)
    events = EventPublisher(storage.events)
    builder = ReportBuilder(releases, deps.skills, deps.sources)
    nodes = InvestigationNodes(
        supervisor=supervisor,
        critic=critic,
        synthesizer=synthesizer,
        dispatcher=Dispatcher(handlers, MessageRouter(), events),
        memory=storage.memory,
        builder=builder,
        reports=storage.reports,
        runs=storage.runs,
        events=events,
        retrieval=RetrievalService(storage.retrieval, HashingEmbedder()),
        audit=storage.audit,
    )
    revision = RevisionService(
        synthesizer=synthesizer,
        builder=builder,
        reports=storage.reports,
        runs=storage.runs,
        memory=storage.memory,
        audit=storage.audit,
    )
    return nodes, revision, events


def build_container(
    principals: dict[str, Principal] | None = None,
    settings: Settings | None = None,
    clients: dict[str, ModelClient] | None = None,
    storage: Storage | None = None,
    verifier: TokenVerifier | None = None,
    registry: ModelRegistry | None = None,
    sources: SourceRegistry | None = None,
    initial: ConfigRelease | None = None,
    disabled_steps: frozenset[str] = frozenset(),
) -> Container:
    settings_provider = (lambda: settings) if settings else Settings.current
    storage = storage or in_memory_storage(principals)
    registry = registry or build_registry(storage, settings_provider())
    clients = clients if clients is not None else LazyClients()
    releases = ReleaseStore(registry, storage.releases)
    releases.seed(initial or default_release())
    releases.ensure_complete(AgentName.SYNTHESIZER, SKILL_VERSIONS)  # agents added by an upgrade
    cache = ResponseCache(AO_RESPONSE_CACHE_ENTRIES)
    gateway = ModelGateway(registry, releases, clients, storage.flags, cache)
    sources = sources or build_sources(live=settings_provider().live_sources)
    skills = SkillRegistry()
    deps = AgentDeps(sources, gateway, skills, releases)
    nodes, revision, events = build_nodes(storage, deps, releases)
    graph = build_graph(nodes, storage.checkpointer, disabled_steps)
    executor = RunExecutor(graph, storage.runs, events)
    review = ReviewService(storage.reports, executor.resume_after_review)
    return Container(
        verifier=verifier or StaticTokenVerifier(principals or {}),
        investigations=InvestigationService(
            settings=settings_provider,
            runs=storage.runs,
            queue=storage.jobs,
            releases=releases,
            reports=storage.reports,
            review=review,
            revision=revision,
            events=storage.events,
        ),
        admin=AdminService(
            releases=releases,
            registry=registry,
            audit=storage.audit,
            runs=storage.runs,
            jobs=storage.jobs,
            flags=storage.flags,
            gateway=gateway,
            evaluator=make_evaluator(registry, clients),
            sources=sources,
            skills=skills,
        ),
        worker=Worker(storage.jobs, executor),
        releases=releases,
        storage=storage,
        graph=graph,
        nodes=nodes,
        gateway=gateway,
        projects=ProjectService(storage.projects, storage.users),
        inline_worker=settings_provider().inline_worker,
        meta=lambda: describe_mode(sources, registry, releases, settings_provider()),
    )


def describe_mode(
    sources: SourceRegistry, registry: ModelRegistry, releases: ReleaseStore, settings: Settings
) -> dict:
    """What the running system is actually using, so the UI can say so plainly."""
    providers = {
        registry.get_for_call(b.model_id).provider for b in releases.active().bindings.values()
    }
    live = any(row["mode"] == "live" for row in sources.describe())
    return {
        "data_mode": "live" if live else "demo",
        "demo_diseases": [] if live else sources.fixture_diseases(),
        "model_mode": "demo" if providers <= {"fixture"} else "live",
        "sources": [row["name"] for row in sources.describe()],
        "limits": {
            "run_budget_usd": settings.run_budget_usd,
            "run_warn_usd": settings.run_warn_usd,
            "max_repair_rounds": MAX_REPAIR_ROUNDS,
        },
    }


SANDBOX_USER = Principal(
    user_id="sandbox",
    role=Role.SCIENTIST,
    tenant_id="sandbox",
    project_ids=frozenset({"sandbox"}),
    client_kind=ClientKind.SCIENTIST,
)
SANDBOX_SETTINGS = Settings(run_budget_usd=0.5, run_max_model_calls=20)


def make_evaluator(registry: ModelRegistry, clients: dict[str, ModelClient]):
    """Runs a synthetic fixture investigation under a candidate release, in isolation (ADMIN-04)."""

    def evaluate(candidate: ConfigRelease) -> dict:
        sandbox = build_container(
            settings=SANDBOX_SETTINGS,
            clients=clients,
            registry=registry,
            sources=SourceRegistry.from_fixtures(),
            initial=candidate,
        )
        request = InvestigationRequest(
            disease="Crohn's disease",
            targets=("NOD2", "IL23R"),
            question="Safe fixture evaluation of a candidate configuration.",
            evidence_cutoff=date(2026, 1, 1),
        )
        run = sandbox.investigations.submit(SANDBOX_USER, "sandbox", request, "evaluation")
        sandbox.worker.run_pending()
        return summarise_evaluation(sandbox.investigations.get(SANDBOX_USER, run.run_id))

    return evaluate


def summarise_evaluation(state) -> dict:
    known = set(state.evidence)
    ungrounded = [c.claim_id for c in state.claims if not set(c.evidence_ids) <= known]
    return {
        "status": state.status.value,
        "stop_reason": state.stop_reason,
        "model_calls": len(state.invocations),
        "models_used": sorted({i.model_id for i in state.invocations}),
        "cost_usd": round(state.budget.spent_usd, 6),
        "grounding_warnings": ungrounded,
    }
