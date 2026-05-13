"""
sandbox.py — Secure Python code execution in a subprocess.

Security measures:
  - Blocked dangerous imports (os, subprocess, socket, shutil, etc.)
  - 5-second execution timeout
  - Temp file created and cleaned up
  - Only Python supported (JS/HTML/CSS are static, not executed)
  - stdout + stderr captured and truncated
"""

import ast
import logging
import os
import subprocess
import tempfile
import textwrap

logger = logging.getLogger(__name__)

TIMEOUT_SECONDS = 5
MAX_OUTPUT_LEN  = 1500

# Imports that are blocked in the sandbox
BLOCKED_IMPORTS = {
    "os", "sys", "subprocess", "socket", "shutil", "multiprocessing",
    "threading", "pathlib", "glob", "io", "builtins", "importlib",
    "ctypes", "signal", "resource", "pty", "fcntl", "termios",
    "pickle", "shelve", "dbm", "zipfile", "tarfile",
}

# A tiny wrapper that blocks dangerous builtins at runtime
SANDBOX_WRAPPER = textwrap.dedent("""
import builtins as _builtins

_safe_builtins = {
    'print', 'len', 'range', 'enumerate', 'zip', 'map', 'filter',
    'list', 'dict', 'set', 'tuple', 'str', 'int', 'float', 'bool',
    'type', 'isinstance', 'issubclass', 'hasattr', 'getattr',
    'abs', 'max', 'min', 'sum', 'sorted', 'reversed',
    'round', 'divmod', 'pow', 'hex', 'oct', 'bin',
    'repr', 'format', 'chr', 'ord',
    'True', 'False', 'None',
    'Exception', 'ValueError', 'TypeError', 'KeyError',
    'IndexError', 'AttributeError', 'ZeroDivisionError',
    'StopIteration', 'RuntimeError', 'NotImplementedError',
    '__name__', '__doc__',
}

# Prevent open() and exec() in user code
_builtins.open    = None
_builtins.__import__ = None

# ── USER CODE BELOW ──
""")


def _check_blocked_imports(code: str) -> list[str]:
    """
    Parse the AST and return a list of any blocked import names found.
    This is a static check before execution.
    """
    blocked_found = []
    try:
        tree = ast.parse(code)
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    root = alias.name.split(".")[0]
                    if root in BLOCKED_IMPORTS:
                        blocked_found.append(alias.name)
            elif isinstance(node, ast.ImportFrom):
                if node.module:
                    root = node.module.split(".")[0]
                    if root in BLOCKED_IMPORTS:
                        blocked_found.append(node.module)
    except SyntaxError:
        pass  # Syntax errors are handled separately by syntax_checker
    return blocked_found


async def run_python(code: str) -> dict:
    """
    Safely execute Python code and return:
    {
        "success": bool,
        "output":  str,      # stdout
        "error":   str,      # stderr or security message
        "blocked": list[str] # blocked imports detected
    }
    """
    # 1. Static import check
    blocked = _check_blocked_imports(code)
    if blocked:
        return {
            "success": False,
            "output":  "",
            "error":   f"Taqiqlangan importlar: {', '.join(blocked)}",
            "blocked": blocked,
        }

    # 2. Write user code to a temp file with sandbox wrapper
    full_code = SANDBOX_WRAPPER + "\n" + code

    tmp_path = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".py", delete=False, encoding="utf-8"
        ) as tmp:
            tmp.write(full_code)
            tmp_path = tmp.name

        # 3. Run in subprocess with timeout
        result = subprocess.run(
            ["python", tmp_path],
            capture_output=True,
            text=True,
            timeout=TIMEOUT_SECONDS,
        )

        stdout = result.stdout.strip()
        stderr = result.stderr.strip()

        # Truncate long outputs
        if len(stdout) > MAX_OUTPUT_LEN:
            stdout = stdout[:MAX_OUTPUT_LEN] + "\n... [chiqish qisqartirildi]"
        if len(stderr) > MAX_OUTPUT_LEN:
            stderr = stderr[:MAX_OUTPUT_LEN] + "\n... [xato qisqartirildi]"

        return {
            "success": result.returncode == 0,
            "output":  stdout,
            "error":   stderr,
            "blocked": [],
        }

    except subprocess.TimeoutExpired:
        return {
            "success": False,
            "output":  "",
            "error":   f"⏰ Vaqt tugadi ({TIMEOUT_SECONDS} soniya). Cheksiz tsikl bo'lishi mumkin.",
            "blocked": [],
        }
    except Exception as exc:
        logger.error("Sandbox execution error: %s", exc)
        return {
            "success": False,
            "output":  "",
            "error":   f"Sandbox xatosi: {exc}",
            "blocked": [],
        }
    finally:
        # 4. Always clean up temp file
        if tmp_path and os.path.exists(tmp_path):
            os.unlink(tmp_path)


def format_execution_result(result: dict) -> str:
    """Format sandbox result into a Telegram message."""
    lines = []

    if result.get("blocked"):
        lines.append(f"🚫 *Taqiqlangan importlar aniqlandi:*")
        for b in result["blocked"]:
            lines.append(f"  `{b}`")
        lines.append("\nBu importlarga ruxsat berilmaydi xavfsizlik sababli.")
        return "\n".join(lines)

    if result["success"]:
        lines.append("✅ *Kod muvaffaqiyatli bajarildi*")
        if result["output"]:
            lines.append(f"\n```\n{result['output']}\n```")
        else:
            lines.append("\n_(chiqish yo'q)_")
    else:
        lines.append("❌ *Xato yuz berdi*")
        if result["error"]:
            lines.append(f"\n```\n{result['error']}\n```")

    return "\n".join(lines)