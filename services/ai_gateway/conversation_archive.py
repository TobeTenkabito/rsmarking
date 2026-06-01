from __future__ import annotations

import json
import os
import re
import time
import uuid
from typing import Any

from pydantic import BaseModel, Field


CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
BASE_DIR = os.path.abspath(os.path.join(CURRENT_DIR, "..", ".."))
ARCHIVE_DIR = os.path.join(BASE_DIR, "storage", "ai_conversations")


class ConversationArchiveRequest(BaseModel):
    session_id: str | None = Field(default=None, description="Agent session id.")
    title: str | None = Field(default=None, max_length=120, description="Optional archive title.")
    messages: list[dict[str, Any]] = Field(default_factory=list, description="Conversation messages.")
    metadata: dict[str, Any] = Field(default_factory=dict, description="Optional client metadata.")


class ConversationRestoreRequest(BaseModel):
    session_id: str | None = Field(default=None, description="Optional session id to restore into.")


def archive_conversation(payload: ConversationArchiveRequest) -> dict[str, Any]:
    messages = _normalize_messages(payload.messages)
    if not messages:
        raise ValueError("Conversation archive requires at least one message")

    now = _timestamp()
    archive_id = uuid.uuid4().hex
    record = {
        "archive_id": archive_id,
        "session_id": payload.session_id or f"archive-{archive_id}",
        "title": _archive_title(payload.title, messages),
        "created_at": now,
        "updated_at": now,
        "message_count": len(messages),
        "messages": messages,
        "metadata": payload.metadata or {},
    }
    _write_archive(record)
    return _summary(record)


def list_conversation_archives() -> list[dict[str, Any]]:
    _ensure_archive_dir()
    archives = []
    for name in os.listdir(ARCHIVE_DIR):
        if not name.endswith(".json"):
            continue
        try:
            archives.append(_summary(_read_archive_by_filename(name)))
        except Exception:
            continue
    return sorted(archives, key=lambda item: item.get("updated_at", ""), reverse=True)


def get_conversation_archive(archive_id: str) -> dict[str, Any]:
    return _read_archive(archive_id)


def delete_conversation_archive(archive_id: str) -> dict[str, Any]:
    path = _archive_path(archive_id)
    if not os.path.exists(path):
        raise FileNotFoundError(archive_id)
    os.remove(path)
    return {"status": "success", "archive_id": archive_id}


def _normalize_messages(messages: list[dict[str, Any]]) -> list[dict[str, Any]]:
    normalized = []
    for message in messages:
        role = str(message.get("role") or "").strip()
        content = str(message.get("content") or "")
        if role not in {"user", "assistant", "system", "tool"} or not content:
            continue

        item: dict[str, Any] = {
            "role": role,
            "content": content[:20000],
        }
        if isinstance(message.get("steps"), list):
            item["steps"] = message["steps"]
        if message.get("created_at"):
            item["created_at"] = str(message["created_at"])
        normalized.append(item)
    return normalized


def _archive_title(title: str | None, messages: list[dict[str, Any]]) -> str:
    if title and title.strip():
        return title.strip()[:120]
    for message in messages:
        if message["role"] == "user":
            clean = re.sub(r"\s+", " ", message["content"]).strip()
            return clean[:80] or "Agent conversation"
    return "Agent conversation"


def _summary(record: dict[str, Any]) -> dict[str, Any]:
    return {
        "archive_id": record["archive_id"],
        "session_id": record.get("session_id"),
        "title": record.get("title") or "Agent conversation",
        "created_at": record.get("created_at"),
        "updated_at": record.get("updated_at"),
        "message_count": record.get("message_count", len(record.get("messages", []))),
        "metadata": record.get("metadata", {}),
    }


def _write_archive(record: dict[str, Any]) -> None:
    _ensure_archive_dir()
    tmp_path = f"{_archive_path(record['archive_id'])}.tmp"
    with open(tmp_path, "w", encoding="utf-8") as file:
        json.dump(record, file, ensure_ascii=False, indent=2)
    os.replace(tmp_path, _archive_path(record["archive_id"]))


def _read_archive(archive_id: str) -> dict[str, Any]:
    path = _archive_path(archive_id)
    if not os.path.exists(path):
        raise FileNotFoundError(archive_id)
    with open(path, "r", encoding="utf-8") as file:
        return json.load(file)


def _read_archive_by_filename(filename: str) -> dict[str, Any]:
    path = os.path.join(ARCHIVE_DIR, filename)
    with open(path, "r", encoding="utf-8") as file:
        return json.load(file)


def _archive_path(archive_id: str) -> str:
    safe_id = re.sub(r"[^a-zA-Z0-9_-]", "", archive_id)
    if not safe_id:
        raise ValueError("Invalid archive id")
    return os.path.join(ARCHIVE_DIR, f"{safe_id}.json")


def _ensure_archive_dir() -> None:
    os.makedirs(ARCHIVE_DIR, exist_ok=True)


def _timestamp() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
