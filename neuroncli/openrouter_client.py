"""NeuronCLI — OpenRouter HTTP streaming client. Zero external dependencies.

Supports reasoning models (Kimi K2.5) where the response has both
a `reasoning` field (chain-of-thought) and a `content` field (final answer).
"""

from __future__ import annotations

import json
import urllib.error
import urllib.request
from dataclasses import dataclass
from typing import Generator

from .config import AgentConfig


class OpenRouterConnectionError(Exception):
    """Raised when the OpenRouter API is unreachable or returns an error."""
    pass


@dataclass(frozen=True)
class ChatMessage:
    """A single message in the conversation."""
    role: str       # "system", "user", "assistant"
    content: str

    def to_dict(self) -> dict[str, str]:
        return {"role": self.role, "content": self.content}


class OpenRouterClient:
    """
    HTTP client for OpenRouter's OpenAI-compatible /api/v1/chat/completions.
    Uses only stdlib — no pip dependencies needed.

    Handles reasoning models (like Kimi K2.5) that emit:
      - `delta.reasoning` tokens (thinking, shown dimmed)
      - `delta.content` tokens (final answer)
    """

    API_BASE = "https://openrouter.ai/api/v1"

    def __init__(self, config: AgentConfig | None = None):
        self.config = config or AgentConfig.from_env()

    def health_check(self) -> bool:
        """Check if OpenRouter API is reachable and the API key is valid."""
        try:
            req = urllib.request.Request(
                f"{self.API_BASE}/models",
                headers=self._headers(),
            )
            with urllib.request.urlopen(req, timeout=10) as resp:
                return resp.status == 200
        except (urllib.error.URLError, OSError):
            return False

    def list_models(self) -> list[str]:
        """List coding-relevant models from OpenRouter."""
        try:
            req = urllib.request.Request(
                f"{self.API_BASE}/models",
                headers=self._headers(),
            )
            with urllib.request.urlopen(req, timeout=10) as resp:
                data = json.loads(resp.read().decode())
                models = data.get("data", [])
                keywords = ("kimi", "deepseek", "qwen", "codestral", "claude", "gemini")
                names = [m["id"] for m in models
                         if any(k in m["id"].lower() for k in keywords)]
                return sorted(names)[:25]
        except (urllib.error.URLError, OSError):
            return []

    def chat(self, messages: list[ChatMessage], model: str | None = None) -> str:
        """Send a chat request and return the full response text."""
        payload = self._build_payload(messages, model, stream=False)
        data = self._post(payload)
        choice = data.get("choices", [{}])[0]
        msg = choice.get("message", {})
        # Kimi K2.5 reasoning models: content may be in `content` or `reasoning`
        content = msg.get("content") or ""
        if not content:
            content = msg.get("reasoning", "")
        return content

    def chat_stream(
        self,
        messages: list[ChatMessage],
        model: str | None = None,
    ) -> Generator[str, None, None]:
        """
        Stream a chat response token by token.
        
        For reasoning models (Kimi K2.5), yields:
          - reasoning tokens with a dim prefix (hidden thinking)
          - content tokens normally (the actual response)
        """
        payload = self._build_payload(messages, model, stream=True)
        body = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(
            f"{self.API_BASE}/chat/completions",
            data=body,
            headers=self._headers(json_body=True),
            method="POST",
        )

        try:
            resp = urllib.request.urlopen(req, timeout=300)
        except urllib.error.HTTPError as exc:
            error_body = exc.read().decode("utf-8", errors="replace")
            try:
                err_data = json.loads(error_body)
                msg = err_data.get("error", {}).get("message", error_body)
            except json.JSONDecodeError:
                msg = error_body
            raise OpenRouterConnectionError(
                f"\n  [X] OpenRouter API error ({exc.code})\n"
                f"  {msg}"
            ) from exc
        except urllib.error.URLError as exc:
            raise OpenRouterConnectionError(
                f"\n  [X] Cannot reach OpenRouter API.\n"
                f"  Check your internet connection.\n"
                f"  Error: {exc}"
            ) from exc

        in_reasoning = False
        try:
            for raw_line in resp:
                line = raw_line.decode("utf-8", errors="replace").strip()
                if not line or line == "data: [DONE]":
                    continue
                if not line.startswith("data: "):
                    continue
                try:
                    chunk = json.loads(line[6:])
                except json.JSONDecodeError:
                    continue
                choices = chunk.get("choices", [])
                if not choices:
                    continue
                delta = choices[0].get("delta", {})

                # Handle reasoning tokens (Kimi K2.5 chain-of-thought)
                reasoning_token = delta.get("reasoning", "")
                content_token = delta.get("content", "")

                if reasoning_token:
                    if not in_reasoning:
                        yield "\033[2m\033[90m"  # DIM + GRAY
                        in_reasoning = True
                    yield reasoning_token

                if content_token:
                    if in_reasoning:
                        yield "\033[0m\n"  # Reset after reasoning
                        in_reasoning = False
                    yield content_token
        finally:
            if in_reasoning:
                yield "\033[0m\n"
            resp.close()

    # ── Internal helpers ──────────────────────────────────────────

    def _headers(self, json_body: bool = False) -> dict[str, str]:
        h: dict[str, str] = {
            "Authorization": f"Bearer {self.config.api_key}",
            "HTTP-Referer": "https://github.com/RAHUL-DevelopeRR/neuroncli",
            "X-Title": "NeuronCLI",
        }
        if json_body:
            h["Content-Type"] = "application/json"
        return h

    def _build_payload(
        self,
        messages: list[ChatMessage],
        model: str | None,
        stream: bool,
    ) -> dict:
        return {
            "model": model or self.config.model,
            "messages": [m.to_dict() for m in messages],
            "stream": stream,
            "max_tokens": self.config.max_tokens,
            "temperature": self.config.temperature,
            "top_p": self.config.top_p,
        }

    def _post(self, payload: dict) -> dict:
        body = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(
            f"{self.API_BASE}/chat/completions",
            data=body,
            headers=self._headers(json_body=True),
            method="POST",
        )
        try:
            with urllib.request.urlopen(req, timeout=300) as resp:
                return json.loads(resp.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            error_body = exc.read().decode("utf-8", errors="replace")
            try:
                err_data = json.loads(error_body)
                msg = err_data.get("error", {}).get("message", error_body)
            except json.JSONDecodeError:
                msg = error_body
            raise OpenRouterConnectionError(
                f"\n  [X] OpenRouter API error ({exc.code})\n"
                f"  {msg}"
            ) from exc
        except urllib.error.URLError as exc:
            raise OpenRouterConnectionError(
                f"\n  [X] Cannot reach OpenRouter API.\n"
                f"  Error: {exc}"
            ) from exc
