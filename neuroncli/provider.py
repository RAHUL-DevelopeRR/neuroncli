"""NeuronCLI — Provider abstraction. OpenRouter primary, Ollama fallback."""

from __future__ import annotations

from typing import Generator, Protocol

from .config import AgentConfig


class ChatMessage:
    """A single message in the conversation."""
    __slots__ = ("role", "content")

    def __init__(self, role: str, content: str):
        self.role = role
        self.content = content

    def to_dict(self) -> dict[str, str]:
        return {"role": self.role, "content": self.content}


class LLMProvider(Protocol):
    """Protocol for LLM backends."""
    def health_check(self) -> bool: ...
    def list_models(self) -> list[str]: ...
    def chat(self, messages: list, model: str | None = None) -> str: ...
    def chat_stream(self, messages: list, model: str | None = None) -> Generator[str, None, None]: ...


class ProviderConnectionError(Exception):
    """Raised when the active provider cannot be reached."""
    pass


def create_provider(config: AgentConfig):
    """
    Factory: returns the correct LLM client based on config.provider.
    Supports 'openrouter' (primary) and 'ollama' (fallback).
    """
    if config.provider == "ollama":
        from .ollama_client import OllamaClient
        return OllamaClient(config)
    else:
        from .openrouter_client import OpenRouterClient
        return OpenRouterClient(config)
