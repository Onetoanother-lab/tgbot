"""
syntax_checker.py — Static syntax and basic lint checks.

Supported:
  .py   → ast.parse (built-in, no external deps)
  .js   → regex-based pattern checks
  .html → html.parser-based tag matching
  .css  → regex brace-balance check

Returns list of Issue objects with line numbers and messages.
"""

import ast
import re
import logging
from html.parser import HTMLParser
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class Issue:
    line:    int | None
    level:   str        # 'error' | 'warning' | 'hint'
    message: str

    def __str__(self) -> str:
        prefix = {"error": "❌", "warning": "⚠️", "hint": "💡"}.get(self.level, "•")
        loc    = f"Qator {self.line}: " if self.line else ""
        return f"{prefix} {loc}{self.message}"


def check_python(code: str) -> list[Issue]:
    issues: list[Issue] = []

    # 1. Syntax check via AST
    try:
        tree = ast.parse(code)
    except SyntaxError as e:
        return [Issue(e.lineno, "error", f"Sintaksis xatosi: {e.msg}")]

    lines = code.splitlines()

    # 2. Walk AST for common beginner mistakes
    for node in ast.walk(tree):

        # Bare except clause
        if isinstance(node, ast.ExceptHandler) and node.type is None:
            issues.append(Issue(
                getattr(node, "lineno", None), "warning",
                "Yalang'och `except:` — aniq exception turi ko'rsating"
            ))

        # Mutable default arguments (e.g. def f(x=[]))
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            for default in node.args.defaults:
                if isinstance(default, (ast.List, ast.Dict, ast.Set)):
                    issues.append(Issue(
                        node.lineno, "warning",
                        f"`{node.name}`: o'zgaruvchan default argument ishlatmang"
                    ))

        # print() without arguments (likely debug leftover)
        if (isinstance(node, ast.Call) and
                isinstance(node.func, ast.Name) and
                node.func.id == "print" and
                not node.args and not node.keywords):
            issues.append(Issue(
                getattr(node, "lineno", None), "hint",
                "Bo'sh `print()` — debug qoldig'i bo'lishi mumkin"
            ))

        # == None instead of `is None`
        if (isinstance(node, ast.Compare) and
                any(isinstance(op, ast.Eq) for op in node.ops)):
            for comparator in node.comparators:
                if isinstance(comparator, ast.Constant) and comparator.value is None:
                    issues.append(Issue(
                        getattr(node, "lineno", None), "hint",
                        "`== None` o'rniga `is None` ishlating"
                    ))

    # 3. Line-level checks
    for i, line in enumerate(lines, start=1):
        stripped = line.rstrip()

        # Long lines
        if len(stripped) > 100:
            issues.append(Issue(i, "hint", f"Uzun qator ({len(stripped)} belgi) — 100 dan oshirmaslik tavsiya etiladi"))

        # TODO / FIXME left in code
        if re.search(r"\b(TODO|FIXME|HACK|XXX)\b", stripped, re.IGNORECASE):
            issues.append(Issue(i, "hint", "Tugallanmagan izoh: TODO/FIXME"))

        # Single-character variable names (except i, j, k, x, y, n)
        m = re.search(r"\b([a-wz])\s*=\s*[^=]", stripped)
        if m and m.group(1) not in ("i", "j", "k", "x", "y", "n", "s", "f"):
            issues.append(Issue(i, "hint", f"Noaniq o'zgaruvchi nomi: `{m.group(1)}`"))

    # 4. No docstrings on functions
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            if not (node.body and isinstance(node.body[0], ast.Expr) and
                    isinstance(node.body[0].value, ast.Constant)):
                issues.append(Issue(
                    node.lineno, "hint",
                    f"`{node.name}` funksiyasida docstring yo'q"
                ))
            break  # Only warn about first function to avoid noise

    return issues[:10]  # Cap at 10 issues


def check_javascript(code: str) -> list[Issue]:
    issues: list[Issue] = []
    lines = code.splitlines()

    for i, line in enumerate(lines, start=1):
        stripped = line.strip()

        # var usage (prefer let/const)
        if re.match(r"\bvar\b\s+\w+", stripped):
            issues.append(Issue(i, "warning", "`var` o'rniga `let`/`const` ishlating"))

        # == instead of ===
        if re.search(r"(?<!=)={2}(?!=)", stripped) and "===" not in stripped:
            issues.append(Issue(i, "warning", "`==` o'rniga `===` (qat'iy tenglik) ishlating"))

        # console.log leftover
        if "console.log" in stripped:
            issues.append(Issue(i, "hint", "Debug `console.log` — ishlab chiqarishda olib tashlang"))

        # Missing semicolons on statement lines
        if (stripped and not stripped.endswith((";", "{", "}", "//", ",", "("))
                and re.search(r"[a-zA-Z0-9_'\"`\])]$", stripped)
                and not stripped.startswith(("//", "/*", "*", "if", "for", "while", "function", "class"))):
            issues.append(Issue(i, "hint", "Nuqta-vergul (;) yetishmayapti"))

    return issues[:10]


def check_html(code: str) -> list[Issue]:
    issues: list[Issue] = []

    class _TagChecker(HTMLParser):
        def __init__(self):
            super().__init__()
            self.stack  = []
            self.errors = []
            # Void elements that don't need closing
            self.void   = {
                "area","base","br","col","embed","hr","img","input",
                "link","meta","param","source","track","wbr",
            }

        def handle_starttag(self, tag, attrs):
            if tag not in self.void:
                self.stack.append(tag)

        def handle_endtag(self, tag):
            if tag in self.void:
                return
            if self.stack and self.stack[-1] == tag:
                self.stack.pop()
            else:
                self.errors.append(f"</{tag}> yopilishi noto'g'ri yoki mos tag yo'q")

        def finish(self):
            for unclosed in self.stack:
                self.errors.append(f"<{unclosed}> yopilmagan")

    checker = _TagChecker()
    try:
        checker.feed(code)
        checker.finish()
        for err in checker.errors[:5]:
            issues.append(Issue(None, "error", err))
    except Exception as e:
        issues.append(Issue(None, "error", f"HTML tahlil xatosi: {e}"))

    # Check for missing alt on img
    for i, line in enumerate(code.splitlines(), 1):
        if "<img" in line.lower() and "alt=" not in line.lower():
            issues.append(Issue(i, "warning", "`<img>` da `alt` atributi yo'q"))

    return issues[:10]


def check_css(code: str) -> list[Issue]:
    issues: list[Issue] = []

    # Brace balance
    open_count  = code.count("{")
    close_count = code.count("}")
    if open_count != close_count:
        issues.append(Issue(
            None, "error",
            f"Qavslar balansi noto'g'ri: {open_count} ochish, {close_count} yopish"
        ))

    # Missing semicolons inside rules
    rule_bodies = re.findall(r"\{([^}]+)\}", code)
    for body in rule_bodies:
        for prop_line in body.splitlines():
            stripped = prop_line.strip()
            if stripped and ":" in stripped and not stripped.endswith(";") and not stripped.startswith("//"):
                issues.append(Issue(None, "hint", f"Nuqta-vergul yetishmaydi: `{stripped[:50]}`"))

    # Vendor prefixes without standard property
    for m in re.finditer(r"-webkit-(\S+)", code):
        prop = m.group(1)
        if prop not in code.replace(m.group(0), ""):
            issues.append(Issue(None, "hint", f"Standart xususiyat ham qo'shing: `{prop}`"))

    return issues[:10]


def check_file(code: str, extension: str) -> list[Issue]:
    """Entry point — dispatch to the correct checker based on file extension."""
    ext = extension.lower().lstrip(".")
    if ext == "py":
        return check_python(code)
    elif ext in ("js", "ts", "jsx", "tsx"):
        return check_javascript(code)
    elif ext in ("html", "htm"):
        return check_html(code)
    elif ext == "css":
        return check_css(code)
    else:
        return []


def format_issues(issues: list[Issue], file_ext: str) -> str:
    """Format the issues list into a Telegram-ready message."""
    if not issues:
        return f"✅ *Sintaksis tekshiruvi o'tdi* (.{file_ext})\nHech qanday muammo topilmadi."

    lines = [f"🔍 *Sintaksis tekshiruvi* (.{file_ext}) — {len(issues)} ta topildi:\n"]
    for issue in issues:
        lines.append(str(issue))
    return "\n".join(lines)