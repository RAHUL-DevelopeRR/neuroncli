"""NeuronCLI — Ollama HTTP streaming client. Zero external dependencies."""

from __future__ import annotations

import json
import urllib.error
import urllib.request
from dataclasses import dataclass
from typing import Generator

from .config import AgentConfig


class OllamaConnectionError(Exception):
    """Raised when the Ollama server is unreachable."""
    pass


@dataclass(frozen=True)
class ChatMessage:
    """A single message in the conversation."""
    role: str       # "system", "user", "assistant"
    content: str

    def to_dict(self) -> dict[str, str]:
        return {"role": self.role, "content": self.content}


class OllamaClient:
    """
    HTTP client for Ollama's /api/chat endpoint.
    Uses only stdlib — no pip dependencies needed.
    """

    def __init__(self, config: AgentConfig | None = None):
        self.config = config or AgentConfig.from_env()
        self._base = self.config.base_url.rstrip("/")

    def health_check(self) -> bool:
        """Check if Ollama server is responding."""
        try:
            req = urllib.request.Request(f"{self._base}/api/tags")
            with urllib.request.urlopen(req, timeout=5) as resp:
                return resp.status == 200
        except (urllib.error.URLError, OSError):
            return False

    def list_models(self) -> list[str]:
        """List locally installed model names."""
        try:
            req = urllib.request.Request(f"{self._base}/api/tags")
            with urllib.request.urlopen(req, timeout=5) as resp:
                data = json.loads(resp.read().decode())
                return [m["name"] for m in data.get("models", [])]
        except (urllib.error.URLError, OSError):
            return []

    def chat(self, messages: list[ChatMessage], model: str | None = None) -> str:
        """Send a chat request and return the full response text."""
        payload = self._build_payload(messages, model, stream=False)
        data = self._post("/api/chat", payload)
        return data.get("message", {}).get("content", "")

    def chat_stream(
        self,
        messages: list[ChatMessage],
        model: str | None = None,
    ) -> Generator[str, None, None]:
        """
        Stream a chat response token by token.
        Yields individual tokens as strings.
        """
        payload = self._build_payload(messages, model, stream=True)
        body = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(
            f"{self._base}/api/chat",
            data=body,
            headers={"Content-Type": "application/json"},
            method="POST",
        )

        try:
            resp = urllib.request.urlopen(req, timeout=300)
        except urllib.error.URLError as exc:
            raise OllamaConnectionError(
                f"\n  [X] Cannot connect to Ollama at {self._base}\n"
                f"  Start it with: ollama serve\n"
                f"  Error: {exc}"
            ) from exc

        buffer = b""
        try:
            while True:
                byte = resp.read(1)
                if not byte:
                    break
                buffer += byte
                if byte == b"\n":
                    line = buffer.decode("utf-8", errors="replace").strip()
                    buffer = b""
                    if not line:
                        continue
                    try:
                        data = json.loads(line)
                    except json.JSONDecodeError:
                        continue
                    token = data.get("message", {}).get("content", "")
                    if token:
                        yield token
                    if data.get("done", False):
                        break
        finally:
            resp.close()

    # ── Internal helpers ──────────────────────────────────────────

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
            "options": {
                "temperature": self.config.temperature,
                "top_p": self.config.top_p,
                "num_ctx": self.config.num_ctx,
            },
        }

    def _post(self, path: str, payload: dict) -> dict:
        body = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(
            f"{self._base}{path}",
            data=body,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            with urllib.request.urlopen(req, timeout=300) as resp:
                return json.loads(resp.read().decode("utf-8"))
        except urllib.error.URLError as exc:
            raise OllamaConnectionError(
                f"\n  [X] Cannot connect to Ollama at {self._base}\n"
                f"  Start it with: ollama serve\n"
                f"  Error: {exc}"
            ) from exc
