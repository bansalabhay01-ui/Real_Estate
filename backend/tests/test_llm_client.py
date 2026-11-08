"""The exact Claude request the wrapper sends, checked offline through a fake HTTP transport (no key, no cost)."""

import json

import anthropic
import httpx2
import pytest

from app.ai.llm_client import LLMClient, LLMError


def claude_wrapper(handler, model: str) -> LLMClient:
    client = LLMClient()
    client.provider, client.model = "anthropic", model
    client._claude_client = anthropic.Anthropic(
        api_key="test-key",
        max_retries=0,
        http_client=anthropic.DefaultHttpxClient(transport=httpx2.MockTransport(handler)),
    )
    return client


def reply(stop_reason: str = "end_turn", text: str = "Here are two homes in Pune.") -> httpx2.Response:
    return httpx2.Response(
        200,
        json={
            "id": "msg_test",
            "type": "message",
            "role": "assistant",
            "model": "claude-opus-5-5",
            "content": [{"type": "text", "text": text}] if text else [],
            "stop_reason": stop_reason,
            "stop_sequence": None,
            "usage": {"input_tokens": 10, "output_tokens": 5},
        },
    )


def test_opus_request_uses_low_effort_and_refusal_fallback():
    seen = {}

    def handler(request: httpx2.Request) -> httpx2.Response:
        seen["body"] = json.loads(request.content)
        seen["beta"] = request.headers.get("anthropic-beta", "")
        return reply()

    wrapper = claude_wrapper(handler, "claude-opus-5-5")
    text = wrapper.generate("system prompt", [{"role": "user", "content": "3BHK in Pune?"}])

    assert text == "Here are two homes in Pune."
    body = seen["body"]
    assert body["model"] == "claude-opus-5-5"
    assert body["system"] == "system prompt"
    assert body["messages"] == [{"role": "user", "content": "3BHK in Pune?"}]
    assert body["output_config"] == {"effort": "low"}
    assert body["fallbacks"] == "default"
    assert "server-side-fallback-2026-07-01" in seen["beta"]
    assert "temperature" not in body  # removed from the API; sending it is a 400


def test_haiku_request_has_no_fallback():
    seen = {}

    def handler(request: httpx2.Request) -> httpx2.Response:
        seen["body"] = json.loads(request.content)
        return reply()

    claude_wrapper(handler, "claude-haiku-5-5").generate("s", [{"role": "user", "content": "hi"}])
    assert "fallbacks" not in seen["body"]
    assert seen["body"]["output_config"] == {"effort": "low"}


@pytest.mark.parametrize(
    ("response", "message"),
    [
        (reply(stop_reason="refusal", text=""), "declined"),
        (httpx2.Response(401, json={"type": "error", "error": {"type": "authentication_error", "message": "bad key"}}), "API key"),
        (httpx2.Response(429, json={"type": "error", "error": {"type": "rate_limit_error", "message": "slow down"}}), "rate limit"),
        (reply(text=""), "empty"),
    ],
)
def test_failures_become_llm_errors(response, message):
    wrapper = claude_wrapper(lambda request: response, "claude-opus-5-5")
    with pytest.raises(LLMError, match=message):
        wrapper.generate("s", [{"role": "user", "content": "hi"}])


SCHEMA = {"type": "object", "properties": {"city": {"type": "string"}}, "required": ["city"], "additionalProperties": False}


def test_json_request_uses_structured_outputs_with_low_effort():
    seen = {}

    def handler(request: httpx2.Request) -> httpx2.Response:
        seen["body"] = json.loads(request.content)
        return reply(text='{"city": "Pune"}')

    wrapper = claude_wrapper(handler, "claude-opus-5-5")
    assert wrapper.generate_json("extract", [{"role": "user", "content": "Pune mein"}], SCHEMA) == {"city": "Pune"}
    body = seen["body"]
    assert body["output_config"] == {"effort": "low", "format": {"type": "json_schema", "schema": SCHEMA}}
    assert body["fallbacks"] == "default" and "temperature" not in body


def test_json_answers_that_are_cut_off_or_not_json_are_errors():
    cut_off = claude_wrapper(lambda request: reply(stop_reason="max_tokens", text='{"city": "Pu'), "claude-opus-5-5")
    with pytest.raises(LLMError, match="cut off"):
        cut_off.generate_json("s", [{"role": "user", "content": "hi"}], SCHEMA)
    prose = claude_wrapper(lambda request: reply(text="Sorry, I can't help with that."), "claude-opus-5-5")
    with pytest.raises(LLMError, match="JSON"):
        prose.generate_json("s", [{"role": "user", "content": "hi"}], SCHEMA)


def test_json_from_models_without_a_schema_is_unwrapped():
    from app.ai.llm_client import _json_object

    assert _json_object('```json\n{"type": "broker"}\n```', "groq") == {"type": "broker"}
    assert _json_object('Here you go: {"a": 1}', "gemini") == {"a": 1}
    with pytest.raises(LLMError):
        _json_object("[1, 2]", "groq")
