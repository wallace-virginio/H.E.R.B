from __future__ import annotations

from pathlib import Path

from app.memory.store import MemoryStore


def test_conversation_persistence(tmp_path: Path) -> None:
    store = MemoryStore(tmp_path / "herb.db")
    conv = store.create_conversation("Teste")
    store.add_message(conv.id, "user", "Olá")
    store.add_message(conv.id, "assistant", "Oi. Em que posso ser útil... ou divertido.")
    messages = store.get_messages(conv.id)
    assert len(messages) == 2
    assert messages[0].role == "user"
    assert messages[1].role == "assistant"


def test_preferences_and_notes(tmp_path: Path) -> None:
    store = MemoryStore(tmp_path / "herb.db")
    store.set_preference("theme", "jarvis_dark")
    assert store.get_preference("theme") == "jarvis_dark"
    store.add_note("Gosto de respostas curtas", tags=["pref"])
    notes = store.search_notes("respostas")
    assert len(notes) == 1


def test_action_log(tmp_path: Path) -> None:
    store = MemoryStore(tmp_path / "herb.db")
    store.log_action("open_app", {"name": "calc"}, 1, "ok", "Abrindo")
    actions = store.list_actions()
    assert actions[0].tool_name == "open_app"
