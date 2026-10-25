"""Immutable configuration releases. A run pins one release for its whole life (MODEL-11/12)."""

from datetime import UTC, datetime

from bionexus.contracts.errors import Conflict, NotFound
from bionexus.contracts.messages import AgentName
from bionexus.llm.models import AgentBinding, ConfigRelease
from bionexus.llm.registry import ModelRegistry
from bionexus.storage.ports import ReleaseRepository

__all__ = ["AgentBinding", "ConfigRelease", "ReleaseStore"]


class ReleaseStore:
    """Append-only history. Activating a release never alters an older one."""

    def __init__(self, registry: ModelRegistry, repository: ReleaseRepository) -> None:
        self._registry = registry
        self._repository = repository

    def seed(self, initial: ConfigRelease) -> None:
        """Install the first release if the database has none yet."""
        if not self._repository.history():
            self._repository.add(initial, activate=True)

    def ensure_complete(
        self, template: AgentName, skill_versions: dict[str, str]
    ) -> ConfigRelease | None:
        """Add any agent or skill the active release lacks, as a new release (history is kept).

        A product upgrade can add agents. A release saved before that has no binding for them, so
        they borrow the `template` agent's models. Returns the new release, or None if nothing was
        missing or another process added it first.
        """
        current = self.active()
        agents = [a for a in AgentName if a not in current.bindings]
        skills = {k: v for k, v in skill_versions.items() if k not in current.skill_versions}
        if not agents and not skills:
            return None
        revision = current.revision + 1
        release = current.model_copy(
            update={
                "release_id": f"rel-{revision}",
                "revision": revision,
                "bindings": {**current.bindings, **{a: current.bindings[template] for a in agents}},
                "skill_versions": {**current.skill_versions, **skills},
                "created_by": "system",
                "reason": f"added to this release: {', '.join([*agents, *skills])}",
                "parent_id": current.release_id,
                "created_at": datetime.now(UTC),
            }
        )
        try:
            self._repository.add(release, activate=True)
        except Conflict:  # another process upgraded first
            return None
        return release

    def active(self) -> ConfigRelease:
        return self._repository.active()

    def get(self, release_id: str) -> ConfigRelease:
        release = self._repository.get(release_id)
        if release is None:
            raise NotFound(f"Release '{release_id}' does not exist")
        return release

    def history(self) -> list[ConfigRelease]:
        return self._repository.history()

    def rebind_agent(
        self,
        agent: AgentName,
        binding: AgentBinding,
        *,
        actor: str,
        reason: str,
        expected_revision: int,
    ) -> ConfigRelease:
        current = self.active()
        if current.revision != expected_revision:
            raise Conflict(f"Active revision is {current.revision}, not {expected_revision}")
        self._validate(binding)
        release = self._derive(current, agent, binding, actor, reason)
        self._repository.add(release, activate=True)
        return release

    def republish(
        self, source: ConfigRelease, *, actor: str, reason: str, expected_revision: int
    ) -> ConfigRelease:
        current = self.active()
        if current.revision != expected_revision:
            raise Conflict(f"Active revision is {current.revision}, not {expected_revision}")
        revision = current.revision + 1
        release = source.model_copy(
            update={
                "release_id": f"rel-{revision}",
                "revision": revision,
                "created_by": actor,
                "reason": reason,
                "parent_id": current.release_id,
                "created_at": datetime.now(UTC),
            }
        )
        self._repository.add(release, activate=True)
        return release

    def derive(
        self, agent: AgentName, binding: AgentBinding, *, actor: str, reason: str
    ) -> ConfigRelease:
        """A candidate release that is *not* stored or activated (used for evaluation)."""
        self._validate(binding)
        return self._derive(self.active(), agent, binding, actor, reason)

    def _validate(self, binding: AgentBinding) -> None:
        for model_id in binding.model_chain():
            self._registry.get(model_id)

    @staticmethod
    def _derive(
        current: ConfigRelease, agent: AgentName, binding: AgentBinding, actor: str, reason: str
    ) -> ConfigRelease:
        revision = current.revision + 1
        return current.model_copy(
            update={
                "release_id": f"rel-{revision}",
                "revision": revision,
                "bindings": {**current.bindings, agent: binding},
                "created_by": actor,
                "reason": reason,
                "parent_id": current.release_id,
                "created_at": datetime.now(UTC),
            }
        )
