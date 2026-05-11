import sqlite3
import os
from datetime import datetime

DB_PATH = os.getenv("DB_PATH", "homework.db")


def get_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    """Initialize all tables."""
    conn = get_connection()
    c = conn.cursor()

    # Registered group chats (parents groups, teacher groups)
    c.execute("""
        CREATE TABLE IF NOT EXISTS chats (
            chat_id     INTEGER PRIMARY KEY,
            title       TEXT NOT NULL,
            chat_type   TEXT NOT NULL  -- 'parents' | 'teachers'
        )
    """)

    # Homework submissions
    c.execute("""
        CREATE TABLE IF NOT EXISTS submissions (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            student_id      INTEGER NOT NULL,
            student_name    TEXT NOT NULL,
            group_name      TEXT NOT NULL,
            file_id         TEXT NOT NULL,
            file_type       TEXT NOT NULL,   -- 'document' | 'photo'
            status          TEXT NOT NULL DEFAULT 'pending',
            submitted_at    TEXT NOT NULL,
            reviewed_at     TEXT,
            feedback        TEXT,
            grade           TEXT,
            reviewer_id     INTEGER
        )
    """)

    conn.commit()
    conn.close()


# ── Chat registry ────────────────────────────────────────────────────────────

def register_chat(chat_id: int, title: str, chat_type: str):
    conn = get_connection()
    conn.execute(
        "INSERT OR REPLACE INTO chats (chat_id, title, chat_type) VALUES (?, ?, ?)",
        (chat_id, title, chat_type),
    )
    conn.commit()
    conn.close()


def find_parents_chat(group_name: str) -> dict | None:
    """Find the parents group chat for a given student group name."""
    conn = get_connection()
    # Flexible match: "5A parents", "5a parents", "5A Parents" etc.
    row = conn.execute(
        """
        SELECT * FROM chats
        WHERE chat_type = 'parents'
          AND LOWER(title) LIKE LOWER(?)
        LIMIT 1
        """,
        (f"%{group_name}%parents%",),
    ).fetchone()
    conn.close()
    return dict(row) if row else None


def find_teacher_chats() -> list[dict]:
    conn = get_connection()
    rows = conn.execute(
        "SELECT * FROM chats WHERE chat_type = 'teachers'"
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def list_registered_chats() -> list[dict]:
    conn = get_connection()
    rows = conn.execute("SELECT * FROM chats ORDER BY chat_type, title").fetchall()
    conn.close()
    return [dict(r) for r in rows]


# ── Submissions ──────────────────────────────────────────────────────────────

def create_submission(
    student_id: int,
    student_name: str,
    group_name: str,
    file_id: str,
    file_type: str,
) -> int:
    conn = get_connection()
    cur = conn.execute(
        """
        INSERT INTO submissions
            (student_id, student_name, group_name, file_id, file_type, submitted_at)
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        (student_id, student_name, group_name, file_id, file_type,
         datetime.now().isoformat(timespec="seconds")),
    )
    submission_id = cur.lastrowid
    conn.commit()
    conn.close()
    return submission_id


def get_submission(submission_id: int) -> dict | None:
    conn = get_connection()
    row = conn.execute(
        "SELECT * FROM submissions WHERE id = ?", (submission_id,)
    ).fetchone()
    conn.close()
    return dict(row) if row else None


def get_pending_submissions() -> list[dict]:
    conn = get_connection()
    rows = conn.execute(
        "SELECT * FROM submissions WHERE status = 'pending' ORDER BY submitted_at"
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def complete_review(
    submission_id: int,
    reviewer_id: int,
    grade: str,
    feedback: str,
):
    conn = get_connection()
    conn.execute(
        """
        UPDATE submissions
        SET status = 'reviewed',
            reviewed_at = ?,
            reviewer_id = ?,
            grade = ?,
            feedback = ?
        WHERE id = ?
        """,
        (
            datetime.now().isoformat(timespec="seconds"),
            reviewer_id,
            grade,
            feedback,
            submission_id,
        ),
    )
    conn.commit()
    conn.close()


def get_student_submissions(student_id: int) -> list[dict]:
    conn = get_connection()
    rows = conn.execute(
        "SELECT * FROM submissions WHERE student_id = ? ORDER BY submitted_at DESC",
        (student_id,),
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]