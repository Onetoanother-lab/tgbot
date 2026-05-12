"""All user-facing message templates. Language: Uzbek."""

# ── Emojis ───────────────────────────────────────────────────────────────────
BOOK   = "📚"
CHECK  = "✅"
CLOCK  = "🕐"
BELL   = "🔔"
STAR   = "⭐"
WARN   = "⚠️"
PENCIL = "✏️"
GROUP  = "👥"
FILE   = "📄"
GRADE  = "🏆"
CHART  = "📊"
CAL    = "📅"
BUBBLE = "💬"
SPEED  = "⚡"
EDIT   = "🔄"


# ── Submission flow ───────────────────────────────────────────────────────────

def step_ask_name() -> str:
    return (
        f"{PENCIL} *Uy vazifasini yuborish*\n\n"
        f"1️⃣ 1-qadam / 3\n\n"
        "Iltimos, *to'liq ismingizni* kiriting:"
    )


def step_ask_group(name: str) -> str:
    return (
        f"👤 Ism saqlandi: *{name}*\n\n"
        f"2️⃣ 2-qadam / 3\n\n"
        f"{GROUP} *Guruh nomingizni* kiriting (masalan: `5A`, `10B`):"
    )


def step_ask_file(group: str) -> str:
    return (
        f"{GROUP} Guruh: *{group}*\n\n"
        f"3️⃣ 3-qadam / 3\n\n"
        f"{FILE} Uy vazifangizni *rasm* yoki *hujjat* (PDF, Word va boshqalar) sifatida yuboring:"
    )


def submission_received(submission_id: int, student_name: str, group: str) -> str:
    return (
        f"{BOOK} *Uy vazifasi yuborildi*\n\n"
        f"Uy vazifangiz qabul qilindi va hozir tekshirilmoqda.\n\n"
        f"{FILE} *Yuborish raqami:* `#{submission_id}`\n"
        f"👤 *Ism:* {student_name}\n"
        f"{GROUP} *Guruh:* {group}\n"
        f"{CLOCK} *Holat:* Tekshirish kutilmoqda\n\n"
        f"O'qituvchi tekshirgandan so'ng sizga xabar beriladi."
    )


def parents_notification(submission_id: int, student_name: str, group: str) -> str:
    return (
        f"{BELL} *Yangi uy vazifasi yuborildi*\n\n"
        f"Guruhingizdan o'quvchi uy vazifasini yubordi.\n\n"
        f"{FILE} *Yuborish raqami:* `#{submission_id}`\n"
        f"👤 *O'quvchi:* {student_name}\n"
        f"{GROUP} *Guruh:* {group}\n"
        f"{CLOCK} *Holat:* Tekshirish kutilmoqda\n\n"
        f"Tekshiruv tugagach sizga xabar beriladi."
    )


def teacher_notification(submission_id: int, student_name: str, group: str, file_type: str) -> str:
    file_type_uz = "Rasm" if file_type == "photo" else "Hujjat"
    return (
        f"{PENCIL} *Tekshirish uchun yangi uy vazifasi*\n\n"
        f"{FILE} *Yuborish raqami:* `#{submission_id}`\n"
        f"👤 *O'quvchi:* {student_name}\n"
        f"{GROUP} *Guruh:* {group}\n"
        f"📎 *Turi:* {file_type_uz}\n\n"
        f"Baho tanlang:"
    )


def teacher_notification_updated(submission_id: int, student_name: str, group: str, file_type: str) -> str:
    """Used when a student resubmits — replaces the original teacher notification."""
    file_type_uz = "Rasm" if file_type == "photo" else "Hujjat"
    return (
        f"{EDIT} *Yangilangan uy vazifasi*\n\n"
        f"{FILE} *Yuborish raqami:* `#{submission_id}`\n"
        f"👤 *O'quvchi:* {student_name}\n"
        f"{GROUP} *Guruh:* {group}\n"
        f"📎 *Turi:* {file_type_uz}\n\n"
        f"Baho tanlang:"
    )


def review_complete_student(
    submission_id: int, grade: str, feedback: str, student_name: str
) -> str:
    return (
        f"{CHECK} *Uy vazifasi tekshirildi!*\n\n"
        f"Assalomu alaykum, {student_name}! Uy vazifangiz tekshirildi.\n\n"
        f"{FILE} *Yuborish raqami:* `#{submission_id}`\n"
        f"{GRADE} *Baho:* {grade}\n\n"
        f"{PENCIL} *O'qituvchi izohi:*\n{feedback}"
    )


def review_updated_student(
    submission_id: int, grade: str, feedback: str, student_name: str
) -> str:
    return (
        f"{EDIT} *Uy vazifasi bahosi yangilandi*\n\n"
        f"Assalomu alaykum, {student_name}! O'qituvchi bahoni yangiladi.\n\n"
        f"{FILE} *Yuborish raqami:* `#{submission_id}`\n"
        f"{GRADE} *Yangi baho:* {grade}\n\n"
        f"{PENCIL} *Yangilangan izoh:*\n{feedback}"
    )


def review_complete_parents(
    submission_id: int, student_name: str, group: str, grade: str, feedback: str
) -> str:
    return (
        f"{CHECK} *Uy vazifasi tekshiruvi tugadi*\n\n"
        f"👤 *O'quvchi:* {student_name}\n"
        f"{GROUP} *Guruh:* {group}\n"
        f"{FILE} *Yuborish raqami:* `#{submission_id}`\n"
        f"{GRADE} *Baho:* {grade}\n\n"
        f"{PENCIL} *O'qituvchi izohi:*\n{feedback}"
    )


def review_updated_parents(
    submission_id: int, student_name: str, group: str, grade: str, feedback: str
) -> str:
    return (
        f"{EDIT} *Baho yangilandi*\n\n"
        f"👤 *O'quvchi:* {student_name}\n"
        f"{GROUP} *Guruh:* {group}\n"
        f"{FILE} *Yuborish raqami:* `#{submission_id}`\n"
        f"{GRADE} *Yangi baho:* {grade}\n\n"
        f"{PENCIL} *Yangilangan izoh:*\n{feedback}"
    )


def no_parents_group(group: str) -> str:
    return (
        f"{WARN} *{group}* guruhi uchun ota-onalar guruhi topilmadi.\n\n"
        f"Botni quyidagi nomli guruhga qo'shing:\n"
        f"`{group} parents`\n\n"
        f"Admin `/register_parents` buyrug'i orqali ro'yxatdan o'tkazishi mumkin."
    )


# ── Teacher message caption after review (replaces grade buttons) ─────────────

def reviewed_caption(
    submission_id: int, student_name: str, group: str,
    grade: str, reviewer_name: str, reviewed_at: str
) -> str:
    return (
        f"{CHECK} *Tekshirildi*\n\n"
        f"{FILE} *Yuborish raqami:* `#{submission_id}`\n"
        f"👤 *O'quvchi:* {student_name}\n"
        f"{GROUP} *Guruh:* {group}\n\n"
        f"{GRADE} *Baho:* {grade}\n"
        f"👤 *Tekshiruvchi:* {reviewer_name}\n"
        f"{CLOCK} *Tekshirilgan vaqt:* {reviewed_at}"
    )


# ── Resend ────────────────────────────────────────────────────────────────────

def resend_caption(sub: dict) -> str:
    status_uz = "Tekshirildi" if sub["status"] == "reviewed" else "Kutilmoqda"
    lines = [
        f"{FILE} *Yuborish raqami:* `#{sub['id']}`",
        f"👤 *O'quvchi:* {sub['student_name']}",
        f"{GROUP} *Guruh:* {sub['group_name']}",
        f"{CLOCK} *Holat:* {status_uz}",
        f"{CAL} *Yuborilgan:* {sub['submitted_at']}",
    ]
    if sub.get("grade"):
        lines.append(f"{GRADE} *Baho:* {sub['grade']}")
    return "\n".join(lines)


# ── History ───────────────────────────────────────────────────────────────────

def history_row(s: dict) -> str:
    icon = CHECK if s["status"] == "reviewed" else CLOCK
    grade_part = f" — {s['grade']}" if s.get("grade") else ""
    return (
        f"{icon} `#{s['id']}` *{s['student_name']}* ({s['group_name']})"
        f"{grade_part}\n"
        f"     {CAL} {s['submitted_at'][:10]}"
    )


def history_page_header(query: str, page: int, total_pages: int, count: int) -> str:
    return (
        f"{BOOK} *Topshiriqlar tarixi*\n"
        f"🔍 Qidiruv: `{query}` — {count} ta natija\n"
        f"📃 Sahifa {page}/{total_pages}\n"
        f"{'─' * 28}\n"
    )


# ── Mystatus (improved) ───────────────────────────────────────────────────────

def mystatus_row(s: dict) -> str:
    icon = CHECK if s["status"] == "reviewed" else CLOCK
    status_uz = "Tekshirildi" if s["status"] == "reviewed" else "Kutilmoqda"
    lines = [
        f"{FILE} `#{s['id']}` — {s['group_name']}",
        f"{CAL} *{s['submitted_at'][:10]}*   {CHART} {status_uz}",
    ]
    if s.get("grade"):
        lines.append(f"{icon} *Baho:* {s['grade']}")
    if s.get("feedback"):
        preview = s["feedback"][:60] + ("…" if len(s["feedback"]) > 60 else "")
        lines.append(f"{BUBBLE} _{preview}_")
    return "\n".join(lines)


def mystatus_header(page: int, total_pages: int, count: int) -> str:
    return (
        f"{BOOK} *Mening topshiriqlarim*\n"
        f"Jami: {count} ta   📃 Sahifa {page}/{total_pages}\n"
        f"{'─' * 28}\n"
    )


# ── Rate limit ────────────────────────────────────────────────────────────────

def rate_limit_warning(remaining_minutes: int) -> str:
    return (
        f"{WARN} *Yuborish chegarasiga yetdingiz*\n\n"
        f"10 daqiqa ichida 3 ta topshiriq yuborish mumkin.\n"
        f"Iltimos, taxminan *{remaining_minutes} daqiqadan* so'ng qayta urinib ko'ring."
    )


# ── Resubmit ──────────────────────────────────────────────────────────────────

def resubmit_ask_file(sub_id: int) -> str:
    return (
        f"{EDIT} *Topshiriqni yangilash — `#{sub_id}`*\n\n"
        f"Yangi faylni yuboring (rasm yoki hujjat).\n"
        f"Bekor qilish uchun: /cancel"
    )


def resubmit_confirmed(sub_id: int) -> str:
    return (
        f"{CHECK} *Topshiriq yangilandi!*\n\n"
        f"`#{sub_id}` raqamli topshiriqingiz yangi fayl bilan almashtirildi.\n"
        f"O'qituvchiga xabar yuborildi."
    )


def resubmit_teacher_notice(sub_id: int, student_name: str, group: str) -> str:
    return (
        f"{EDIT} *Topshiriq yangilandi*\n\n"
        f"`#{sub_id}` raqamli topshiriq o'quvchi tomonidan yangilandi.\n"
        f"👤 *O'quvchi:* {student_name}\n"
        f"{GROUP} *Guruh:* {group}"
    )


# ── Stats ─────────────────────────────────────────────────────────────────────

def global_stats(s: dict) -> str:
    return (
        f"{CHART} *Umumiy statistika*\n\n"
        f"{FILE} Jami topshiriqlar: *{s['total']}*\n"
        f"{CLOCK} Kutilmoqda: *{s['pending']}*\n"
        f"{CHECK} Tekshirildi: *{s['reviewed']}*\n"
        f"{GROUP} Guruhlar soni: *{s['groups']}*\n"
        f"👤 Faol o'quvchilar: *{s['students']}*\n"
        f"{GRADE} Tekshiruv darajasi: *{s['rate']}%*"
    )


def group_stats(s: dict) -> str:
    avg_label = f"{s['avg_grade']}/5" if s["avg_grade"] else "—"
    return (
        f"{CHART} *{s['group']} guruhi statistikasi*\n\n"
        f"{FILE} Jami topshiriqlar: *{s['total']}*\n"
        f"{CLOCK} Kutilmoqda: *{s['pending']}*\n"
        f"{CHECK} Tekshirildi: *{s['reviewed']}*\n"
        f"{GRADE} O'rtacha baho: *{avg_label}*"
    )


def student_stats(name: str, subs: list[dict]) -> str:
    from database import _grade_average
    total    = len(subs)
    reviewed = sum(1 for s in subs if s["status"] == "reviewed")
    avg      = _grade_average(subs)
    avg_label = f"{avg}/5" if avg else "—"
    lines = [
        f"{CHART} *{name} — shaxsiy statistika*\n",
        f"{FILE} Jami topshiriqlar: *{total}*",
        f"{CHECK} Tekshirildi: *{reviewed}*",
        f"{GRADE} O'rtacha baho: *{avg_label}*\n",
        f"*So'nggi topshiriqlar:*",
    ]
    for s in subs[:5]:
        icon = CHECK if s["status"] == "reviewed" else CLOCK
        grade_part = f" — {s['grade']}" if s.get("grade") else ""
        lines.append(f"{icon} `#{s['id']}` {s['submitted_at'][:10]}{grade_part}")
    return "\n".join(lines)


# ── Weekly report ─────────────────────────────────────────────────────────────

def weekly_report(group: str, stats: dict) -> str:
    avg_label = f"{stats['avg_grade']}/5" if stats["avg_grade"] else "—"
    return (
        f"{BELL} *Haftalik hisobot — {group}*\n\n"
        f"{FILE} Yuborilgan topshiriqlar: *{stats['total']}*\n"
        f"{CHECK} Tekshirildi: *{stats['reviewed']}*\n"
        f"{CLOCK} Kutilmoqda: *{stats['pending']}*\n"
        f"{GRADE} O'rtacha baho: *{avg_label}*"
    )