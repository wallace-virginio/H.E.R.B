"""Modelos de memória."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class Message(BaseModel):
    id: int | None = None
    conversation_id: str
    role: str
    content: str
    created_at: datetime | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class Conversation(BaseModel):
    id: str
    title: str = "Conversa"
    created_at: datetime | None = None
    updated_at: datetime | None = None
    archived: bool = False


class Preference(BaseModel):
    key: str
    value: Any
    updated_at: datetime | None = None


class ActionLog(BaseModel):
    id: int | None = None
    tool_name: str
    args: dict[str, Any] = Field(default_factory=dict)
    level: int = 1
    status: str = "pending"
    result: str = ""
    created_at: datetime | None = None


class MemoryNote(BaseModel):
    """Nota autorizada pelo usuário (base futura para RAG)."""

    id: int | None = None
    content: str
    tags: list[str] = Field(default_factory=list)
    created_at: datetime | None = None
