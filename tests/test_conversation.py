from __future__ import annotations

import pytest
import respx
from httpx import Response

from app.config.settings import Settings
from app.intelligence.conversation import ConversationManager
from app.intelligence.ollama_client import OllamaClient
from app.memory.store import MemoryStore


@pytest.mark.asyncio
@respx.mock
async def test_ask_persists_messages(tmp_path) -> None:
    respx.get("http://127.0.0.1:11434/api/tags").mock(
        return_value=Response(200, json={"models": [{"name": "llama3.2:3b"}]})
    )
    respx.post("http://127.0.0.1:11434/api/chat").mock(
        return_value=Response(200, json={"message": {"role": "assistant", "content": "Olá, humano."}})
    )
    settings = Settings()
    settings.memory.db_path = str(tmp_path / "herb.db")
    settings.ollama.primary_model = "llama3.2:3b"
    memory = MemoryStore(settings.memory.db_path)
    client = OllamaClient()
    mgr = ConversationManager(settings, memory, client)
    result = await mgr.ask("Oi HERB")
    await client.aclose()
    assert "Olá" in result["text"]
    msgs = memory.get_messages(mgr.conversation_id)
    assert msgs[-2].role == "user"
    assert msgs[-1].role == "assistant"


def test_extract_tool_call() -> None:
    raw = 'Claro.\n{"tool":"open_app","args":{"name":"calc"},"speak":"Abrindo a calculadora."}'
    call = ConversationManager._extract_tool_call(raw)
    assert call is not None
    assert call["tool"] == "open_app"
    assert call["args"]["name"] == "calc"
