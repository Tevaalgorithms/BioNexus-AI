"""Platform-admin services: model registry, safe configuration change, usage, health, stop."""

from collections import defaultdict
from collections.abc import Callable
from dataclasses import dataclass

from bionexus.agents.skills import SkillRegistry
from bionexus.auth.policy import require_admin
from bionexus.contracts.errors import InvalidRequest
from bionexus.contracts.identity import Principal
from bionexus.contracts.messages import AgentName
from bionexus.llm.clients import ProviderError
from bionexus.llm.gateway import MODELS_DISABLED, ModelGateway
from bionexus.llm.models import AgentBinding, ConfigRelease
from bionexus.llm.registry import ModelRegistry, ModelSpec, ModelStatus, model_problems
from bionexus.llm.release import ReleaseStore
from bionexus.llm.secrets import secret_is_configured
from bionexus.params import parameters
from bionexus.sources.registry import SourceRegistry
from bionexus.storage.ports import AuditStore, FlagStore, JobStore, RunStore

STRUCTURED_OUTPUT_AGENTS = frozenset(
    {AgentName.SUPERVISOR, AgentName.CRITIC, AgentName.SYNTHESIZER}
)


@dataclass(frozen=True)
class Validation:
    valid: bool
    problems: list[str]
    changes: dict[str, str]


class AdminService:
    def __init__(
        self,
        *,
        releases: ReleaseStore,
        registry: ModelRegistry,
        audit: AuditStore,
        runs: RunStore,
        jobs: JobStore,
        flags: FlagStore,
        gateway: ModelGateway,
        evaluator: Callable[[ConfigRelease], dict],
        sources: SourceRegistry,
        skills: SkillRegistry,
    ) -> None:
        self._releases = releases
        self._registry = registry
        self._audit = audit
        self._runs = runs
        self._jobs = jobs
        self._flags = flags
        self._gateway = gateway
        self._evaluator = evaluator
        self._sources = sources
        self._skills = skills

    def active_release(self, principal: Principal) -> ConfigRelease:
        require_admin(principal)
        return self._releases.active()

    def release_history(self, principal: Principal) -> list[ConfigRelease]:
        require_admin(principal)
        return self._releases.history()

    def models(self, principal: Principal) -> list[dict]:
        require_admin(principal)
        return [self._model_row(spec) for spec in self._registry.all()]

    @staticmethod
    def _model_row(spec: ModelSpec) -> dict:
        row = spec.model_dump()
        configured = spec.api_key_secret is None or secret_is_configured(spec.api_key_secret)
        row["credential_status"] = "configured" if configured else "missing"  # never the value
        return row

    def register_model(self, principal: Principal, spec: ModelSpec) -> ModelSpec:
        """Add a model at runtime: validated, smoke-tested, then active. No restart or deploy."""
        require_admin(principal)
        problems = model_problems(spec, parameters().is_production())
        if problems:
            raise InvalidRequest("; ".join(problems))
        self._require_smoke_test(spec)
        stored = spec.model_copy(
            update={"created_by": principal.user_id, "status": ModelStatus.ACTIVE}
        )
        self._registry.add(stored)
        self._audit.record(principal.user_id, "model.registered", spec.model_id)
        return stored

    def _require_smoke_test(self, spec: ModelSpec) -> None:
        try:
            answered = self._gateway.smoke_test_spec(spec)["ok"]
        except ProviderError as error:
            raise InvalidRequest(f"{spec.model_id} failed its smoke test: {error}") from error
        if not answered:
            raise InvalidRequest(f"{spec.model_id} did not answer the smoke test")

    def set_model_status(
        self, principal: Principal, model_id: str, status: ModelStatus, reason: str
    ) -> ModelSpec:
        require_admin(principal)
        if not reason.strip():
            raise InvalidRequest("A reason is required")
        updated = self._registry.set_status(model_id, status)
        self._audit.record(principal.user_id, f"model.{status}", f"{model_id} ({reason})")
        return updated

    def validate_binding(
        self, principal: Principal, agent: AgentName, binding: AgentBinding
    ) -> Validation:
        require_admin(principal)
        problems = self._capability_problems(agent, binding)
        current = self._releases.active().bindings[agent]
        changes = {
            field: f"{getattr(current, field)} -> {getattr(binding, field)}"
            for field in AgentBinding.model_fields
            if getattr(current, field) != getattr(binding, field)
        }
        return Validation(not problems, problems, changes)

    def _capability_problems(self, agent: AgentName, binding: AgentBinding) -> list[str]:
        problems = []
        for model_id in binding.model_chain():
            try:
                spec = self._registry.get(model_id)
            except Exception:
                problems.append(f"{model_id} is not in the approved registry")
                continue
            if agent in STRUCTURED_OUTPUT_AGENTS and not spec.supports_structured_output:
                problems.append(f"{model_id} lacks structured-output support required by {agent}")
        return problems

    def rebind_agent(
        self,
        principal: Principal,
        agent: AgentName,
        binding: AgentBinding,
        reason: str,
        expected_revision: int,
    ) -> ConfigRelease:
        require_admin(principal)
        validation = self.validate_binding(principal, agent, binding)
        if not validation.valid:
            raise InvalidRequest("; ".join(validation.problems))
        release = self._releases.rebind_agent(
            agent,
            binding,
            actor=principal.user_id,
            reason=reason,
            expected_revision=expected_revision,
        )
        self._audit.record(
            principal.user_id, "config.rebind", f"{agent}->{binding.model_id} ({reason})"
        )
        return release

    def evaluate_binding(
        self, principal: Principal, agent: AgentName, binding: AgentBinding, reason: str
    ) -> dict:
        """Run a safe fixture investigation under the candidate configuration (ADMIN-04)."""
        require_admin(principal)
        validation = self.validate_binding(principal, agent, binding)
        if not validation.valid:
            raise InvalidRequest("; ".join(validation.problems))
        candidate = self._releases.derive(agent, binding, actor=principal.user_id, reason=reason)
        result = self._evaluator(candidate)
        self._audit.record(principal.user_id, "config.evaluate", f"{agent}->{binding.model_id}")
        return result

    def rollback(self, principal: Principal, release_id: str, reason: str) -> ConfigRelease:
        """Rollback is a *new* release copying an old one, so history stays append-only."""
        require_admin(principal)
        target = self._releases.get(release_id)
        current = self._releases.active()
        restored = self._releases.republish(
            target,
            actor=principal.user_id,
            reason=f"rollback to {release_id}: {reason}",
            expected_revision=current.revision,
        )
        self._audit.record(principal.user_id, "config.rollback", f"{release_id} ({reason})")
        return restored

    def usage(self, principal: Principal) -> dict:
        require_admin(principal)
        by_model: dict[str, float] = defaultdict(float)
        by_agent: dict[str, float] = defaultdict(float)
        total = 0.0
        for run in self._runs.list_all():
            for call in run.invocations:
                by_model[call.model_id] += call.cost_usd
                by_agent[call.agent.value] += call.cost_usd
                total += call.cost_usd
        return {
            "total_usd": round(total, 6),
            "by_model": dict(by_model),
            "by_agent": dict(by_agent),
        }

    def health(self, principal: Principal) -> dict:
        require_admin(principal)
        runs = self._runs.list_all()
        counts: dict[str, int] = defaultdict(int)
        for run in runs:
            counts[run.status.value] += 1
        return {
            "queue_depth": self._jobs.depth(),
            "runs_by_status": dict(counts),
            "emergency_stop": self._flags.is_set(MODELS_DISABLED),
        }

    def set_emergency_stop(self, principal: Principal, enabled: bool, reason: str) -> bool:
        require_admin(principal)
        self._flags.set(MODELS_DISABLED, enabled)
        self._audit.record(principal.user_id, "emergency_stop", f"enabled={enabled}: {reason}")
        return enabled

    def smoke_test(self, principal: Principal, model_id: str) -> dict:
        require_admin(principal)
        result = self._gateway.smoke_test(model_id)
        self._audit.record(principal.user_id, "model.smoke_test", model_id)
        return result

    def audit_events(self, principal: Principal) -> list[dict]:
        require_admin(principal)
        return [event.model_dump(mode="json") for event in self._audit.events()]

    def skills(self, principal: Principal) -> dict:
        """Active skill versions with content hashes, for inspection (SKILL-06)."""
        require_admin(principal)
        versions = self._releases.active().skill_versions
        return {
            "versions": versions,
            "hashes": self._skills.hashes(versions),
            "skills": self._skills.describe(versions),
        }

    def sources(self, principal: Principal) -> list[dict]:
        require_admin(principal)
        return self._sources.describe()

    def check_source(self, principal: Principal, name: str) -> dict:
        require_admin(principal)
        return self._sources.check(name)

    def metrics_text(self, principal: Principal) -> str:
        """Prometheus exposition format for queue depth, run states and spend."""
        require_admin(principal)
        health = self.health(principal)
        lines = [f"bionexus_queue_depth {health['queue_depth']}"]
        lines += [
            f'bionexus_runs{{status="{status}"}} {count}'
            for status, count in sorted(health["runs_by_status"].items())
        ]
        lines.append(f"bionexus_spend_usd_total {self.usage(principal)['total_usd']}")
        lines.append(f"bionexus_emergency_stop {int(health['emergency_stop'])}")
        return "\n".join(lines) + "\n"
