from __future__ import annotations

from pathlib import Path

from app.config.personality import load_personality


def test_load_default_personality() -> None:
    personality = load_personality()
    assert "H.E.R.B" in personality.name or personality.name == "H.E.R.B."
    prompt = personality.build_system_message()
    assert "português" in prompt.lower() or "brasileiro" in prompt.lower() or len(prompt) > 20


def test_custom_personality_file(tmp_path: Path) -> None:
    path = tmp_path / "p.yaml"
    path.write_text(
        "name: TEST\nsystem_prompt: |\n  Voce e um teste.\ntraits:\n  - objetivo\n",
        encoding="utf-8",
    )
    personality = load_personality(path)
    assert personality.name == "TEST"
    assert "teste" in personality.build_system_message().lower()
