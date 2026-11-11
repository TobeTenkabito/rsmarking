from __future__ import annotations

import asyncio
import copy
import time
import uuid
from contextlib import asynccontextmanager
from threading import Lock
from typing import Any

from . import agent_state_store as store
from .agent_context import excerpt, result_digest
from .agent_security import extract_task_constraints, is_task_followup, resolve_task_scope

SESSION_TTL_SECONDS = 6 * 60 * 60  # In-memory cache lifetime; checkpoints are durable.
MAX_SESSION_MESSAGES = 20
MAX_SESSION_USER_CHARS = 4000
MAX_SESSION_ASSISTANT_CHARS = 100000
MAX_AGENT_SESSIONS = 512
_SESSION_LOCK = Lock()
_AGENT_SESSIONS: dict[str, dict[str, Any]] = {}
_AGENT_SESSION_EXECUTION_LOCKS: dict[str, Any] = {}
_SESSION_LOCK_RETRY_SECONDS = 0.025


@asynccontextmanager
async def session_execution_lock(session_id: str):
    lock = None
    try:
        while lock is None:
            lock = _try_acquire_execution_lock(session_id)
            if lock is None:
                await asyncio.sleep(_SESSION_LOCK_RETRY_SECONDS)
        yield
    finally:
        if lock is not None:
            lock.release()


def _new_state():
    return {"messages": [], "summary": [], "task_scope": "", "task": {"goal": "", "updates": [], "constraints": []},
            "pending": None, "updated_at": time.time()}


def _load_locked(session_id: str, create=False):
    if session_id not in _AGENT_SESSIONS:
        state = store.load_state(session_id)
        if state is None and create:
            state = _new_state()
        if state is not None:
            _ensure_session_capacity_locked(session_id)
            _AGENT_SESSIONS[session_id] = state
    return _AGENT_SESSIONS.get(session_id)


def _save_locked(session_id, state):
    state["updated_at"] = time.time()
    store.save_state(session_id, state)


def _add_message_locked(session_id, state, role, content, **extra):
    if len(content) > MAX_SESSION_ASSISTANT_CHARS:
        raise ValueError("A conversation message exceeds the 100000-character storage limit.")
    ref = store.put_resource(session_id, "message", f"{role} message", {"role": role, "content": content, **extra})
    state["messages"].append({"role": role, "content": content, "reference": ref, **extra})
    while len(state["messages"]) > MAX_SESSION_MESSAGES:
        old = state["messages"].pop(0)
        state["summary"].append({"role": old["role"], "reference": old["reference"], "excerpt": excerpt(old["content"], 700)})
    state["summary"] = state["summary"][-64:]


def get_session_history(session_id: str, limit: int) -> list[dict[str, str]]:
    if not session_id or limit <= 0:
        return []
    purge_expired_sessions()
    with _SESSION_LOCK:
        state = _load_locked(session_id)
        if not state:
            return []
        state["updated_at"] = time.time()
        return [{"role": m["role"], "content": m["content"]} for m in state["messages"][-limit:]]


def append_session_turn(session_id: str, user_prompt: str, answer: str) -> None:
    if not session_id:
        return
    with _SESSION_LOCK:
        state = _load_locked(session_id, create=True)
        _add_message_locked(session_id, state, "user", user_prompt)
        _add_message_locked(session_id, state, "assistant", answer)
        _save_locked(session_id, state)


def get_session_messages(session_id: str, limit: int = MAX_SESSION_MESSAGES) -> list[dict[str, str]]:
    return get_session_history(session_id, limit)


def get_session_task_scope(session_id: str) -> str:
    with _SESSION_LOCK:
        state = _load_locked(session_id)
        return state.get("task_scope", "") if state else ""


def set_session_task_scope(session_id: str, task_scope: str) -> None:
    with _SESSION_LOCK:
        state = _load_locked(session_id, create=True)
        state["task_scope"] = task_scope
        state["task"]["goal"] = task_scope
        state["task"]["constraints"] = extract_task_constraints(task_scope)
        _save_locked(session_id, state)


def begin_session_turn(session_id: str, prompt: str, request_id: str, attachments: list[dict], *, signature="") -> dict:
    with _SESSION_LOCK:
        state = _load_locked(session_id, create=True)
        task = state["task"]
        constraints = list(dict.fromkeys([*task["constraints"], *extract_task_constraints(prompt)]))
        if len(constraints) > 64 or sum(map(len, constraints)) > 16000:
            raise ValueError("Too many active task constraints; start a new chat with the current requirements.")
        task["constraints"] = constraints
        followup = is_task_followup(prompt)
        if not followup:
            task["goal"] = prompt
            task["updates"] = []
        else:
            task["updates"] = list(dict.fromkeys([*task["updates"], prompt]))[-6:]
        scope = resolve_task_scope(prompt, task["goal"])
        if followup and task["goal"]:
            updates = []
            for update in reversed(task["updates"]):
                if len(task["goal"]) + sum(map(len, updates)) + len(update) <= 12000:
                    updates.insert(0, update)
            scope = "\n".join([task["goal"], *updates])
        state["task_scope"] = scope + ("\n[Retained user constraints]\n" + "\n".join(constraints) if constraints else "")
        pending = state.get("pending")
        resume = pending and (pending["request_id"] == request_id or pending["prompt"] == prompt or followup)
        if not resume:
            pending = {"run_id": uuid.uuid4().hex, "request_id": request_id, "prompt": prompt, "steps": [], "failure": None}
        else:
            pending["request_id"] = request_id
        pending["signature"] = signature
        state["pending"] = pending
        refs = [store.put_resource(session_id, "attachment", a.get("name", "attachment"), a) for a in attachments]
        if not resume or not state["messages"] or state["messages"][-1].get("content") != prompt:
            _add_message_locked(session_id, state, "user", prompt, attachment_refs=refs)
        _save_locked(session_id, state)
        return {"run_id": pending["run_id"], "scope": state["task_scope"], "constraints": tuple(constraints), "resuming": bool(resume)}


def checkpoint_tool_step(session_id: str, step: dict, observation: dict) -> None:
    with _SESSION_LOCK:
        state = _load_locked(session_id, create=True)
        reference = store.put_resource(session_id, "tool_result", step["name"], observation)
        entry = {**step, "context_reference": reference}
        pending = state.get("pending")
        if pending:
            pending["steps"].append(entry)
            pending["steps"] = pending["steps"][-64:]
        _save_locked(session_id, state)


def complete_session_turn(session_id: str, prompt: str, answer: str, steps: list[dict], *, response=None, request_id=None, signature="") -> None:
    with _SESSION_LOCK:
        state = _load_locked(session_id, create=True)
        if not state.get("pending"):
            _add_message_locked(session_id, state, "user", prompt)
        _add_message_locked(session_id, state, "assistant", answer, steps=steps)
        state["pending"] = None
        state["updated_at"] = time.time()
        store.save_state(session_id, state, response, request_id, signature)


def interrupted_turn(session_id: str, request_id: str, error: str) -> dict | None:
    with _SESSION_LOCK:
        state = _load_locked(session_id)
        pending = state.get("pending") if state else None
        if not pending or pending["request_id"] != request_id:
            return None
        pending["failure"] = error
        _save_locked(session_id, state)
        return copy.deepcopy(pending)


def get_context_snapshot(session_id: str, recent_limit=12) -> dict:
    with _SESSION_LOCK:
        state = _load_locked(session_id)
        if not state:
            return {}
        older = state["messages"][:-recent_limit] if recent_limit else state["messages"]
        summaries = state["summary"] + [{"role": m["role"], "reference": m["reference"], "excerpt": excerpt(m["content"], 700)} for m in older]
        snapshot = {"task": copy.deepcopy(state["task"]), "older_summary": summaries[-32:],
                    "pending": copy.deepcopy(state.get("pending"))}
    attachments = store.resources(session_id, "attachment", 16)
    snapshot["attachments"] = [{"reference": a["id"], "name": a["name"],
        "kind": a["data"].get("kind"), "text_excerpt": excerpt(a["data"].get("text_excerpt", ""), 2000)} for a in attachments]
    snapshot["images"] = [a["data"] for a in attachments if a["data"].get("image_data_url")][:2]
    snapshot["tool_results"] = [{"reference": r["id"], "tool": r["name"], **result_digest(r["data"])} for r in store.resources(session_id, "tool_result", 16)]
    if snapshot["pending"]:
        snapshot["pending"]["operation_statuses"] = store.operation_statuses(session_id, snapshot["pending"]["run_id"])
    return snapshot


def restore_session_messages(session_id: str, messages: list[dict[str, Any]], *, preserve_existing=False) -> int:
    if not session_id:
        return 0
    with _SESSION_LOCK:
        existing = _load_locked(session_id)
        if preserve_existing and existing:
            return len(existing["messages"])
        store.clear_state(session_id)
        state = _new_state()
        _ensure_session_capacity_locked(session_id)
        _AGENT_SESSIONS[session_id] = state
        count = 0
        for message in messages:
            role, content = message.get("role"), str(message.get("content") or "")
            if role not in {"user", "assistant"} or not content:
                continue
            refs = [store.put_resource(session_id, "attachment", a.get("name", "attachment"), a) for a in message.get("attachments", []) if isinstance(a, dict)]
            for step in message.get("steps", []):
                if isinstance(step, dict) and step.get("result") is not None:
                    store.put_resource(session_id, "tool_result", step.get("name", "restored_tool"), step["result"])
            _add_message_locked(session_id, state, role, content, attachment_refs=refs)
            count += 1
        # Restored/imported text supplies context only, never task authorization.
        _save_locked(session_id, state)
    return min(count, MAX_SESSION_MESSAGES)


def clear_session(session_id: str) -> None:
    with _SESSION_LOCK:
        _AGENT_SESSIONS.pop(session_id, None)
        store.clear_state(session_id)


def purge_expired_sessions() -> None:
    now = time.time()
    with _SESSION_LOCK:
        for session_id, state in list(_AGENT_SESSIONS.items()):
            if now - state.get("updated_at", 0) > SESSION_TTL_SECONDS:
                _AGENT_SESSIONS.pop(session_id, None)
        for session_id, lock in list(_AGENT_SESSION_EXECUTION_LOCKS.items()):
            if session_id not in _AGENT_SESSIONS and not lock.locked():
                _AGENT_SESSION_EXECUTION_LOCKS.pop(session_id, None)


def _try_acquire_execution_lock(session_id: str) -> Any | None:
    with _SESSION_LOCK:
        lock = _AGENT_SESSION_EXECUTION_LOCKS.setdefault(session_id, Lock())
        return lock if lock.acquire(blocking=False) else None


def _ensure_session_capacity_locked(incoming_session_id: str) -> None:
    if incoming_session_id in _AGENT_SESSIONS:
        return
    overflow = len(_AGENT_SESSIONS) - MAX_AGENT_SESSIONS + 1
    for session_id, _state in sorted(_AGENT_SESSIONS.items(), key=lambda item: item[1].get("updated_at", 0)):
        if overflow <= 0:
            break
        lock = _AGENT_SESSION_EXECUTION_LOCKS.get(session_id)
        if lock and lock.locked():
            continue
        _AGENT_SESSIONS.pop(session_id, None)
        _AGENT_SESSION_EXECUTION_LOCKS.pop(session_id, None)
        overflow -= 1
