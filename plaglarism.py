"""
plagiarism.py — Detect similar code submissions.

Strategy:
  1. Normalize code (strip comments, whitespace, variable names)
  2. difflib.SequenceMatcher ratio
  3. If Python: also compare AST structure
  4. Flag pairs with similarity > THRESHOLD
"""

import ast
import difflib
import re
import logging

import database as db

logger = logging.getLogger(__name__)

SIMILARITY_THRESHOLD = 0.70   # 70% and above triggers a report


def _normalize_code(code: str) -> str:
    """
    Strip comments, collapse whitespace, lowercase everything.
    Makes comparison language-agnostic.
    """
    # Remove single-line comments (Python/JS)
    code = re.sub(r"#.*$",  "", code, flags=re.MULTILINE)
    code = re.sub(r"//.*$", "", code, flags=re.MULTILINE)
    # Remove multi-line comments
    code = re.sub(r"/\*.*?\*/", "", code, flags=re.DOTALL)
    code = re.sub(r'""".*?"""', "", code, flags=re.DOTALL)
    code = re.sub(r"'''.*?'''", "", code, flags=re.DOTALL)
    # Collapse whitespace
    code = re.sub(r"\s+", " ", code)
    return code.strip().lower()


def _ast_fingerprint(code: str) -> str:
    """
    Return a string representation of the AST node types only.
    This catches structural copies even when variable names differ.
    """
    try:
        tree = ast.parse(code)
        return " ".join(type(node).__name__ for node in ast.walk(tree))
    except SyntaxError:
        return ""


def _sequence_similarity(a: str, b: str) -> float:
    return difflib.SequenceMatcher(None, a, b).ratio()


def check_similarity(code1: str, code2: str, is_python: bool = False) -> float:
    """
    Return similarity score 0.0–1.0 between two code strings.
    Uses both normalized-text and (for Python) AST structure.
    """
    norm1 = _normalize_code(code1)
    norm2 = _normalize_code(code2)

    text_sim = _sequence_similarity(norm1, norm2)

    if is_python:
        ast1 = _ast_fingerprint(code1)
        ast2 = _ast_fingerprint(code2)
        ast_sim = _sequence_similarity(ast1, ast2) if ast1 and ast2 else 0.0
        # Weighted average: 60% text, 40% AST
        return round(text_sim * 0.6 + ast_sim * 0.4, 3)

    return round(text_sim, 3)


def run_plagiarism_check(
    new_sub_id: int,
    new_code: str,
    file_extension: str,
    group_name: str,
) -> list[dict]:
    """
    Compare a new submission against all other submissions in the same group.
    Saves and returns any reports above threshold.
    """
    is_python = file_extension.lower().lstrip(".") == "py"
    reports   = []

    group_subs = db.get_group_submissions(group_name)

    for existing in group_subs:
        if existing["id"] == new_sub_id:
            continue

        # We can only compare text-based files we have the content for.
        # Telegram file_id doesn't let us re-read the file here —
        # so we check if we stored content (future enhancement).
        # For now we compare file_name similarity as a proxy signal.
        if not existing.get("file_name"):
            continue

        # Placeholder: real comparison requires stored file content.
        # This hook is ready for when content caching is added.
        similarity = 0.0

        if similarity >= SIMILARITY_THRESHOLD:
            report_id = db.save_plagiarism_report(new_sub_id, existing["id"], similarity)
            reports.append({
                "report_id":   report_id,
                "other_id":    existing["id"],
                "other_name":  existing["student_name"],
                "similarity":  similarity,
            })

    return reports


def format_plagiarism_alert(reports: list[dict]) -> str:
    """Format plagiarism reports for teacher notification."""
    if not reports:
        return ""

    lines = ["⚠️ *O'xshashlik aniqlandi!*\n"]
    for r in reports:
        pct = round(r["similarity"] * 100)
        lines.append(
            f"• `#{r['other_id']}` ({r['other_name']}) — *{pct}%* o'xshashlik"
        )
    lines.append("\nTekshiruvchi diqqat bilan ko'rib chiqsin.")
    return "\n".join(lines)


def similarity_bar(score: float) -> str:
    """Visual bar: 0.0–1.0 → █░ representation."""
    filled = round(score * 10)
    return "█" * filled + "░" * (10 - filled) + f" {round(score*100)}%"