"""Detecção de palavra-chave (HERB).

Prioridade:
1. openWakeWord (se modelo disponível)
2. Fallback: STT curto + match textual da wake word
"""

from __future__ import annotations

from typing import Any

import numpy as np

from app.core.logging_setup import get_logger

logger = get_logger("wakeword")


class WakeWordDetector:
    def __init__(self, wake_word: str = "HERB", threshold: float = 0.5) -> None:
        self.wake_word = wake_word.strip().lower()
        self.threshold = threshold
        self._oww: Any = None
        self._backend = "text"
        self._try_openwakeword()

    def _try_openwakeword(self) -> None:
        try:
            import openwakeword  # noqa: F401

            # Pacote presente. Modelo customizado "HERB" ainda não é distribuído;
            # a detecção efetiva usa match textual via STT (ver docs/VOICE.md).
            # Não instanciamos Model() sem arquivos .onnx válidos para evitar erros.
            self._oww = None
            self._backend = "openwakeword-ready+text"
            logger.info(
                "openWakeWord instalado. Wake word '%s' ativa via match textual "
                "até existir modelo ONNX dedicado.",
                self.wake_word,
            )
        except Exception as exc:
            logger.info("Wake word textual ativa (openWakeWord indisponível: %s)", exc)
            self._backend = "text"

    @property
    def backend(self) -> str:
        return self._backend

    def match_text(self, text: str) -> bool:
        normalized = "".join(ch for ch in text.lower() if ch.isalnum() or ch.isspace())
        tokens = normalized.split()
        target = self.wake_word.lower()
        if target in normalized:
            return True
        # tolerância a variações: herb / herbe / erbe
        aliases = {target, "herb", "herbe", "erb", "erve"}
        return any(tok in aliases for tok in tokens)

    def strip_wake_word(self, text: str) -> str:
        lower = text.lower()
        for alias in (self.wake_word.lower(), "herb", "herbe"):
            idx = lower.find(alias)
            if idx >= 0:
                return (text[:idx] + text[idx + len(alias) :]).strip(" ,.-:")
        return text.strip()

    def process_audio(self, audio: np.ndarray) -> float:
        """Retorna score 0..1. Sem modelo customizado, retorna 0 (use match_text)."""
        if self._oww is None:
            return 0.0
        try:
            preds = self._oww.predict(audio)
            if not preds:
                return 0.0
            return float(max(preds.values()))
        except Exception:
            return 0.0
