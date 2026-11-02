"""Cadastra amostra de voz do proprietário.

Uso:
  python scripts/enroll_speaker.py --seconds 4 --speaker owner
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def main() -> int:
    parser = argparse.ArgumentParser(description="Cadastro de locutor H.E.R.B.")
    parser.add_argument("--seconds", type=float, default=4.0)
    parser.add_argument("--speaker", default="owner")
    parser.add_argument("--owner", action="store_true", default=True)
    args = parser.parse_args()

    from app.audio.speaker import SpeakerRecognizer
    from app.config.settings import Settings

    settings = Settings.load()
    try:
        import sounddevice as sd
    except ImportError:
        print("Instale sounddevice primeiro (setup.bat).")
        return 1

    sr = settings.audio.sample_rate
    print(f"Gravando {args.seconds}s... Fale naturalmente.")
    audio = sd.rec(int(args.seconds * sr), samplerate=sr, channels=1, dtype="float32")
    sd.wait()
    mono = audio[:, 0]
    recognizer = SpeakerRecognizer(settings.speaker.samples_dir, settings.speaker.confidence_threshold)
    path = recognizer.enroll(args.speaker, mono, sr, is_owner=args.owner)
    print(f"Amostra salva: {path}")
    print("Dica: grave 3–5 amostras em ambientes diferentes para melhorar a confiança.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
