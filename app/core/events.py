"""Barramento de eventos simples (desacopla UI, áudio e núcleo)."""

from __future__ import annotations

import asyncio
import threading
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Awaitable, Callable


class EventType(str, Enum):
    MESSAGE_USER = "message.user"
    MESSAGE_ASSISTANT = "message.assistant"
    STATUS = "status"
    LISTENING = "listening"
    PROCESSING = "processing"
    SPEAKING = "speaking"
    ERROR = "error"
    CONFIRMATION_REQUIRED = "confirmation.required"
    CONFIRMATION_RESULT = "confirmation.result"
    HOTKEY = "hotkey"
    WAKE_WORD = "wake_word"
    MIC_TOGGLED = "mic.toggled"
    EMERGENCY_STOP = "emergency.stop"
    SCREEN_CONTEXT = "screen.context"
    READY = "ready"
    SHUTDOWN = "shutdown"


@dataclass
class HerbEvent:
    type: EventType
    payload: dict[str, Any] = field(default_factory=dict)
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


Listener = Callable[[HerbEvent], Any] | Callable[[HerbEvent], Awaitable[Any]]


class EventBus:
    """Pub/sub thread-safe com suporte a callbacks sync/async."""

    def __init__(self) -> None:
        self._listeners: dict[EventType | str, list[Listener]] = defaultdict(list)
        self._lock = threading.RLock()

    def subscribe(self, event_type: EventType | str, listener: Listener) -> None:
        with self._lock:
            self._listeners[event_type].append(listener)

    def unsubscribe(self, event_type: EventType | str, listener: Listener) -> None:
        with self._lock:
            if listener in self._listeners[event_type]:
                self._listeners[event_type].remove(listener)

    def emit(self, event: HerbEvent) -> None:
        with self._lock:
            listeners = list(self._listeners.get(event.type, []))
            listeners += list(self._listeners.get("*", []))
        for listener in listeners:
            try:
                result = listener(event)
                if asyncio.iscoroutine(result):
                    try:
                        loop = asyncio.get_running_loop()
                        loop.create_task(result)
                    except RuntimeError:
                        asyncio.run(result)
            except Exception:
                # Listener não deve derrubar o barramento; log externo.
                get_logger = __import__("app.core.logging_setup", fromlist=["get_logger"]).get_logger
                get_logger("events").exception("Falha em listener de %s", event.type)

    def emit_simple(self, event_type: EventType, **payload: Any) -> None:
        self.emit(HerbEvent(type=event_type, payload=payload))
