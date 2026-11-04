"""One wrapper for every LLM call, so the provider can be switched by changing a key in backend/.env.

With LLM_PROVIDER=auto (the default) the first key that is set wins: ANTHROPIC_API_KEY (Claude), then
GEMINI_API_KEY, then GROQ_API_KEY. LLM_MODEL overrides the provider's default model.
With no key, or LLM_PROVIDER=none, available() is False and callers use their template fallback.
Every failure raises LLMError, so callers fall back the same way and the demo never breaks.
"""

import logging

import anthropic
import httpx

from ..config import settings

log = logging.getLogger("leadops.llm")

DEFAULT_MODELS = {
    "anthropic": "claude-opus-5-5",  # best quality; LLM_MODEL=claude-haiku-5-5 costs much less
    "gemini": "gemini-flash-latest",
    "groq": "llama-3.3-70b-versatile",
}
TIMEOUT_SECONDS = 15.0  # chat should fall back to a template quickly rather than keep a visitor waiting

# Claude models that take output_config.effort (older models reject it).
_EFFORT_MODEL_PREFIXES = (
    "claude-opus-5", "claude-sonnet-5", "claude-haiku-5", "claude-fable-5", "claude-mythos-5",
    "claude-opus-4-6", "claude-opus-4-7", "claude-opus-4-8", "claude-sonnet-4-6",
)  # fmt: skip
# Claude models that support Anthropic's server-side refusal fallback (fallbacks="default").
_FALLBACK_MODELS = {"claude-opus-5-5", "claude-opus-5", "claude-fable-5-1", "claude-sonnet-5-5"}


class LLMError(Exception):
    """Any LLM failure: no provider, network error, timeout, rate limit, refusal or empty answer."""


class LLMClient:
    def __init__(self) -> None:
        self.provider = self._pick_provider()
        self.model = settings.llm_model or DEFAULT_MODELS.get(self.provider or "", "")
        self._claude_client: anthropic.Anthropic | None = None

    @staticmethod
    def _pick_provider() -> str | None:
        keys = {"anthropic": settings.anthropic_api_key, "gemini": settings.gemini_api_key, "groq": settings.groq_api_key}
        choice = settings.llm_provider
        if choice in ("none", "off", "template"):
            return None
        if choice in keys:  # a forced provider still needs its key
            return choice if keys[choice] else None
        return next((name for name, key in keys.items() if key), None)

    def available(self) -> bool:
        return self.provider is not None

    def describe(self) -> str:
        return f"{self.provider}:{self.model}" if self.provider else "template"

    def generate(self, system: str, messages: list[dict[str, str]], *, max_tokens: int = 1024) -> str:
        """Reply text for a conversation.

        messages: [{"role": "user" | "assistant", "content": "..."}], oldest first, ending with the user.
        max_tokens applies to Gemini and Groq; Claude gets a generous cap because its thinking counts too.
        """
        if self.provider == "anthropic":
            text = self._claude(system, messages)
        elif self.provider == "gemini":
            text = self._gemini(system, messages)
        elif self.provider == "groq":
            text = self._groq(system, messages, max_tokens)
        else:
            raise LLMError("No LLM provider is configured")
        text = text.strip()
        if not text:
            raise LLMError(f"{self.provider} returned an empty answer")
        return text

    # ---------------------------------------------------------------- Claude (Anthropic SDK)

    def _claude(self, system: str, messages: list[dict[str, str]]) -> str:
        if self._claude_client is None:
            self._claude_client = anthropic.Anthropic(
                api_key=settings.anthropic_api_key, timeout=TIMEOUT_SECONDS, max_retries=1
            )
        params: dict = {"model": self.model, "max_tokens": 16000, "system": system, "messages": messages}
        if self.model.startswith(_EFFORT_MODEL_PREFIXES):
            params["output_config"] = {"effort": "low"}  # short chat replies: quick and cheap
        try:
            if self.model in _FALLBACK_MODELS:
                # If Claude's safety checks decline a message, Anthropic re-runs it on its recommended
                # fallback model inside the same call instead of returning a refusal.
                response = self._claude_client.beta.messages.create(
                    betas=["server-side-fallback-2026-07-01"], fallbacks="default", **params
                )
            else:
                response = self._claude_client.messages.create(**params)
        except anthropic.AuthenticationError as exc:
            raise LLMError("Claude rejected the API key (check ANTHROPIC_API_KEY)") from exc
        except anthropic.NotFoundError as exc:
            raise LLMError(f"Claude model not found: {self.model} (check LLM_MODEL)") from exc
        except anthropic.RateLimitError as exc:
            raise LLMError("Claude rate limit or credit limit reached") from exc
        except anthropic.APIStatusError as exc:
            raise LLMError(f"Claude API error {exc.status_code}: {exc.message}") from exc
        except anthropic.APIConnectionError as exc:  # includes timeouts
            raise LLMError("Could not reach the Claude API (network problem or timeout)") from exc
        if response.stop_reason == "refusal":
            raise LLMError("Claude declined to answer this message")
        return "".join(block.text for block in response.content if block.type == "text")

    # ---------------------------------------------------------------- Gemini and Groq (REST)

    def _gemini(self, system: str, messages: list[dict[str, str]]) -> str:
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{self.model}:generateContent"
        body = {
            "systemInstruction": {"parts": [{"text": system}]},
            "contents": [
                {"role": "model" if m["role"] == "assistant" else "user", "parts": [{"text": m["content"]}]}
                for m in messages
            ],
            # Room for the model's thinking as well as the reply; keep replies short through the prompt.
            "generationConfig": {"temperature": 0.4, "maxOutputTokens": 4096},
        }
        data = self._post("Gemini", url, body, {"x-goog-api-key": settings.gemini_api_key})
        try:
            parts = data["candidates"][0]["content"]["parts"]
        except (KeyError, IndexError, TypeError) as exc:
            reason = (data.get("candidates") or [{}])[0].get("finishReason", "unknown")
            raise LLMError(f"Gemini returned no answer (finish reason: {reason})") from exc
        return "".join(part.get("text", "") for part in parts if not part.get("thought"))

    def _groq(self, system: str, messages: list[dict[str, str]], max_tokens: int) -> str:
        body = {
            "model": self.model,
            "messages": [{"role": "system", "content": system}, *messages],
            "temperature": 0.4,
            "max_tokens": max_tokens,
        }
        headers = {"Authorization": f"Bearer {settings.groq_api_key}"}
        data = self._post("Groq", "https://api.groq.com/openai/v1/chat/completions", body, headers)
        try:
            return data["choices"][0]["message"]["content"] or ""
        except (KeyError, IndexError, TypeError) as exc:
            raise LLMError("Groq returned no answer") from exc

    @staticmethod
    def _post(name: str, url: str, body: dict, headers: dict[str, str]) -> dict:
        try:
            response = httpx.post(url, json=body, headers=headers, timeout=TIMEOUT_SECONDS)
        except httpx.HTTPError as exc:
            raise LLMError(f"Could not reach {name} ({exc.__class__.__name__})") from exc
        if response.status_code >= 400:
            raise LLMError(f"{name} API error {response.status_code}: {response.text[:300]}")
        try:
            return response.json()
        except ValueError as exc:
            raise LLMError(f"{name} sent a response that isn't JSON") from exc


llm = LLMClient()
