"""All user-facing Telegram message templates. Language: Uzbek."""

# ── Icons ─────────────────────────────────────────────────────────────────────
BOOK   = "📚"; CHECK  = "✅"; CLOCK  = "🕐"; BELL   = "🔔"
STAR   = "⭐"; WARN   = "⚠️"; PENCIL = "✏️"; GROUP  = "👥"
FILE   = "📄"; GRADE  = "🏆"; CHART  = "📊"; CAL    = "📅"
BUBBLE = "💬"; EDIT   = "🔄"; SPEED  = "⚡"; MEDAL  = "🎖️"
ROCKET = "🚀"; BRAIN  = "🧠"; FIRE   = "🔥"; CROWN  = "👑"
CODE   = "💻"; LOCK   = "🔐"; NOTE   = "📝"


# ── Submit flow steps ─────────────────────────────────────────────────────────

def step_ask_name() -> str:
    return (
        f"{PENCIL} *Uy vazifasini yuborish*\n\n"
        "1️⃣  *1-qadam / 3*\n\n"
        "Iltimos, *to'liq ismingizni* kiriting:"
    )

def step_ask_group(name: str) -> str:
    return (
        f"👤 Ism saqlandi: *{name}*\n\n"
        "2️⃣  *2-qadam / 3*\n\n"
        f"{GROUP} *Guruh nomingizni* kiriting (masalan: `5A`, `10B`):"
    )

def step_ask_file(group: str) -> str:
    return (
        f"{GROUP} Guruh: *{group}*\n\n"
        "3️⃣  *3-qadam / 3*\n\n"
        f"{FILE} Uy vazifangizni *rasm* yoki *hujjat* (PDF, .py, .js, .html …) sifatida yuboring:"
    )


# ── Submission ────────────────────────────────────────────────────────────────

def submission_received(sub_id: int, student_name: str, group: str, is_late: bool = False) -> str:
    late_tag = f"\n{WARN} *Kech topshirildi!*" if is_late else ""
    return (
        f"{BOOK} *Uy vazifasi yuborildi*{late_tag}\n\n"
        f"Uy vazifangiz qabul qilindi va hozir tekshirilmoqda.\n\n"
        f"{FILE} *Yuborish raqami:* `#{sub_id}`\n"
        f"👤 *Ism:* {student_name}\n"
        f"{GROUP} *Guruh:* {group}\n"
        f"{CLOCK} *Holat:* Tekshirish kutilmoqda\n\n"
        f"O'qituvchi tekshirgandan so'ng sizga xabar beriladi."
    )

def parents_notification(sub_id: int, student_name: str, group: str) -> str:
    return (
        f"{BELL} *Yangi uy vazifasi yuborildi*\n\n"
        f"{FILE} *Yuborish raqami:* `#{sub_id}`\n"
        f"👤 *O'quvchi:* {student_name}\n"
        f"{GROUP} *Guruh:* {group}\n"
        f"{CLOCK} *Holat:* Tekshirish kutilmoqda\n\n"
        f"Tekshiruv tugagach sizga xabar beriladi."
    )

def teacher_notification(sub_id: int, student_name: str, group: str, file_type: str, file_name: str | None = None) -> str:
    type_uz  = "Rasm" if file_type == "photo" else "Hujjat"
    name_tag = f"\n📎 *Fayl:* `{file_name}`" if file_name else ""
    return (
        f"{PENCIL} *Tekshirish uchun yangi uy vazifasi*\n\n"
        f"{FILE} *Yuborish raqami:* `#{sub_id}`\n"
        f"👤 *O'quvchi:* {student_name}\n"
        f"{GROUP} *Guruh:* {group}\n"
        f"📎 *Turi:* {type_uz}{name_tag}\n\n"
        f"Baho tanlang:"
    )

def teacher_notification_updated(sub_id: int, student_name: str, group: str, file_type: str) -> str:
    type_uz = "Rasm" if file_type == "photo" else "Hujjat"
    return (
        f"{EDIT} *Yangilangan uy vazifasi*\n\n"
        f"{FILE} *Yuborish raqami:* `#{sub_id}`\n"
        f"👤 *O'quvchi:* {student_name}\n"
        f"{GROUP} *Guruh:* {group}\n"
        f"📎 *Turi:* {type_uz}\n\n"
        f"Baho tanlang:"
    )

def no_parents_group(group: str) -> str:
    return (
        f"{WARN} *{group}* guruhi uchun ota-onalar guruhi topilmadi.\n\n"
        f"Botni `{group} parents` nomli guruhga qo'shing."
    )

def reviewed_caption(sub_id: int, student_name: str, group: str,
                     grade: str, reviewer_name: str, reviewed_at: str) -> str:
    return (
        f"{CHECK} *Tekshirildi*\n\n"
        f"{FILE} `#{sub_id}` | 👤 {student_name} | {GROUP} {group}\n\n"
        f"{GRADE} *Baho:* {grade}\n"
        f"👤 *Tekshiruvchi:* {reviewer_name}\n"
        f"{CLOCK} *Vaqt:* {reviewed_at}"
    )


# ── Review complete ───────────────────────────────────────────────────────────

def review_complete_student(sub_id: int, grade: str, feedback: str, student_name: str) -> str:
    return (
        f"{CHECK} *Uy vazifasi tekshirildi!*\n\n"
        f"Assalomu alaykum, {student_name}!\n\n"
        f"{FILE} *Yuborish raqami:* `#{sub_id}`\n"
        f"{GRADE} *Baho:* {grade}\n\n"
        f"{PENCIL} *O'qituvchi izohi:*\n{feedback}"
    )

def review_updated_student(sub_id: int, grade: str, feedback: str, student_name: str) -> str:
    return (
        f"{EDIT} *Baho yangilandi!*\n\n"
        f"Assalomu alaykum, {student_name}!\n\n"
        f"{FILE} `#{sub_id}` | {GRADE} *Yangi baho:* {grade}\n\n"
        f"{PENCIL} *Yangilangan izoh:*\n{feedback}"
    )

def review_complete_parents(sub_id: int, student_name: str, group: str, grade: str, feedback: str) -> str:
    return (
        f"{CHECK} *Uy vazifasi tekshiruvi tugadi*\n\n"
        f"👤 *O'quvchi:* {student_name}\n"
        f"{GROUP} *Guruh:* {group}\n"
        f"{FILE} *Yuborish raqami:* `#{sub_id}`\n"
        f"{GRADE} *Baho:* {grade}\n\n"
        f"{PENCIL} *O'qituvchi izohi:*\n{feedback}"
    )

def review_updated_parents(sub_id: int, student_name: str, group: str, grade: str, feedback: str) -> str:
    return (
        f"{EDIT} *Baho yangilandi*\n\n"
        f"👤 {student_name} | {GROUP} {group}\n"
        f"{FILE} `#{sub_id}` | {GRADE} *{grade}*\n\n"
        f"{PENCIL} {feedback}"
    )


# ── Quick-review feedback templates ──────────────────────────────────────────

QUICK_FEEDBACK = {
    "excellent": (
        "⭐ A'lo",
        "Ajoyib ish! Kodni toza yozgansiz, mantiq to'g'ri va formatlashtirish mukammal. "
        "Shu darajani saqlang."
    ),
    "good": (
        "👍 Yaxshi",
        "Yaxshi ishlangan. Asosiy g'oya to'g'ri, lekin bir necha kichik joylarni yaxshilash mumkin. "
        "Izohlar qo'shishni unutmang."
    ),
    "needs_work": (
        "⚠️ Yaxshilash kerak",
        "Asosiy tushuncha bor, lekin kodda xatolar topildi. "
        "O'zgaruvchi nomlarini aniqlashtiring va exception handling qo'shing."
    ),
    "late": (
        "📝 Qoniqarli",
        "Topshiriq kech topshirildi. Kontent qoniqarli, lekin muddatlarni hurmat qiling."
    ),
}


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


# ── History rows ──────────────────────────────────────────────────────────────

def history_row(s: dict) -> str:
    icon       = CHECK if s["status"] == "reviewed" else CLOCK
    grade_part = f" — {s['grade']}" if s.get("grade") else ""
    return (
        f"{icon} `#{s['id']}` *{s['student_name']}* ({s['group_name']})"
        f"{grade_part}\n"
        f"     {CAL} {s['submitted_at'][:10]}"
    )

def history_page_header(query: str, page: int, total_pages: int, count: int) -> str:
    return (
        f"{BOOK} *Topshiriqlar tarixi*\n"
        f"🔍 `{query}` — {count} ta natija  •  📃 {page}/{total_pages}\n"
        f"{'─'*28}\n"
    )


# ── Mystatus ──────────────────────────────────────────────────────────────────

def mystatus_row(s: dict) -> str:
    icon      = CHECK if s["status"] == "reviewed" else CLOCK
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
        f"{'─'*28}\n"
    )


# ── Dashboard ─────────────────────────────────────────────────────────────────

def dashboard(name: str, d: dict) -> str:
    avg_str = f"{d['avg']}/5" if d["avg"] else "—"
    streak  = f"{FIRE} {d['streak']} kun" if d["streak"] > 0 else "—"
    badge_count = len(d.get("badges", []))
    return (
        f"{CHART} *{name} — Dashboard*\n\n"
        f"{'─'*28}\n"
        f"{FILE} Jami topshiriqlar:  *{d['total']}*\n"
        f"{CLOCK} Kutilmoqda:        *{d['pending']}*\n"
        f"{CHECK} Tekshirildi:       *{d['reviewed']}*\n"
        f"{GRADE} O'rtacha baho:     *{avg_str}*\n"
        f"{FIRE}  Ketma-ketlik:      *{streak}*\n"
        f"{CAL}  Oxirgi topshiriq:  *{d['last']}*\n"
        f"{MEDAL} Yutuqlar:          *{badge_count} ta*\n"
        f"{'─'*28}\n"
        f"_/badges — yutuqlarni ko'rish_\n"
        f"_/mystatus — topshiriqlar tarixi_"
    )


# ── Leaderboard ───────────────────────────────────────────────────────────────

def leaderboard(rows: list[dict], period: str) -> str:
    medals = ["🥇", "🥈", "🥉"]
    lines  = [f"{CROWN} *{period} Reytingi*\n{'─'*28}\n"]
    for i, r in enumerate(rows[:10]):
        medal   = medals[i] if i < 3 else f"{i+1}."
        avg_str = f"{round(r['avg_grade'],1)}/5" if r.get("avg_grade") else "—"
        lines.append(
            f"{medal} *{r['student_name']}* ({r['group_name']})\n"
            f"    {GRADE} {avg_str}   {FILE} {r['sub_count']} ta topshiriq"
        )
    if not rows:
        lines.append("Hali ma'lumot yo'q.")
    return "\n".join(lines)


# ── Rate limit ────────────────────────────────────────────────────────────────

def rate_limit_warning(minutes: int) -> str:
    return (
        f"{WARN} *Yuborish chegarasiga yetdingiz*\n\n"
        f"10 daqiqa ichida 3 ta topshiriq yuborish mumkin.\n"
        f"Iltimos, taxminan *{minutes} daqiqadan* so'ng qayta urinib ko'ring."
    )


# ── Resubmit ──────────────────────────────────────────────────────────────────

def resubmit_ask_file(sub_id: int) -> str:
    return (
        f"{EDIT} *Topshiriqni yangilash — `#{sub_id}`*\n\n"
        f"Yangi faylni yuboring (rasm yoki hujjat).\n"
        f"Bekor qilish: /cancel"
    )

def resubmit_confirmed(sub_id: int) -> str:
    return (
        f"{CHECK} *Topshiriq yangilandi!*\n\n"
        f"`#{sub_id}` raqamli topshiriqingiz yangi fayl bilan almashtirildi."
    )


# ── Teacher note ──────────────────────────────────────────────────────────────

def note_saved(sub_id: int) -> str:
    return f"{NOTE} *Eslatma saqlandi* — `#{sub_id}`"

def notes_list(sub_id: int, notes: list[dict]) -> str:
    if not notes:
        return f"{NOTE} `#{sub_id}` uchun eslatmalar yo'q."
    lines = [f"{NOTE} *`#{sub_id}` — O'qituvchi eslatmalari*\n"]
    for n in notes:
        lines.append(f"👤 *{n['teacher_name']}* — _{n['created_at'][:16]}_\n{n['note']}\n")
    return "\n".join(lines)


# ── Deadline ──────────────────────────────────────────────────────────────────

def deadlines_list(group: str, deadlines: list[dict]) -> str:
    if not deadlines:
        return f"{CAL} *{group}* guruhi uchun muddatlar yo'q."
    lines = [f"{CAL} *{group} — Muddatlar*\n"]
    for d in deadlines:
        lines.append(
            f"• *{d['subject']}*  —  {d['due_date']}\n"
            f"  _{d['description'] or ''}_"
        )
    return "\n".join(lines)

def deadline_reminder(group: str, subject: str, due_date: str, days_left: int) -> str:
    urgency = FIRE if days_left <= 1 else WARN
    return (
        f"{urgency} *Muddad eslatmasi*\n\n"
        f"{GROUP} *Guruh:* {group}\n"
        f"{NOTE} *Fan:* {subject}\n"
        f"{CAL} *Muddat:* {due_date}\n"
        f"⏳ *Qoldi:* {days_left} kun"
    )


# ── Stats ─────────────────────────────────────────────────────────────────────

def global_stats(s: dict) -> str:
    return (
        f"{CHART} *Umumiy statistika*\n\n"
        f"{FILE} Jami topshiriqlar: *{s['total']}*\n"
        f"{CLOCK} Kutilmoqda:       *{s['pending']}*\n"
        f"{CHECK} Tekshirildi:      *{s['reviewed']}*\n"
        f"{GROUP} Guruhlar soni:    *{s['groups']}*\n"
        f"👤 Faol o'quvchilar:  *{s['students']}*\n"
        f"{GRADE} Tekshiruv %:      *{s['rate']}%*"
    )

def group_stats(s: dict) -> str:
    avg = f"{s['avg_grade']}/5" if s["avg_grade"] else "—"
    return (
        f"{CHART} *{s['group']} guruhi statistikasi*\n\n"
        f"{FILE} Jami topshiriqlar: *{s['total']}*\n"
        f"{CLOCK} Kutilmoqda:       *{s['pending']}*\n"
        f"{CHECK} Tekshirildi:      *{s['reviewed']}*\n"
        f"{GRADE} O'rtacha baho:    *{avg}*"
    )

def student_stats_msg(name: str, subs: list[dict]) -> str:
    from database import _grade_average
    total    = len(subs)
    reviewed = sum(1 for s in subs if s["status"] == "reviewed")
    avg      = _grade_average(subs)
    lines    = [
        f"{CHART} *{name} — statistika*\n",
        f"{FILE} Jami: *{total}*   {CHECK} Tekshirildi: *{reviewed}*",
        f"{GRADE} O'rtacha: *{avg}/5*\n",
        f"*So'nggi topshiriqlar:*",
    ]
    for s in subs[:5]:
        icon = CHECK if s["status"] == "reviewed" else CLOCK
        grade_part = f" — {s['grade']}" if s.get("grade") else ""
        lines.append(f"{icon} `#{s['id']}` {s['submitted_at'][:10]}{grade_part}")
    return "\n".join(lines)


# ── Weekly report ─────────────────────────────────────────────────────────────

def weekly_report(group: str, stats: dict) -> str:
    avg = f"{stats['avg_grade']}/5" if stats["avg_grade"] else "—"
    return (
        f"{BELL} *Haftalik hisobot — {group}*\n\n"
        f"{FILE} Yuborilgan:   *{stats['total']}*\n"
        f"{CHECK} Tekshirildi: *{stats['reviewed']}*\n"
        f"{CLOCK} Kutilmoqda:  *{stats['pending']}*\n"
        f"{GRADE} O'rtacha:    *{avg}*"
    )


# ── Daily digest ─────────────────────────────────────────────────────────────

def daily_digest(d: dict) -> str:
    return (
        f"{CAL} *Kunlik Hisobot*\n\n"
        f"{FILE} Bugun yuborildi:    *{d['today_subs']}*\n"
        f"{CHECK} Bugun tekshirildi: *{d['today_reviewed']}*\n"
        f"{CLOCK} Jami kutilmoqda:   *{d['total_pending']}*\n"
        f"{WARN} Kech topshiriqlar: *{d['late_count']}*"
    )


# ── Reminder ─────────────────────────────────────────────────────────────────

def pending_reminder(student_name: str, sub_id: int) -> str:
    return (
        f"{BELL} Assalomu alaykum, *{student_name}*!\n\n"
        f"`#{sub_id}` raqamli topshiriqingiz hali tekshirilmagan.\n"
        f"Tez orada natija yuboriladi."
    )

def submit_reminder(student_name: str, group: str, subject: str) -> str:
    return (
        f"{WARN} Assalomu alaykum, *{student_name}*!\n\n"
        f"{NOTE} *{subject}* uy vazifasini hali topshirmadingiz.\n"
        f"{GROUP} Guruh: *{group}*\n\n"
        f"`/submit` buyrug'i bilan uy vazifangizni yuboring."
    )


# ── Bulk review ───────────────────────────────────────────────────────────────

def bulk_review_confirm(group: str, count: int, grade: str) -> str:
    return (
        f"{WARN} *Ommaviy tekshiruv tasdiqlash*\n\n"
        f"{GROUP} Guruh: *{group}*\n"
        f"{FILE} Topshiriqlar soni: *{count}*\n"
        f"{GRADE} Baho: *{grade}*\n\n"
        f"Davom etish uchun: /confirm\\_bulk\nBekor qilish: /cancel"
    )

def bulk_review_done(group: str, count: int, grade: str) -> str:
    return f"{CHECK} *{group}* guruhida *{count}* ta topshiriq *{grade}* baho bilan tekshirildi."


# ── Code analysis ─────────────────────────────────────────────────────────────

def code_analysis_header(file_name: str) -> str:
    return f"{CODE} *Kod tahlili bajarilmoqda:* `{file_name}`\n_Iltimos, kuting…_"