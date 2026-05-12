import sqlite3
import os
from datetime import datetime, timedelta

DB_PATH = os.getenv("DB_PATH", "homework.db")

# Numeric weight for each grade label — used for average calculations
GRADE_SCORES: dict[str, int] = {
    "⭐ A'lo":             5,
    "👍 Yaxshi":           4,
    "📝 Qoniqarli":        3,
    "⚠️ Yaxshilash kerak": 2,
    "❌ Bajarilmagan":      1,
}


def get_connection() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    """Create all tables. Safe to call on every startup."""
    conn = get_connection()
    c = conn.cursor()

    c.execute("""
        CREATE TABLE IF NOT EXISTS chats (
            chat_id   INTEGER PRIMARY KEY,
            title     TEXT NOT NULL,
            chat_type TEXT NOT NULL
        )
    """)

    c.execute("""
        CREATE TABLE IF NOT EXISTS submissions (
            id            INTEGER PRIMARY KEY AUTOINCREMENT,
            student_id    INTEGER NOT NULL,
            student_name  TEXT NOT NULL,
            group_name    TEXT NOT NULL,
            file_id       TEXT NOT NULL,
            file_type     TEXT NOT NULL,
            status        TEXT NOT NULL DEFAULT 'pending',
            submitted_at  TEXT NOT NULL,
            reviewed_at   TEXT,
            feedback      TEXT,
            grade         TEXT,
            reviewer_id   INTEGER
        )
    """)

    # Stores every (chat_id, message_id) where a teacher notification was sent.
    # Used to edit/disable grade buttons after review is complete.
    c.execute("""
        CREATE TABLE IF NOT EXISTS teacher_messages (
            id            INTEGER PRIMARY KEY AUTOINCREMENT,
            submission_id INTEGER NOT NULL,
            chat_id       INTEGER NOT NULL,
            message_id    INTEGER NOT NULL
        )
    """)

    # Tracks submission timestamps per user for rate limiting.
    c.execute("""
        CREATE TABLE IF NOT EXISTS rate_limit (
            id           INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id      INTEGER NOT NULL,
            submitted_at TEXT NOT NULL
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
    conn = get_connection()
    row = conn.execute(
        """SELECT * FROM chats
           WHERE chat_type = 'parents'
             AND LOWER(title) LIKE LOWER(?)
           LIMIT 1""",
        (f"%{group_name}%parents%",),
    ).fetchone()
    conn.close()
    return dict(row) if row else None


def find_teacher_chats() -> list[dict]:
    conn = get_connection()
    rows = conn.execute("SELECT * FROM chats WHERE chat_type='teachers'").fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_all_parents_chats() -> list[dict]:
    conn = get_connection()
    rows = conn.execute("SELECT * FROM chats WHERE chat_type='parents'").fetchall()
    conn.close()
    return [dict(r) for r in rows]


def list_registered_chats() -> list[dict]:
    conn = get_connection()
    rows = conn.execute("SELECT * FROM chats ORDER BY chat_type, title").fetchall()
    conn.close()
    return [dict(r) for r in rows]


# ── Submissions — core CRUD ──────────────────────────────────────────────────

def create_submission(
    student_id: int,
    student_name: str,
    group_name: str,
    file_id: str,
    file_type: str,
) -> int:
    conn = get_connection()
    cur = conn.execute(
        """INSERT INTO submissions
               (student_id, student_name, group_name, file_id, file_type, submitted_at)
           VALUES (?, ?, ?, ?, ?, ?)""",
        (student_id, student_name, group_name, file_id, file_type,
         datetime.now().isoformat(timespec="seconds")),
    )
    sub_id = cur.lastrowid
    conn.commit()
    conn.close()
    return sub_id


def get_submission(submission_id: int) -> dict | None:
    conn = get_connection()
    row = conn.execute(
        "SELECT * FROM submissions WHERE id=?", (submission_id,)
    ).fetchone()
    conn.close()
    return dict(row) if row else None


def get_pending_submissions() -> list[dict]:
    conn = get_connection()
    rows = conn.execute(
        "SELECT * FROM submissions WHERE status='pending' ORDER BY submitted_at"
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_student_submissions(student_id: int) -> list[dict]:
    conn = get_connection()
    rows = conn.execute(
        "SELECT * FROM submissions WHERE student_id=? ORDER BY submitted_at DESC",
        (student_id,),
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def complete_review(submission_id: int, reviewer_id: int, grade: str, feedback: str):
    conn = get_connection()
    conn.execute(
        """UPDATE submissions
           SET status='reviewed', reviewed_at=?, reviewer_id=?, grade=?, feedback=?
           WHERE id=?""",
        (datetime.now().isoformat(timespec="seconds"), reviewer_id, grade, feedback, submission_id),
    )
    conn.commit()
    conn.close()


def update_review(submission_id: int, reviewer_id: int, grade: str, feedback: str):
    """Edit an existing review — updates the reviewed_at timestamp."""
    conn = get_connection()
    conn.execute(
        """UPDATE submissions
           SET grade=?, feedback=?, reviewer_id=?, reviewed_at=?
           WHERE id=?""",
        (grade, feedback, reviewer_id,
         datetime.now().isoformat(timespec="seconds"), submission_id),
    )
    conn.commit()
    conn.close()


def update_submission_file(submission_id: int, file_id: str, file_type: str):
    """Replace the file on a pending submission (resubmit feature)."""
    conn = get_connection()
    conn.execute(
        """UPDATE submissions
           SET file_id=?, file_type=?, submitted_at=?
           WHERE id=?""",
        (file_id, file_type, datetime.now().isoformat(timespec="seconds"), submission_id),
    )
    conn.commit()
    conn.close()


# ── Teacher messages (for editing grade buttons after review) ────────────────

def save_teacher_message(submission_id: int, chat_id: int, message_id: int):
    conn = get_connection()
    conn.execute(
        "INSERT INTO teacher_messages (submission_id, chat_id, message_id) VALUES (?, ?, ?)",
        (submission_id, chat_id, message_id),
    )
    conn.commit()
    conn.close()


def get_teacher_messages(submission_id: int) -> list[dict]:
    conn = get_connection()
    rows = conn.execute(
        "SELECT * FROM teacher_messages WHERE submission_id=?", (submission_id,)
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def delete_teacher_messages(submission_id: int):
    conn = get_connection()
    conn.execute("DELETE FROM teacher_messages WHERE submission_id=?", (submission_id,))
    conn.commit()
    conn.close()


# ── Search / filter ──────────────────────────────────────────────────────────

def search_submissions(query: str) -> list[dict]:
    """
    Search by status keyword, exact group name, or partial student name.
    Returns newest-first.
    """
    conn = get_connection()
    q = query.strip()
    q_lower = q.lower()

    if q_lower in ("pending", "kutilmoqda"):
        rows = conn.execute(
            "SELECT * FROM submissions WHERE status='pending' ORDER BY submitted_at DESC"
        ).fetchall()
    elif q_lower in ("reviewed", "tekshirildi"):
        rows = conn.execute(
            "SELECT * FROM submissions WHERE status='reviewed' ORDER BY submitted_at DESC"
        ).fetchall()
    else:
        rows = conn.execute(
            """SELECT * FROM submissions
               WHERE UPPER(group_name)=UPPER(?)
                  OR LOWER(student_name) LIKE LOWER(?)
               ORDER BY submitted_at DESC""",
            (q, f"%{q}%"),
        ).fetchall()

    conn.close()
    return [dict(r) for r in rows]


# ── Rate limiting ────────────────────────────────────────────────────────────

def record_submission_attempt(user_id: int):
    conn = get_connection()
    conn.execute(
        "INSERT INTO rate_limit (user_id, submitted_at) VALUES (?, ?)",
        (user_id, datetime.now().isoformat(timespec="seconds")),
    )
    conn.commit()
    conn.close()


def count_recent_submissions(user_id: int, minutes: int = 10) -> int:
    conn = get_connection()
    cutoff = (datetime.now() - timedelta(minutes=minutes)).isoformat(timespec="seconds")
    count = conn.execute(
        "SELECT COUNT(*) FROM rate_limit WHERE user_id=? AND submitted_at>?",
        (user_id, cutoff),
    ).fetchone()[0]
    conn.close()
    return count


def cleanup_old_rate_records():
    """Remove rate_limit rows older than 1 hour. Called by the scheduler."""
    conn = get_connection()
    cutoff = (datetime.now() - timedelta(hours=1)).isoformat(timespec="seconds")
    conn.execute("DELETE FROM rate_limit WHERE submitted_at<?", (cutoff,))
    conn.commit()
    conn.close()


# ── Statistics ───────────────────────────────────────────────────────────────

def _grade_average(subs: list[dict]) -> float:
    scored = [
        GRADE_SCORES[s["grade"]]
        for s in subs
        if s.get("grade") and s["grade"] in GRADE_SCORES
    ]
    return round(sum(scored) / len(scored), 1) if scored else 0.0


def get_global_stats() -> dict:
    conn = get_connection()
    total    = conn.execute("SELECT COUNT(*) FROM submissions").fetchone()[0]
    pending  = conn.execute("SELECT COUNT(*) FROM submissions WHERE status='pending'").fetchone()[0]
    reviewed = conn.execute("SELECT COUNT(*) FROM submissions WHERE status='reviewed'").fetchone()[0]
    groups   = conn.execute("SELECT COUNT(DISTINCT group_name) FROM submissions").fetchone()[0]
    students = conn.execute("SELECT COUNT(DISTINCT student_id) FROM submissions").fetchone()[0]
    conn.close()
    return {
        "total": total, "pending": pending, "reviewed": reviewed,
        "groups": groups, "students": students,
        "rate": round(reviewed / total * 100, 1) if total else 0.0,
    }


def get_group_stats(group_name: str) -> dict:
    conn = get_connection()
    rows = conn.execute(
        "SELECT * FROM submissions WHERE UPPER(group_name)=UPPER(?)",
        (group_name,),
    ).fetchall()
    conn.close()
    subs = [dict(r) for r in rows]
    return {
        "group":     group_name.upper(),
        "total":     len(subs),
        "pending":   sum(1 for s in subs if s["status"] == "pending"),
        "reviewed":  sum(1 for s in subs if s["status"] == "reviewed"),
        "avg_grade": _grade_average(subs),
    }


def get_student_stats(name_query: str) -> list[dict]:
    conn = get_connection()
    rows = conn.execute(
        """SELECT * FROM submissions
           WHERE LOWER(student_name) LIKE LOWER(?)
           ORDER BY submitted_at DESC""",
        (f"%{name_query}%",),
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_submissions_since(days_back: int = 7) -> list[dict]:
    """Return all submissions within the last N days — used by weekly report."""
    conn = get_connection()
    cutoff = (datetime.now() - timedelta(days=days_back)).isoformat(timespec="seconds")
    rows = conn.execute(
        "SELECT * FROM submissions WHERE submitted_at>? ORDER BY group_name, submitted_at",
        (cutoff,),
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]