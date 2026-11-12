"""Local durable checkpoints. No client-supplied history is trusted as a grant."""

from __future__ import annotations

import hashlib
import json
import sqlite3
import time
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from typing import Any

STATE_DB = Path(__file__).resolve().parents[2] / "storage" / "ai_agent_state.sqlite3"


@contextmanager
def connection() -> Iterator[sqlite3.Connection]:
    Path(STATE_DB).parent.mkdir(parents=True, exist_ok=True)
    db = sqlite3.connect(str(STATE_DB), timeout=15)
    try:
        db.execute("PRAGMA busy_timeout=15000")
        db.executescript("""
            CREATE TABLE IF NOT EXISTS sessions (id TEXT PRIMARY KEY, state TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS resources (
                session TEXT, id TEXT, kind TEXT, name TEXT, data TEXT, created REAL,
                PRIMARY KEY(session, id));
            CREATE TABLE IF NOT EXISTS operations (
                session TEXT, run TEXT, fingerprint TEXT, name TEXT, status TEXT, result TEXT,
                PRIMARY KEY(session, run, fingerprint));
            CREATE TABLE IF NOT EXISTS responses (
                session TEXT, request TEXT, signature TEXT, response TEXT,
                PRIMARY KEY(session, request));
        """)
        yield db
        db.commit()
    finally:
        db.close()


def encode(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, default=str)


def load_state(session_id: str) -> dict | None:
    with connection() as db:
        row = db.execute("SELECT state FROM sessions WHERE id=?", (session_id,)).fetchone()
    return json.loads(row[0]) if row else None


def save_state(
    session_id: str,
    state: dict,
    response: dict | None = None,
    request_id: str | None = None,
    signature: str = "",
) -> None:
    with connection() as db:
        db.execute("INSERT OR REPLACE INTO sessions VALUES (?,?)", (session_id, encode(state)))
        if response is not None and request_id:
            db.execute(
                "INSERT OR REPLACE INTO responses VALUES (?,?,?,?)",
                (session_id, request_id, signature, encode(response)),
            )


def clear_state(session_id: str) -> None:
    with connection() as db:
        db.execute("DELETE FROM sessions WHERE id=?", (session_id,))
        for table in ("resources", "operations", "responses"):
            db.execute(f"DELETE FROM {table} WHERE session=?", (session_id,))


def put_resource(session_id: str, kind: str, name: str, data: Any) -> str:
    encoded = encode(data)
    resource_id = hashlib.sha256((kind + name + encoded).encode()).hexdigest()[:32]
    with connection() as db:
        db.execute(
            "INSERT OR IGNORE INTO resources VALUES (?,?,?,?,?,?)",
            (session_id, resource_id, kind, name, encoded, time.time()),
        )
    return resource_id


def resources(session_id: str, kind: str | None = None, limit: int = 16) -> list[dict]:
    with connection() as db:
        rows = db.execute(
            "SELECT id,kind,name,data FROM resources WHERE session=? AND (? IS NULL OR kind=?) ORDER BY created DESC LIMIT ?",
            (session_id, kind, kind, limit),
        ).fetchall()
    return [
        {
            "id": row[0],
            "kind": row[1],
            "name": row[2],
            "data": json.loads(row[3]),
        } for row in rows
    ]


def read_resource(
    session_id: str, resource_id: str = "", query: str = "", offset: int = 0, limit: int = 6000
) -> dict:
    if (
        not isinstance(offset, int)
        or offset < 0
        or not isinstance(limit, int)
        or not 1 <= limit <= 12000
    ):
        return {"status": "error", "error": "Use offset >= 0 and limit between 1 and 12000."}
    with connection() as db:
        if resource_id:
            row = db.execute(
                "SELECT kind,name,data FROM resources WHERE session=? AND id=?",
                (session_id, resource_id),
            ).fetchone()
            if not row:
                return {"status": "error", "error": "Context reference not found in this session."}
            data = json.loads(row[2])
            if row[0] == "attachment" and isinstance(data, dict):
                data = {key: value for key, value in data.items() if key != "image_data_url"}
            text = data if isinstance(data, str) else encode(data)
            return {
                "status": "success",
                "id": resource_id,
                "name": row[1],
                "offset": offset,
                "text": text[offset : offset + limit],
                "total_chars": len(text),
                "next_offset": offset + limit if offset + limit < len(text) else None,
            }
        rows = db.execute(
            "SELECT id,kind,name,data FROM resources WHERE session=? AND (instr(lower(name),lower(?))>0 OR instr(lower(data),lower(?))>0) ORDER BY created DESC LIMIT 10",
            (session_id, query[:200], query[:200]),
        ).fetchall()
    return {
        "status": "success",
        "matches": [{"id": r[0], "kind": r[1], "name": r[2]} for r in rows],
    }


def claim_operation(
    session_id: str, run_id: str, fingerprint: str, name: str, *, recovering: bool = False
) -> tuple[bool, dict]:
    """Commit the intent before invoking a side-effectful tool, even across processes."""
    with connection() as db:
        db.execute("BEGIN IMMEDIATE")
        known = db.execute(
            "SELECT status,result FROM operations WHERE session=? AND run=? AND fingerprint=?",
            (session_id, run_id, fingerprint),
        ).fetchone()
        if known and known[0] == "success":
            return False, json.loads(known[1])
        if (
            recovering
            and db.execute(
                "SELECT 1 FROM operations WHERE session=? AND run=? AND status!='success' LIMIT 1",
                (session_id, run_id),
            ).fetchone()
        ):
            return False, {
                "status": "error",
                "error": "An earlier operation has an unknown or failed outcome. Inspect existing outputs before explicitly starting a new attempt; no additional write was executed.",
            }
        cursor = db.execute(
            "INSERT OR IGNORE INTO operations VALUES (?,?,?,?,?,?)",
            (session_id, run_id, fingerprint, name, "running", "{}"),
        )
        if cursor.rowcount:
            return True, {}
        row = db.execute(
            "SELECT status,result FROM operations WHERE session=? AND run=? AND fingerprint=?",
            (session_id, run_id, fingerprint),
        ).fetchone()
    if row[0] == "success":
        return False, json.loads(row[1])
    return False, {
        "status": "error",
        "error": "A previous attempt is incomplete or failed. Inspect existing outputs before explicitly starting a new attempt; this operation was not executed again.",
        "previous_status": row[0],
    }


def finish_operation(session_id: str, run_id: str, fingerprint: str, result: dict) -> None:
    status = "error" if result.get("status") == "error" else "success"
    with connection() as db:
        db.execute(
            "UPDATE operations SET status=?,result=? WHERE session=? AND run=? AND fingerprint=?",
            (status, encode(result), session_id, run_id, fingerprint),
        )
        name = db.execute(
            "SELECT name FROM operations WHERE session=? AND run=? AND fingerprint=?",
            (session_id, run_id, fingerprint),
        ).fetchone()[0]
        data = encode(result)
        resource_id = hashlib.sha256(("tool_result" + name + data).encode()).hexdigest()[:32]
        db.execute(
            "INSERT OR IGNORE INTO resources VALUES (?,?,?,?,?,?)",
            (session_id, resource_id, "tool_result", name, data, time.time()),
        )


def operation_statuses(session_id: str, run_id: str) -> list[dict]:
    with connection() as db:
        rows = db.execute(
            "SELECT name,status FROM operations WHERE session=? AND run=?", (session_id, run_id)
        ).fetchall()
    return [{"tool": name, "status": status} for name, status in rows]


def resource_image(session_id: str, resource_id: str) -> dict | None:
    with connection() as db:
        row = db.execute(
            "SELECT data FROM resources WHERE session=? AND id=? AND kind='attachment'",
            (session_id, resource_id),
        ).fetchone()
    data = json.loads(row[0]) if row else {}
    return data if data.get("image_data_url") else None


def get_response(session_id: str, request_id: str | None, signature: str) -> dict | None:
    if not request_id:
        return None
    with connection() as db:
        row = db.execute(
            "SELECT signature,response FROM responses WHERE session=? AND request=?",
            (session_id, request_id),
        ).fetchone()
    if not row:
        return None
    if row[0] != signature:
        raise ValueError("This request_id was already used with different inputs.")
    return json.loads(row[1])


def load_request_response(session_id: str, request_id: str) -> dict | None:
    """Internal lookup for the public progress projection; never returned verbatim."""
    with connection() as db:
        row = db.execute(
            "SELECT response FROM responses WHERE session=? AND request=?",
            (session_id, request_id),
        ).fetchone()
    return json.loads(row[0]) if row else None
