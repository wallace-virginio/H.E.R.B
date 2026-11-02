"""Enumeração de dispositivos de áudio."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass
class AudioDevice:
    index: int
    name: str
    max_input_channels: int
    max_output_channels: int
    default_samplerate: float


def list_devices() -> list[AudioDevice]:
    try:
        import sounddevice as sd
    except ImportError:
        return []

    devices: list[AudioDevice] = []
    for idx, info in enumerate(sd.query_devices()):
        devices.append(
            AudioDevice(
                index=idx,
                name=str(info.get("name", f"device-{idx}")),
                max_input_channels=int(info.get("max_input_channels", 0)),
                max_output_channels=int(info.get("max_output_channels", 0)),
                default_samplerate=float(info.get("default_samplerate", 16000)),
            )
        )
    return devices


def list_input_devices() -> list[AudioDevice]:
    return [d for d in list_devices() if d.max_input_channels > 0]


def list_output_devices() -> list[AudioDevice]:
    return [d for d in list_devices() if d.max_output_channels > 0]


def devices_summary() -> dict[str, Any]:
    return {
        "inputs": [{"index": d.index, "name": d.name} for d in list_input_devices()],
        "outputs": [{"index": d.index, "name": d.name} for d in list_output_devices()],
    }
