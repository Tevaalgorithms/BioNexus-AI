"""Provider access through LangChain chat models.

LangChain is used for one thing here: a maintained, provider-neutral chat-model interface
(`BaseChatModel`) with built-in retries and usage metadata. Everything that matters to the product
stays ours and sits *around* it in the gateway: approved-model checks, pinned configuration
releases, fallback order, atomic budgets, the invocation ledger, and secret lookup by name.
We do not use LangChain agents, chains, tools, retrievers, memory or vector stores.
"""

from collections.abc import Callable

from langchain_anthropic import ChatAnthropic
from langchain_core.language_models import BaseChatModel
from langchain_core.messages import AIMessage, HumanMessage
from langchain_openai import ChatOpenAI

from bionexus.llm.clients import ModelResponse, ProviderError
from bionexus.llm.secrets import resolve_secret

TIMEOUT_SECONDS = 120.0
TRANSPORT_RETRIES = 2  # transient 429/5xx handled by the SDK; model *fallback* is the gateway's job

ChatModelFactory = Callable[[str, int, float | None, str], BaseChatModel]
"""(model_id, max_output_tokens, temperature, api_key) -> chat model"""


def anthropic_model(model_id: str, max_tokens: int, temperature: float | None, api_key: str):
    options = {} if temperature is None else {"temperature": temperature}
    return ChatAnthropic(
        model=model_id,
        max_tokens=max_tokens,
        api_key=api_key,
        timeout=TIMEOUT_SECONDS,
        max_retries=TRANSPORT_RETRIES,
        **options,
    )


def openai_model(model_id: str, max_tokens: int, temperature: float | None, api_key: str):
    options = {} if temperature is None else {"temperature": temperature}
    return ChatOpenAI(
        model=model_id,
        max_completion_tokens=max_tokens,
        api_key=api_key,
        base_url="https://api.openai.com/v1",  # fixed: no client-supplied destinations
        timeout=TIMEOUT_SECONDS,
        max_retries=TRANSPORT_RETRIES,
        **options,
    )


def message_text(message: AIMessage) -> str:
    """Plain text of a reply, whether the provider returns a string or content blocks."""
    content = message.content
    if isinstance(content, str):
        return content
    return "".join(b.get("text", "") for b in content if isinstance(b, dict))


class LangChainClient:
    """Implements our `ModelClient` port on top of any LangChain chat model."""

    def __init__(self, factory: ChatModelFactory, default_secret: str) -> None:
        self._factory = factory
        self._default_secret = default_secret

    def generate(
        self,
        model_id: str,
        prompt: str,
        max_output_tokens: int,
        temperature: float | None = None,
        api_key_secret: str | None = None,
    ) -> ModelResponse:
        api_key = resolve_secret(api_key_secret or self._default_secret)  # read at call time
        model = self._factory(model_id, max_output_tokens, temperature, api_key)
        try:
            reply = model.invoke([HumanMessage(content=prompt)])
        except Exception as error:  # SDK errors vary by provider; the gateway only needs "failed"
            raise ProviderError(f"{type(error).__name__} from provider") from error
        return self._to_response(reply)

    @staticmethod
    def _to_response(reply: AIMessage) -> ModelResponse:
        text = message_text(reply)
        if not text:
            raise ProviderError("provider returned no text (refusal or truncation)")
        usage = reply.usage_metadata or {}
        return ModelResponse(text, usage.get("input_tokens", 0), usage.get("output_tokens", 0))
