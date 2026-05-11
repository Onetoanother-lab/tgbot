"""Message templates for the HomeworkBot."""

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
        f"Quyidagi tugmalardan baho tanlang yoki buyruq yuboring:\n"
        f"`/review {submission_id} <baho> | <izoh>`"
    )


def review_complete_student(
    submission_id: int,
    grade: str,
    feedback: str,
    student_name: str,
) -> str:
    return (
        f"{CHECK} *Uy vazifasi tekshirildi!*\n\n"
        f"Assalomu alaykum, {student_name}! Uy vazifangiz tekshirildi.\n\n"
        f"{FILE} *Yuborish raqami:* `#{submission_id}`\n"
        f"{GRADE} *Baho:* {grade}\n\n"
        f"{PENCIL} *O'qituvchi izohi:*\n{feedback}"
    )


def review_complete_parents(
    submission_id: int,
    student_name: str,
    group: str,
    grade: str,
    feedback: str,
) -> str:
    return (
        f"{CHECK} *Uy vazifasi tekshiruvi tugadi*\n\n"
        f"👤 *O'quvchi:* {student_name}\n"
        f"{GROUP} *Guruh:* {group}\n"
        f"{FILE} *Yuborish raqami:* `#{submission_id}`\n"
        f"{GRADE} *Baho:* {grade}\n\n"
        f"{PENCIL} *O'qituvchi izohi:*\n{feedback}"
    )


def no_parents_group(group: str) -> str:
    return (
        f"{WARN} *{group}* guruhi uchun ota-onalar guruhi topilmadi.\n\n"
        f"Botni quyidagi nomli guruhga qo'shing:\n"
        f"`{group} parents`\n\n"
        f"Admin `/register_parents` buyrug'i orqali ro'yxatdan o'tkazishi mumkin."
    )