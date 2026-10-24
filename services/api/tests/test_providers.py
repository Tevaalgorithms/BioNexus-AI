import json

import pytest
from langchain_anthropic import ChatAnthropic
from langchain_core.messages import AIMessage
from langchain_openai import ChatOpenAI

from bionexus.contracts.errors import InvalidRequest
from bionexus.llm.clients import ProviderError
from bionexus.llm.langchain_client import (
    LangChainClient,
    anthropic_model,
    message_text,
    openai_model,
)
from bionexus.llm.registry import load_specs


class StubChat:
    """Stands in for a LangChain chat model: records the call, returns a canned reply."""

    def __init__(self, reply=None, error=None):
        self.reply, self.error, self.seen = reply, error, []

    def invoke(self, messages):
        self.seen.append(messages)
        if self.error:
            raise self.error
        return self.reply


def client_with(stub, secrets):
    captured = {}

    def factory(model_id, max_tokens, temperature, api_key):
        captured.update(
            model_id=model_id, max_tokens=max_tokens, temperature=temperature, key=api_key
        )
        return stub

    secrets.values["MY_KEY"] = "sekret-value"
    return LangChainClient(factory, "MY_KEY"), captured


def test_reply_text_and_token_usage_are_mapped(isolated_parameters):
    reply = AIMessage(
        content="hi", usage_metadata={"input_tokens": 5, "output_tokens": 2, "total_tokens": 7}
    )
    client, captured = client_with(StubChat(reply), isolated_parameters)
    response = client.generate("m", "prompt", 50, temperature=0.2)
    assert (response.text, response.input_tokens, response.output_tokens) == ("hi", 5, 2)
    assert captured == {
        "model_id": "m",
        "max_tokens": 50,
        "temperature": 0.2,
        "key": "sekret-value",
    }


def test_key_is_looked_up_by_name_at_call_time_so_rotation_needs_no_restart(isolated_parameters):
    client, captured = client_with(StubChat(AIMessage(content="x")), isolated_parameters)
    isolated_parameters.values["MY_KEY"] = "rotated"
    client.generate("m", "p", 10)
    assert captured["key"] == "rotated"
    isolated_parameters.values["OTHER"] = "other-key"
    client.generate("m", "p", 10, api_key_secret="OTHER")  # a model's own key name wins
    assert captured["key"] == "other-key"


def test_missing_key_parameter_is_a_clear_error(isolated_parameters):
    client = LangChainClient(lambda *a: StubChat(), "ABSENT_KEY")
    with pytest.raises(InvalidRequest, match="ABSENT_KEY"):
        client.generate("m", "p", 10)


@pytest.mark.parametrize(
    "stub",
    [
        StubChat(error=RuntimeError("429 rate limited")),
        StubChat(reply=AIMessage(content="")),
        StubChat(reply=AIMessage(content=[{"type": "tool_use", "id": "1"}])),
    ],
)
def test_provider_failures_become_provider_errors(stub, isolated_parameters):
    client, _ = client_with(stub, isolated_parameters)
    with pytest.raises(ProviderError):
        client.generate("m", "p", 10)


def test_content_blocks_are_flattened_to_text():
    reply = AIMessage(content=[{"type": "text", "text": "a"}, {"type": "text", "text": "b"}])
    assert message_text(reply) == "ab"


def test_real_chat_models_are_configured_without_any_network_call():
    claude = anthropic_model("some-model", 77, 0.3, "k")
    assert (
        isinstance(claude, ChatAnthropic) and claude.max_tokens == 77 and claude.temperature == 0.3
    )
    gpt = openai_model("some-model", 88, None, "k")
    assert isinstance(gpt, ChatOpenAI) and gpt.max_tokens == 88
    assert "api.openai.com" in str(gpt.openai_api_base)


def test_registry_file_requires_verified_prices(tmp_path):
    path = tmp_path / "models.json"
    row = {
        "model_id": "m",
        "provider": "anthropic",
        "supports_structured_output": True,
        "input_usd_per_million": 1,
        "output_usd_per_million": 2,
    }
    path.write_text(json.dumps({"models": [row]}))
    with pytest.raises(InvalidRequest):
        load_specs(path)
    path.write_text(json.dumps({"models": [{**row, "price_verified_on": "2026-10-23"}]}))
    assert load_specs(path)[0].provider == "anthropic"
