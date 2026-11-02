"""Speech-to-Text com Faster-Whisper (CPU INT8)."""

from __future__ import annotations

from typing import Any

import numpy as np

from app.core.logging_setup import get_logger

logger = get_logger("stt")


class SpeechToText:
    def __init__(
        self,
        model_size: str = "base",
        device: str = "cpu",
        compute_type: str = "int8",
        language: str = "pt",
    ) -> None:
        self.model_size = model_size
        self.device = device
        self.compute_type = compute_type
        self.language = language
        self._model: Any = None

    def load(self) -> None:
        if self._model is not None:
            return
        from faster_whisper import WhisperModel

        logger.info(
            "Carregando Faster-Whisper %s (%s/%s)...",
            self.model_size,
            self.device,
            self.compute_type,
        )
        self._model = WhisperModel(
            self.model_size,
            device=self.device,
            compute_type=self.compute_type,
        )

    def unload(self) -> None:
        self._model = None

    def transcribe(self, audio: np.ndarray, sample_rate: int = 16000) -> str:
        self.load()
        assert self._model is not None
        if audio.dtype != np.float32:
            audio = audio.astype(np.float32)
        # Normaliza se vier em int16 escala
        if audio.max() > 1.0 or audio.min() < -1.0:
            audio = audio / 32768.0
        segments, _info = self._model.transcribe(
            audio,
            language=self.language,
            vad_filter=True,
            beam_size=1,
        )
        text = " ".join(seg.text.strip() for seg in segments).strip()
        logger.debug("STT: %s", text)
        return text
