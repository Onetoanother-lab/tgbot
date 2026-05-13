"""
database.py — All SQLite interactions for HomeworkBot.

Tables
──────
  chats               Registered Telegram group chats
  submissions         Student homework submissions
  teacher_messages    Message IDs of teacher notifications (for editing)
  rate_limit          Per-user submission timestamps (rate limiting)
  badges              Earned achievement badges per student
  teacher_notes       Private teacher notes on submissions
  activity_logs       Audit log of all system actions
  deadlines           Assignment deadlines per group/subject
  plagiarism_reports  Similarity reports between submissions
  ai_reviews          Cached AI analysis results per submission
"""

import sqlite3
import os
from datetime import datetime, timedelta

DB_PATH = os.getenv("DB_PATH", "homework.db")

# Numeric weight per grade label — used for averages everywhere
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
    """Create all tables. Safe to call on every startup (IF NOT EXISTS)."""
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
            file_name     TEXT,
            file_type     TEXT NOT NULL,
            status        TEXT NOT NULL DEFAULT 'pending',
            submitted_at  TEXT NOT NULL,
            reviewed_at   TEXT,
            feedback      TEXT,
            grade         TEXT,
            reviewer_id   INTEGER,
            is_late       INTEGER NOT NULL DEFAULT 0
        )
    """)

    # Stores message IDs of teacher notifications so we can edit them after review
    c.execute("""
        CREATE TABLE IF NOT EXISTS teacher_messages (
            id            INTEGER PRIMARY KEY AUTOINCREMENT,
            submission_id INTEGER NOT NULL,
            chat_id       INTEGER NOT NULL,
            message_id    INTEGER NOT NULL
        )
    """)

    # Per-user submission timestamps — pruned hourly
    c.execute("""
        CREATE TABLE IF NOT EXISTS rate_limit (
            id           INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id      INTEGER NOT NULL,
            submitted_at TEXT NOT NULL
        )
    """)

    # ── New tables ────────────────────────────────────────────────────────────

    c.execute("""
        CREATE TABLE IF NOT EXISTS badges (
            id         INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id    INTEGER NOT NULL,
            badge_type TEXT NOT NULL,
            awarded_at TEXT NOT NULL,
            UNIQUE(user_id, badge_type)
        )
    """)

    c.execute("""
        CREATE TABLE IF NOT EXISTS teacher_notes (
            id            INTEGER PRIMARY KEY AUTOINCREMENT,
            submission_id INTEGER NOT NULL,
            teacher_id    INTEGER NOT NULL,
            teacher_name  TEXT NOT NULL,
            note          TEXT NOT NULL,
            created_at    TEXT NOT NULL
        )
    """)

    c.execute("""
        CREATE TABLE IF NOT EXISTS activity_logs (
            id         INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id    INTEGER,
            action     TEXT NOT NULL,
            details    TEXT,
            created_at TEXT NOT NULL
        )
    """)

    c.execute("""
        CREATE TABLE IF NOT EXISTS deadlines (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            group_name  TEXT NOT NULL,
            subject     TEXT NOT NULL,
            description TEXT,
            due_date    TEXT NOT NULL,
            created_by  INTEGER NOT NULL,
            created_at  TEXT NOT NULL
        )
    """)

    c.execute("""
        CREATE TABLE IF NOT EXISTS plagiarism_reports (
            id               INTEGER PRIMARY KEY AUTOINCREMENT,
            submission_id_1  INTEGER NOT NULL,
            submission_id_2  INTEGER NOT NULL,
            similarity_score REAL NOT NULL,
            detected_at      TEXT NOT NULL
        )
    """)

    c.execute("""
        CREATE TABLE IF NOT EXISTS ai_reviews (
            id            INTEGER PRIMARY KEY AUTOINCREMENT,
            submission_id INTEGER NOT NULL UNIQUE,
            analysis      TEXT NOT NULL,
            score         INTEGER,
            created_at    TEXT NOT NULL
        )
    """)

    # Indexes for common query patterns
    c.execute("CREATE INDEX IF NOT EXISTS idx_submissions_student ON submissions(student_id)")
    c.execute("CREATE INDEX IF NOT EXISTS idx_submissions_group   ON submissions(group_name)")
    c.execute("CREATE INDEX IF NOT EXISTS idx_submissions_status  ON submissions(status)")
    c.execute("CREATE INDEX IF NOT EXISTS idx_activity_user       ON activity_logs(user_id)")
    c.execute("CREATE INDEX IF NOT EXISTS idx_badges_user         ON badges(user_id)")
    c.execute("CREATE INDEX IF NOT EXISTS idx_deadline_group      ON deadlines(group_name)")

    conn.commit()
    conn.close()


# ═══════════════════════════════════════════════════════════════════════════════
#  CHAT REGISTRY
# ═══════════════════════════════════════════════════════════════════════════════

def register_chat(chat_id: int, title: str, chat_type: str):
    conn = get_connection()
    conn.execute(
        "INSERT OR REPLACE INTO chats (chat_id, title, chat_type) VALUES (?, ?, ?)",
        (chat_id, title, chat_type),
    )
    conn.commit(); conn.close()


def find_parents_chat(group_name: str) -> dict | None:
    conn = get_connection()
    row = conn.execute(
        "SELECT * FROM chats WHERE chat_type='parents' AND LOWER(title) LIKE LOWER(?) LIMIT 1",
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


# ═══════════════════════════════════════════════════════════════════════════════
#  SUBMISSIONS
# ═══════════════════════════════════════════════════════════════════════════════

def create_submission(
    student_id: int,
    student_name: str,
    group_name: str,
    file_id: str,
    file_type: str,
    file_name: str | None = None,
    is_late: bool = False,
) -> int:
    conn = get_connection()
    cur = conn.execute(
        """INSERT INTO submissions
               (student_id, student_name, group_name, file_id, file_name,
                file_type, submitted_at, is_late)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
        (student_id, student_name, group_name, file_id, file_name,
         file_type, datetime.now().isoformat(timespec="seconds"), int(is_late)),
    )
    sub_id = cur.lastrowid
    conn.commit(); conn.close()
    return sub_id


def get_submission(submission_id: int) -> dict | None:
    conn = get_connection()
    row = conn.execute("SELECT * FROM submissions WHERE id=?", (submission_id,)).fetchone()
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


def get_all_submissions() -> list[dict]:
    conn = get_connection()
    rows = conn.execute("SELECT * FROM submissions ORDER BY submitted_at DESC").fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_group_submissions(group_name: str) -> list[dict]:
    conn = get_connection()
    rows = conn.execute(
        "SELECT * FROM submissions WHERE UPPER(group_name)=UPPER(?) ORDER BY submitted_at DESC",
        (group_name,),
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
    conn.commit(); conn.close()


def update_review(submission_id: int, reviewer_id: int, grade: str, feedback: str):
    conn = get_connection()
    conn.execute(
        """UPDATE submissions
           SET grade=?, feedback=?, reviewer_id=?, reviewed_at=? WHERE id=?""",
        (grade, feedback, reviewer_id,
         datetime.now().isoformat(timespec="seconds"), submission_id),
    )
    conn.commit(); conn.close()


def update_submission_file(
    submission_id: int, file_id: str, file_type: str, file_name: str | None = None
):
    conn = get_connection()
    conn.execute(
        """UPDATE submissions
           SET file_id=?, file_type=?, file_name=?, submitted_at=? WHERE id=?""",
        (file_id, file_type, file_name,
         datetime.now().isoformat(timespec="seconds"), submission_id),
    )
    conn.commit(); conn.close()


def bulk_review_group(group_name: str, reviewer_id: int, grade: str, feedback: str) -> int:
    """Mark all pending submissions for a group as reviewed. Returns count updated."""
    conn = get_connection()
    now = datetime.now().isoformat(timespec="seconds")
    cur = conn.execute(
        """UPDATE submissions
           SET status='reviewed', reviewed_at=?, reviewer_id=?, grade=?, feedback=?
           WHERE UPPER(group_name)=UPPER(?) AND status='pending'""",
        (now, reviewer_id, grade, feedback, group_name),
    )
    count = cur.rowcount
    conn.commit(); conn.close()
    return count


# ═══════════════════════════════════════════════════════════════════════════════
#  TEACHER MESSAGES
# ═══════════════════════════════════════════════════════════════════════════════

def save_teacher_message(submission_id: int, chat_id: int, message_id: int):
    conn = get_connection()
    conn.execute(
        "INSERT INTO teacher_messages (submission_id, chat_id, message_id) VALUES (?, ?, ?)",
        (submission_id, chat_id, message_id),
    )
    conn.commit(); conn.close()


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
    conn.commit(); conn.close()


# ═══════════════════════════════════════════════════════════════════════════════
#  RATE LIMITING
# ═══════════════════════════════════════════════════════════════════════════════

def record_submission_attempt(user_id: int):
    conn = get_connection()
    conn.execute(
        "INSERT INTO rate_limit (user_id, submitted_at) VALUES (?, ?)",
        (user_id, datetime.now().isoformat(timespec="seconds")),
    )
    conn.commit(); conn.close()


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
    conn = get_connection()
    cutoff = (datetime.now() - timedelta(hours=1)).isoformat(timespec="seconds")
    conn.execute("DELETE FROM rate_limit WHERE submitted_at<?", (cutoff,))
    conn.commit(); conn.close()


# ═══════════════════════════════════════════════════════════════════════════════
#  BADGES
# ═══════════════════════════════════════════════════════════════════════════════

BADGE_LABELS = {
    "streak_7":    "🔥 7 kunlik ketma-ketlik",
    "fast":        "🚀 Tez topshiruvchi",
    "perfect":     "⭐ Mukammal baho",
    "clean_code":  "🧠 Toza kod",
    "consistent":  "🏅 Izchil o'quvchi",
    "first_sub":   "🎯 Birinchi topshiriq",
    "ten_subs":    "💎 10 ta topshiriq",
}


def award_badge(user_id: int, badge_type: str) -> bool:
    """Award a badge. Returns True if newly awarded, False if already had it."""
    conn = get_connection()
    try:
        conn.execute(
            "INSERT INTO badges (user_id, badge_type, awarded_at) VALUES (?, ?, ?)",
            (user_id, badge_type, datetime.now().isoformat(timespec="seconds")),
        )
        conn.commit()
        return True
    except sqlite3.IntegrityError:
        return False  # UNIQUE constraint — already has this badge
    finally:
        conn.close()


def get_user_badges(user_id: int) -> list[dict]:
    conn = get_connection()
    rows = conn.execute(
        "SELECT * FROM badges WHERE user_id=? ORDER BY awarded_at DESC",
        (user_id,),
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def has_badge(user_id: int, badge_type: str) -> bool:
    conn = get_connection()
    count = conn.execute(
        "SELECT COUNT(*) FROM badges WHERE user_id=? AND badge_type=?",
        (user_id, badge_type),
    ).fetchone()[0]
    conn.close()
    return count > 0


# ═══════════════════════════════════════════════════════════════════════════════
#  TEACHER NOTES
# ═══════════════════════════════════════════════════════════════════════════════

def add_teacher_note(
    submission_id: int, teacher_id: int, teacher_name: str, note: str
) -> int:
    conn = get_connection()
    cur = conn.execute(
        """INSERT INTO teacher_notes
               (submission_id, teacher_id, teacher_name, note, created_at)
           VALUES (?, ?, ?, ?, ?)""",
        (submission_id, teacher_id, teacher_name, note,
         datetime.now().isoformat(timespec="seconds")),
    )
    note_id = cur.lastrowid
    conn.commit(); conn.close()
    return note_id


def get_submission_notes(submission_id: int) -> list[dict]:
    conn = get_connection()
    rows = conn.execute(
        "SELECT * FROM teacher_notes WHERE submission_id=? ORDER BY created_at DESC",
        (submission_id,),
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


# ═══════════════════════════════════════════════════════════════════════════════
#  ACTIVITY LOGS
# ═══════════════════════════════════════════════════════════════════════════════

def log_action(action: str, user_id: int | None = None, details: str | None = None):
    conn = get_connection()
    conn.execute(
        "INSERT INTO activity_logs (user_id, action, details, created_at) VALUES (?, ?, ?, ?)",
        (user_id, action, details, datetime.now().isoformat(timespec="seconds")),
    )
    conn.commit(); conn.close()


def get_recent_logs(limit: int = 50) -> list[dict]:
    conn = get_connection()
    rows = conn.execute(
        "SELECT * FROM activity_logs ORDER BY created_at DESC LIMIT ?", (limit,)
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


# ═══════════════════════════════════════════════════════════════════════════════
#  DEADLINES
# ═══════════════════════════════════════════════════════════════════════════════

def create_deadline(
    group_name: str, subject: str, due_date: str,
    created_by: int, description: str | None = None
) -> int:
    conn = get_connection()
    cur = conn.execute(
        """INSERT INTO deadlines
               (group_name, subject, description, due_date, created_by, created_at)
           VALUES (?, ?, ?, ?, ?, ?)""",
        (group_name.upper(), subject, description, due_date, created_by,
         datetime.now().isoformat(timespec="seconds")),
    )
    dl_id = cur.lastrowid
    conn.commit(); conn.close()
    return dl_id


def get_group_deadlines(group_name: str) -> list[dict]:
    conn = get_connection()
    rows = conn.execute(
        """SELECT * FROM deadlines
           WHERE UPPER(group_name)=UPPER(?) AND due_date >= ?
           ORDER BY due_date""",
        (group_name, datetime.now().strftime("%Y-%m-%d")),
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_all_upcoming_deadlines() -> list[dict]:
    conn = get_connection()
    rows = conn.execute(
        "SELECT * FROM deadlines WHERE due_date >= ? ORDER BY due_date",
        (datetime.now().strftime("%Y-%m-%d"),),
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_overdue_for_group(group_name: str) -> list[dict]:
    """Deadlines that have passed with no submission from that group."""
    conn = get_connection()
    rows = conn.execute(
        "SELECT * FROM deadlines WHERE UPPER(group_name)=UPPER(?) AND due_date < ?",
        (group_name, datetime.now().strftime("%Y-%m-%d")),
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


# ═══════════════════════════════════════════════════════════════════════════════
#  PLAGIARISM REPORTS
# ═══════════════════════════════════════════════════════════════════════════════

def save_plagiarism_report(
    sub_id_1: int, sub_id_2: int, similarity: float
) -> int:
    conn = get_connection()
    # Avoid duplicate pairs regardless of order
    existing = conn.execute(
        """SELECT id FROM plagiarism_reports
           WHERE (submission_id_1=? AND submission_id_2=?)
              OR (submission_id_1=? AND submission_id_2=?)""",
        (sub_id_1, sub_id_2, sub_id_2, sub_id_1),
    ).fetchone()
    if existing:
        conn.close()
        return existing["id"]

    cur = conn.execute(
        """INSERT INTO plagiarism_reports
               (submission_id_1, submission_id_2, similarity_score, detected_at)
           VALUES (?, ?, ?, ?)""",
        (sub_id_1, sub_id_2, similarity,
         datetime.now().isoformat(timespec="seconds")),
    )
    report_id = cur.lastrowid
    conn.commit(); conn.close()
    return report_id


def get_plagiarism_for_submission(submission_id: int) -> list[dict]:
    conn = get_connection()
    rows = conn.execute(
        """SELECT * FROM plagiarism_reports
           WHERE submission_id_1=? OR submission_id_2=?
           ORDER BY similarity_score DESC""",
        (submission_id, submission_id),
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


# ═══════════════════════════════════════════════════════════════════════════════
#  AI REVIEWS
# ═══════════════════════════════════════════════════════════════════════════════

def save_ai_review(submission_id: int, analysis: str, score: int | None = None):
    conn = get_connection()
    conn.execute(
        """INSERT OR REPLACE INTO ai_reviews
               (submission_id, analysis, score, created_at)
           VALUES (?, ?, ?, ?)""",
        (submission_id, analysis, score,
         datetime.now().isoformat(timespec="seconds")),
    )
    conn.commit(); conn.close()


def get_ai_review(submission_id: int) -> dict | None:
    conn = get_connection()
    row = conn.execute(
        "SELECT * FROM ai_reviews WHERE submission_id=?", (submission_id,)
    ).fetchone()
    conn.close()
    return dict(row) if row else None


# ═══════════════════════════════════════════════════════════════════════════════
#  SEARCH / FILTER
# ═══════════════════════════════════════════════════════════════════════════════

def search_submissions(query: str) -> list[dict]:
    conn = get_connection()
    q_lower = query.strip().lower()
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
            (query.strip(), f"%{query.strip()}%"),
        ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


# ═══════════════════════════════════════════════════════════════════════════════
#  STATISTICS & ANALYTICS
# ═══════════════════════════════════════════════════════════════════════════════

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
    subs = get_group_submissions(group_name)
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
        "SELECT * FROM submissions WHERE LOWER(student_name) LIKE LOWER(?) ORDER BY submitted_at DESC",
        (f"%{name_query}%",),
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_student_dashboard(student_id: int) -> dict:
    """All data needed for /dashboard in one call."""
    subs = get_student_submissions(student_id)
    reviewed = [s for s in subs if s["status"] == "reviewed"]
    pending  = [s for s in subs if s["status"] == "pending"]
    avg      = _grade_average(subs)

    # Streak: count consecutive days with at least one submission ending today
    dates = sorted({s["submitted_at"][:10] for s in subs}, reverse=True)
    streak = 0
    check  = datetime.now().date()
    for d in dates:
        if str(check) == d:
            streak += 1
            check -= timedelta(days=1)
        else:
            break

    last = subs[0]["submitted_at"][:10] if subs else "—"
    badges = get_user_badges(student_id)

    return {
        "total":    len(subs),
        "pending":  len(pending),
        "reviewed": len(reviewed),
        "avg":      avg,
        "streak":   streak,
        "last":     last,
        "badges":   badges,
    }


def get_leaderboard(days_back: int = 7) -> list[dict]:
    """
    Leaderboard based on:
      - average grade score (weight 50%)
      - submission count (weight 30%)
      - streak (weight 20%)
    """
    conn = get_connection()
    cutoff = (datetime.now() - timedelta(days=days_back)).isoformat(timespec="seconds")
    rows = conn.execute(
        """SELECT student_id, student_name, group_name,
                  COUNT(*) AS sub_count,
                  AVG(CASE
                    WHEN grade="⭐ A'lo" THEN 5
                    WHEN grade='👍 Yaxshi' THEN 4
                    WHEN grade='📝 Qoniqarli' THEN 3
                    WHEN grade='⚠️ Yaxshilash kerak' THEN 2
                    WHEN grade='❌ Bajarilmagan' THEN 1
                    ELSE NULL END) AS avg_grade
           FROM submissions
           WHERE submitted_at > ? AND status='reviewed'
           GROUP BY student_id
           ORDER BY avg_grade DESC, sub_count DESC""",
        (cutoff,),
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_submissions_since(days_back: int = 7) -> list[dict]:
    conn = get_connection()
    cutoff = (datetime.now() - timedelta(days=days_back)).isoformat(timespec="seconds")
    rows = conn.execute(
        "SELECT * FROM submissions WHERE submitted_at>? ORDER BY group_name, submitted_at",
        (cutoff,),
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_submissions_per_day(days_back: int = 14) -> list[dict]:
    """Returns list of {date, count} for chart data."""
    conn = get_connection()
    cutoff = (datetime.now() - timedelta(days=days_back)).strftime("%Y-%m-%d")
    rows = conn.execute(
        """SELECT SUBSTR(submitted_at, 1, 10) AS date, COUNT(*) AS count
           FROM submissions
           WHERE submitted_at >= ?
           GROUP BY date ORDER BY date""",
        (cutoff,),
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_grade_distribution() -> list[dict]:
    conn = get_connection()
    rows = conn.execute(
        """SELECT grade, COUNT(*) AS count
           FROM submissions WHERE grade IS NOT NULL
           GROUP BY grade ORDER BY count DESC""",
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]