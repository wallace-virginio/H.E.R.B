"""Camada de inteligência (Ollama + conversas)."""

from .ollama_client import OllamaClient, OllamaError
from .conversation import ConversationManager

__all__ = ["OllamaClient", "OllamaError", "ConversationManager"]
