"""Detecção de atividade vocal.

Tenta Silero VAD; fallback para energia RMS simples (sempre disponível).
"""

from __future__ import annotations

import numpy as np

from app.core.logging_setup import get_logger

logger = get_logger("vad")


class VoiceActivityDetector:
    def __init__(self, threshold: float = 0.5, sample_rate: int = 16000) -> None:
        self.threshold = threshold
        self.sample_rate = sample_rate
        self._silero = None
        self._backend = "energy"
        self._try_load_silero()

    def _try_load_silero(self) -> None:
        try:
            import torch

            model, utils = torch.hub.load(
                repo_or_dir="snakers4/silero-vad",
                model="silero_vad",
                trust_repo=True,
            )
            self._silero = model
            self._backend = "silero"
            logger.info("Silero VAD carregado.")
        except Exception as exc:
            logger.info("Usando VAD por energia (Silero indisponível: %s)", exc)

    @property
    def backend(self) -> str:
        return self._backend

    def is_speech(self, audio: np.ndarray) -> bool:
        if audio.size == 0:
            return False
        audio = audio.astype(np.float32)
        if self._silero is not None:
            try:
                import torch

                tensor = torch.from_numpy(audio)
                if tensor.ndim > 1:
                    tensor = tensor.mean(dim=-1)
                prob = float(self._silero(tensor, self.sample_rate).item())
                return prob >= self.threshold
            except Exception:
                pass
        # Fallback energia
        rms = float(np.sqrt(np.mean(np.square(audio))))
        # threshold 0.5 ~ mapeado para energia ~0.01-0.02
        energy_threshold = 0.01 + (1.0 - self.threshold) * 0.04
        return rms >= energy_threshold
