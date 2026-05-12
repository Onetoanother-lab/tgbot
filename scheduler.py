"""
scheduler.py — Background jobs using PTB's built-in JobQueue (APScheduler).

Jobs:
  • weekly_report  — every Monday 08:00 UTC, sends grade summary to each parents group
  • cleanup_rates  — every hour, prunes old rate_limit rows
"""

import logging
from collections import defaultdict
from telegram.ext import ContextTypes

import database as db
import messages as msg

logger = logging.getLogger(__name__)


async def weekly_report_job(context: ContextTypes.DEFAULT_TYPE):
    """
    Fired every Monday at 08:00 UTC by the JobQueue.
    Collects the past 7 days of submissions, groups them by group_name,
    and sends a summary to each matching parents chat.
    """
    logger.info("Running weekly report job…")
    submissions = db.get_submissions_since(days_back=7)

    if not submissions:
        logger.info("No submissions in the past 7 days — skipping report.")
        return

    # Group submissions by group_name
    by_group: dict[str, list[dict]] = defaultdict(list)
    for s in submissions:
        by_group[s["group_name"]].append(s)

    parents_chats = db.get_all_parents_chats()

    for group_name, subs in by_group.items():
        # Find the parents chat for this group
        parents_chat = next(
            (c for c in parents_chats if group_name.lower() in c["title"].lower()),
            None,
        )
        if not parents_chat:
            logger.warning("No parents chat found for group %s — skipping.", group_name)
            continue

        # Build stats for this group
        total    = len(subs)
        reviewed = sum(1 for s in subs if s["status"] == "reviewed")
        pending  = total - reviewed
        avg = db._grade_average(subs)

        stats = {"total": total, "reviewed": reviewed, "pending": pending, "avg_grade": avg}
        text  = msg.weekly_report(group_name, stats)

        try:
            await context.bot.send_message(
                chat_id=parents_chat["chat_id"],
                text=text,
                parse_mode="Markdown",
            )
            logger.info("Weekly report sent to %s parents group.", group_name)
        except Exception as e:
            logger.error("Failed to send weekly report to %s: %s", group_name, e)


async def cleanup_rate_limits_job(context: ContextTypes.DEFAULT_TYPE):
    """Prune stale rate_limit rows — runs every hour."""
    db.cleanup_old_rate_records()
    logger.debug("Rate limit table cleaned up.")


def register_jobs(app):
    """
    Attach recurring jobs to the application's JobQueue.
    Call this inside main() after the Application is built.
    """
    jq = app.job_queue

    # Weekly report — every Monday at 08:00 UTC
    jq.run_daily(
        weekly_report_job,
        time=__import__("datetime").time(hour=8, minute=0),
        days=(0,),   # 0 = Monday in PTB's JobQueue (Mon=0 … Sun=6)
        name="weekly_report",
    )

    # Rate limit cleanup — every 60 minutes
    jq.run_repeating(
        cleanup_rate_limits_job,
        interval=3600,
        first=60,
        name="cleanup_rates",
    )

    logger.info("Scheduled jobs registered: weekly_report, cleanup_rates")