from __future__ import annotations

from pathlib import Path

from app.config.settings import AuthLevel, Settings


def test_settings_roundtrip(tmp_path: Path) -> None:
    cfg = tmp_path / "config.json"
    settings = Settings()
    settings.ollama.primary_model = "llama3.2:3b"
    settings.audio.wake_word = "HERB"
    settings.automation.auto_confirm_level = AuthLevel.SIMPLE
    settings.save(cfg)

    loaded = Settings.load(cfg)
    assert loaded.ollama.primary_model == "llama3.2:3b"
    assert loaded.audio.wake_word == "HERB"
    assert loaded.automation.auto_confirm_level == AuthLevel.SIMPLE


def test_default_paths_resolved(tmp_path: Path, monkeypatch) -> None:
    from app.config import paths as paths_mod

    monkeypatch.setattr(paths_mod, "_paths", None)
    p = paths_mod.get_paths(tmp_path)
    assert p.data == tmp_path / "data"
    assert p.memory.exists()
