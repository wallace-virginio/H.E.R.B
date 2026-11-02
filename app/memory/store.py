"""Armazenamento SQLite da memória do H.E.R.B."""

from __future__ import annotations

import json
import sqlite3
import threading
import uuid
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterator

from .models import ActionLog, Conversation, MemoryNote, Message, Preference


def _utcnow() -> str:
    return datetime.now(timezone.utc).isoformat()


class MemoryStore:
    """Persistência local com schema preparado para futura expansão RAG."""

    def __init__(self, db_path: str | Path) -> None:
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.RLock()
        self._init_schema()

    @contextmanager
    def _conn(self) -> Iterator[sqlite3.Connection]:
        with self._lock:
            conn = sqlite3.connect(self.db_path, check_same_thread=False)
            conn.row_factory = sqlite3.Row
            try:
                yield conn
                conn.commit()
            except Exception:
                conn.rollback()
                raise
            finally:
                conn.close()

    def _init_schema(self) -> None:
        with self._conn() as conn:
            conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS conversations (
                    id TEXT PRIMARY KEY,
                    title TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    archived INTEGER NOT NULL DEFAULT 0
                );

                CREATE TABLE IF NOT EXISTS messages (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    conversation_id TEXT NOT NULL,
                    role TEXT NOT NULL,
                    content TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    metadata TEXT NOT NULL DEFAULT '{}',
                    FOREIGN KEY(conversation_id) REFERENCES conversations(id)
                );

                CREATE TABLE IF NOT EXISTS preferences (
                    key TEXT PRIMARY KEY,
                    value TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS action_logs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    tool_name TEXT NOT NULL,
                    args TEXT NOT NULL,
                    level INTEGER NOT NULL,
                    status TEXT NOT NULL,
                    result TEXT NOT NULL,
                    created_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS memory_notes (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    content TEXT NOT NULL,
                    tags TEXT NOT NULL DEFAULT '[]',
                    created_at TEXT NOT NULL,
                    embedding_placeholder TEXT
                );

                CREATE INDEX IF NOT EXISTS idx_messages_conv
                    ON messages(conversation_id, created_at);
                """
            )

    def create_conversation(self, title: str = "Conversa") -> Conversation:
        cid = str(uuid.uuid4())
        now = _utcnow()
        with self._conn() as conn:
            conn.execute(
                "INSERT INTO conversations(id, title, created_at, updated_at) VALUES (?,?,?,?)",
                (cid, title, now, now),
            )
        return Conversation(id=cid, title=title, created_at=datetime.fromisoformat(now), updated_at=datetime.fromisoformat(now))

    def list_conversations(self, include_archived: bool = False) -> list[Conversation]:
        sql = "SELECT * FROM conversations"
        if not include_archived:
            sql += " WHERE archived = 0"
        sql += " ORDER BY updated_at DESC"
        with self._conn() as conn:
            rows = conn.execute(sql).fetchall()
        return [
            Conversation(
                id=r["id"],
                title=r["title"],
                created_at=datetime.fromisoformat(r["created_at"]),
                updated_at=datetime.fromisoformat(r["updated_at"]),
                archived=bool(r["archived"]),
            )
            for r in rows
        ]

    def add_message(
        self,
        conversation_id: str,
        role: str,
        content: str,
        metadata: dict[str, Any] | None = None,
    ) -> Message:
        now = _utcnow()
        meta = json.dumps(metadata or {}, ensure_ascii=False)
        with self._conn() as conn:
            cur = conn.execute(
                "INSERT INTO messages(conversation_id, role, content, created_at, metadata) VALUES (?,?,?,?,?)",
                (conversation_id, role, content, now, meta),
            )
            conn.execute(
                "UPDATE conversations SET updated_at = ? WHERE id = ?",
                (now, conversation_id),
            )
            msg_id = int(cur.lastrowid)
        return Message(
            id=msg_id,
            conversation_id=conversation_id,
            role=role,
            content=content,
            created_at=datetime.fromisoformat(now),
            metadata=metadata or {},
        )

    def get_messages(self, conversation_id: str, limit: int = 50) -> list[Message]:
        with self._conn() as conn:
            rows = conn.execute(
                """
                SELECT * FROM (
                    SELECT * FROM messages
                    WHERE conversation_id = ?
                    ORDER BY id DESC
                    LIMIT ?
                ) ORDER BY id ASC
                """,
                (conversation_id, limit),
            ).fetchall()
        return [
            Message(
                id=r["id"],
                conversation_id=r["conversation_id"],
                role=r["role"],
                content=r["content"],
                created_at=datetime.fromisoformat(r["created_at"]),
                metadata=json.loads(r["metadata"] or "{}"),
            )
            for r in rows
        ]

    def clear_conversation(self, conversation_id: str) -> None:
        with self._conn() as conn:
            conn.execute("DELETE FROM messages WHERE conversation_id = ?", (conversation_id,))
            conn.execute(
                "UPDATE conversations SET updated_at = ? WHERE id = ?",
                (_utcnow(), conversation_id),
            )

    def clear_all(self) -> None:
        with self._conn() as conn:
            conn.execute("DELETE FROM messages")
            conn.execute("DELETE FROM conversations")
            conn.execute("DELETE FROM memory_notes")

    def set_preference(self, key: str, value: Any) -> Preference:
        now = _utcnow()
        payload = json.dumps(value, ensure_ascii=False)
        with self._conn() as conn:
            conn.execute(
                """
                INSERT INTO preferences(key, value, updated_at) VALUES (?,?,?)
                ON CONFLICT(key) DO UPDATE SET value=excluded.value, updated_at=excluded.updated_at
                """,
                (key, payload, now),
            )
        return Preference(key=key, value=value, updated_at=datetime.fromisoformat(now))

    def get_preference(self, key: str, default: Any = None) -> Any:
        with self._conn() as conn:
            row = conn.execute("SELECT value FROM preferences WHERE key = ?", (key,)).fetchone()
        if not row:
            return default
        return json.loads(row["value"])

    def log_action(
        self,
        tool_name: str,
        args: dict[str, Any],
        level: int,
        status: str,
        result: str = "",
    ) -> ActionLog:
        now = _utcnow()
        with self._conn() as conn:
            cur = conn.execute(
                """
                INSERT INTO action_logs(tool_name, args, level, status, result, created_at)
                VALUES (?,?,?,?,?,?)
                """,
                (tool_name, json.dumps(args, ensure_ascii=False), level, status, result, now),
            )
            action_id = int(cur.lastrowid)
        return ActionLog(
            id=action_id,
            tool_name=tool_name,
            args=args,
            level=level,
            status=status,
            result=result,
            created_at=datetime.fromisoformat(now),
        )

    def list_actions(self, limit: int = 100) -> list[ActionLog]:
        with self._conn() as conn:
            rows = conn.execute(
                "SELECT * FROM action_logs ORDER BY id DESC LIMIT ?",
                (limit,),
            ).fetchall()
        return [
            ActionLog(
                id=r["id"],
                tool_name=r["tool_name"],
                args=json.loads(r["args"] or "{}"),
                level=r["level"],
                status=r["status"],
                result=r["result"],
                created_at=datetime.fromisoformat(r["created_at"]),
            )
            for r in rows
        ]

    def add_note(self, content: str, tags: list[str] | None = None) -> MemoryNote:
        now = _utcnow()
        tag_json = json.dumps(tags or [], ensure_ascii=False)
        with self._conn() as conn:
            cur = conn.execute(
                "INSERT INTO memory_notes(content, tags, created_at) VALUES (?,?,?)",
                (content, tag_json, now),
            )
            note_id = int(cur.lastrowid)
        return MemoryNote(
            id=note_id,
            content=content,
            tags=tags or [],
            created_at=datetime.fromisoformat(now),
        )

    def search_notes(self, query: str, limit: int = 20) -> list[MemoryNote]:
        like = f"%{query}%"
        with self._conn() as conn:
            rows = conn.execute(
                """
                SELECT * FROM memory_notes
                WHERE content LIKE ?
                ORDER BY id DESC
                LIMIT ?
                """,
                (like, limit),
            ).fetchall()
        return [
            MemoryNote(
                id=r["id"],
                content=r["content"],
                tags=json.loads(r["tags"] or "[]"),
                created_at=datetime.fromisoformat(r["created_at"]),
            )
            for r in rows
        ]
