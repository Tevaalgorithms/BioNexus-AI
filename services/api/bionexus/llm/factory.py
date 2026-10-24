"""Provider clients, built on first use so a model added at runtime works without a restart."""

from collections.abc import Callable, Mapping

from bionexus.contracts.errors import InvalidRequest
from bionexus.llm.clients import DeterministicModelClient, ModelClient
from bionexus.llm.langchain_client import LangChainClient, anthropic_model, openai_model

PRODUCTION_PROVIDERS = frozenset({"anthropic", "openai"})
ALL_PROVIDERS = PRODUCTION_PROVIDERS | {"fixture"}


_BUILDERS: dict[str, Callable[[str | None], ModelClient]] = {
    "anthropic": lambda secret: LangChainClient(anthropic_model, secret or "ANTHROPIC_API_KEY"),
    "openai": lambda secret: LangChainClient(openai_model, secret or "OPENAI_API_KEY"),
    "fixture": lambda secret: DeterministicModelClient(),
}


def build_client(provider: str, secret_name: str | None) -> ModelClient:
    builder = _BUILDERS.get(provider)
    if builder is None:
        raise InvalidRequest(f"Unknown provider '{provider}'")
    return builder(secret_name)


class LazyClients(Mapping):
    """provider -> client. A client reads its API key by name at call time, so key rotation in
    SSM needs no restart either."""

    def __init__(self) -> None:
        self._clients: dict[str, ModelClient] = {}

    def __getitem__(self, provider: str) -> ModelClient:
        if provider not in self._clients:
            self._clients[provider] = build_client(provider, None)
        return self._clients[provider]

    def __iter__(self):
        return iter(self._clients)

    def __len__(self) -> int:
        return len(self._clients)
