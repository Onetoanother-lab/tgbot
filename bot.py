"""
HomeworkBot — main entry point.

Conversation states
───────────────────
SUBMIT flow   (student):  ASK_NAME → ASK_GROUP → ASK_FILE → done
RESUBMIT flow (student):  RESUBMIT_FILE → done
REVIEW flow   (teacher):  grade button → /feedback <id> <text>
"""

import csv
import io
import logging
import os
from datetime import datetime

from dotenv import load_dotenv
from telegram import (
    Update,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
)
from telegram.ext import (
    Application,
    CallbackQueryHandler,
    ChatMemberHandler,
    CommandHandler,
    ContextTypes,
    ConversationHandler,
    MessageHandler,
    filters,
)
from telegram.constants import ParseMode

import database as db
import messages as msg
from scheduler import register_jobs

load_dotenv()

logging.basicConfig(
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)

TOKEN = os.environ["BOT_TOKEN"]

# Teacher's personal Telegram chat ID (optional).
# Get it with /myid, then set TEACHER_CHAT_ID in Render Environment.
TEACHER_CHAT_ID: int | None = (
    int(os.environ["TEACHER_CHAT_ID"]) if os.getenv("TEACHER_CHAT_ID") else None
)

# ── Conversation states ───────────────────────────────────────────────────────
ASK_NAME, ASK_GROUP, ASK_FILE = range(3)
RESUBMIT_FILE = 10

# ── Pagination ────────────────────────────────────────────────────────────────
PAGE_SIZE = 5

# ── Rate limiting ─────────────────────────────────────────────────────────────
MAX_SUBMISSIONS = 3      # per window
RATE_WINDOW_MIN = 10     # minutes


# ═══════════════════════════════════════════════════════════════════════════════
#  UTILITY HELPERS
# ═══════════════════════════════════════════════════════════════════════════════

async def send_safe(context: ContextTypes.DEFAULT_TYPE, chat_id: int, text: str, **kwargs):
    """Send a message, swallowing errors (e.g. bot not in group)."""
    try:
        await context.bot.send_message(
            chat_id=chat_id,
            text=text,
            parse_mode=ParseMode.MARKDOWN,
            **kwargs,
        )
    except Exception as exc:
        logger.warning("send_safe failed to %s: %s", chat_id, exc)


def _paginate(items: list, page: int, size: int = PAGE_SIZE) -> tuple[list, int]:
    """Return (page_items, total_pages). page is 1-indexed."""
    total_pages = max(1, (len(items) + size - 1) // size)
    page = max(1, min(page, total_pages))
    start = (page - 1) * size
    return items[start: start + size], total_pages


def _pagination_keyboard(
    page: int,
    total_pages: int,
    callback_prefix: str,
) -> InlineKeyboardMarkup | None:
    """Build Previous / Next buttons. Returns None if only one page."""
    if total_pages <= 1:
        return None
    buttons = []
    if page > 1:
        buttons.append(InlineKeyboardButton("◀️ Oldingi", callback_data=f"{callback_prefix}:{page-1}"))
    if page < total_pages:
        buttons.append(InlineKeyboardButton("Keyingi ▶️", callback_data=f"{callback_prefix}:{page+1}"))
    return InlineKeyboardMarkup([buttons]) if buttons else None


async def _send_file_to_teacher(
    context: ContextTypes.DEFAULT_TYPE,
    chat_id: int,
    sub: dict,
    caption: str,
    keyboard: InlineKeyboardMarkup,
):
    """
    Send a single message (file + caption + grade buttons) to one teacher destination.
    Saves the resulting message_id so we can edit it after review.
    """
    try:
        if sub["file_type"] == "photo":
            sent = await context.bot.send_photo(
                chat_id=chat_id,
                photo=sub["file_id"],
                caption=caption,
                parse_mode=ParseMode.MARKDOWN,
                reply_markup=keyboard,
            )
        else:
            sent = await context.bot.send_document(
                chat_id=chat_id,
                document=sub["file_id"],
                caption=caption,
                parse_mode=ParseMode.MARKDOWN,
                reply_markup=keyboard,
            )
        # Record message_id so we can edit it after review
        db.save_teacher_message(sub["id"], chat_id, sent.message_id)
    except Exception as e:
        logger.warning("Could not send to teacher chat %s: %s", chat_id, e)


async def _notify_teachers(
    context: ContextTypes.DEFAULT_TYPE,
    sub: dict,
    caption: str,
    keyboard: InlineKeyboardMarkup,
):
    """Send submission to all teacher groups + optional teacher DM."""
    for tc in db.find_teacher_chats():
        await _send_file_to_teacher(context, tc["chat_id"], sub, caption, keyboard)

    if TEACHER_CHAT_ID:
        await _send_file_to_teacher(context, TEACHER_CHAT_ID, sub, caption, keyboard)


async def _finalize_review(
    context: ContextTypes.DEFAULT_TYPE,
    sub: dict,
    grade: str,
    feedback: str,
    reviewer_name: str,
    is_edit: bool = False,
):
    """
    After a review is saved:
      1. Edit every teacher message to show the result and remove grade buttons.
      2. Notify the student.
      3. Notify the parents group.
    """
    sub_id = sub["id"]

    # 1. Edit teacher messages — remove buttons, append review info
    reviewed_at = datetime.now().strftime("%Y-%m-%d %H:%M")
    new_caption = msg.reviewed_caption(
        sub_id, sub["student_name"], sub["group_name"],
        grade, reviewer_name, reviewed_at,
    )

    for tm in db.get_teacher_messages(sub_id):
        try:
            await context.bot.edit_message_caption(
                chat_id=tm["chat_id"],
                message_id=tm["message_id"],
                caption=new_caption,
                parse_mode=ParseMode.MARKDOWN,
                reply_markup=None,   # removes all inline buttons
            )
        except Exception as e:
            logger.warning("Could not edit teacher message: %s", e)

    db.delete_teacher_messages(sub_id)

    # 2. Notify student
    if is_edit:
        student_text = msg.review_updated_student(
            sub_id, grade, feedback, sub["student_name"]
        )
    else:
        student_text = msg.review_complete_student(
            sub_id, grade, feedback, sub["student_name"]
        )
    await send_safe(context, sub["student_id"], student_text)

    # 3. Notify parents group
    parents_chat = db.find_parents_chat(sub["group_name"])
    if parents_chat:
        if is_edit:
            parent_text = msg.review_updated_parents(
                sub_id, sub["student_name"], sub["group_name"], grade, feedback
            )
        else:
            parent_text = msg.review_complete_parents(
                sub_id, sub["student_name"], sub["group_name"], grade, feedback
            )
        await send_safe(context, parents_chat["chat_id"], parent_text)


# ═══════════════════════════════════════════════════════════════════════════════
#  GRADE BUTTONS
# ═══════════════════════════════════════════════════════════════════════════════

GRADES = ["⭐ A'lo", "👍 Yaxshi", "📝 Qoniqarli", "⚠️ Yaxshilash kerak", "❌ Bajarilmagan"]


def _review_keyboard(submission_id: int) -> InlineKeyboardMarkup:
    buttons = [
        [InlineKeyboardButton(g, callback_data=f"grade|{submission_id}|{g}")]
        for g in GRADES
    ]
    return InlineKeyboardMarkup(buttons)


# ═══════════════════════════════════════════════════════════════════════════════
#  GROUP AUTO-REGISTRATION
# ═══════════════════════════════════════════════════════════════════════════════

async def on_my_chat_member(update: Update, context: ContextTypes.DEFAULT_TYPE):
    result = update.my_chat_member
    if result.new_chat_member.status not in ("member", "administrator"):
        return

    chat = result.chat
    if chat.type not in ("group", "supergroup"):
        return

    title       = chat.title or ""
    title_lower = title.lower()

    if "parents" in title_lower:
        chat_type = "parents"
    elif "teacher" in title_lower:
        chat_type = "teachers"
    else:
        return

    db.register_chat(chat.id, title, chat_type)
    logger.info("Auto-registered %s: %s (%s)", chat_type, title, chat.id)

    chat_type_uz = "ota-onalar" if chat_type == "parents" else "o'qituvchilar"
    await context.bot.send_message(
        chat_id=chat.id,
        text=(
            f"✅ *HomeworkBot bu guruhni* *{chat_type_uz}* guruhi sifatida ro'yxatdan o'tkazdi.\n"
            f"Guruh nomi: `{title}`\n\n"
            f"Uy vazifalari haqida bildirishnomalar shu yerga yuboriladi."
        ),
        parse_mode=ParseMode.MARKDOWN,
    )


async def cmd_register(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat = update.effective_chat
    if chat.type not in ("group", "supergroup"):
        await update.message.reply_text("⚠️ Bu buyruqni faqat guruh ichida ishlating.")
        return

    command    = update.message.text.split("@")[0].lstrip("/")
    chat_type  = "parents" if "parents" in command else "teachers"
    chat_type_uz = "ota-onalar" if chat_type == "parents" else "o'qituvchilar"

    db.register_chat(chat.id, chat.title, chat_type)
    await update.message.reply_text(
        f"✅ *{chat.title}* guruhi *{chat_type_uz}* guruhi sifatida ro'yxatdan o'tkazildi.",
        parse_mode=ParseMode.MARKDOWN,
    )


async def cmd_list_chats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chats = db.list_registered_chats()
    if not chats:
        await update.message.reply_text("Hali hech qanday guruh ro'yxatdan o'tmagan.")
        return
    lines = ["*Ro'yxatdan o'tgan guruhlar:*\n"]
    for c in chats:
        lines.append(f"• [{c['chat_type'].upper()}] {c['title']} (`{c['chat_id']}`)")
    await update.message.reply_text("\n".join(lines), parse_mode=ParseMode.MARKDOWN)


# ═══════════════════════════════════════════════════════════════════════════════
#  STUDENT — SUBMIT CONVERSATION
# ═══════════════════════════════════════════════════════════════════════════════

async def cmd_submit(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    user_id = update.effective_user.id

    # ── Rate limit check ──────────────────────────────────────────────────────
    recent = db.count_recent_submissions(user_id, minutes=RATE_WINDOW_MIN)
    if recent >= MAX_SUBMISSIONS:
        from datetime import timedelta
        import sqlite3
        # Calculate approximate wait time from oldest recent record
        await update.message.reply_text(
            msg.rate_limit_warning(RATE_WINDOW_MIN),
            parse_mode=ParseMode.MARKDOWN,
        )
        return ConversationHandler.END

    await update.message.reply_text(
        msg.step_ask_name(),
        parse_mode=ParseMode.MARKDOWN,
    )
    return ASK_NAME


async def got_name(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    name = update.message.text.strip()
    if len(name) < 2:
        await update.message.reply_text("⚠️ Ism juda qisqa. Qaytadan kiriting:")
        return ASK_NAME

    context.user_data["student_name"] = name
    await update.message.reply_text(
        msg.step_ask_group(name),
        parse_mode=ParseMode.MARKDOWN,
    )
    return ASK_GROUP


async def got_group(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    group = update.message.text.strip()
    if not group:
        await update.message.reply_text(
            "⚠️ Guruh nomi bo'sh bo'lishi mumkin emas. Qaytadan kiriting:"
        )
        return ASK_GROUP

    context.user_data["group_name"] = group.upper()
    await update.message.reply_text(
        msg.step_ask_file(group.upper()),
        parse_mode=ParseMode.MARKDOWN,
    )
    return ASK_FILE


async def got_file(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    message = update.message

    if message.photo:
        file_id, file_type = message.photo[-1].file_id, "photo"
    elif message.document:
        file_id, file_type = message.document.file_id, "document"
    else:
        await message.reply_text(
            "⚠️ Iltimos, *rasm* yoki *hujjat* (PDF, Word, rasm fayl) yuboring.",
            parse_mode=ParseMode.MARKDOWN,
        )
        return ASK_FILE

    student_name = context.user_data["student_name"]
    group_name   = context.user_data["group_name"]
    student_id   = update.effective_user.id

    # Log attempt for rate limiting BEFORE saving submission
    db.record_submission_attempt(student_id)

    sub_id = db.create_submission(student_id, student_name, group_name, file_id, file_type)
    sub    = db.get_submission(sub_id)

    # 1. Confirm to student
    await message.reply_text(
        msg.submission_received(sub_id, student_name, group_name),
        parse_mode=ParseMode.MARKDOWN,
    )

    # 2. Notify parents group
    parents_chat = db.find_parents_chat(group_name)
    if parents_chat:
        await send_safe(
            context,
            parents_chat["chat_id"],
            msg.parents_notification(sub_id, student_name, group_name),
        )

    # 3. Single message to teacher group(s) + optional DM
    caption  = msg.teacher_notification(sub_id, student_name, group_name, file_type)
    keyboard = _review_keyboard(sub_id)
    await _notify_teachers(context, sub, caption, keyboard)

    context.user_data.clear()
    return ConversationHandler.END


async def cancel_submit(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    context.user_data.clear()
    await update.message.reply_text("❌ Yuborish bekor qilindi.")
    return ConversationHandler.END


# ═══════════════════════════════════════════════════════════════════════════════
#  STUDENT — RESUBMIT CONVERSATION
# ═══════════════════════════════════════════════════════════════════════════════

async def cmd_resubmit(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    args = context.args
    if not args:
        await update.message.reply_text(
            "Ishlatish: `/resubmit <raqam>`\nMisol: `/resubmit 42`",
            parse_mode=ParseMode.MARKDOWN,
        )
        return ConversationHandler.END

    try:
        sub_id = int(args[0])
    except ValueError:
        await update.message.reply_text("⚠️ Noto'g'ri raqam.")
        return ConversationHandler.END

    sub = db.get_submission(sub_id)
    if not sub:
        await update.message.reply_text("⚠️ Topshiriq topilmadi.")
        return ConversationHandler.END

    if sub["student_id"] != update.effective_user.id:
        await update.message.reply_text("⚠️ Bu topshiriq sizga tegishli emas.")
        return ConversationHandler.END

    if sub["status"] != "pending":
        await update.message.reply_text(
            f"⚠️ `#{sub_id}` allaqachon tekshirilgan. Yangilash mumkin emas.",
            parse_mode=ParseMode.MARKDOWN,
        )
        return ConversationHandler.END

    context.user_data["resubmit_id"] = sub_id
    await update.message.reply_text(
        msg.resubmit_ask_file(sub_id),
        parse_mode=ParseMode.MARKDOWN,
    )
    return RESUBMIT_FILE


async def got_resubmit_file(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    message = update.message
    sub_id  = context.user_data.get("resubmit_id")

    if message.photo:
        file_id, file_type = message.photo[-1].file_id, "photo"
    elif message.document:
        file_id, file_type = message.document.file_id, "document"
    else:
        await message.reply_text("⚠️ Iltimos, rasm yoki hujjat yuboring.")
        return RESUBMIT_FILE

    # Update the submission in DB
    db.update_submission_file(sub_id, file_id, file_type)
    sub = db.get_submission(sub_id)

    await message.reply_text(
        msg.resubmit_confirmed(sub_id),
        parse_mode=ParseMode.MARKDOWN,
    )

    # Notify teachers with a fresh single message + new grade buttons
    caption  = msg.teacher_notification_updated(
        sub_id, sub["student_name"], sub["group_name"], file_type
    )
    keyboard = _review_keyboard(sub_id)
    await _notify_teachers(context, sub, caption, keyboard)

    context.user_data.clear()
    return ConversationHandler.END


async def cancel_resubmit(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    context.user_data.clear()
    await update.message.reply_text("❌ Yangilash bekor qilindi.")
    return ConversationHandler.END


# ═══════════════════════════════════════════════════════════════════════════════
#  TEACHER — GRADE BUTTON CALLBACK
# ═══════════════════════════════════════════════════════════════════════════════

async def callback_grade_selected(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Teacher taps a grade button → store grade, ask for written feedback."""
    query = update.callback_query
    await query.answer()

    _, sub_id_str, grade = query.data.split("|", 2)
    sub_id = int(sub_id_str)

    sub = db.get_submission(sub_id)
    if not sub:
        await query.edit_message_caption("⚠️ Topshiriq topilmadi.")
        return

    if sub["status"] == "reviewed":
        await query.answer("✅ Bu topshiriq allaqachon tekshirilgan.", show_alert=True)
        return

    # Store pending grade in chat-scoped data
    context.chat_data[f"review_{sub_id}"] = {
        "grade": grade,
        "reviewer_id": query.from_user.id,
        "reviewer_name": query.from_user.full_name,
    }

    await query.edit_message_caption(
        f"✅ Baho tanlandi: *{grade}*\n\n"
        f"`#{sub_id}` uchun izoh yuboring:\n"
        f"`/feedback {sub_id} <izohingiz>`",
        parse_mode=ParseMode.MARKDOWN,
    )


# ═══════════════════════════════════════════════════════════════════════════════
#  TEACHER — /feedback (completes inline review)
# ═══════════════════════════════════════════════════════════════════════════════

async def cmd_feedback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    args = context.args
    if not args or len(args) < 2:
        await update.message.reply_text(
            "Ishlatish: `/feedback <raqam> <izohingiz>`",
            parse_mode=ParseMode.MARKDOWN,
        )
        return

    try:
        sub_id = int(args[0])
    except ValueError:
        await update.message.reply_text("⚠️ Noto'g'ri topshiriq raqami.")
        return

    feedback_text = " ".join(args[1:])
    review_data   = context.chat_data.get(f"review_{sub_id}")

    if not review_data:
        await update.message.reply_text(
            f"⚠️ `#{sub_id}` uchun baho tanlanmagan. Avval baho tugmasini bosing.",
            parse_mode=ParseMode.MARKDOWN,
        )
        return

    sub = db.get_submission(sub_id)
    if not sub:
        await update.message.reply_text("⚠️ Topshiriq topilmadi.")
        return
    if sub["status"] == "reviewed":
        await update.message.reply_text("✅ Bu topshiriq allaqachon tekshirilgan.")
        return

    grade         = review_data["grade"]
    reviewer_id   = review_data["reviewer_id"]
    reviewer_name = review_data["reviewer_name"]

    db.complete_review(sub_id, reviewer_id, grade, feedback_text)
    del context.chat_data[f"review_{sub_id}"]

    await update.message.reply_text(
        f"✅ `#{sub_id}` tekshiruvi saqlandi.", parse_mode=ParseMode.MARKDOWN
    )

    await _finalize_review(context, sub, grade, feedback_text, reviewer_name, is_edit=False)


# ═══════════════════════════════════════════════════════════════════════════════
#  TEACHER — /review (one-shot review, no buttons needed)
# ═══════════════════════════════════════════════════════════════════════════════

async def cmd_review_direct(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    /review <id> <grade> | <feedback>
    One-shot review without using inline grade buttons.
    """
    full = " ".join(context.args)
    if "|" not in full:
        await update.message.reply_text(
            "Ishlatish: `/review <raqam> <baho> | <izoh>`\n"
            "Misol: `/review 3 Yaxshi | Yaxshi ishlangan.`",
            parse_mode=ParseMode.MARKDOWN,
        )
        return

    left, feedback_text = full.split("|", 1)
    parts = left.strip().split(None, 1)
    if len(parts) < 2:
        await update.message.reply_text("⚠️ Baho ko'rsatilmagan.")
        return

    try:
        sub_id = int(parts[0])
    except ValueError:
        await update.message.reply_text("⚠️ Noto'g'ri raqam.")
        return

    grade         = parts[1].strip()
    feedback_text = feedback_text.strip()
    reviewer_name = update.effective_user.full_name

    sub = db.get_submission(sub_id)
    if not sub:
        await update.message.reply_text("⚠️ Topshiriq topilmadi.")
        return
    if sub["status"] == "reviewed":
        await update.message.reply_text("✅ Allaqachon tekshirilgan.")
        return

    db.complete_review(sub_id, update.effective_user.id, grade, feedback_text)

    await update.message.reply_text(
        f"✅ `#{sub_id}` tekshiruvi yakunlandi.", parse_mode=ParseMode.MARKDOWN
    )
    await _finalize_review(context, sub, grade, feedback_text, reviewer_name, is_edit=False)


# ═══════════════════════════════════════════════════════════════════════════════
#  TEACHER — /editreview  (edit an existing review)
# ═══════════════════════════════════════════════════════════════════════════════

async def cmd_editreview(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    /editreview <id> <new grade> | <new feedback>
    Updates grade and feedback on an already-reviewed submission.
    """
    full = " ".join(context.args)
    if "|" not in full:
        await update.message.reply_text(
            "Ishlatish: `/editreview <raqam> <yangi baho> | <yangi izoh>`\n"
            "Misol: `/editreview 3 A'lo | Juda yaxshi ishlangan!`",
            parse_mode=ParseMode.MARKDOWN,
        )
        return

    left, feedback_text = full.split("|", 1)
    parts = left.strip().split(None, 1)
    if len(parts) < 2:
        await update.message.reply_text("⚠️ Yangi baho ko'rsatilmagan.")
        return

    try:
        sub_id = int(parts[0])
    except ValueError:
        await update.message.reply_text("⚠️ Noto'g'ri raqam.")
        return

    grade         = parts[1].strip()
    feedback_text = feedback_text.strip()
    reviewer_name = update.effective_user.full_name

    sub = db.get_submission(sub_id)
    if not sub:
        await update.message.reply_text("⚠️ Topshiriq topilmadi.")
        return
    if sub["status"] != "reviewed":
        await update.message.reply_text(
            f"⚠️ `#{sub_id}` hali tekshirilmagan. Avval tekshiring.",
            parse_mode=ParseMode.MARKDOWN,
        )
        return

    db.update_review(sub_id, update.effective_user.id, grade, feedback_text)

    await update.message.reply_text(
        f"✅ `#{sub_id}` bahosi yangilandi.", parse_mode=ParseMode.MARKDOWN
    )
    await _finalize_review(context, sub, grade, feedback_text, reviewer_name, is_edit=True)


# ═══════════════════════════════════════════════════════════════════════════════
#  TEACHER — /resend  (re-send a submission file)
# ═══════════════════════════════════════════════════════════════════════════════

async def cmd_resend(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    /resend <id>
    Re-sends the original submission file to wherever the command is used.
    """
    args = context.args
    if not args:
        await update.message.reply_text(
            "Ishlatish: `/resend <raqam>`", parse_mode=ParseMode.MARKDOWN
        )
        return

    try:
        sub_id = int(args[0])
    except ValueError:
        await update.message.reply_text("⚠️ Noto'g'ri raqam.")
        return

    sub = db.get_submission(sub_id)
    if not sub:
        await update.message.reply_text("⚠️ Topshiriq topilmadi.")
        return

    caption = msg.resend_caption(sub)
    chat_id = update.effective_chat.id

    try:
        if sub["file_type"] == "photo":
            await context.bot.send_photo(
                chat_id=chat_id,
                photo=sub["file_id"],
                caption=caption,
                parse_mode=ParseMode.MARKDOWN,
            )
        else:
            await context.bot.send_document(
                chat_id=chat_id,
                document=sub["file_id"],
                caption=caption,
                parse_mode=ParseMode.MARKDOWN,
            )
    except Exception as e:
        logger.error("/resend failed for #%s: %s", sub_id, e)
        await update.message.reply_text(
            f"⚠️ Faylni yuborishda xato.\n"
            f"Telegram fayli o'chirilgan bo'lishi mumkin.\n"
            f"Texnik xato: `{type(e).__name__}`",
            parse_mode=ParseMode.MARKDOWN,
        )


# ═══════════════════════════════════════════════════════════════════════════════
#  TEACHER — /history  (search & filter with pagination)
# ═══════════════════════════════════════════════════════════════════════════════

async def cmd_history(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    /history <query>
    query can be: group name, student name, 'pending', or 'reviewed'
    """
    args = context.args
    if not args:
        await update.message.reply_text(
            f"Ishlatish:\n"
            f"`/history 5A` — guruh bo'yicha\n"
            f"`/history jasur` — o'quvchi ismi bo'yicha\n"
            f"`/history pending` — kutilayotganlar\n"
            f"`/history reviewed` — tekshirilganlar",
            parse_mode=ParseMode.MARKDOWN,
        )
        return

    query   = " ".join(args)
    results = db.search_submissions(query)

    if not results:
        await update.message.reply_text(
            f"🔍 `{query}` bo'yicha topshiriq topilmadi.", parse_mode=ParseMode.MARKDOWN
        )
        return

    # Store query in user_data for pagination callbacks
    context.user_data["hist_query"]   = query
    context.user_data["hist_results"] = results

    await _send_history_page(update, context, results, query, page=1)


async def _send_history_page(
    update_or_query,
    context: ContextTypes.DEFAULT_TYPE,
    results: list[dict],
    query: str,
    page: int,
):
    page_items, total_pages = _paginate(results, page)

    header = msg.history_page_header(query, page, total_pages, len(results))
    rows   = "\n\n".join(msg.history_row(s) for s in page_items)
    text   = header + rows

    keyboard = _pagination_keyboard(page, total_pages, "hist_page")

    send = (
        update_or_query.message.reply_text
        if hasattr(update_or_query, "message")
        else update_or_query.edit_message_text
    )
    await send(text, parse_mode=ParseMode.MARKDOWN, reply_markup=keyboard)


async def callback_history_page(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    page     = int(query.data.split(":")[1])
    results  = context.user_data.get("hist_results", [])
    hist_q   = context.user_data.get("hist_query", "?")

    await _send_history_page(query, context, results, hist_q, page)


# ═══════════════════════════════════════════════════════════════════════════════
#  STUDENT — /mystatus  (improved with pagination + detail)
# ═══════════════════════════════════════════════════════════════════════════════

async def cmd_mystatus(update: Update, context: ContextTypes.DEFAULT_TYPE):
    subs = db.get_student_submissions(update.effective_user.id)
    if not subs:
        await update.message.reply_text(
            "Siz hali hech qanday topshiriq yubormadingiz.\n/submit orqali uy vazifasini yuboring."
        )
        return

    context.user_data["myst_results"] = subs
    await _send_mystatus_page(update, context, subs, page=1)


async def _send_mystatus_page(
    update_or_query,
    context: ContextTypes.DEFAULT_TYPE,
    results: list[dict],
    page: int,
):
    page_items, total_pages = _paginate(results, page, size=3)

    header = msg.mystatus_header(page, total_pages, len(results))
    rows   = f"\n{'─' * 28}\n".join(msg.mystatus_row(s) for s in page_items)
    text   = header + rows

    keyboard = _pagination_keyboard(page, total_pages, "myst_page")

    send = (
        update_or_query.message.reply_text
        if hasattr(update_or_query, "message")
        else update_or_query.edit_message_text
    )
    await send(text, parse_mode=ParseMode.MARKDOWN, reply_markup=keyboard)


async def callback_mystatus_page(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    page    = int(query.data.split(":")[1])
    results = context.user_data.get("myst_results", [])

    await _send_mystatus_page(query, context, results, page)


# ═══════════════════════════════════════════════════════════════════════════════
#  STATS — /stats, /groupstats, /studentstats
# ═══════════════════════════════════════════════════════════════════════════════

async def cmd_stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    stats = db.get_global_stats()
    await update.message.reply_text(
        msg.global_stats(stats), parse_mode=ParseMode.MARKDOWN
    )


async def cmd_groupstats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text(
            "Ishlatish: `/groupstats 5A`", parse_mode=ParseMode.MARKDOWN
        )
        return
    group = " ".join(context.args).upper()
    stats = db.get_group_stats(group)
    if stats["total"] == 0:
        await update.message.reply_text(f"⚠️ `{group}` guruhi uchun topshiriq topilmadi.")
        return
    await update.message.reply_text(
        msg.group_stats(stats), parse_mode=ParseMode.MARKDOWN
    )


async def cmd_studentstats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text(
            "Ishlatish: `/studentstats jasur`", parse_mode=ParseMode.MARKDOWN
        )
        return
    name = " ".join(context.args)
    subs = db.get_student_stats(name)
    if not subs:
        await update.message.reply_text(f"⚠️ `{name}` bo'yicha hech narsa topilmadi.")
        return
    await update.message.reply_text(
        msg.student_stats(name, subs), parse_mode=ParseMode.MARKDOWN
    )


# ═══════════════════════════════════════════════════════════════════════════════
#  ADMIN — /export  (send all submissions as CSV)
# ═══════════════════════════════════════════════════════════════════════════════

async def cmd_export(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Generate a CSV file of all submissions and send it in Telegram."""
    conn = __import__("sqlite3").connect(os.getenv("DB_PATH", "homework.db"))
    conn.row_factory = __import__("sqlite3").Row
    rows = conn.execute(
        "SELECT * FROM submissions ORDER BY submitted_at DESC"
    ).fetchall()
    conn.close()

    if not rows:
        await update.message.reply_text("Hali hech qanday topshiriq yo'q.")
        return

    # Write CSV to an in-memory buffer
    buffer = io.StringIO()
    writer = csv.writer(buffer)
    writer.writerow([
        "id", "student_name", "group_name", "status",
        "grade", "feedback", "submitted_at", "reviewed_at",
        "student_id", "reviewer_id",
    ])
    for r in rows:
        writer.writerow([
            r["id"], r["student_name"], r["group_name"], r["status"],
            r["grade"] or "", r["feedback"] or "",
            r["submitted_at"], r["reviewed_at"] or "",
            r["student_id"], r["reviewer_id"] or "",
        ])

    # Convert to bytes and send as document
    bio = io.BytesIO(buffer.getvalue().encode("utf-8-sig"))  # utf-8-sig for Excel compat
    bio.name = f"submissions_{datetime.now().strftime('%Y%m%d_%H%M')}.csv"

    await context.bot.send_document(
        chat_id=update.effective_chat.id,
        document=bio,
        filename=bio.name,
        caption=f"📊 Jami {len(rows)} ta topshiriq — {bio.name}",
    )


# ═══════════════════════════════════════════════════════════════════════════════
#  GENERAL
# ═══════════════════════════════════════════════════════════════════════════════

async def cmd_myid(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid  = update.effective_user.id
    name = update.effective_user.full_name
    await update.message.reply_text(
        f"👤 *{name}*\n\n"
        f"Sizning Telegram ID raqamingiz:\n`{uid}`\n\n"
        f"Bu raqamni Render'da `TEACHER_CHAT_ID` sifatida kiriting.",
        parse_mode=ParseMode.MARKDOWN,
    )


async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        f"📚 *HomeworkBot'ga xush kelibsiz!*\n\n"
        f"*O'quvchilar uchun:*\n"
        f"  /submit — Uy vazifasini yuborish\n"
        f"  /resubmit — Topshiriqni almashtirish\n"
        f"  /mystatus — Topshiriqlarim holati\n\n"
        f"*O'qituvchilar uchun:*\n"
        f"  /pending — Kutilayotgan topshiriqlar\n"
        f"  /history — Topshiriqlar tarixi\n"
        f"  /resend — Faylni qayta yuborish\n"
        f"  /editreview — Bahoni tahrirlash\n\n"
        f"*Statistika:*\n"
        f"  /stats — Umumiy statistika\n"
        f"  /groupstats — Guruh statistikasi\n"
        f"  /studentstats — O'quvchi statistikasi\n\n"
        f"*Adminlar uchun:*\n"
        f"  /export — CSV eksport\n"
        f"  /register\\_parents — Ota-onalar guruhini ro'yxatdan o'tkazish\n"
        f"  /register\\_teachers — O'qituvchilar guruhini ro'yxatdan o'tkazish\n"
        f"  /chats — Ro'yxatdan o'tgan guruhlar",
        parse_mode=ParseMode.MARKDOWN,
    )


async def cmd_pending(update: Update, context: ContextTypes.DEFAULT_TYPE):
    subs = db.get_pending_submissions()
    if not subs:
        await update.message.reply_text("🎉 Tekshirilmagan topshiriqlar yo'q!")
        return
    lines = [f"*Kutayotgan topshiriqlar ({len(subs)}):*\n"]
    for s in subs:
        lines.append(
            f"• `#{s['id']}` — {s['student_name']} ({s['group_name']}) — {s['submitted_at'][:16]}"
        )
    await update.message.reply_text("\n".join(lines), parse_mode=ParseMode.MARKDOWN)


# ═══════════════════════════════════════════════════════════════════════════════
#  HEALTH SERVER (Render compatibility)
# ═══════════════════════════════════════════════════════════════════════════════

def _run_health_server():
    import threading
    from http.server import BaseHTTPRequestHandler, HTTPServer

    port = int(os.getenv("PORT", 8080))

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            self.send_response(200)
            self.end_headers()
            self.wfile.write(b"OK")
        def log_message(self, *args):
            pass

    server = HTTPServer(("0.0.0.0", port), Handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    logger.info("Health server on port %s", port)


# ═══════════════════════════════════════════════════════════════════════════════
#  BOOTSTRAP
# ═══════════════════════════════════════════════════════════════════════════════

def main():
    db.init_db()
    _run_health_server()

    app = Application.builder().token(TOKEN).build()

    # ── Submit conversation ──────────────────────────────────────────────────
    submit_conv = ConversationHandler(
        entry_points=[CommandHandler("submit", cmd_submit)],
        states={
            ASK_NAME:  [MessageHandler(filters.TEXT & ~filters.COMMAND, got_name)],
            ASK_GROUP: [MessageHandler(filters.TEXT & ~filters.COMMAND, got_group)],
            ASK_FILE:  [
                MessageHandler(filters.PHOTO | filters.Document.ALL, got_file),
                MessageHandler(
                    filters.TEXT & ~filters.COMMAND,
                    lambda u, c: u.message.reply_text("⚠️ Iltimos, rasm yoki hujjat fayl yuboring.")
                ),
            ],
        },
        fallbacks=[CommandHandler("cancel", cancel_submit)],
        allow_reentry=True,
    )

    # ── Resubmit conversation ────────────────────────────────────────────────
    resubmit_conv = ConversationHandler(
        entry_points=[CommandHandler("resubmit", cmd_resubmit)],
        states={
            RESUBMIT_FILE: [
                MessageHandler(filters.PHOTO | filters.Document.ALL, got_resubmit_file),
                MessageHandler(
                    filters.TEXT & ~filters.COMMAND,
                    lambda u, c: u.message.reply_text("⚠️ Iltimos, rasm yoki hujjat fayl yuboring.")
                ),
            ],
        },
        fallbacks=[CommandHandler("cancel", cancel_resubmit)],
        allow_reentry=True,
    )

    # ── Command handlers ─────────────────────────────────────────────────────
    for cmd, handler in [
        ("start",             cmd_start),
        ("myid",              cmd_myid),
        ("pending",           cmd_pending),
        ("mystatus",          cmd_mystatus),
        ("feedback",          cmd_feedback),
        ("review",            cmd_review_direct),
        ("editreview",        cmd_editreview),
        ("resend",            cmd_resend),
        ("history",           cmd_history),
        ("stats",             cmd_stats),
        ("groupstats",        cmd_groupstats),
        ("studentstats",      cmd_studentstats),
        ("export",            cmd_export),
        ("register_parents",  cmd_register),
        ("register_teachers", cmd_register),
        ("chats",             cmd_list_chats),
    ]:
        app.add_handler(CommandHandler(cmd, handler))

    # ── Conversation handlers ────────────────────────────────────────────────
    app.add_handler(submit_conv)
    app.add_handler(resubmit_conv)

    # ── Callback query handlers ──────────────────────────────────────────────
    app.add_handler(CallbackQueryHandler(callback_grade_selected,  pattern=r"^grade\|"))
    app.add_handler(CallbackQueryHandler(callback_history_page,    pattern=r"^hist_page:"))
    app.add_handler(CallbackQueryHandler(callback_mystatus_page,   pattern=r"^myst_page:"))

    # ── Group auto-registration ──────────────────────────────────────────────
    app.add_handler(ChatMemberHandler(on_my_chat_member, ChatMemberHandler.MY_CHAT_MEMBER))

    # ── Scheduled jobs ───────────────────────────────────────────────────────
    register_jobs(app)

    logger.info("HomeworkBot is running…")
    app.run_polling(drop_pending_updates=True)


if __name__ == "__main__":
    import asyncio
    asyncio.set_event_loop(asyncio.new_event_loop())
    main()