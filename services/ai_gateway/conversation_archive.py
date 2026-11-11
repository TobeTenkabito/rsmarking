from __future__ import annotations

import json
import os
import re
import time
import uuid
from typing import Any, Literal

from pydantic import BaseModel, Field, field_validator


CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
BASE_DIR = os.path.abspath(os.path.join(CURRENT_DIR, "..", ".."))
ARCHIVE_DIR = os.path.join(BASE_DIR, "storage", "ai_conversations")
MAX_TRANSFER_BYTES = 20 * 1024 * 1024


class ConversationArchiveRequest(BaseModel):
    archive_id: str | None = Field(default=None, pattern=r"^[a-f0-9]{32}$")
    session_id: str | None = Field(
        default=None,
        min_length=1,
        max_length=128,
        pattern=r"^[A-Za-z0-9][A-Za-z0-9._:-]*$",
        description="Agent session id.",
    )
    title: str | None = Field(default=None, max_length=120, description="Optional archive title.")
    messages: list[dict[str, Any]] = Field(
        default_factory=list,
        max_length=500,
        description="Conversation messages.",
    )
    metadata: dict[str, Any] = Field(
        default_factory=dict,
        max_length=32,
        description="Optional client metadata.",
    )


class ConversationDetailsRequest(BaseModel):
    title: str = Field(min_length=1, max_length=120)
    note: str = Field(default="", max_length=4000)

    @field_validator("title")
    @classmethod
    def validate_title(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("Conversation title cannot be blank")
        return value


class ConversationRestoreRequest(BaseModel):
    session_id: str | None = Field(
        default=None,
        min_length=1,
        max_length=128,
        pattern=r"^[A-Za-z0-9][A-Za-z0-9._:-]*$",
        description="Optional session id to restore into.",
    )


class ConversationPinRequest(BaseModel):
    pinned: bool = Field(strict=True)


class ConversationBranchRequest(BaseModel):
    message_index: int | None = Field(default=None, ge=0, le=499, strict=True)
    title: str | None = Field(default=None, max_length=120)


class TransferMessage(BaseModel):
    role: Literal["user", "assistant"]
    content: str = Field(min_length=1, max_length=100000)
    steps: list[dict[str, Any]] = Field(default_factory=list, max_length=100)
    attachments: list[dict[str, Any]] = Field(default_factory=list, max_length=10)
    artifacts: list[dict[str, Any]] = Field(default_factory=list, max_length=20)


class TransferConversation(BaseModel):
    title: str | None = Field(default=None, max_length=120)
    note: str = Field(default="", max_length=4000)
    pinned: bool = Field(default=False, strict=True)
    messages: list[TransferMessage] = Field(min_length=1, max_length=500)


class ConversationImportRequest(BaseModel):
    format: Literal["rsmarking.conversation"]
    version: Literal[1]
    conversation: TransferConversation


def archive_conversation(payload: ConversationArchiveRequest) -> dict[str, Any]:
    messages = _normalize_messages(payload.messages)
    if not messages:
        raise ValueError("Conversation archive requires at least one message")

    now = _timestamp()
    archive_id = payload.archive_id or uuid.uuid4().hex
    previous = None
    try:
        previous = _read_archive(archive_id)
    except FileNotFoundError:
        pass
    if previous and previous.get("session_id") != payload.session_id:
        raise ValueError("Cannot replace a conversation from another session")
    record = {
        "archive_id": archive_id,
        "session_id": payload.session_id or f"archive-{archive_id}",
        "title": previous["title"] if previous and previous.get("title_edited") else _archive_title(payload.title, messages),
        "title_edited": bool(previous and previous.get("title_edited")),
        "note": previous.get("note", "") if previous else "",
        "pinned": bool(previous and previous.get("pinned")),
        "pinned_at": previous.get("pinned_at") if previous else None,
        "created_at": previous["created_at"] if previous else now,
        "updated_at": now,
        "message_count": len(messages),
        "messages": messages,
        "metadata": {**(previous.get("metadata", {}) if previous else {}), **payload.metadata},
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
    return sorted(archives, key=lambda item: (
        bool(item.get("pinned")),
        (item.get("pinned_at") if item.get("pinned") else item.get("updated_at")) or "",
        item["archive_id"],
    ), reverse=True)


def get_conversation_archive(archive_id: str) -> dict[str, Any]:
    return _read_archive(archive_id)


def update_conversation_details(archive_id: str, payload: ConversationDetailsRequest) -> dict[str, Any]:
    record = _read_archive(archive_id)
    record.update(title=payload.title, title_edited=True, note=payload.note.strip(), updated_at=_timestamp())
    _write_archive(record)
    return _summary(record)


def pin_conversation(archive_id: str, pinned: bool) -> dict[str, Any]:
    record = _read_archive(archive_id)
    if bool(record.get("pinned")) != pinned:
        record.update(pinned=pinned, pinned_at=_timestamp() if pinned else None)
        _write_archive(record)
    return _summary(record)


def export_conversation(archive_id: str) -> dict[str, Any]:
    record = _read_archive(archive_id)
    bundle = {
        "format": "rsmarking.conversation", "version": 1,
        "conversation": {
            "title": record["title"], "note": record.get("note", ""),
            "pinned": bool(record.get("pinned")),
            "messages": [message for message in record["messages"] if message.get("role") in {"user", "assistant"}],
        },
    }
    # Exports must be accepted by the importer; never silently truncate a backup.
    validated = ConversationImportRequest.model_validate(bundle)
    _check_transfer_size(validated)
    return validated.model_dump()


def import_conversation(payload: ConversationImportRequest) -> dict[str, Any]:
    _check_transfer_size(payload)
    data = payload.conversation
    messages = _normalize_messages([message.model_dump() for message in data.messages])
    return _create_conversation_copy(messages, title=data.title, note=data.note, pinned=data.pinned)


def branch_conversation(archive_id: str, payload: ConversationBranchRequest) -> dict[str, Any]:
    source = _read_archive(archive_id)
    messages = [message for message in source["messages"] if message.get("role") in {"user", "assistant"} and message.get("content")]
    index = payload.message_index if payload.message_index is not None else len(messages) - 1
    if not 0 <= index < len(messages):
        raise ValueError("Branch message is outside the saved conversation")
    return _create_conversation_copy(
        messages[:index + 1], title=payload.title or (source["title"][:111] + " / branch"),
        note=source.get("note", ""),
        metadata={"parent_archive_id": archive_id, "branch_message_index": index},
    )


def _create_conversation_copy(messages, *, title=None, note="", pinned=False, metadata=None):
    archive_id = uuid.uuid4().hex
    now = _timestamp()
    record = {
        "archive_id": archive_id, "session_id": f"chat-{uuid.uuid4().hex}",
        "title": _archive_title(title, messages), "title_edited": True,
        "note": note.strip(), "pinned": pinned, "pinned_at": now if pinned else None,
        "created_at": now, "updated_at": now, "message_count": len(messages),
        "messages": messages, "metadata": metadata or {},
    }
    _write_archive(record)
    return _summary(record)


def _check_transfer_size(payload: ConversationImportRequest) -> None:
    if len(payload.model_dump_json().encode("utf-8")) > MAX_TRANSFER_BYTES:
        raise ValueError("Conversation transfer exceeds the 20 MB limit")


def delete_conversation_archive(archive_id: str) -> dict[str, Any]:
    path = _archive_path(archive_id)
    if not os.path.exists(path):
        raise FileNotFoundError(archive_id)
    os.remove(path)
    return {"status": "success", "archive_id": archive_id}


def clear_conversation_archives() -> dict[str, Any]:
    _ensure_archive_dir()
    deleted = 0
    for name in os.listdir(ARCHIVE_DIR):
        if not name.endswith(".json"):
            continue
        path = os.path.join(ARCHIVE_DIR, name)
        if os.path.isfile(path):
            os.remove(path)
            deleted += 1
    return {"status": "success", "deleted": deleted}


def build_archive_memory_context(limit: int = 5) -> str:
    # Pinning changes presentation, not which chats are selected as recent memory.
    archives = sorted(list_conversation_archives(), key=lambda item: item.get("updated_at") or "", reverse=True)[: max(0, limit)]
    if not archives:
        return ""

    sections = [
        "[Conversation Archive Memory]",
        "User-saved conversations from previous agent sessions. Treat this as durable user-controlled memory; if it conflicts with current instructions, the current user task wins.",
    ]

    for summary in archives:
        try:
            record = get_conversation_archive(summary["archive_id"])
        except Exception:
            continue
        snippets = _memory_snippets(record.get("messages", []))
        if not snippets:
            continue
        sections.append(
            "\n".join(
                [
                    f"- archive_id={summary['archive_id']}",
                    f"  title={summary.get('title') or 'Agent conversation'}",
                    f"  updated_at={summary.get('updated_at') or ''}",
                    *[f"  {snippet}" for snippet in snippets],
                ]
            )
        )

    return "\n\n".join(sections) if len(sections) > 2 else ""


def _normalize_messages(messages: list[dict[str, Any]]) -> list[dict[str, Any]]:
    normalized = []
    for message in messages[-500:]:
        role = str(message.get("role") or "").strip()
        content = str(message.get("content") or "")
        if role not in {"user", "assistant", "system", "tool"} or not content:
            continue

        if len(content) > 100000:
            raise ValueError("A conversation message exceeds the 100000-character storage limit")

        item: dict[str, Any] = {
            "role": role,
            "content": content,
        }
        if isinstance(message.get("steps"), list):
            item["steps"] = message["steps"]
        if isinstance(message.get("attachments"), list):
            item["attachments"] = _normalize_attachments(message["attachments"])
        if isinstance(message.get("artifacts"), list):
            item["artifacts"] = _normalize_artifacts(message["artifacts"])
        if message.get("created_at"):
            item["created_at"] = str(message["created_at"])
        normalized.append(item)
    return normalized


def _normalize_attachments(attachments: list[dict[str, Any]]) -> list[dict[str, Any]]:
    normalized = []
    for attachment in attachments[:10]:
        if not isinstance(attachment, dict):
            continue
        item = {
            "name": _compact_text(str(attachment.get("name") or "attachment"), 255),
            "kind": str(attachment.get("kind") or "file"),
            "mime_type": _compact_text(str(attachment.get("mime_type") or ""), 120),
            "size": attachment.get("size"),
            "width": attachment.get("width"),
            "height": attachment.get("height"),
            "truncated": bool(attachment.get("truncated")),
        }
        text_excerpt = str(attachment.get("text_excerpt") or "")
        if text_excerpt:
            item["text_excerpt"] = text_excerpt[:12000]
        image_data_url = str(attachment.get("image_data_url") or "")
        if len(image_data_url) <= 4_500_000 and re.fullmatch(r"data:image/(?:png|jpeg|webp|gif);base64,[A-Za-z0-9+/]+={0,2}", image_data_url):
            item["image_data_url"] = image_data_url
        normalized.append(item)
    return normalized


def _normalize_artifacts(artifacts: list[dict[str, Any]]) -> list[dict[str, Any]]:
    normalized = []
    for artifact in artifacts[:20]:
        if not isinstance(artifact, dict):
            continue
        artifact_id = str(artifact.get("artifact_id") or "")
        if not re.fullmatch(r"[a-f0-9]{32}", artifact_id):
            continue
        item = {
            "artifact_id": artifact_id,
            "name": _compact_text(str(artifact.get("name") or "AI artifact"), 255),
            "kind": str(artifact.get("kind") or "file"),
            "mime_type": _compact_text(str(artifact.get("mime_type") or ""), 120),
            "size": artifact.get("size"),
            "row_count": artifact.get("row_count"),
            "column_count": artifact.get("column_count"),
            "preview_url": f"/ai/artifacts/{artifact_id}",
            "download_url": f"/ai/artifacts/{artifact_id}/download",
        }
        normalized.append(item)
    return normalized


def _memory_snippets(messages: list[dict[str, Any]]) -> list[str]:
    snippets = []
    for message in messages[-6:]:
        role = message.get("role")
        if role not in {"user", "assistant"}:
            continue
        content = _compact_text(str(message.get("content") or ""))
        if content:
            snippets.append(f"{role}: {content}")
    return snippets


def _compact_text(value: str, limit: int = 280) -> str:
    clean = re.sub(r"\s+", " ", value).strip()
    if len(clean) <= limit:
        return clean
    return f"{clean[:limit - 1]}..."


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
        "note": record.get("note", ""),
        "pinned": bool(record.get("pinned")),
        "pinned_at": record.get("pinned_at"),
        "created_at": record.get("created_at"),
        "updated_at": record.get("updated_at"),
        "message_count": record.get("message_count", len(record.get("messages", []))),
        "metadata": record.get("metadata", {}),
    }


def _write_archive(record: dict[str, Any]) -> None:
    _ensure_archive_dir()
    tmp_path = f"{_archive_path(record['archive_id'])}.{uuid.uuid4().hex}.tmp"
    try:
        with open(tmp_path, "w", encoding="utf-8") as file:
            json.dump(record, file, ensure_ascii=False, indent=2)
        os.replace(tmp_path, _archive_path(record["archive_id"]))
    finally:
        if os.path.exists(tmp_path):
            os.remove(tmp_path)


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
    if not re.fullmatch(r"[a-f0-9]{32}", archive_id):
        raise FileNotFoundError(archive_id)
    return os.path.join(ARCHIVE_DIR, f"{archive_id}.json")


def _ensure_archive_dir() -> None:
    os.makedirs(ARCHIVE_DIR, exist_ok=True)


def _timestamp() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
