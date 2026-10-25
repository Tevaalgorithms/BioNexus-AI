"""The single door to language models: binding lookup, fallback, budget and invocation ledger."""

import time

from bionexus.contracts.errors import ModelUnavailable
from bionexus.contracts.invocation import Invocation
from bionexus.contracts.messages import AgentName
from bionexus.llm.cache import CachedAnswer, ResponseCache
from bionexus.llm.clients import ModelClient, ProviderError
from bionexus.llm.registry import ModelRegistry, ModelSpec
from bionexus.llm.release import AgentBinding, ReleaseStore
from bionexus.storage.ports import FlagStore
from bionexus.workflow.state import RunState

MODELS_DISABLED = "models_disabled"
SMOKE_PROMPT = "Reply with the single word: ready."
SMOKE_MAX_TOKENS = 8


class ModelGateway:
    def __init__(
        self,
        registry: ModelRegistry,
        releases: ReleaseStore,
        clients: dict[str, ModelClient],
        flags: FlagStore,
        cache: ResponseCache | None = None,
    ) -> None:
        self._registry = registry
        self._releases = releases
        self._clients = clients
        self._flags = flags
        self._cache = cache or ResponseCache(0)  # no cache unless one is given

    def complete(self, state: RunState, agent: AgentName, prompt: str) -> str:
        if self._flags.is_set(MODELS_DISABLED):
            raise ModelUnavailable("Model calls are disabled by an administrator")
        binding = self._releases.get(state.release_id).bindings[agent]
        key = self._cache.key(state.tenant_id, binding, prompt)
        cached = self._cache.get(key)
        if cached is not None:
            self._record_hit(state, agent, cached)
            return cached.text
        answer = self._ask_chain(state, agent, binding, prompt)
        self._cache.put(key, answer)
        return answer.text

    def _ask_chain(
        self, state: RunState, agent: AgentName, binding: AgentBinding, prompt: str
    ) -> CachedAnswer:
        """Try the bound model, then its fallback. Returns the answer and who gave it."""
        failure_reason: str | None = None
        for model_id in binding.model_chain():
            try:
                text = self._invoke(state, agent, binding, model_id, prompt, failure_reason)
                return CachedAnswer(text, model_id)
            except ProviderError as error:
                failure_reason = str(error)
        raise ModelUnavailable(f"No approved model could serve the {agent} agent")

    @staticmethod
    def _record_hit(state: RunState, agent: AgentName, hit: CachedAnswer) -> None:
        """A cache hit costs nothing and uses no call, but it still appears in the ledger."""
        invocation = Invocation(
            agent=agent, model_id=hit.model_id, input_tokens=0, output_tokens=0, cost_usd=0.0
        )
        with state.lock:
            state.invocations.append(invocation.model_copy(update={"cached": True}))

    def _invoke(
        self,
        state: RunState,
        agent: AgentName,
        binding: AgentBinding,
        model_id: str,
        prompt: str,
        fallback_reason: str | None,
    ) -> str:
        spec = self._registry.get_for_call(model_id)
        worst_case = spec.cost(len(prompt) // 4 + 1, binding.max_output_tokens)
        with state.lock:
            state.budget.reserve(worst_case)
        temperature = binding.temperature if spec.supports_temperature else None
        response = self._clients[spec.provider].generate(
            model_id, prompt, binding.max_output_tokens, temperature, spec.api_key_secret
        )
        actual = spec.cost(response.input_tokens, response.output_tokens)
        with state.lock:
            state.budget.settle(reserved=worst_case, actual=actual)
            state.invocations.append(
                Invocation(
                    agent=agent,
                    model_id=model_id,
                    input_tokens=response.input_tokens,
                    output_tokens=response.output_tokens,
                    cost_usd=actual,
                    fallback_reason=fallback_reason,
                )
            )
        return response.text

    def smoke_test(self, model_id: str) -> dict:
        """Capability check with a nonconfidential prompt and a tiny output cap (MODEL-09)."""
        return self.smoke_test_spec(self._registry.get_for_call(model_id))

    def smoke_test_spec(self, spec: ModelSpec) -> dict:
        """Same check for a model that is not registered yet (used before registration)."""
        model_id = spec.model_id
        started = time.monotonic()
        response = self._clients[spec.provider].generate(
            model_id, SMOKE_PROMPT, SMOKE_MAX_TOKENS, None, spec.api_key_secret
        )
        return {
            "model_id": model_id,
            "ok": bool(response.text),
            "latency_ms": round((time.monotonic() - started) * 1000),
            "cost_usd": round(spec.cost(response.input_tokens, response.output_tokens), 8),
        }
