"""Text-to-Speech via Kokoro (local).

Estratégia:
1. Tenta `kokoro` / `kokoro_onnx` se instalados.
2. Se `kokoro_path` apontar para um projeto local, tenta importar dali.
3. Fallback: Windows SAPI (pyttsx3 ou powershell) — ainda local, sem nuvem.
"""

from __future__ import annotations

import asyncio
import sys
import tempfile
import wave
from pathlib import Path
from typing import Any

import numpy as np

from app.core.logging_setup import get_logger

logger = get_logger("tts")


class TextToSpeech:
    def __init__(
        self,
        voice: str = "pf_dora",
        speed: float = 1.0,
        kokoro_path: str = "",
        lang: str = "p",
        sample_rate: int = 24000,
    ) -> None:
        self.voice = voice
        self.speed = speed
        self.kokoro_path = kokoro_path
        self.lang = lang
        self.sample_rate = sample_rate
        self._pipeline: Any = None
        self._backend = "none"
        self._playing = False
        self._stop_flag = False

    @property
    def backend(self) -> str:
        return self._backend

    @property
    def is_speaking(self) -> bool:
        return self._playing

    def load(self) -> None:
        if self._pipeline is not None:
            return
        if self.kokoro_path:
            path = Path(self.kokoro_path)
            if path.exists() and str(path) not in sys.path:
                sys.path.insert(0, str(path))

        # Tentativa 1: kokoro-onnx
        try:
            from kokoro_onnx import Kokoro  # type: ignore

            model = path_join_first(self.kokoro_path, "kokoro-v1.0.onnx", "model.onnx")
            voices = path_join_first(self.kokoro_path, "voices.bin", "voices.npz")
            if model and voices:
                self._pipeline = Kokoro(model, voices)
                self._backend = "kokoro_onnx"
                logger.info("Kokoro ONNX carregado.")
                return
        except Exception as exc:
            logger.debug("kokoro_onnx indisponível: %s", exc)

        # Tentativa 2: pacote kokoro
        try:
            from kokoro import KPipeline  # type: ignore

            self._pipeline = KPipeline(lang_code=self.lang)
            self._backend = "kokoro"
            logger.info("Kokoro pipeline carregado.")
            return
        except Exception as exc:
            logger.debug("kokoro indisponível: %s", exc)

        # Fallback local Windows
        self._backend = "sapi"
        self._pipeline = "sapi"
        logger.warning(
            "Kokoro não encontrado. Usando voz SAPI do Windows como fallback local. "
            "Configure audio.kokoro_path no config.json."
        )

    def stop(self) -> None:
        self._stop_flag = True

    def synthesize(self, text: str) -> tuple[np.ndarray, int]:
        self.load()
        self._stop_flag = False
        if self._backend == "kokoro_onnx":
            samples, sr = self._pipeline.create(text, voice=self.voice, speed=self.speed, lang=self.lang)
            return np.asarray(samples, dtype=np.float32), int(sr)
        if self._backend == "kokoro":
            audio_parts: list[np.ndarray] = []
            sr = self.sample_rate
            for _gs, _ps, audio in self._pipeline(text, voice=self.voice, speed=self.speed):
                audio_parts.append(np.asarray(audio, dtype=np.float32))
                sr = getattr(audio, "sample_rate", sr) if hasattr(audio, "sample_rate") else sr
            if not audio_parts:
                return np.zeros(0, dtype=np.float32), sr
            return np.concatenate(audio_parts), sr
        # SAPI: gera wav temporário via PowerShell
        return self._sapi_synth(text)

    def _sapi_synth(self, text: str) -> tuple[np.ndarray, int]:
        import subprocess

        out = Path(tempfile.gettempdir()) / "herb_tts.wav"
        safe = text.replace("'", "''")
        ps = (
            f"Add-Type -AssemblyName System.Speech; "
            f"$s = New-Object System.Speech.Synthesis.SpeechSynthesizer; "
            f"$s.Rate = {max(-10, min(10, int((self.speed - 1) * 5)))}; "
            f"$s.SetOutputToWaveFile('{out}'); "
            f"$s.Speak('{safe}'); "
            f"$s.Dispose()"
        )
        subprocess.run(
            ["powershell", "-NoProfile", "-Command", ps],
            check=False,
            capture_output=True,
            text=True,
        )
        if not out.exists():
            return np.zeros(0, dtype=np.float32), 22050
        with wave.open(str(out), "rb") as wf:
            sr = wf.getframerate()
            frames = wf.readframes(wf.getnframes())
            audio = np.frombuffer(frames, dtype=np.int16).astype(np.float32) / 32768.0
        return audio, sr

    async def speak(self, text: str, output_device: int | None = None) -> None:
        if not text.strip():
            return
        audio, sr = await asyncio.to_thread(self.synthesize, text)
        if audio.size == 0 or self._stop_flag:
            return
        await asyncio.to_thread(self._play, audio, sr, output_device)

    def _play(self, audio: np.ndarray, sample_rate: int, output_device: int | None) -> None:
        try:
            import sounddevice as sd
        except ImportError as exc:
            raise RuntimeError("sounddevice não instalado") from exc

        self._playing = True
        self._stop_flag = False
        try:
            sd.play(audio, sample_rate, device=output_device)
            # Permite barge-in / stop
            while sd.get_stream().active:
                if self._stop_flag:
                    sd.stop()
                    break
                sd.sleep(50)
        finally:
            self._playing = False


def path_join_first(base: str, *names: str) -> str | None:
    if not base:
        return None
    root = Path(base)
    for name in names:
        candidate = root / name
        if candidate.exists():
            return str(candidate)
        # procura um nível abaixo
        matches = list(root.rglob(name))
        if matches:
            return str(matches[0])
    return None
