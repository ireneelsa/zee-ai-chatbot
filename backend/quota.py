import os
import sqlite3
from datetime import date

from fastapi import HTTPException

from conversations import DB_PATH


def _caps(account_type):
    if account_type == "creator":
        return (
            int(os.environ["ZEE_DAILY_MSG_CAP_CREATOR"]),
            int(os.environ["ZEE_DAILY_TOKEN_CAP_CREATOR"]),
        )
    return (
        int(os.environ["ZEE_DAILY_MSG_CAP_BRAND"]),
        int(os.environ["ZEE_DAILY_TOKEN_CAP_BRAND"]),
    )


def check_and_increment(account_id, account_type):
    msg_cap, token_cap = _caps(account_type)
    today = date.today().isoformat()
    conn = sqlite3.connect(DB_PATH)
    try:
        cur = conn.cursor()
        cur.execute("BEGIN IMMEDIATE")
        cur.execute(
            "SELECT msg_count, tokens_in, tokens_out FROM zee_usage "
            "WHERE account_id = ? AND day = ?",
            (account_id, today),
        )
        row = cur.fetchone()
        if row is None:
            msg_count, tin, tout = 0, 0, 0
        else:
            msg_count, tin, tout = int(row[0]), int(row[1]), int(row[2])
        if msg_count >= msg_cap:
            conn.rollback()
            raise HTTPException(
                status_code=429, detail="Daily message limit reached"
            )
        if (tin + tout) >= token_cap:
            conn.rollback()
            raise HTTPException(
                status_code=429, detail="Daily token limit reached"
            )
        cur.execute(
            """
            INSERT INTO zee_usage (account_id, day, msg_count, tokens_in, tokens_out)
            VALUES (?, ?, 1, 0, 0)
            ON CONFLICT(account_id, day) DO UPDATE SET
                msg_count = msg_count + 1
            """,
            (account_id, today),
        )
        conn.commit()
    finally:
        conn.close()


def finalize_usage(account_id, tokens_in, tokens_out):
    today = date.today().isoformat()
    conn = sqlite3.connect(DB_PATH)
    try:
        cur = conn.cursor()
        cur.execute(
            "UPDATE zee_usage SET tokens_in = tokens_in + ?, tokens_out = tokens_out + ? "
            "WHERE account_id = ? AND day = ?",
            (tokens_in, tokens_out, account_id, today),
        )
        conn.commit()
    finally:
        conn.close()
