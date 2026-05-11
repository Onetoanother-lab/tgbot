"""
HomeworkBot — main entry point.

Conversation states
───────────────────
SUBMIT flow (student):
    ASK_NAME  → ASK_GROUP → ASK_FILE → done

REVIEW flow (teacher, inline):
    REVIEW_FEEDBACK  → done
"""

import logging
import os
from dotenv import load_dotenv

from telegram import (
    Update,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
)
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    ConversationHandler,
    CallbackQueryHandler,
    ContextTypes,
    filters,
)
from telegram.constants import ParseMode

import database as db
import messages as msg

load_dotenv()

logging.basicConfig(
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)

TOKEN = os.environ["BOT_TOKEN"]

# ── Conversation states ───────────────────────────────────────────────────────
ASK_NAME, ASK_GROUP, ASK_FILE = range(3)
REVIEW_FEEDBACK = 10


# ═══════════════════════════════════════════════════════════════════════════════
#  UTILITY
# ═══════════════════════════════════════════════════════════════════════════════

async def send_safe(context: ContextTypes.DEFAULT_TYPE, chat_id: int, text: str, **kwargs):
    """Send a message and swallow errors (e.g. bot not in group)."""
    try:
        await context.bot.send_message(
            chat_id=chat_id,
            text=text,
            parse_mode=ParseMode.MARKDOWN,
            **kwargs,
        )
    except Exception as exc:
        logger.warning("Could not send to %s: %s", chat_id, exc)


# ═══════════════════════════════════════════════════════════════════════════════
#  GROUP REGISTRATION  (run in any group the bot is added to)
# ═══════════════════════════════════════════════════════════════════════════════

async def on_my_chat_member(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Auto-detect when the bot is added to a group and register it.
    Groups named '* parents' → type 'parents'
    Groups named '* teachers' → type 'teachers'
    """
    result = update.my_chat_member
    if result.new_chat_member.status not in ("member", "administrator"):
        return

    chat = result.chat
    if chat.type not in ("group", "supergroup"):
        return

    title = chat.title or ""
    title_lower = title.lower()

    if "parents" in title_lower:
        chat_type = "parents"
    elif "teacher" in title_lower:
        chat_type = "teachers"
    else:
        return  # ignore unrecognised groups

    db.register_chat(chat.id, title, chat_type)
    logger.info("Registered %s chat: %s (%s)", chat_type, title, chat.id)

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
    """
    /register_parents  — manually register the current group as a parents group.
    /register_teachers — manually register as teachers group.
    Only works inside a group.
    """
    chat = update.effective_chat
    if chat.type not in ("group", "supergroup"):
        await update.message.reply_text("⚠️ Bu buyruqni faqat guruh ichida ishlating.")
        return

    command = update.message.text.split("@")[0].lstrip("/")
    chat_type = "parents" if "parents" in command else "teachers"
    chat_type_uz = "ota-onalar" if chat_type == "parents" else "o'qituvchilar"

    db.register_chat(chat.id, chat.title, chat_type)
    await update.message.reply_text(
        f"✅ *{chat.title}* guruhi *{chat_type_uz}* guruhi sifatida ro'yxatdan o'tkazildi.",
        parse_mode=ParseMode.MARKDOWN,
    )


async def cmd_list_chats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Admin: list all registered groups."""
    chats = db.list_registered_chats()
    if not chats:
        await update.message.reply_text("Hali hech qanday guruh ro'yxatdan o'tmagan.")
        return
    lines = ["*Ro'yxatdan o'tgan guruhlar:*\n"]
    for c in chats:
        lines.append(f"• [{c['chat_type'].upper()}] {c['title']} (`{c['chat_id']}`)")
    await update.message.reply_text("\n".join(lines), parse_mode=ParseMode.MARKDOWN)


# ═══════════════════════════════════════════════════════════════════════════════
#  STUDENT — SUBMIT HOMEWORK CONVERSATION
# ═══════════════════════════════════════════════════════════════════════════════

async def cmd_submit(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    await update.message.reply_text(
        f"{msg.PENCIL} *Uy vazifasini yuborish*\n\n"
        "Boshlaylik! Iltimos, *to'liq ismingizni* kiriting:",
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
        f"👤 Ism saqlandi: *{name}*\n\n"
        f"{msg.GROUP} Endi *guruh nomingizni* kiriting (masalan: `5A`, `10B`):",
        parse_mode=ParseMode.MARKDOWN,
    )
    return ASK_GROUP


async def got_group(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    group = update.message.text.strip()
    if len(group) < 1:
        await update.message.reply_text("⚠️ Guruh nomi bo'sh bo'lishi mumkin emas. Qaytadan kiriting:")
        return ASK_GROUP

    context.user_data["group_name"] = group.upper()
    await update.message.reply_text(
        f"{msg.GROUP} Guruh: *{group.upper()}*\n\n"
        f"{msg.FILE} Endi uy vazifangizni *rasm* yoki *hujjat* (PDF, Word va boshqalar) sifatida yuboring:",
        parse_mode=ParseMode.MARKDOWN,
    )
    return ASK_FILE


async def got_file(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    message = update.message

    # Accept photo or document
    if message.photo:
        file_id = message.photo[-1].file_id  # best quality
        file_type = "photo"
    elif message.document:
        file_id = message.document.file_id
        file_type = "document"
    else:
        await message.reply_text(
            "⚠️ Iltimos, *rasm* yoki *hujjat* (PDF, Word, rasm fayl) yuboring.",
            parse_mode=ParseMode.MARKDOWN,
        )
        return ASK_FILE

    student_name = context.user_data["student_name"]
    group_name   = context.user_data["group_name"]
    student_id   = update.effective_user.id

    # Save to DB
    sub_id = db.create_submission(student_id, student_name, group_name, file_id, file_type)

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
    else:
        await message.reply_text(
            msg.no_parents_group(group_name),
            parse_mode=ParseMode.MARKDOWN,
        )

    # 3. Notify all teacher groups + forward file
    teacher_chats = db.find_teacher_chats()
    keyboard = _review_keyboard(sub_id)
    for tc in teacher_chats:
        await send_safe(
            context,
            tc["chat_id"],
            msg.teacher_notification(sub_id, student_name, group_name, file_type),
            reply_markup=keyboard,
        )
        # Forward the actual file
        try:
            await context.bot.forward_message(
                chat_id=tc["chat_id"],
                from_chat_id=message.chat_id,
                message_id=message.message_id,
            )
        except Exception as e:
            logger.warning("Could not forward file to teacher chat: %s", e)

    context.user_data.clear()
    return ConversationHandler.END


async def cancel_submit(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    context.user_data.clear()
    await update.message.reply_text("❌ Yuborish bekor qilindi.")
    return ConversationHandler.END


# ═══════════════════════════════════════════════════════════════════════════════
#  TEACHER — REVIEW INLINE FLOW
# ═══════════════════════════════════════════════════════════════════════════════

GRADES = ["⭐ A'lo", "👍 Yaxshi", "📝 Qoniqarli", "⚠️ Yaxshilash kerak", "❌ Bajarilmagan"]


def _review_keyboard(submission_id: int) -> InlineKeyboardMarkup:
    buttons = [
        [InlineKeyboardButton(g, callback_data=f"grade|{submission_id}|{g}")]
        for g in GRADES
    ]
    return InlineKeyboardMarkup(buttons)


async def callback_grade_selected(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Teacher taps a grade button → bot asks for written feedback."""
    query = update.callback_query
    await query.answer()

    _, sub_id, grade = query.data.split("|", 2)
    sub_id = int(sub_id)

    submission = db.get_submission(sub_id)
    if not submission:
        await query.edit_message_text("⚠️ Yuborilgan topshiriq topilmadi.")
        return

    if submission["status"] == "reviewed":
        await query.edit_message_text("✅ Bu topshiriq allaqachon tekshirilgan.")
        return

    context.chat_data[f"review_{sub_id}"] = {"grade": grade, "reviewer_id": query.from_user.id}

    await query.edit_message_text(
        f"✅ Baho tanlandi: *{grade}*\n\n"
        f"`#{sub_id}` raqamli topshiriq uchun izoh yozing.\n"
        f"Nima yaxshi bajarilgani va nimani yaxshilash kerakligini yozing.\n\n"
        f"Quyidagi buyruq bilan yuboring:\n"
        f"`/feedback {sub_id} <izohingiz>`",
        parse_mode=ParseMode.MARKDOWN,
    )


async def cmd_feedback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    /feedback <submission_id> <text...>
    Complete the review and notify student + parents.
    """
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
    review_data = context.chat_data.get(f"review_{sub_id}")

    if not review_data:
        await update.message.reply_text(
            f"⚠️ `#{sub_id}` uchun hali baho tanlanmagan.\n"
            "Avval baho tugmasini bosing.",
            parse_mode=ParseMode.MARKDOWN,
        )
        return

    grade = review_data["grade"]
    reviewer_id = review_data["reviewer_id"]

    submission = db.get_submission(sub_id)
    if not submission:
        await update.message.reply_text("⚠️ Topshiriq topilmadi.")
        return

    if submission["status"] == "reviewed":
        await update.message.reply_text("✅ Bu topshiriq allaqachon tekshirilgan.")
        return

    # Save review
    db.complete_review(sub_id, reviewer_id, grade, feedback_text)
    del context.chat_data[f"review_{sub_id}"]

    await update.message.reply_text(
        f"✅ `#{sub_id}` raqamli topshiriq tekshiruvi saqlandi.",
        parse_mode=ParseMode.MARKDOWN,
    )

    # Notify student
    await send_safe(
        context,
        submission["student_id"],
        msg.review_complete_student(sub_id, grade, feedback_text, submission["student_name"]),
    )

    # Notify parents group
    parents_chat = db.find_parents_chat(submission["group_name"])
    if parents_chat:
        await send_safe(
            context,
            parents_chat["chat_id"],
            msg.review_complete_parents(
                sub_id,
                submission["student_name"],
                submission["group_name"],
                grade,
                feedback_text,
            ),
        )


async def cmd_review_direct(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    /review <id> <grade> | <feedback>
    One-shot review command (alternative to inline buttons).
    Example: /review 3 Good | Great structure but fix spelling.
    """
    full = " ".join(context.args)
    if "|" not in full:
        await update.message.reply_text(
            "Ishlatish: `/review <raqam> <baho> | <izoh>`\n"
            "Misol: `/review 3 Yaxshi | Yaxshi ishla\\'ngan, imlo xatolarini tuzating.`",
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

    grade = parts[1].strip()
    feedback_text = feedback_text.strip()

    submission = db.get_submission(sub_id)
    if not submission:
        await update.message.reply_text("⚠️ Topshiriq topilmadi.")
        return

    if submission["status"] == "reviewed":
        await update.message.reply_text("✅ Allaqachon tekshirilgan.")
        return

    db.complete_review(sub_id, update.effective_user.id, grade, feedback_text)

    await update.message.reply_text(
        f"✅ `#{sub_id}` raqamli topshiriq tekshiruvi yakunlandi.",
        parse_mode=ParseMode.MARKDOWN,
    )

    # Notify student
    await send_safe(
        context,
        submission["student_id"],
        msg.review_complete_student(sub_id, grade, feedback_text, submission["student_name"]),
    )

    # Notify parents
    parents_chat = db.find_parents_chat(submission["group_name"])
    if parents_chat:
        await send_safe(
            context,
            parents_chat["chat_id"],
            msg.review_complete_parents(
                sub_id,
                submission["student_name"],
                submission["group_name"],
                grade,
                feedback_text,
            ),
        )


# ═══════════════════════════════════════════════════════════════════════════════
#  GENERAL COMMANDS
# ═══════════════════════════════════════════════════════════════════════════════

async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        f"{msg.BOOK} *HomeworkBot'ga xush kelibsiz!*\n\n"
        "*O'quvchilar uchun:*\n"
        "  /submit — Uy vazifasini yuborish\n"
        "  /mystatus — Topshiriqlarim holatini ko'rish\n\n"
        "*O'qituvchilar uchun (o'qituvchilar guruhida):*\n"
        "  /pending — Tekshirilmagan topshiriqlar\n"
        "  /review — Topshiriqni tekshirish\n\n"
        "*Adminlar uchun (istalgan guruhda):*\n"
        "  /register\\_parents — Bu guruhni ota-onalar guruhi sifatida ro'yxatdan o'tkazish\n"
        "  /register\\_teachers — Bu guruhni o'qituvchilar guruhi sifatida ro'yxatdan o'tkazish\n"
        "  /chats — Barcha ro'yxatdan o'tgan guruhlarni ko'rish",
        parse_mode=ParseMode.MARKDOWN,
    )


async def cmd_pending(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Tekshirilmagan topshiriqlar ro'yxati (o'qituvchilar uchun)."""
    subs = db.get_pending_submissions()
    if not subs:
        await update.message.reply_text("🎉 Tekshirilmagan topshiriqlar yo'q!")
        return

    lines = [f"*Kutayotgan topshiriqlar ({len(subs)}):*\n"]
    for s in subs:
        lines.append(
            f"• `#{s['id']}` — {s['student_name']} ({s['group_name']}) "
            f"— {s['submitted_at']}"
        )
    await update.message.reply_text("\n".join(lines), parse_mode=ParseMode.MARKDOWN)


async def cmd_mystatus(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """O'quvchi: o'z topshiriqlari tarixini ko'rish."""
    subs = db.get_student_submissions(update.effective_user.id)
    if not subs:
        await update.message.reply_text(
            "Siz hali hech qanday topshiriq yubormadingiz.\n/submit orqali uy vazifasini yuboring."
        )
        return

    status_uz = {"pending": "KUTILMOQDA", "reviewed": "TEKSHIRILDI"}
    lines = [f"*Mening topshiriqlarim ({len(subs)}):*\n"]
    for s in subs:
        status_icon = msg.CHECK if s["status"] == "reviewed" else msg.CLOCK
        line = f"{status_icon} `#{s['id']}` {s['group_name']} — {status_uz.get(s['status'], s['status'])}"
        if s["grade"]:
            line += f" — {s['grade']}"
        lines.append(line)

    await update.message.reply_text("\n".join(lines), parse_mode=ParseMode.MARKDOWN)


# ═══════════════════════════════════════════════════════════════════════════════
#  APP BOOTSTRAP
# ═══════════════════════════════════════════════════════════════════════════════

def main():
    db.init_db()

    app = Application.builder().token(TOKEN).build()

    # ── Submit conversation ──────────────────────────────────────────────────
    submit_conv = ConversationHandler(
        entry_points=[CommandHandler("submit", cmd_submit)],
        states={
            ASK_NAME:  [MessageHandler(filters.TEXT & ~filters.COMMAND, got_name)],
            ASK_GROUP: [MessageHandler(filters.TEXT & ~filters.COMMAND, got_group)],
            ASK_FILE:  [
                MessageHandler(filters.PHOTO | filters.Document.ALL, got_file),
                MessageHandler(filters.TEXT & ~filters.COMMAND,
                               lambda u, c: u.message.reply_text(
                                   "⚠️ Iltimos, rasm yoki hujjat fayl yuboring."
                               )),
            ],
        },
        fallbacks=[CommandHandler("cancel", cancel_submit)],
        allow_reentry=True,
    )

    # ── Handlers ─────────────────────────────────────────────────────────────
    app.add_handler(CommandHandler("start",               cmd_start))
    app.add_handler(CommandHandler("pending",             cmd_pending))
    app.add_handler(CommandHandler("mystatus",            cmd_mystatus))
    app.add_handler(CommandHandler("feedback",            cmd_feedback))
    app.add_handler(CommandHandler("review",              cmd_review_direct))
    app.add_handler(CommandHandler("register_parents",    cmd_register))
    app.add_handler(CommandHandler("register_teachers",   cmd_register))
    app.add_handler(CommandHandler("chats",               cmd_list_chats))
    app.add_handler(submit_conv)

    # Grade button callback
    app.add_handler(CallbackQueryHandler(callback_grade_selected, pattern=r"^grade\|"))

    # Auto-register when bot is added to a group
    from telegram.ext import ChatMemberHandler
    app.add_handler(ChatMemberHandler(on_my_chat_member, ChatMemberHandler.MY_CHAT_MEMBER))

    logger.info("HomeworkBot is running…")
    app.run_polling(drop_pending_updates=True)


if __name__ == "__main__":
    import asyncio
    asyncio.set_event_loop(asyncio.new_event_loop())
    main()