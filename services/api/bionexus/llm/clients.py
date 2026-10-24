"""The model-client port. Real providers sit behind LangChain; tests use the deterministic one."""

from dataclasses import dataclass
from typing import Protocol


class ProviderError(Exception):
    """A provider failure that a configured fallback may absorb (outage, rate limit, refusal)."""


@dataclass(frozen=True)
class ModelResponse:
    text: str
    input_tokens: int
    output_tokens: int


class ModelClient(Protocol):
    def generate(
        self,
        model_id: str,
        prompt: str,
        max_output_tokens: int,
        temperature: float | None = None,
        api_key_secret: str | None = None,
    ) -> ModelResponse: ...


class DeterministicModelClient:
    """Offline stand-in: echoes the final prompt line so runs are reproducible and free."""

    def __init__(self, failing_models: frozenset[str] = frozenset()) -> None:
        self._failing_models = failing_models

    def generate(
        self,
        model_id: str,
        prompt: str,
        max_output_tokens: int,
        temperature: float | None = None,
        api_key_secret: str | None = None,
    ) -> ModelResponse:
        if model_id in self._failing_models:
            raise ProviderError(f"{model_id} is unavailable")
        text = f"[{model_id}] {prompt.strip().splitlines()[-1]}"[: max_output_tokens * 4]
        return ModelResponse(text, len(prompt) // 4 + 1, len(text) // 4 + 1)
