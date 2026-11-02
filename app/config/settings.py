"""Configurações tipadas do H.E.R.B. (Pydantic Settings)."""

from __future__ import annotations

import json
from enum import IntEnum
from functools import lru_cache
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

from .paths import get_paths


class AuthLevel(IntEnum):
    """Níveis de autorização para automações."""

    SIMPLE = 1
    MODIFY = 2
    CRITICAL = 3


class OllamaSettings(BaseModel):
    host: str = "http://127.0.0.1:11434"
    primary_model: str = ""
    alternate_model: str = ""
    temperature: float = 0.7
    max_tokens: int = 1024
    keep_alive: str = "5m"
    timeout_seconds: float = 120.0
    multimodal_model: str = ""


class AudioSettings(BaseModel):
    enabled: bool = True
    input_device: int | None = None
    output_device: int | None = None
    sample_rate: int = 16000
    channels: int = 1
    vad_threshold: float = 0.5
    silence_duration_ms: int = 800
    wake_word: str = "HERB"
    wake_word_enabled: bool = True
    wake_word_threshold: float = 0.5
    stt_model: str = "base"
    stt_compute_type: str = "int8"
    stt_device: str = "cpu"
    tts_enabled: bool = True
    tts_voice: str = "pf_dora"
    tts_speed: float = 1.0
    kokoro_path: str = ""
    kokoro_lang: str = "p"
    barge_in_enabled: bool = True
    mute_mic_while_speaking: bool = True


class SpeakerSettings(BaseModel):
    enabled: bool = False
    confidence_threshold: float = 0.75
    require_owner_for_critical: bool = False
    samples_dir: str = ""


class VisionSettings(BaseModel):
    enabled: bool = True
    ocr_lang: str = "por+eng"
    tesseract_cmd: str = ""
    use_multimodal: bool = False
    max_image_side: int = 1280


class AutomationSettings(BaseModel):
    enabled: bool = True
    auto_confirm_level: AuthLevel = AuthLevel.SIMPLE
    require_confirm_level: AuthLevel = AuthLevel.MODIFY
    action_timeout_seconds: float = 30.0
    emergency_stop: bool = False
    allowed_roots: list[str] = Field(default_factory=lambda: ["C:\\Users"])


class InterfaceSettings(BaseModel):
    opacity: float = 0.92
    always_on_top: bool = True
    width: int = 420
    height: int = 640
    start_minimized_to_tray: bool = False
    theme: str = "jarvis_dark"
    global_hotkey: str = "ctrl+alt+space"
    show_onboarding: bool = True


class MemorySettings(BaseModel):
    db_path: str = ""
    max_history_messages: int = 30
    retain_days: int = 90


class SecuritySettings(BaseModel):
    treat_screen_as_untrusted: bool = True
    log_all_actions: bool = True
    block_shell_passthrough: bool = True


class Settings(BaseSettings):
    """Configuração agregada do H.E.R.B."""

    model_config = SettingsConfigDict(
        env_prefix="HERB_",
        env_nested_delimiter="__",
        extra="ignore",
    )

    app_name: str = "H.E.R.B."
    language: str = "pt-BR"
    log_level: str = "INFO"
    first_run_completed: bool = False

    ollama: OllamaSettings = Field(default_factory=OllamaSettings)
    audio: AudioSettings = Field(default_factory=AudioSettings)
    speaker: SpeakerSettings = Field(default_factory=SpeakerSettings)
    vision: VisionSettings = Field(default_factory=VisionSettings)
    automation: AutomationSettings = Field(default_factory=AutomationSettings)
    interface: InterfaceSettings = Field(default_factory=InterfaceSettings)
    memory: MemorySettings = Field(default_factory=MemorySettings)
    security: SecuritySettings = Field(default_factory=SecuritySettings)

    @field_validator("log_level")
    @classmethod
    def _upper_log(cls, value: str) -> str:
        return value.upper()

    def resolve_paths(self) -> "Settings":
        paths = get_paths()
        data = self.model_dump()
        if not data["memory"]["db_path"]:
            data["memory"]["db_path"] = str(paths.memory / "herb.db")
        if not data["speaker"]["samples_dir"]:
            data["speaker"]["samples_dir"] = str(paths.speakers)
        return Settings.model_validate(data)

    def save(self, path: Path | None = None) -> Path:
        paths = get_paths()
        target = path or paths.config_file
        target.parent.mkdir(parents=True, exist_ok=True)
        payload = self.model_dump(mode="json")
        target.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
        return target

    @classmethod
    def load(cls, path: Path | None = None) -> "Settings":
        paths = get_paths()
        target = path or paths.config_file
        if target.exists():
            raw: dict[str, Any] = json.loads(target.read_text(encoding="utf-8"))
            settings = cls.model_validate(raw)
        else:
            settings = cls()
        return settings.resolve_paths()


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings.load()


def reload_settings() -> Settings:
    get_settings.cache_clear()
    return get_settings()
