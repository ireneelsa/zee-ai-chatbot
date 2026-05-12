import json
import os
import sqlite3
import uuid
from datetime import datetime, timezone

DB_PATH = os.path.join(os.path.dirname(__file__), "zee.db")


def _connect():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def _now():
    return datetime.now(timezone.utc).isoformat()


def init_db():
    conn = _connect()
    try:
        cur = conn.cursor()
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS zee_conversations (
                id TEXT PRIMARY KEY,
                account_id TEXT NOT NULL,
                persona TEXT NOT NULL,
                title TEXT,
                archived INTEGER NOT NULL DEFAULT 0,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
            """
        )
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS zee_messages (
                id TEXT PRIMARY KEY,
                conversation_id TEXT NOT NULL,
                role TEXT NOT NULL,
                content TEXT NOT NULL,
                model TEXT,
                tokens_in INTEGER DEFAULT 0,
                tokens_out INTEGER DEFAULT 0,
                latency_ms INTEGER,
                created_at TEXT NOT NULL
            )
            """
        )
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS zee_usage (
                account_id TEXT NOT NULL,
                day TEXT NOT NULL,
                msg_count INTEGER NOT NULL DEFAULT 0,
                tokens_in INTEGER NOT NULL DEFAULT 0,
                tokens_out INTEGER NOT NULL DEFAULT 0,
                PRIMARY KEY (account_id, day)
            )
            """
        )
        cur.execute(
            "CREATE INDEX IF NOT EXISTS idx_zee_messages_conv_created "
            "ON zee_messages(conversation_id, created_at)"
        )
        conn.commit()
    finally:
        conn.close()


def create_conversation(account_id: str, persona: str) -> dict:
    conv_id = str(uuid.uuid4())
    now = _now()
    conn = _connect()
    try:
        conn.execute(
            "INSERT INTO zee_conversations "
            "(id, account_id, persona, title, archived, created_at, updated_at) "
            "VALUES (?, ?, ?, ?, 0, ?, ?)",
            (conv_id, account_id, persona, None, now, now),
        )
        conn.commit()
    finally:
        conn.close()
    return {
        "id": conv_id,
        "account_id": account_id,
        "persona": persona,
        "title": None,
        "archived": 0,
        "created_at": now,
        "updated_at": now,
    }


def get_conversation(conv_id: str, account_id: str) -> dict | None:
    conn = _connect()
    try:
        row = conn.execute(
            "SELECT id, account_id, persona, title, archived, created_at, updated_at "
            "FROM zee_conversations WHERE id = ? AND account_id = ?",
            (conv_id, account_id),
        ).fetchone()
    finally:
        conn.close()
    if row is None:
        return None
    return dict(row)


def list_messages(conv_id: str, limit: int = 50) -> list[dict]:
    conn = _connect()
    try:
        rows = conn.execute(
            "SELECT id, conversation_id, role, content, model, tokens_in, tokens_out, "
            "latency_ms, created_at FROM zee_messages "
            "WHERE conversation_id = ? ORDER BY created_at ASC LIMIT ?",
            (conv_id, limit),
        ).fetchall()
    finally:
        conn.close()
    results = []
    for row in rows:
        msg = dict(row)
        msg["content"] = json.loads(msg["content"])
        results.append(msg)
    return results


def append_message(
    conv_id: str,
    role: str,
    content: list,
    model: str | None = None,
    tokens_in: int = 0,
    tokens_out: int = 0,
    latency_ms: int | None = None,
) -> str:
    msg_id = str(uuid.uuid4())
    now = _now()
    conn = _connect()
    try:
        conn.execute(
            "INSERT INTO zee_messages "
            "(id, conversation_id, role, content, model, tokens_in, tokens_out, "
            "latency_ms, created_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                msg_id,
                conv_id,
                role,
                json.dumps(content),
                model,
                tokens_in,
                tokens_out,
                latency_ms,
                now,
            ),
        )
        conn.execute(
            "UPDATE zee_conversations SET updated_at = ? WHERE id = ?",
            (now, conv_id),
        )
        conn.commit()
    finally:
        conn.close()
    return msg_id
