"""NeuronCLI — AI Coding Agent powered by Kimi K2.5 + Ollama."""

from .config import AgentConfig, APP_NAME, VERSION
from .agent import Agent, AgentResult
from .provider import ChatMessage, create_provider
from .tools import registry as tool_registry

__version__ = VERSION
__all__ = [
    "Agent",
    "AgentConfig",
    "AgentResult",
    "ChatMessage",
    "create_provider",
    "tool_registry",
]
