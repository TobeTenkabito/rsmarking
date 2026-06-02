from __future__ import annotations

import time
from collections import deque
from threading import Lock
from typing import Any


SESSION_TTL_SECONDS = 6 * 60 * 60
MAX_SESSION_MESSAGES = 20

_SESSION_LOCK = Lock()
_AGENT_SESSIONS: dict[str, dict[str, Any]] = {}


def get_session_history(session_id: str, limit: int) -> list[dict[str, str]]:
    if not session_id or limit <= 0:
        return []

    purge_expired_sessions()
    with _SESSION_LOCK:
        session = _AGENT_SESSIONS.get(session_id)
        if not session:
            return []
        messages = list(session["messages"])[-limit:]
        session["updated_at"] = time.time()
        return [dict(message) for message in messages]


def append_session_turn(session_id: str, user_prompt: str, answer: str) -> None:
    if not session_id:
        return

    purge_expired_sessions()
    with _SESSION_LOCK:
        session = _AGENT_SESSIONS.setdefault(
            session_id,
            {"messages": deque(maxlen=MAX_SESSION_MESSAGES), "updated_at": time.time()},
        )
        session["messages"].append({"role": "user", "content": user_prompt})
        session["messages"].append({"role": "assistant", "content": answer})
        session["updated_at"] = time.time()


def get_session_messages(session_id: str, limit: int = MAX_SESSION_MESSAGES) -> list[dict[str, str]]:
    return get_session_history(session_id, limit)


def restore_session_messages(session_id: str, messages: list[dict[str, Any]]) -> int:
    if not session_id:
        return 0

    normalized = deque(maxlen=MAX_SESSION_MESSAGES)
    for message in messages:
        role = message.get("role")
        content = str(message.get("content") or "")
        if role not in {"user", "assistant"} or not content:
            continue
        normalized.append({"role": role, "content": content})

    with _SESSION_LOCK:
        _AGENT_SESSIONS[session_id] = {
            "messages": normalized,
            "updated_at": time.time(),
        }
    return len(normalized)


def clear_session(session_id: str) -> None:
    with _SESSION_LOCK:
        _AGENT_SESSIONS.pop(session_id, None)


def purge_expired_sessions() -> None:
    now = time.time()
    with _SESSION_LOCK:
        expired = [
            session_id
            for session_id, session in _AGENT_SESSIONS.items()
            if now - session.get("updated_at", now) > SESSION_TTL_SECONDS
        ]
        for session_id in expired:
            _AGENT_SESSIONS.pop(session_id, None)
