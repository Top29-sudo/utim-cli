import os
import re
import sys
import shutil
import zipfile
import io
from utim_cli.logger import redact_text, LOG_FILE
from utim_cli.doctor import run_diagnostics
from rich.console import Console

# ── Unicode → ASCII symbol map ────────────────────────────────────────────────
_UNICODE_TO_ASCII: list = [
    # Rich / doctor symbols
    ("\u2713", "[OK]"),       # ✓
    ("\u2717", "[FAIL]"),     # ✗
    ("\u2022", "-"),          # •
    ("\u2b21", "#"),          # ⬡
    ("\u2026", "..."),        # …
    ("\u2192", "->"),         # →
    ("\u2714", "[OK]"),       # ✔
    ("\u2718", "[FAIL]"),     # ✘
    ("\u25b6", ">"),          # ▶
    ("\u25cf", "*"),          # ●
    # Emoji used in doctor / report
    ("\U0001f4c4", "[file]"),
    ("\u270f",     "[edit]"),
    ("\U0001f5d1", "[del]"),
    ("\U0001f4e6", "[pkg]"),
    ("\u26a1",     "[run]"),
    ("\U0001f4c1", "[dir]"),
    ("\U0001f50d", "[search]"),
    ("\U0001f9e0", "[ai]"),
]

_ANSI_RE = re.compile(r"\x1b\[[0-9;]*[mKHFABCDJsu]")


def _to_ascii(text: str) -> str:
    """Strip ANSI escape codes and replace Unicode symbols with ASCII equivalents.

    Any remaining non-ASCII character (e.g. user-supplied filenames or log
    entries) is replaced with '?' so the output is always 7-bit clean and safe
    to print on any Windows code page.
    """
    # 1. Remove ANSI colour/cursor escape sequences
    text = _ANSI_RE.sub("", text)
    # 2. Map known symbols to ASCII stand-ins
    for uni, asc in _UNICODE_TO_ASCII:
        text = text.replace(uni, asc)
    # 3. Encode to ASCII, replacing anything still non-ASCII
    return text.encode("ascii", errors="replace").decode("ascii")


def create_report_bundle() -> str:
    """Create a support report zip bundle with sensitive data redacted.

    The file written inside the zip is ASCII-only so it can be opened and
    printed on any Windows console regardless of the active code page.
    """
    report_dir = ".utim_tmp"
    os.makedirs(report_dir, exist_ok=True)

    report_txt_path = os.path.join(report_dir, "support_report.txt")
    bundle_zip_path = os.path.join(report_dir, "report_bundle.zip")

    try:
        # Capture Rich diagnostics into a StringIO buffer (no terminal needed)
        buf = io.StringIO()
        buf_console = Console(file=buf, force_terminal=False, width=100)
        run_diagnostics(buf_console)
        diagnostics_text = buf.getvalue()

        with open(report_txt_path, "w", encoding="utf-8") as f:
            f.write("=== UTIM SUPPORT REPORT ===\n")
            ts = os.path.getmtime(LOG_FILE) if os.path.exists(LOG_FILE) else "unknown"
            f.write(f"Timestamp: {ts}\n\n")

            f.write("=== DIAGNOSTICS ===\n")
            # Redact first, then ASCII-ify so redaction markers stay readable
            f.write(_to_ascii(redact_text(diagnostics_text)) + "\n\n")

            f.write("=== REDACTED DEBUG LOG ===\n")
            if os.path.exists(LOG_FILE):
                with open(LOG_FILE, "r", encoding="utf-8") as lf:
                    log_content = lf.read()
                f.write(_to_ascii(redact_text(log_content)))
            else:
                f.write("(no debug log found)\n")

        with zipfile.ZipFile(bundle_zip_path, "w", zipfile.ZIP_DEFLATED) as z:
            z.write(report_txt_path, "support_report.txt")

        try:
            os.remove(report_txt_path)
        except Exception:
            pass

        return bundle_zip_path
    except Exception as e:
        raise RuntimeError(f"Failed to create support bundle: {e}")
