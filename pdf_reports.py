"""
pdf_reports.py — Generate PDF report cards using reportlab.

Produces a polished single-page or multi-page PDF with:
  - Student name, group, date range
  - Submission table with grades
  - Summary statistics
  - Teacher comments
  - Badges earned
"""

import io
import logging
from datetime import datetime

logger = logging.getLogger(__name__)

try:
    from reportlab.lib              import colors
    from reportlab.lib.pagesizes    import A4
    from reportlab.lib.styles       import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib.units        import cm
    from reportlab.platypus         import (
        SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, HRFlowable
    )
    from reportlab.lib.enums        import TA_CENTER, TA_LEFT, TA_RIGHT
    REPORTLAB_AVAILABLE = True
except ImportError:
    REPORTLAB_AVAILABLE = False
    logger.warning("reportlab not installed — PDF generation disabled.")

import database as db


# ── Colour palette ────────────────────────────────────────────────────────────
PRIMARY     = colors.HexColor("#1a1a2e")
ACCENT      = colors.HexColor("#e94560")
LIGHT_BG    = colors.HexColor("#f5f5f5")
GRID_COLOR  = colors.HexColor("#dddddd")
TEXT_DARK   = colors.HexColor("#222222")


def _grade_color(grade: str | None) -> tuple:
    """Return RGB color based on grade."""
    mapping = {
        "⭐ A'lo":             colors.HexColor("#2ecc71"),
        "👍 Yaxshi":           colors.HexColor("#27ae60"),
        "📝 Qoniqarli":        colors.HexColor("#f39c12"),
        "⚠️ Yaxshilash kerak": colors.HexColor("#e67e22"),
        "❌ Bajarilmagan":      colors.HexColor("#e74c3c"),
    }
    return mapping.get(grade or "", colors.HexColor("#999999"))


def generate_student_report(student_id: int, student_name: str) -> io.BytesIO | None:
    """
    Generate a PDF report for one student.
    Returns BytesIO buffer ready to send as a Telegram document.
    """
    if not REPORTLAB_AVAILABLE:
        return None

    subs    = db.get_student_submissions(student_id)
    badges  = db.get_user_badges(student_id)
    stats   = db.get_student_dashboard(student_id)

    buf = io.BytesIO()
    doc = SimpleDocTemplate(
        buf,
        pagesize=A4,
        leftMargin=2*cm, rightMargin=2*cm,
        topMargin=2*cm,  bottomMargin=2*cm,
    )

    styles = getSampleStyleSheet()
    story  = []

    # ── Header ────────────────────────────────────────────────────────────────
    title_style = ParagraphStyle(
        "title",
        parent=styles["Normal"],
        fontSize=22, textColor=PRIMARY, spaceAfter=4,
        alignment=TA_CENTER, fontName="Helvetica-Bold",
    )
    sub_style = ParagraphStyle(
        "sub", parent=styles["Normal"],
        fontSize=11, textColor=ACCENT,
        alignment=TA_CENTER,
    )
    story.append(Paragraph("📚 HomeworkBot", title_style))
    story.append(Paragraph("O'quvchi Hisoboti", sub_style))
    story.append(HRFlowable(width="100%", thickness=2, color=ACCENT, spaceAfter=12))

    # ── Student info ──────────────────────────────────────────────────────────
    info_style = ParagraphStyle(
        "info", parent=styles["Normal"], fontSize=12, leading=18
    )
    group = subs[0]["group_name"] if subs else "—"
    story.append(Paragraph(f"<b>O'quvchi:</b> {student_name}", info_style))
    story.append(Paragraph(f"<b>Guruh:</b> {group}", info_style))
    story.append(Paragraph(
        f"<b>Sana:</b> {datetime.now().strftime('%d.%m.%Y')}", info_style
    ))
    story.append(Spacer(1, 0.5*cm))

    # ── Summary stats ─────────────────────────────────────────────────────────
    avg_str = f"{stats['avg']}/5" if stats["avg"] else "—"
    stat_data = [
        ["📄 Jami", "✅ Tekshirildi", "🕐 Kutilmoqda", "⭐ O'rtacha"],
        [str(stats["total"]), str(stats["reviewed"]), str(stats["pending"]), avg_str],
    ]
    stat_table = Table(stat_data, colWidths=[4*cm]*4)
    stat_table.setStyle(TableStyle([
        ("BACKGROUND",  (0,0), (-1,0), PRIMARY),
        ("TEXTCOLOR",   (0,0), (-1,0), colors.white),
        ("FONTNAME",    (0,0), (-1,0), "Helvetica-Bold"),
        ("FONTSIZE",    (0,0), (-1,-1), 10),
        ("ALIGN",       (0,0), (-1,-1), "CENTER"),
        ("VALIGN",      (0,0), (-1,-1), "MIDDLE"),
        ("ROWBACKGROUNDS", (0,1), (-1,-1), [LIGHT_BG, colors.white]),
        ("GRID",        (0,0), (-1,-1), 0.5, GRID_COLOR),
        ("ROUNDEDCORNERS", [3]),
        ("TOPPADDING",  (0,0), (-1,-1), 8),
        ("BOTTOMPADDING", (0,0), (-1,-1), 8),
    ]))
    story.append(stat_table)
    story.append(Spacer(1, 0.5*cm))

    # ── Badges ────────────────────────────────────────────────────────────────
    if badges:
        story.append(Paragraph("<b>🎖️ Yutuqlar</b>", info_style))
        badge_text = "   ".join(
            db.BADGE_LABELS.get(b["badge_type"], b["badge_type"]) for b in badges
        )
        story.append(Paragraph(badge_text, styles["Normal"]))
        story.append(Spacer(1, 0.4*cm))

    # ── Submissions table ─────────────────────────────────────────────────────
    story.append(HRFlowable(width="100%", thickness=1, color=GRID_COLOR, spaceAfter=6))
    story.append(Paragraph("<b>📋 Topshiriqlar tarixi</b>", info_style))
    story.append(Spacer(1, 0.3*cm))

    if subs:
        table_data = [["#", "Sana", "Turi", "Baho", "Holat"]]
        for s in subs[:20]:  # Max 20 rows per page
            table_data.append([
                f"#{s['id']}",
                s["submitted_at"][:10],
                s["file_type"].capitalize(),
                _strip_emoji(s.get("grade") or "—"),
                "Tekshirildi" if s["status"] == "reviewed" else "Kutilmoqda",
            ])

        col_widths = [1.5*cm, 3*cm, 3*cm, 5*cm, 3.5*cm]
        sub_table  = Table(table_data, colWidths=col_widths)
        sub_table.setStyle(TableStyle([
            ("BACKGROUND",     (0,0), (-1,0), PRIMARY),
            ("TEXTCOLOR",      (0,0), (-1,0), colors.white),
            ("FONTNAME",       (0,0), (-1,0), "Helvetica-Bold"),
            ("FONTSIZE",       (0,0), (-1,-1), 9),
            ("ALIGN",          (0,0), (-1,-1), "CENTER"),
            ("VALIGN",         (0,0), (-1,-1), "MIDDLE"),
            ("ROWBACKGROUNDS", (0,1), (-1,-1), [colors.white, LIGHT_BG]),
            ("GRID",           (0,0), (-1,-1), 0.5, GRID_COLOR),
            ("TOPPADDING",     (0,0), (-1,-1), 6),
            ("BOTTOMPADDING",  (0,0), (-1,-1), 6),
        ]))
        story.append(sub_table)
    else:
        story.append(Paragraph("Hali topshiriq yuborilmagan.", styles["Normal"]))

    # ── Latest feedback ───────────────────────────────────────────────────────
    reviewed = [s for s in subs if s.get("feedback")]
    if reviewed:
        story.append(Spacer(1, 0.5*cm))
        story.append(HRFlowable(width="100%", thickness=1, color=GRID_COLOR, spaceAfter=6))
        story.append(Paragraph("<b>💬 So'nggi o'qituvchi izohi</b>", info_style))
        last = reviewed[0]
        fb_style = ParagraphStyle(
            "fb", parent=styles["Normal"],
            fontSize=10, textColor=TEXT_DARK,
            leftIndent=10, borderPad=6,
            backColor=LIGHT_BG, leading=14,
        )
        story.append(Paragraph(last["feedback"], fb_style))

    # ── Footer ────────────────────────────────────────────────────────────────
    story.append(Spacer(1, 1*cm))
    footer_style = ParagraphStyle(
        "footer", parent=styles["Normal"],
        fontSize=8, textColor=colors.grey, alignment=TA_CENTER,
    )
    story.append(HRFlowable(width="100%", thickness=1, color=GRID_COLOR))
    story.append(Paragraph(
        f"Yaratildi: HomeworkBot  •  {datetime.now().strftime('%d.%m.%Y %H:%M')}",
        footer_style,
    ))

    doc.build(story)
    buf.seek(0)
    return buf


def generate_group_report(group_name: str) -> io.BytesIO | None:
    """Generate a summary PDF for all students in a group."""
    if not REPORTLAB_AVAILABLE:
        return None

    subs  = db.get_group_submissions(group_name)
    stats = db.get_group_stats(group_name)

    buf = io.BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=A4, leftMargin=2*cm, rightMargin=2*cm,
                            topMargin=2*cm, bottomMargin=2*cm)
    styles = getSampleStyleSheet()
    story  = []

    title_style = ParagraphStyle(
        "t", parent=styles["Normal"],
        fontSize=20, textColor=PRIMARY, alignment=TA_CENTER,
        fontName="Helvetica-Bold", spaceAfter=4,
    )
    story.append(Paragraph(f"📚 {group_name} Guruhi Hisoboti", title_style))
    story.append(HRFlowable(width="100%", thickness=2, color=ACCENT, spaceAfter=10))

    info = ParagraphStyle("i", parent=styles["Normal"], fontSize=11, leading=18)
    avg_str = f"{stats['avg_grade']}/5" if stats["avg_grade"] else "—"
    for text in [
        f"<b>Guruh:</b> {group_name.upper()}",
        f"<b>Jami topshiriqlar:</b> {stats['total']}",
        f"<b>Tekshirildi:</b> {stats['reviewed']}",
        f"<b>Kutilmoqda:</b> {stats['pending']}",
        f"<b>O'rtacha baho:</b> {avg_str}",
        f"<b>Sana:</b> {datetime.now().strftime('%d.%m.%Y')}",
    ]:
        story.append(Paragraph(text, info))

    story.append(Spacer(1, 0.5*cm))
    story.append(Paragraph("<b>📋 Topshiriqlar</b>", info))
    story.append(Spacer(1, 0.3*cm))

    if subs:
        data = [["#", "O'quvchi", "Sana", "Baho", "Holat"]]
        for s in subs[:30]:
            data.append([
                f"#{s['id']}",
                s["student_name"],
                s["submitted_at"][:10],
                _strip_emoji(s.get("grade") or "—"),
                "✓" if s["status"] == "reviewed" else "⏳",
            ])
        t = Table(data, colWidths=[1.5*cm, 5*cm, 3*cm, 4.5*cm, 2*cm])
        t.setStyle(TableStyle([
            ("BACKGROUND",     (0,0), (-1,0), PRIMARY),
            ("TEXTCOLOR",      (0,0), (-1,0), colors.white),
            ("FONTNAME",       (0,0), (-1,0), "Helvetica-Bold"),
            ("FONTSIZE",       (0,0), (-1,-1), 9),
            ("ALIGN",          (0,0), (-1,-1), "CENTER"),
            ("ROWBACKGROUNDS", (0,1), (-1,-1), [colors.white, LIGHT_BG]),
            ("GRID",           (0,0), (-1,-1), 0.5, GRID_COLOR),
            ("TOPPADDING",     (0,0), (-1,-1), 5),
            ("BOTTOMPADDING",  (0,0), (-1,-1), 5),
        ]))
        story.append(t)

    doc.build(story)
    buf.seek(0)
    return buf


def _strip_emoji(text: str) -> str:
    """Remove emoji characters — reportlab's default font can't render them."""
    return re.sub(r"[^\x00-\x7F]+", "", text).strip() if text else "—"


import re  # noqa: E402 — placed here to avoid circular at module top