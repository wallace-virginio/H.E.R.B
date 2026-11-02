"""Reconhecimento local de locutor (arquitetura v0.1).

Implementação pragmática baseada em embedding MFCC médio + distância cosseno.
NÃO deve ser usado como autenticação suficiente para ações sensíveis.

Status:
- Cadastro de amostras: IMPLEMENTADO
- Comparação local: IMPLEMENTADO (baseline)
- Multi-locutor: PREPARADO
- Robustez produção: PARCIAL (depende de qualidade/quantidade das amostras)
"""

from __future__ import annotations

import json
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np

from app.core.logging_setup import get_logger

logger = get_logger("speaker")


@dataclass
class SpeakerMatch:
    speaker_id: str
    confidence: float
    is_owner: bool


class SpeakerRecognizer:
    def __init__(self, samples_dir: str | Path, confidence_threshold: float = 0.75) -> None:
        self.samples_dir = Path(samples_dir)
        self.samples_dir.mkdir(parents=True, exist_ok=True)
        self.confidence_threshold = confidence_threshold
        self._index_file = self.samples_dir / "speakers.json"
        self._index = self._load_index()

    def _load_index(self) -> dict[str, Any]:
        if self._index_file.exists():
            return json.loads(self._index_file.read_text(encoding="utf-8"))
        return {"speakers": {}}

    def _save_index(self) -> None:
        self._index_file.write_text(
            json.dumps(self._index, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )

    def list_speakers(self) -> list[str]:
        return sorted(self._index.get("speakers", {}).keys())

    def enroll(
        self,
        speaker_id: str,
        audio: np.ndarray,
        sample_rate: int = 16000,
        *,
        is_owner: bool = False,
    ) -> Path:
        """Cadastra uma amostra e atualiza o embedding médio do locutor."""
        speaker_dir = self.samples_dir / speaker_id
        speaker_dir.mkdir(parents=True, exist_ok=True)
        emb = self._embed(audio, sample_rate)
        ts = int(time.time())
        sample_path = speaker_dir / f"sample_{ts}.npy"
        np.save(sample_path, emb)

        info = self._index.setdefault("speakers", {}).setdefault(
            speaker_id,
            {"is_owner": is_owner, "embeddings": []},
        )
        info["is_owner"] = bool(is_owner or info.get("is_owner"))
        info["embeddings"].append(str(sample_path))
        # Recalcula média
        vectors = [np.load(p) for p in info["embeddings"] if Path(p).exists()]
        if vectors:
            mean = np.mean(np.stack(vectors), axis=0)
            mean_path = speaker_dir / "centroid.npy"
            np.save(mean_path, mean)
            info["centroid"] = str(mean_path)
        self._save_index()
        logger.info("Amostra cadastrada para locutor %s", speaker_id)
        return sample_path

    def identify(self, audio: np.ndarray, sample_rate: int = 16000) -> SpeakerMatch | None:
        speakers = self._index.get("speakers") or {}
        if not speakers:
            return None
        query = self._embed(audio, sample_rate)
        best_id = ""
        best_score = -1.0
        best_owner = False
        for sid, info in speakers.items():
            centroid_path = info.get("centroid")
            if not centroid_path or not Path(centroid_path).exists():
                continue
            centroid = np.load(centroid_path)
            score = self._cosine(query, centroid)
            if score > best_score:
                best_score = score
                best_id = sid
                best_owner = bool(info.get("is_owner"))
        if best_score < self.confidence_threshold:
            return None
        return SpeakerMatch(speaker_id=best_id, confidence=float(best_score), is_owner=best_owner)

    def _embed(self, audio: np.ndarray, sample_rate: int) -> np.ndarray:
        """Embedding leve: estatísticas de MFCC (librosa se disponível) ou FFT bins."""
        audio = audio.astype(np.float32)
        if audio.ndim > 1:
            audio = audio.mean(axis=-1)
        try:
            import librosa

            mfcc = librosa.feature.mfcc(y=audio, sr=sample_rate, n_mfcc=20)
            emb = np.concatenate([mfcc.mean(axis=1), mfcc.std(axis=1)])
            return emb.astype(np.float32)
        except Exception:
            # Fallback: espectro médio normalizado
            n = 512
            if audio.size < n:
                audio = np.pad(audio, (0, n - audio.size))
            windowed = audio[: len(audio) - (len(audio) % n)].reshape(-1, n)
            spec = np.abs(np.fft.rfft(windowed, axis=1)).mean(axis=0)
            norm = np.linalg.norm(spec) + 1e-8
            return (spec / norm).astype(np.float32)

    @staticmethod
    def _cosine(a: np.ndarray, b: np.ndarray) -> float:
        denom = (np.linalg.norm(a) * np.linalg.norm(b)) + 1e-8
        return float(np.dot(a, b) / denom)
