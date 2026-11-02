"""Verificação detalhada do ambiente H.E.R.B."""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


async def main() -> int:
    from app.audio.devices import devices_summary
    from app.config.settings import Settings
    from app.intelligence.ollama_client import OllamaClient

    settings = Settings.load()
    print(f"Config: {ROOT / 'data' / 'config.json'}")
    print(f"Modelo primario: {settings.ollama.primary_model or '(nao definido)'}")
    print(f"Wake word: {settings.audio.wake_word}")
    print(f"Kokoro path: {settings.audio.kokoro_path or '(nao definido)'}")

    devices = devices_summary()
    print(f"Entradas de audio: {len(devices['inputs'])}")
    for d in devices["inputs"][:8]:
        print(f"  - {d['index']}: {d['name']}")
    print(f"Saidas de audio: {len(devices['outputs'])}")
    for d in devices["outputs"][:8]:
        print(f"  - {d['index']}: {d['name']}")

    client = OllamaClient(settings.ollama.host)
    try:
        ok = await client.health()
        print(f"Ollama health: {'OK' if ok else 'FALHA'}")
        if ok:
            models = await client.list_models()
            print("Modelos instalados:")
            for m in models:
                print(f"  - {m}")
            if not models:
                print("  (nenhum) — sugira: ollama pull llama3.2:3b")
    finally:
        await client.aclose()
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
