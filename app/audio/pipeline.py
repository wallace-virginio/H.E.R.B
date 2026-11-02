"""Pipeline de voz do H.E.R.B."""

from __future__ import annotations

import asyncio
import threading
import time
from collections.abc import Awaitable, Callable
from typing import Any

import numpy as np

from app.config.settings import Settings
from app.core.events import EventBus, EventType
from app.core.logging_setup import get_logger

from .speaker import SpeakerRecognizer
from .stt import SpeechToText
from .tts import TextToSpeech
from .vad import VoiceActivityDetector
from .wakeword import WakeWordDetector

logger = get_logger("audio.pipeline")

OnTranscription = Callable[[str, dict[str, Any]], Awaitable[None] | None]


class AudioPipeline:
    def __init__(self, settings: Settings, bus: EventBus) -> None:
        self.settings = settings
        self.bus = bus
        self.mic_enabled = settings.audio.enabled
        self._listening = False
        self._thread: threading.Thread | None = None
        self._stop = threading.Event()
        self._muted_for_playback = False
        self._push_to_talk = False
        self._on_transcription: OnTranscription | None = None

        audio = settings.audio
        self.vad = VoiceActivityDetector(audio.vad_threshold, audio.sample_rate)
        self.wake = WakeWordDetector(audio.wake_word, audio.wake_word_threshold)
        self.stt = SpeechToText(audio.stt_model, audio.stt_device, audio.stt_compute_type)
        self.tts = TextToSpeech(
            voice=audio.tts_voice,
            speed=audio.tts_speed,
            kokoro_path=audio.kokoro_path,
            lang=audio.kokoro_lang,
        )
        self.speaker = SpeakerRecognizer(
            settings.speaker.samples_dir or "data/speakers",
            settings.speaker.confidence_threshold,
        )

    def set_transcription_handler(self, handler: OnTranscription) -> None:
        self._on_transcription = handler

    def start(self) -> None:
        if not self.settings.audio.enabled:
            logger.info("Áudio desabilitado nas configurações.")
            return
        if self._listening:
            return
        self._stop.clear()
        self._listening = True
        self._thread = threading.Thread(target=self._listen_loop, name="herb-audio", daemon=True)
        self._thread.start()
        self.bus.emit_simple(EventType.LISTENING, active=True)
        logger.info("Pipeline de áudio iniciado.")

    def stop(self) -> None:
        self._stop.set()
        self._listening = False
        self.tts.stop()
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=2)
        self.bus.emit_simple(EventType.LISTENING, active=False)

    def toggle_mic(self) -> bool:
        self.mic_enabled = not self.mic_enabled
        self.bus.emit_simple(EventType.MIC_TOGGLED, enabled=self.mic_enabled)
        return self.mic_enabled

    def trigger_listen_once(self) -> None:
        """Ativação por atalho (equivalente a push-to-talk + wake)."""
        self._push_to_talk = True
        self.bus.emit_simple(EventType.HOTKEY, action="listen")

    def interrupt_speech(self) -> None:
        self.tts.stop()
        self._muted_for_playback = False

    async def speak(self, text: str) -> None:
        if not self.settings.audio.tts_enabled:
            return
        self.bus.emit_simple(EventType.SPEAKING, active=True, text=text)
        if self.settings.audio.mute_mic_while_speaking:
            self._muted_for_playback = True
        try:
            await self.tts.speak(text, output_device=self.settings.audio.output_device)
        finally:
            # pequena folga para evitar eco
            await asyncio.sleep(0.25)
            self._muted_for_playback = False
            self.bus.emit_simple(EventType.SPEAKING, active=False)

    def enroll_owner(self, audio: np.ndarray, speaker_id: str = "owner") -> str:
        path = self.speaker.enroll(speaker_id, audio, self.settings.audio.sample_rate, is_owner=True)
        return str(path)

    def _listen_loop(self) -> None:
        try:
            import sounddevice as sd
        except ImportError:
            logger.error("sounddevice não instalado — pipeline de áudio inativo.")
            return

        sr = self.settings.audio.sample_rate
        block = int(sr * 0.5)  # 500ms
        buffer: list[np.ndarray] = []
        speech_ms = 0
        silence_ms = 0
        capturing = False
        wake_armed = False

        def callback(indata, frames, time_info, status):  # noqa: ANN001
            nonlocal buffer, speech_ms, silence_ms, capturing, wake_armed
            if status:
                logger.debug("Audio status: %s", status)
            if not self.mic_enabled or self._muted_for_playback:
                return
            mono = indata[:, 0].copy() if indata.ndim > 1 else indata.copy()
            is_speech = self.vad.is_speech(mono)

            if self._push_to_talk:
                wake_armed = True
                capturing = True
                self._push_to_talk = False
                buffer = [mono]
                speech_ms = 500
                silence_ms = 0
                return

            if not capturing:
                buffer.append(mono)
                # Mantém ~2s para wake
                max_blocks = int(2.0 / 0.5)
                if len(buffer) > max_blocks:
                    buffer = buffer[-max_blocks:]
                if is_speech and self.settings.audio.wake_word_enabled:
                    # Transcreve janela curta periodicamente é custoso;
                    # aqui acumulamos e avaliamos quando silêncio chega.
                    speech_ms += 500
                    if speech_ms >= 800:
                        audio = np.concatenate(buffer)
                        self._maybe_wake(audio)
                        speech_ms = 0
                else:
                    speech_ms = 0
                if wake_armed:
                    capturing = True
                    buffer = [mono]
                    silence_ms = 0
                return

            # Capturando comando após wake/hotkey
            buffer.append(mono)
            if is_speech:
                silence_ms = 0
            else:
                silence_ms += 500
            if silence_ms >= self.settings.audio.silence_duration_ms:
                audio = np.concatenate(buffer)
                buffer = []
                capturing = False
                wake_armed = False
                silence_ms = 0
                threading.Thread(
                    target=self._handle_utterance,
                    args=(audio,),
                    daemon=True,
                ).start()

        try:
            with sd.InputStream(
                samplerate=sr,
                channels=1,
                dtype="float32",
                blocksize=block,
                device=self.settings.audio.input_device,
                callback=callback,
            ):
                while not self._stop.is_set():
                    time.sleep(0.1)
        except Exception:
            logger.exception("Falha no stream de microfone")
            self.bus.emit_simple(EventType.ERROR, message="Falha no microfone. Verifique o dispositivo de áudio.")

    def _maybe_wake(self, audio: np.ndarray) -> None:
        try:
            # Match barato via STT só se VAD detectou fala contínua
            text = self.stt.transcribe(audio, self.settings.audio.sample_rate)
            if self.wake.match_text(text):
                logger.info("Wake word detectada via texto: %s", text)
                self.bus.emit_simple(EventType.WAKE_WORD, text=text)
                # Sinaliza captura do restante
                self._push_to_talk = True
        except Exception:
            logger.exception("Falha na detecção de wake word")

    def _handle_utterance(self, audio: np.ndarray) -> None:
        try:
            self.bus.emit_simple(EventType.PROCESSING, active=True)
            text = self.stt.transcribe(audio, self.settings.audio.sample_rate)
            text = self.wake.strip_wake_word(text)
            meta: dict[str, Any] = {}
            if self.settings.speaker.enabled:
                match = self.speaker.identify(audio, self.settings.audio.sample_rate)
                if match:
                    meta["speaker_id"] = match.speaker_id
                    meta["speaker_confidence"] = match.confidence
                    meta["is_owner"] = match.is_owner
            if not text:
                return
            if self._on_transcription:
                result = self._on_transcription(text, meta)
                if asyncio.iscoroutine(result):
                    asyncio.run(result)
        except Exception as exc:
            logger.exception("Falha ao processar fala")
            self.bus.emit_simple(EventType.ERROR, message=f"Erro no reconhecimento de voz: {exc}")
        finally:
            self.bus.emit_simple(EventType.PROCESSING, active=False)
