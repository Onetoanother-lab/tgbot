"""
activity_log.py — Structured action logging helpers.

All log entries go to the activity_logs table via database.log_action().
Import this module wherever you need to track an event.
"""

from database import log_action


def log_submission(student_id: int, student_name: str, sub_id: int, group: str):
    log_action("submission_created", student_id,
               f"#{sub_id} — {student_name} ({group})")


def log_resubmission(student_id: int, student_name: str, sub_id: int):
    log_action("submission_updated", student_id,
               f"#{sub_id} — {student_name} resubmitted")


def log_review(teacher_id: int, teacher_name: str, sub_id: int, grade: str):
    log_action("review_submitted", teacher_id,
               f"#{sub_id} graded '{grade}' by {teacher_name}")


def log_review_edit(teacher_id: int, teacher_name: str, sub_id: int, grade: str):
    log_action("review_edited", teacher_id,
               f"#{sub_id} re-graded '{grade}' by {teacher_name}")


def log_export(user_id: int):
    log_action("csv_exported", user_id)


def log_reminder_sent(user_id: int, group: str):
    log_action("reminder_sent", user_id, f"Group: {group}")


def log_bulk_review(teacher_id: int, group: str, count: int):
    log_action("bulk_review", teacher_id, f"Group {group}: {count} submissions")


def log_deadline_created(teacher_id: int, group: str, subject: str, due: str):
    log_action("deadline_created", teacher_id, f"{group}/{subject} due {due}")


def log_ai_review(sub_id: int, score: int | None):
    log_action("ai_review_done", None, f"#{sub_id} score={score}")


def log_pdf_generated(user_id: int, target: str):
    log_action("pdf_generated", user_id, target)