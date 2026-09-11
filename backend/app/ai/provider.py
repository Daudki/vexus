"""
AI provider abstraction.

`AIProvider` is a Protocol so the assistant is swappable (cloud today,
local later) without touching AIService. `NullProvider` is the default
— the whole platform must keep working with AI disabled, so it never
raises, it just says AI isn't configured.

The request-building and response-parsing logic (`build_anthropic_request`,
`parse_anthropic_response`) are pure functions, deliberately separated
from `AnthropicProvider.generate`'s actual HTTP call, so they're fully
unit-testable without a network connection or API key — which matters
here specifically, since this environment has no ANTHROPIC_API_KEY to
test the live call against.

`parse_anthropic_response` never returns a best-effort guess on
malformed output. It raises `AIProviderError` instead — a broken or
off-schema model response must not silently masquerade as a real
answer. This is what keeps "never allow AI to present speculation as
fact" true at the code level, not just in the prompt.
"""
import json
from typing import Protocol

import httpx
from pydantic import BaseModel, ValidationError


class AIResponse(BaseModel):
    observed_facts: list[str] = []
    inferences: list[str] = []
    hypotheses: list[str] = []
    recommendations: list[str] = []
    confidence: float = 0.0


class AIProviderError(Exception):
    pass


class AIProvider(Protocol):
    def generate(self, system_prompt: str, user_prompt: str) -> AIResponse: ...


class NullProvider:
    """Used whenever AI_PROVIDER=none (the default). Never raises."""

    def generate(self, system_prompt: str, user_prompt: str) -> AIResponse:
        return AIResponse(
            recommendations=[
                "AI assistant is not configured for this deployment. Set AI_PROVIDER=local "
                "with Ollama running, or configure a paid cloud provider."
            ],
            confidence=0.0,
        )


RESPONSE_SCHEMA_INSTRUCTIONS = (
    "Respond with ONLY a single JSON object, no prose, no markdown fences, matching exactly this shape:\n"
    '{"observed_facts": [string, ...], "inferences": [string, ...], '
    '"hypotheses": [string, ...], "recommendations": [string, ...], '
    '"confidence": number between 0 and 1}\n\n'
    "observed_facts: only things directly stated in the provided context — never invent a fact.\n"
    "inferences: reasonable conclusions drawn from the observed facts, clearly labeled as inferences, "
    "not certainties.\n"
    "hypotheses: possible explanations that would require further verification — do not present these "
    "as established.\n"
    "recommendations: concrete next steps for a human analyst. Never recommend automated action; "
    "this platform is read-only and does not execute responses.\n"
    "confidence: your overall confidence in the inferences, not the observed facts."
)


def build_anthropic_request(system_prompt: str, user_prompt: str, model: str, max_tokens: int = 1024) -> dict:
    """Pure function — no network call, fully testable."""
    return {
        "model": model,
        "max_tokens": max_tokens,
        "system": f"{system_prompt}\n\n{RESPONSE_SCHEMA_INSTRUCTIONS}",
        "messages": [{"role": "user", "content": user_prompt}],
    }


def parse_anthropic_response(raw: dict) -> AIResponse:
    """Pure function — testable against a canned API response, no network call."""
    try:
        content_blocks = raw["content"]
        text = "".join(block["text"] for block in content_blocks if block.get("type") == "text")
    except (KeyError, TypeError) as exc:
        raise AIProviderError(f"Unexpected Anthropic API response shape: {exc}") from exc

    if not text:
        raise AIProviderError("Anthropic API response contained no text content.")

    try:
        parsed = json.loads(text)
    except json.JSONDecodeError as exc:
        raise AIProviderError(f"AI response was not valid JSON: {exc}") from exc

    try:
        return AIResponse(**parsed)
    except ValidationError as exc:
        raise AIProviderError(f"AI response did not match the required schema: {exc}") from exc


class AnthropicProvider:
    """Real implementation. Request-building and response-parsing are unit
    tested via the pure functions above; the live HTTP call itself has not
    been exercised against a real API key in this environment — verify
    before relying on it in production."""

    def __init__(self, api_key: str, model: str, timeout_seconds: float = 30.0):
        self.api_key = api_key
        self.model = model
        self.timeout_seconds = timeout_seconds

    def generate(self, system_prompt: str, user_prompt: str) -> AIResponse:
        payload = build_anthropic_request(system_prompt, user_prompt, self.model)
        headers = {
            "x-api-key": self.api_key,
            "anthropic-version": "2023-06-01",
            "content-type": "application/json",
        }
        try:
            response = httpx.post(
                "https://api.anthropic.com/v1/messages",
                json=payload,
                headers=headers,
                timeout=self.timeout_seconds,
            )
            response.raise_for_status()
        except httpx.HTTPError as exc:
            raise AIProviderError(f"Anthropic API request failed: {exc}") from exc

        return parse_anthropic_response(response.json())


def build_deepseek_request(system_prompt: str, user_prompt: str, model: str, max_tokens: int = 1024) -> dict:
    """Pure function — no network call, fully testable.

    DeepSeek's API is OpenAI-compatible (chat completions shape), so
    the request body differs from Anthropic's even though both are
    asked to return the same AIResponse-shaped JSON.
    """
    return {
        "model": model,
        "max_tokens": max_tokens,
        "messages": [
            {"role": "system", "content": f"{system_prompt}\n\n{RESPONSE_SCHEMA_INSTRUCTIONS}"},
            {"role": "user", "content": user_prompt},
        ],
        "stream": False,
    }


def parse_deepseek_response(raw: dict) -> AIResponse:
    """Pure function — testable against a canned API response, no network call."""
    try:
        text = raw["choices"][0]["message"]["content"]
    except (KeyError, IndexError, TypeError) as exc:
        raise AIProviderError(f"Unexpected DeepSeek API response shape: {exc}") from exc

    if not text:
        raise AIProviderError("DeepSeek API response contained no text content.")

    # DeepSeek sometimes wraps JSON in markdown code fences despite
    # being asked not to; strip them before parsing.
    stripped = text.strip()
    if stripped.startswith("```"):
        stripped = stripped.strip("`")
        if stripped.startswith("json"):
            stripped = stripped[4:]
        stripped = stripped.strip()

    try:
        parsed = json.loads(stripped)
    except json.JSONDecodeError as exc:
        raise AIProviderError(f"AI response was not valid JSON: {exc}") from exc

    try:
        return AIResponse(**parsed)
    except ValidationError as exc:
        raise AIProviderError(f"AI response did not match the required schema: {exc}") from exc


class DeepSeekProvider:
    """DeepSeek implementation of the same AIProvider protocol used by
    AnthropicProvider. Not exercised against a real API key in this
    environment — verify before relying on it in production."""

    def __init__(self, api_key: str, model: str = "deepseek-chat", timeout_seconds: float = 60.0):
        self.api_key = api_key
        self.model = model
        self.timeout_seconds = timeout_seconds

    def generate(self, system_prompt: str, user_prompt: str) -> AIResponse:
        payload = build_deepseek_request(system_prompt, user_prompt, self.model)
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        try:
            response = httpx.post(
                "https://api.deepseek.com/v1/chat/completions",
                json=payload,
                headers=headers,
                timeout=self.timeout_seconds,
            )
            response.raise_for_status()
        except httpx.HTTPError as exc:
            raise AIProviderError(f"DeepSeek API request failed: {exc}") from exc

        return parse_deepseek_response(response.json())


def build_ollama_request(system_prompt: str, user_prompt: str, model: str) -> dict:
    """Build an Ollama chat request with JSON mode enabled."""
    return {
        "model": model,
        "stream": False,
        "format": "json",
        "messages": [
            {"role": "system", "content": f"{system_prompt}\n\n{RESPONSE_SCHEMA_INSTRUCTIONS}"},
            {"role": "user", "content": user_prompt},
        ],
    }


def parse_ollama_response(raw: dict) -> AIResponse:
    try:
        text = raw["message"]["content"]
    except (KeyError, TypeError) as exc:
        raise AIProviderError(f"Unexpected Ollama response shape: {exc}") from exc
    if not text:
        raise AIProviderError("Ollama response contained no content.")
    try:
        return AIResponse(**json.loads(text))
    except (json.JSONDecodeError, ValidationError) as exc:
        raise AIProviderError(f"Ollama response did not match the required schema: {exc}") from exc


class OllamaProvider:
    """Local Ollama provider. No API key or paid service is required."""

    def __init__(self, base_url: str, model: str, timeout_seconds: float = 120.0):
        self.url = f"{base_url.rstrip('/')}/api/chat"
        self.model = model
        self.timeout_seconds = timeout_seconds

    def generate(self, system_prompt: str, user_prompt: str) -> AIResponse:
        try:
            response = httpx.post(
                self.url,
                json=build_ollama_request(system_prompt, user_prompt, self.model),
                timeout=self.timeout_seconds,
            )
            response.raise_for_status()
        except httpx.HTTPError as exc:
            raise AIProviderError(f"Local Ollama request failed: {exc}") from exc
        return parse_ollama_response(response.json())
