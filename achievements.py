"""
achievements.py — Badge evaluation and award logic.

Call check_and_award() after any submission or review event.
It evaluates all badge conditions and awards new ones.

Badges
──────
  first_sub   First submission ever
  ten_subs    10 total submissions
  streak_7    7-day consecutive submission streak
  fast        Submitted within 1 hour of deadline creation
  perfect     Received "⭐ A'lo" grade
  clean_code  AI score >= 85
  consistent  >= 3 reviewed submissions in 7 days
"""

import logging
from datetime import datetime, timedelta
from database import (
    award_badge, has_badge, get_user_badges,
    get_student_submissions, get_ai_review, BADGE_LABELS,
)

logger = logging.getLogger(__name__)


async def check_and_award(
    student_id: int,
    student_name: str,
    context=None,          # PTB context — used to DM the student
) -> list[str]:
    """
    Evaluate all badge conditions for a student.
    Returns list of newly awarded badge types.
    """
    newly_awarded: list[str] = []
    subs = get_student_submissions(student_id)

    # ── first_sub ─────────────────────────────────────────────────────────────
    if len(subs) >= 1 and not has_badge(student_id, "first_sub"):
        if award_badge(student_id, "first_sub"):
            newly_awarded.append("first_sub")

    # ── ten_subs ──────────────────────────────────────────────────────────────
    if len(subs) >= 10 and not has_badge(student_id, "ten_subs"):
        if award_badge(student_id, "ten_subs"):
            newly_awarded.append("ten_subs")

    # ── streak_7 ──────────────────────────────────────────────────────────────
    if not has_badge(student_id, "streak_7"):
        streak = _calculate_streak(subs)
        if streak >= 7:
            if award_badge(student_id, "streak_7"):
                newly_awarded.append("streak_7")

    # ── perfect ───────────────────────────────────────────────────────────────
    if not has_badge(student_id, "perfect"):
        if any(s.get("grade") == "⭐ A'lo" for s in subs):
            if award_badge(student_id, "perfect"):
                newly_awarded.append("perfect")

    # ── consistent ───────────────────────────────────────────────────────────
    if not has_badge(student_id, "consistent"):
        cutoff  = (datetime.now() - timedelta(days=7)).isoformat(timespec="seconds")
        recent  = [s for s in subs if s["submitted_at"] > cutoff and s["status"] == "reviewed"]
        if len(recent) >= 3:
            if award_badge(student_id, "consistent"):
                newly_awarded.append("consistent")

    # ── clean_code — checked separately after AI review ──────────────────────
    # (called by check_clean_code_badge after AI result is stored)

    # Notify student of new badges
    if newly_awarded and context:
        await _notify_badges(context, student_id, student_name, newly_awarded)

    return newly_awarded


async def check_clean_code_badge(
    student_id: int, student_name: str, submission_id: int, context=None
) -> bool:
    """Award clean_code badge if AI score >= 85."""
    if has_badge(student_id, "clean_code"):
        return False
    ai = get_ai_review(submission_id)
    if ai and ai.get("score") and int(ai["score"]) >= 85:
        awarded = award_badge(student_id, "clean_code")
        if awarded and context:
            await _notify_badges(context, student_id, student_name, ["clean_code"])
        return awarded
    return False


async def _notify_badges(context, student_id: int, student_name: str, badge_types: list[str]):
    """Send badge notification DM to student."""
    if not badge_types:
        return
    lines = [f"🎉 *{student_name}, yangi yutuq(lar) qo'lga kiritildi!*\n"]
    for bt in badge_types:
        label = BADGE_LABELS.get(bt, bt)
        lines.append(f"  {label}")
    lines.append("\n`/badges` buyrug'i bilan barcha yutuqlaringizni ko'ring!")
    try:
        await context.bot.send_message(
            chat_id=student_id,
            text="\n".join(lines),
            parse_mode="Markdown",
        )
    except Exception as e:
        logger.warning("Could not send badge notification to %s: %s", student_id, e)


def _calculate_streak(subs: list[dict]) -> int:
    """Count consecutive days (ending today) with at least one submission."""
    dates   = sorted({s["submitted_at"][:10] for s in subs}, reverse=True)
    streak  = 0
    check   = datetime.now().date()
    for d in dates:
        if str(check) == d:
            streak += 1
            check -= timedelta(days=1)
        else:
            break
    return streak


def format_badges(user_id: int) -> str:
    """Format a student's badge list for display."""
    badges = get_user_badges(user_id)
    if not badges:
        return "🎖️ *Yutuqlar*\n\nHali hech qanday yutuq yo'q.\nFaol bo'ling va yutuqlar qozonin!"

    lines = [f"🎖️ *Mening yutuqlarim* — {len(badges)} ta\n"]
    for b in badges:
        label = BADGE_LABELS.get(b["badge_type"], b["badge_type"])
        date  = b["awarded_at"][:10]
        lines.append(f"  {label}  _{date}_")
    return "\n".join(lines)