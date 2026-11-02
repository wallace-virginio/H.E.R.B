from __future__ import annotations

from pathlib import Path

import pytest
import respx
from httpx import Response

from app.config.settings import Settings
from app.core.app_core import HerbCore


@pytest.fixture
def core(tmp_path: Path, monkeypatch) -> HerbCore:
    from app.config import paths as paths_mod

    monkeypatch.setattr(paths_mod, "_paths", None)
    paths_mod.get_paths(tmp_path)
    settings = Settings()
    settings.memory.db_path = str(tmp_path / "herb.db")
    settings.speaker.samples_dir = str(tmp_path / "speakers")
    settings.audio.enabled = False
    settings.audio.tts_enabled = False
    settings.first_run_completed = True
    settings.ollama.primary_model = "llama3.2:3b"
    return HerbCore(settings)


@pytest.mark.asyncio
@respx.mock
async def test_local_system_status(core: HerbCore) -> None:
    reply = await core.handle_user_message("como está meu computador")
    assert "CPU" in reply or "RAM" in reply


@pytest.mark.asyncio
@respx.mock
async def test_chat_via_ollama(core: HerbCore) -> None:
    respx.post("http://127.0.0.1:11434/api/chat").mock(
        return_value=Response(
            200,
            json={"message": {"role": "assistant", "content": "Estou por aqui."}},
        )
    )
    reply = await core.handle_user_message("Tudo bem?")
    assert "aqui" in reply.lower()
    await core.ollama.aclose()


@pytest.mark.asyncio
async def test_remember_note(core: HerbCore) -> None:
    reply = await core.handle_user_message("lembrar: meu editor favorito e o Cursor")
    assert "Anotado" in reply
    notes = core.memory.search_notes("Cursor")
    assert notes
    await core.ollama.aclose()
