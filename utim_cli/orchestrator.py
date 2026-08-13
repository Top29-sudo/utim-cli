"""
UTIM Orchestrator — Manages the full agentic loop.

Architecture:
  - Maintains local message history (system prompt + conversation)
  - For each user message, runs a ReAct loop:
      1. Calls LLM via the UTIM server (/completions, streaming) — keeps API key off client
      2. Content tokens are written to stdout in real-time as they arrive
      3. If the LLM returns tool_calls, executes them locally (filesystem tools)
      4. Feeds tool results back into the loop
      5. Repeats until the LLM responds with plain text (no more tool calls)
  - Falls back to calling OpenRouter directly if the server is unreachable
"""
from __future__ import annotations

import difflib
import json
import os
import re
import shutil
import subprocess
import sys
import threading
import time
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Any, Dict, List, Optional, Tuple

import requests
from utim_cli.constants import DEFAULT_MODEL
# openai SDK removed — we call OpenRouter directly via requests (no Rust/jiter needed)
from rich.console import Console
from rich.live import Live
from rich.markdown import Markdown
from rich.panel import Panel
from rich.rule import Rule
from rich.spinner import Spinner
from rich.text import Text

from .tools import get_tools
import utim_cli.tools as _tools_module   # for injecting cancel_event
from .config import config

# ─── Dynamic Context Budget ─────────────────────────────────────────────────
def _get_model_max_output(model_id: str, fallback: int = 128_000) -> int:
    """Return the model's real max completion tokens from the registry, or user config."""
    try:
        settings = config.get(f"model_settings_{model_id}")
        if settings and isinstance(settings, dict) and "max_tokens" in settings:
            return settings["max_tokens"]
        from utim_cli.server.models import get_max_output_tokens
        return get_max_output_tokens(model_id, fallback=fallback)
    except Exception:
        return fallback


def _extract_write_file_calls(content: str) -> list:
    """Parse large fenced code blocks from a plain-text model response and
    convert them into ``write_file`` tool-call dicts.

    This recovers content when a model outputs code as prose instead of calling
    the write_file tool, preventing expensive generations from being wasted.

    Only activates for code blocks ≥ 40 lines.  Filename is inferred from:
      1. Inline hint on the opening fence line  (e.g. ````html index.html``)
      2. The closest "filename.ext" pattern in the 3 lines *before* the block
      3. Language-to-extension mapping as a last resort

    Returns a list of OpenAI-style tool call dicts (may be empty).
    """
    import re, uuid

    # Map common fence languages to default filenames when no hint is found
    _LANG_DEFAULTS: dict = {
        "html": "index.html",
        "css": "style.css",
        "javascript": "script.js",
        "js": "script.js",
        "typescript": "index.ts",
        "ts": "index.ts",
        "python": "main.py",
        "py": "main.py",
        "json": "data.json",
        "yaml": "config.yaml",
        "yml": "config.yml",
        "bash": "script.sh",
        "sh": "script.sh",
        "sql": "query.sql",
        "go": "main.go",
        "rust": "main.rs",
        "cpp": "main.cpp",
        "c": "main.c",
        "java": "Main.java",
    }

    # Regex: captures opening fence (with optional language + filename hint),
    # the block content, and the closing fence.
    _FENCE_RE = re.compile(
        r"```(?P<lang>[a-zA-Z0-9_+-]*)[ \t]*(?P<hint>[^\n]*)\n"
        r"(?P<code>.*?)"
        r"```",
        re.DOTALL,
    )

    # Filename pattern (for scanning lines before the block)
    _FNAME_RE = re.compile(
        r"\b([\w./\\-]+\.(html|css|js|ts|jsx|tsx|py|json|yaml|yml|sh|bash|go|rs|cpp|c|java|sql|txt|md))\b",
        re.IGNORECASE,
    )

    tool_calls = []
    lines = content.split("\n")

    for m in _FENCE_RE.finditer(content):
        code_body = m.group("code")
        if code_body.count("\n") < 40:
            continue  # skip short snippets

        lang = m.group("lang").strip().lower()
        hint = m.group("hint").strip()

        # 1. Try filename from fence hint line
        fname = None
        if hint:
            fn_m = _FNAME_RE.search(hint)
            if fn_m:
                fname = fn_m.group(1)

        # 2. Scan the 3 lines before the opening fence
        if not fname:
            block_start_pos = m.start()
            pre_text = content[:block_start_pos]
            pre_lines = pre_text.rstrip().split("\n")[-3:]
            for pre_line in reversed(pre_lines):
                fn_m = _FNAME_RE.search(pre_line)
                if fn_m:
                    fname = fn_m.group(1)
                    break

        # 3. Fall back to language default
        if not fname:
            fname = _LANG_DEFAULTS.get(lang)

        if not fname:
            continue  # can't determine filename — skip

        call_id = f"auto_{uuid.uuid4().hex[:8]}"
        tool_calls.append({
            "id": call_id,
            "type": "function",
            "function": {
                "name": "write_file",
                "arguments": json.dumps({
                    "path": fname,
                    "content": code_body,
                    "overwrite": True,
                }),
            },
        })

    return tool_calls


def _get_compression_threshold(model_id: str, context_window: int) -> int:
    """Calculate dynamic compression threshold based on model's context window.
    
    Used for the send-message hard cap to prevent overflow.
    """
    if not context_window or context_window <= 0:
        context_window = 128_000
    return int(context_window * 0.90)


def _get_compression_interval(context_window: int = 0) -> int:
    """Return the iteration gap for model context compression (every 35 iterations)."""
    return 35


from utim_cli.config import get_utim_dir
_utim_dir_posix = get_utim_dir().as_posix()

# System Prompt
SYSTEM_PROMPT = f"""You are UTIM AI, a high-agency senior software engineer operating autonomously inside a CLI. You focus purely on the technical project or task at hand.

### CORE DIRECTIVES:
1. **Explore & Route**: A project architecture snapshot is injected below — use it immediately instead of calling list_directory. For localized tasks (single-file edits, styling): go straight to the file. For system-wide tasks: use the snapshot to plan without extra listings.
2. **Execute Immediately**: Do not wait for permissions. Invoke the right tool call NOW. No preamble, no announcing what you will do, no placeholder stubs.
3. **Architectural & Project Planning**: Proactively invoke `plan_project` (with `plan_part` set to 'design', 'architecture', 'security', 'database', 'testing', 'deployment', or 'features') for non-trivial tasks, new features, or architectural builds to establish expert specifications before implementing. Verify code changes with `run_command` (build/test).
4. **Manifesto Reference**: Safety and coding standards are in {_utim_dir_posix}/UTIM.md. Read only when specific guidance is needed.
5. **Output**: Concise, professional, warm. Summarize changes + test results at the end. Propose improvements only — don't fix unsolicited issues.
6. **Tool Calling**: Use native function-calling only. No raw JSON, no <think> tags, no tool markup in text.
7. **Premium Web Design**: Style UIs per `{_utim_dir_posix}/DESIGN.md` (HSL colors, glassmorphism, animations).
"""

# ─── Runtime environment detection ───────────────────────────────────────────

def _detect_environment() -> str:
    """Detect the runtime environment and return a context string for the prompt."""
    import platform, os

    is_termux   = os.path.isdir("/data/data/com.termux")
    is_wsl      = "microsoft" in platform.uname().release.lower()
    system      = platform.system()   # 'Linux', 'Windows', 'Darwin'
    machine     = platform.machine()  # 'x86_64', 'aarch64', etc.
    home        = os.path.expanduser("~")
    cwd         = os.getcwd()
    shell       = os.environ.get("SHELL", os.environ.get("COMSPEC", "unknown"))

    lines = ["\n\nRUNTIME ENVIRONMENT (auto-detected):"]
    lines.append(f"- OS: {system} ({machine})")
    lines.append(f"- Shell: {shell}")
    lines.append(f"- Home: {home}")
    lines.append(f"- Working directory: {cwd}")

    if is_termux:
        lines += [
            "- Platform: Android Termux",
            "- Package manager: pkg (use `pkg install <name>` not apt/brew/choco)",
            "- Home path: /data/data/com.termux/files/home",
            "- No sudo — Termux is already a user-level Linux environment",
            "- Node.js, Python, git, curl all available via `pkg install`",
            "- The user is on a MOBILE DEVICE (Android). Keep file paths short,",
            "  avoid opening browsers or GUIs, prefer terminal-based workflows.",
            "- Do NOT suggest desktop editors (VS Code, etc.) — use nano/vim instead.",
        ]
    elif is_wsl:
        lines += [
            "- Platform: Windows Subsystem for Linux (WSL)",
            "- Package manager: apt (sudo apt install <name>)",
            "- Windows drives mounted at /mnt/c, /mnt/d, etc.",
            "- Can run both Linux and Windows commands",
        ]
    elif system == "Windows":
        lines += [
            "- Platform: Windows (native PowerShell/CMD)",
            "- Package manager: winget, choco, or scoop",
            "- Use PowerShell syntax for shell commands",
            "- Use backslashes or raw strings for paths when needed",
            "- **CRITICAL**: '&&' and '||' are NOT valid in PowerShell. Use ';' to chain commands.",
            "  WRONG: npm test && npm run build",
            "  RIGHT: npm test ; npm run build",
        ]
    elif system == "Darwin":
        lines += [
            "- Platform: macOS",
            "- Package manager: brew (brew install <name>)",
        ]
    elif system == "Linux":
        lines += [
            "- Platform: Linux",
            "- Package manager: apt / dnf / pacman depending on distro",
        ]

    return "\n".join(lines)


# Build the prompt once at import time (environment is stable per process)
SYSTEM_PROMPT = SYSTEM_PROMPT + _detect_environment()

COMPRESSED_SYSTEM_PROMPT = f"""You are UTIM AI, a high-agency senior CLI software engineer.

### CORE DIRECTIVES:
1. **Explore & Route**: Project snapshot is injected — use it immediately. No redundant list_directory calls.
2. **Execute Immediately**: Invoke tool calls directly. No preamble, no announcing steps.
3. **Think-Create-Verify**: Call tools directly. Verify with run_command, not by re-reading files.
4. **Manifesto**: Safety and coding standards are in {_utim_dir_posix}/UTIM.md.
5. **Output**: Concise, professional, warm.
6. **Tool Calling**: Use native function-calling. No raw JSON, `<think>` tags, or raw tool markup.
7. **Premium Web Design**: Style UIs per `{_utim_dir_posix}/DESIGN.md` (HSL colors, glassmorphism, animations).
"""

def _detect_environment_compressed() -> str:
    """Detect the runtime environment and return a compressed context string."""
    import platform, os
    is_termux   = os.path.isdir("/data/data/com.termux")
    is_wsl      = "microsoft" in platform.uname().release.lower()
    system      = platform.system()
    shell       = os.environ.get("SHELL", os.environ.get("COMSPEC", "unknown"))
    cwd         = os.getcwd()

    lines = ["\n\nENV:"]
    lines.append(f"- OS: {system} | Shell: {shell} | CWD: {cwd}")
    if is_termux:
        lines.append("- Termux: pkg manager, user-level Linux, mobile device.")
    elif is_wsl:
        lines.append("- WSL: apt, Windows mount at /mnt/c.")
    elif system == "Windows":
        lines.append("- Windows (PowerShell/CMD). PowerShell syntax. CRITICAL: Use ';' instead of '&&'/'||'.")
    elif system == "Darwin":
        lines.append("- macOS: brew.")
    elif system == "Linux":
        lines.append("- Linux.")
    return "\n".join(lines)


# ─── Fast project architecture snapshot (injected once into system prompt) ────
_arch_snapshot_cache: dict = {"ts": 0.0, "text": ""}
_ARCH_SNAPSHOT_TTL = 30  # seconds — refresh on CWD change or after 30s


def _get_project_architecture_snapshot() -> str:
    """Return a clean, high-level file tree of the project.
    
    Generically walks top-level and nested directories using balanced, capped breadth-first
    traversal. Does NOT rely on hardcoded project-specific directory names.
    """
    import os, time
    global _arch_snapshot_cache

    now = time.time()
    cwd = os.getcwd()
    cache_key = cwd

    if (
        _arch_snapshot_cache.get("ts", 0) + _ARCH_SNAPSHOT_TTL > now
        and _arch_snapshot_cache.get("cwd") == cache_key
        and _arch_snapshot_cache.get("text")
    ):
        return _arch_snapshot_cache["text"]

    # Standard toolchain/system build noise only (universal, non-project-specific)
    _STANDARD_NOISE = {
        ".git", "node_modules", "__pycache__", ".venv", "venv", "env",
        ".next", ".nuxt", "dist", "build", ".turbo", ".utim_tmp",
        ".mypy_cache", ".pytest_cache", "coverage", ".tox",
    }
    _MEDIA_EXTS = {
        ".pyc", ".pyo", ".pyd", ".so", ".dll", ".exe",
        ".png", ".jpg", ".jpeg", ".gif", ".ico", ".svg",
        ".mp4", ".mp3", ".wav", ".zip", ".tar", ".gz",
        ".db", ".sqlite", ".sqlite3", ".log", ".mov",
    }

    lines: list[str] = [f"PROJECT FILE TREE ({os.path.basename(cwd) or cwd}):"]
    
    try:
        top_entries = sorted(os.scandir(cwd), key=lambda e: (not e.is_dir(), e.name.lower()))
    except Exception:
        top_entries = []

    # Max items per single directory listing to prevent bloat from large asset or test folders
    MAX_ITEMS_PER_DIR = 12

    for i, entry in enumerate(top_entries):
        name = entry.name
        if name.startswith(".") and name not in {".env", ".gitignore", ".editorconfig"}:
            continue
        ext = os.path.splitext(name)[1].lower()
        if not entry.is_dir() and ext in _MEDIA_EXTS:
            continue

        connector = "└── " if i == len(top_entries) - 1 else "├── "
        child_prefix = "    " if i == len(top_entries) - 1 else "│   "

        if entry.is_dir():
            if name in _STANDARD_NOISE:
                lines.append(f"{connector}{name}/ (skipped)")
                continue
            lines.append(f"{connector}{name}/")
            # Walk depth 1 inside top-level dir
            try:
                sub_entries = sorted(os.scandir(entry.path), key=lambda e: (not e.is_dir(), e.name.lower()))
                sub_filtered = [
                    e for e in sub_entries
                    if not (e.name.startswith(".") and e.name not in {".env"})
                    and not (not e.is_dir() and os.path.splitext(e.name)[1].lower() in _MEDIA_EXTS)
                ]
                
                count = 0
                for j, sub in enumerate(sub_filtered):
                    if count >= MAX_ITEMS_PER_DIR:
                        lines.append(f"{child_prefix}└── ... ({len(sub_filtered) - count} more items)")
                        break
                    sub_name = sub.name
                    sub_conn = "└── " if j == len(sub_filtered) - 1 or count == MAX_ITEMS_PER_DIR - 1 else "├── "
                    sub_child_pref = child_prefix + ("    " if sub_conn == "└── " else "│   ")

                    if sub.is_dir():
                        if sub_name in _STANDARD_NOISE:
                            lines.append(f"{child_prefix}{sub_conn}{sub_name}/ (skipped)")
                        else:
                            lines.append(f"{child_prefix}{sub_conn}{sub_name}/")
                            # Walk depth 2 inside nested dir
                            try:
                                deep_entries = sorted(os.scandir(sub.path), key=lambda e: (not e.is_dir(), e.name.lower()))
                                deep_filtered = [
                                    d for d in deep_entries
                                    if not d.name.startswith(".")
                                    and not (not d.is_dir() and os.path.splitext(d.name)[1].lower() in _MEDIA_EXTS)
                                ]
                                deep_count = 0
                                for k, deep in enumerate(deep_filtered):
                                    if deep_count >= 8:
                                        lines.append(f"{sub_child_pref}└── ... ({len(deep_filtered) - deep_count} more items)")
                                        break
                                    deep_name = deep.name
                                    deep_conn = "└── " if k == len(deep_filtered) - 1 or deep_count == 7 else "├── "
                                    if deep.is_dir():
                                        lines.append(f"{sub_child_pref}{deep_conn}{deep_name}/")
                                    else:
                                        lines.append(f"{sub_child_pref}{deep_conn}{deep_name}")
                                    deep_count += 1
                            except Exception:
                                pass
                    else:
                        lines.append(f"{child_prefix}{sub_conn}{sub_name}")
                    count += 1
            except Exception:
                pass
        else:
            lines.append(f"{connector}{name}")

    text = "\n".join(lines)
    _arch_snapshot_cache = {"ts": now, "cwd": cache_key, "text": text}
    return text


def is_casual_message(prompt: str) -> bool:
    if not prompt:
        return True
    p = prompt.strip().lower().rstrip("?.!")
    if not p:
        return True
    
    casual_words = {
        "hello", "hi", "hey", "yo", "sup", "hola", "greetings", "good morning", "good afternoon", "good evening",
        "how are you", "how's it going", "howdy", "hi there", "hello there", "test", "testing", "ping", "clear",
        "exit", "quit", "menu", "help", "restart", "reset", "ok", "okay", "yes", "no", "thanks", "thank you",
        "nice", "cool", "sure", "fine", "awesome", "perfect", "good", "great", "hello!", "hi!"
    }
    
    if p in casual_words:
        return True
        
    # If the message is very short (e.g. less than 15 chars) and doesn't contain code/paths/technical symbols
    if len(p) <= 15:
        # Heuristics: if it doesn't contain slashes, backslashes, dots, underscores, braces, or brackets
        import re
        if not re.search(r'[./_\\{}()\[\]=+\-*<>]', p):
            # Check if it has any common casual words as substrings
            for w in casual_words:
                if w in p:
                    return True
            # Otherwise, check if it's purely letters and spaces
            if re.match(r'^[a-z\s]+$', p):
                return True
                
    return False

def estimate_tokens(text: str) -> int:
    """Estimate token count based on typical ~4 chars per token ratio."""
    return len(text) // 4

def compress_experience(text: str) -> str:
    """Shorten common verbose patterns to compress experiences/lessons and conserve context window space."""
    t = text.strip()
    replacements = {
        "Windows PowerShell": "PowerShell",
        "the && operator is not supported": "no &&",
        "do not use '&&' as a statement separator because it is invalid and throws a ParserError. Instead, use a semicolon ';' to chain commands or run them separately.": "use ';' instead of '&&'",
        "do not use '&&' as a statement separator. Instead, use a semicolon ';' to chain commands.": "use ';' instead of '&&'",
        "do not use && as a statement separator. Instead, use a semicolon ;": "use ';' instead of '&&'",
        "Use a semicolon ; to separate commands instead": "use ';'",
        "Sequential tool workflow observed": "Workflow",
        "broad search → inspect result → identify noise/inconsistency": "search → inspect → target",
        "Always run pytest": "Run pytest",
        "before final commit": "before commit",
        "Todo tracking for bug fixes and feature implementation": "Track bugs/features in todos"
    }
    for old, new in replacements.items():
        t = t.replace(old, new)
    return t

_qwen_model = None
_qwen_tokenizer = None
_qwen_downloading = False

def _trigger_qwen_download_bg():
    """Trigger background download and caching of Qwen local model if not already loaded or downloading."""
    global _qwen_model, _qwen_tokenizer, _qwen_downloading
    # LITE MODE: never download/load the local Qwen model (torch + ~1GB RAM).
    # Falls back to the cloud API path (proxy_openrouter_request) instead.
    if os.environ.get("UTIM_LITE_MODE", "0") in ("1", "true", "TRUE", "yes"):
        return
    if _qwen_model is None and not _qwen_downloading:
        import sys
        if "pytest" in sys.modules:
            return
        
        _qwen_downloading = True
        import threading
        
        def download_model_bg():
            global _qwen_model, _qwen_tokenizer, _qwen_downloading
            try:
                import torch
                from transformers import AutoModelForCausalLM, AutoTokenizer
                model_id = "Qwen/Qwen2.5-0.5B-Instruct"
                tok = AutoTokenizer.from_pretrained(model_id, trust_remote_code=True, local_files_only=False)
                mod = AutoModelForCausalLM.from_pretrained(
                    model_id,
                    torch_dtype=torch.float16 if torch.cuda.is_available() else torch.float32,
                    device_map="auto",
                    trust_remote_code=True,
                    local_files_only=False
                )
                _qwen_tokenizer = tok
                _qwen_model = mod
            except Exception:
                pass
            finally:
                _qwen_downloading = False
                
        t = threading.Thread(target=download_model_bg, daemon=True)
        t.start()

def summarize_experiences_with_model(experiences: list[dict], existing_cache: str = "") -> str:
    """Consolidate list of experiences into a clean list of rules deterministically without LLM calls."""
    if not experiences:
        return existing_cache
        
    seen = set()
    rules = []
    
    if existing_cache:
        for line in existing_cache.splitlines():
            line_str = line.strip()
            if line_str and line_str not in seen:
                seen.add(line_str)
                rules.append(line_str)

    for e in experiences:
        c = str(e.get("content", "")).strip().replace("\n", " ")
        if not c:
            continue
        
        c_lower = c.lower()
        if any(kw in c_lower for kw in ["powershell", "cmd", "bash", "terminal", "command", "shell"]):
            tag = "[SHELL_CONVENTION]"
        elif any(kw in c_lower for kw in ["style", "format", "import", "type", "indent"]):
            tag = "[CODING_STYLE]"
        elif any(kw in c_lower for kw in ["error", "bug", "fail", "fix", "exception", "traceback"]):
            tag = "[BUG_FIX]"
        elif any(kw in c_lower for kw in ["like", "prefer", "dislike", "user"]):
            tag = "[USER_PREF]"
        else:
            tag = "[GENERAL_RULE]"

        rule_entry = f"- {tag} {c}"
        if rule_entry not in seen:
            seen.add(rule_entry)
            rules.append(rule_entry)

    return "\n".join(rules)

def update_experience_summary_cache(user_prompt: str, messages: Optional[List[Dict]] = None) -> str:
    """Fetch relevant experiences using Qwen-expanded sub-queries + MiniLM re-ranking,
    summarize them using an LLM reflection model, and cache the result.
    Cache is invalidated whenever the active task changes (prompt hash check).
    """
    if not user_prompt:
        return ""
        
    try:
        import os
        import hashlib
        from utim_cli.vector_memory import fetch_relevant_experiences
        from utim_cli.situational_scoring import score_and_filter_context
        
        os.makedirs(".utim_tmp", exist_ok=True)
        cache_path   = ".utim_tmp/summarized_experiences_cache.txt"
        dirty_path   = ".utim_tmp/experience_cache_dirty.txt"
        task_hash_path = ".utim_tmp/experience_cache_task_hash.txt"
        
        active_task = _get_active_task(user_prompt, messages=messages)
        # Hash the active task to detect prompt changes
        current_task_hash = hashlib.sha256(active_task.encode("utf-8")).hexdigest()[:16]
        
        existing_cache = ""
        if os.path.exists(cache_path):
            try:
                with open(cache_path, "r", encoding="utf-8") as f:
                    existing_cache = f.read().strip()
            except Exception:
                pass
        
        # Read the last cached task hash
        last_task_hash = ""
        if os.path.exists(task_hash_path):
            try:
                with open(task_hash_path, "r", encoding="utf-8") as f:
                    last_task_hash = f.read().strip()
            except Exception:
                pass
        
        # Invalidate cache if: marked dirty OR task has changed since last cache build
        task_changed = current_task_hash != last_task_hash
        if existing_cache and not os.path.exists(dirty_path) and not task_changed:
            return existing_cache
        
        # ── Stage 1: Seed query — fetch top-k memories directly relevant to the task ──
        task_exps = fetch_relevant_experiences(active_task, top_k=15)
        
        # ── Stage 2: Qwen sub-query expansion (brain.py pipeline) ─────────────────────
        # Ask Qwen to decompose the active task into specific sub-queries so we
        # retrieve more precise memories instead of generic static strings.
        expanded_queries: list[str] = []
        try:
            from utim_cli.brain import _call_qwen_brain
            preview = "\n".join(
                f"- {str(e.get('content', ''))[:120]}"
                for e in task_exps[:5]
            )
            sub_query_prompt = (
                f"The user's active task is: \"{active_task[:300]}\"\n\n"
                f"Top retrieved experiences so far:\n{preview}\n\n"
                "Generate 3-4 SPECIFIC sub-queries (as a JSON array of strings) to retrieve "
                "MORE precise and RELEVANT experiences from memory for this exact task. "
                "Focus on: user style preferences, known corrections, task-specific conventions, "
                "and past failures related to THIS domain only.\n"
                "Return ONLY a JSON array like: [\"sub-query 1\", \"sub-query 2\"]"
            )
            import re as _re, json as _json
            qwen_resp = _call_qwen_brain(
                sub_query_prompt,
                system="You are a memory retrieval optimizer. Return ONLY a JSON array of query strings.",
                max_tokens=250,
            )
            if qwen_resp:
                match = _re.search(r'\[.*?\]', qwen_resp, _re.DOTALL)
                if match:
                    expanded_queries = _json.loads(match.group())[:4]
        except Exception:
            pass
        
        # ── Stage 3: Fetch memories for each Qwen-generated sub-query ─────────────────
        # Always include user preferences as a stable sub-query (it's domain-agnostic
        # and small enough not to pollute the results)
        stable_queries = [
            "user preferences communication style tone formatting language",
        ]
        all_exps = list(task_exps)
        for q in (expanded_queries + stable_queries):
            exps = fetch_relevant_experiences(q, top_k=6)
            all_exps.extend(exps)
        
        # ── Stage 4: Deduplicate ───────────────────────────────────────────────────────
        seen_content = set()
        unique_exps = []
        for e in all_exps:
            c = str(e.get("content", "")).strip()
            if c and c not in seen_content:
                metadata = e.get("metadata") or {}
                category = metadata.get("category")
                if category == "task_experience" or c.startswith("Task:"):
                    continue
                seen_content.add(c)
                unique_exps.append(e)
        
        # ── Stage 5: Situational re-scoring + raised relevance threshold ──────────────
        # 0.62 threshold (was 0.45) prevents domain-mismatched lessons from slipping in.
        # user_correction items are now also subject to the threshold (handled in
        # score_and_filter_context) — the unconditional +2.0 source bonus has been
        # adjusted in situational_scoring.py to be concept-gated.
        scored_exps = score_and_filter_context(unique_exps, active_task, limit=len(unique_exps))
        # Apply 0.62 relevance floor — but always keep user corrections regardless of score
        # (score_and_filter_context already gates corrections via concept-overlap boost,
        # so we trust its judgment here rather than double-cutting with a hard floor).
        def _is_correction(e):
            meta = e.get("metadata") or {}
            return (
                meta.get("source") == "user_correction"
                or meta.get("category") in ("knowledge_correction", "failure_correction")
                or "correction" in str(meta.get("category", ""))
            )
        scored_exps = [e for e in scored_exps if e.get("situational_score", 1.0) >= 0.62 or _is_correction(e)]
        
        # ── Stage 6: Summarize with model ─────────────────────────────────────────────
        # Only merge with the existing cache when the task has NOT changed.
        # When the active task changed, start fresh so lessons from unrelated
        # past tasks don't leak into the current task's context. (Within the
        # same task, merging is fine — it accumulates that task's own lessons.)
        merge_cache = existing_cache if not task_changed else ""
        summary = summarize_experiences_with_model(scored_exps, existing_cache=merge_cache)
        
        # ── Stage 7: Write cache + task hash ──────────────────────────────────────────
        with open(cache_path, "w", encoding="utf-8") as f:
            f.write(summary)
        with open(task_hash_path, "w", encoding="utf-8") as f:
            f.write(current_task_hash)
            
        # Clear the dirty flag
        if os.path.exists(dirty_path):
            try:
                os.remove(dirty_path)
            except Exception:
                pass
                
        return summary
    except Exception as e:
        from utim_cli.logger import log_error
        log_error("orchestrator", "Failed to update experience summary cache", e)
        return ""

# Cache keyed by hash of last-6-messages content. Qwen runs once per distinct
# conversation state, then subsequent calls (line 936, 985, 1051 in get_system_prompt)
# all return instantly without hitting the network.
_active_task_cache: dict = {}  # {msg_hash: active_task_str}

def _get_active_task(
    user_prompt: str,
    messages: Optional[List[Dict]] = None,
) -> str:
    """
    Derive the active task from the full conversation history.

    Strategy:
    1. Hash the last 6 message contents → check module-level cache.
       If hit: return immediately (no network call).
    2. If miss and >= 3 turns: ask Qwen to summarize the ongoing task in
       one sentence. Cache and return the result.
    3. Fallback to latest user prompt.

    The cache means the 3 call sites inside get_system_prompt (called every
    model request iteration) only pay the Qwen cost ONCE per distinct message
    state, not once per call site per iteration.
    """
    import hashlib
    latest = (user_prompt or "").strip()

    # Build cache key from last 6 messages
    relevant = []
    if messages:
        relevant = [
            m for m in messages
            if m.get("role") in ("user", "assistant")
        ][-6:]

    if not relevant or len(relevant) < 2:
        return latest

    # Fast cache key — hash of message contents
    key_src = "||".join(
        str(m.get("content", ""))[:200] for m in relevant
    )
    cache_key = hashlib.sha256(key_src.encode("utf-8")).hexdigest()[:16]

    if cache_key in _active_task_cache:
        return _active_task_cache[cache_key]

    # Cache miss — call Qwen once
    try:
        transcript_lines = []
        for m in relevant:
            role    = m.get("role", "")
            content = m.get("content") or ""
            if isinstance(content, list):
                content = " ".join(
                    p.get("text", "") for p in content
                    if isinstance(p, dict) and p.get("type") == "text"
                )
            transcript_lines.append(f"{role.upper()}: {content[:300]}")

        transcript = "\n".join(transcript_lines)

        from utim_cli.brain import _call_qwen_brain
        summary = _call_qwen_brain(
            f"Conversation so far:\n{transcript}\n\n"
            "In ONE sentence, what is the user's current ongoing task or goal? "
            "Focus on the specific thing they are working on, not just the last message.",
            system="You are a task summarizer. Reply with exactly one concise sentence.",
            max_tokens=80,
        )
        if summary and len(summary.strip()) > 10:
            result = summary.strip()
            _active_task_cache[cache_key] = result
            # Evict old entries — keep at most 20 cached states
            if len(_active_task_cache) > 20:
                oldest_key = next(iter(_active_task_cache))
                del _active_task_cache[oldest_key]
            return result
    except Exception:
        pass

    _active_task_cache[cache_key] = latest
    return latest

def _get_dynamic_directives(is_compressed: bool, messages: Optional[List[Dict]] = None) -> str:
    from pathlib import Path
    from utim_cli.config import get_utim_dir
    _posix = get_utim_dir().as_posix()

    from utim_cli.config import config
    disabled = config.get("disabled_tools") or []
    if not isinstance(disabled, list):
        disabled = []

    try:
        from utim_cli.tools import get_tools as _gt
        _all_real = [t["function"]["name"] for t in _gt()[0]]
    except Exception:
        _all_real = ["edit_file", "write_file", "run_command", "read_file", "list_directory", "grep_search"]

    enabled_tools = [t for t in _all_real if t not in disabled]
    if not enabled_tools:
        return "### TOOL STATUS: ALL TOOLS DISABLED\nAll tools are disabled. You may only respond in text."

    if is_compressed:
        # Short, token-efficient directives for steady-state turns. The full
        # version is only injected on iteration 0 (first turn).
        directives = [
            "### CORE DIRECTIVES:",
            "1. **Targeted Search**: Use `grep_search` for symbols/errors; `read_file` with symbol_name or line ranges — no un-sliced large reads.",
            "2. **Images**: If the prompt includes an image path (.png/.jpg/.jpeg), `read_file` it immediately on Turn 1 with that exact path.",
            "3. **Planning**: Invoke `plan_project` for non-trivial tasks/new features/refactors before implementing.",
            "4. **Think-Create-Verify**: Execute tools directly (no preamble). Verify edits with `run_command` (build/test).",
            "5. **Output**: Native function-calling only — no raw JSON, <think> tags, or tool markup in text. Finish with a concise summary.",
        ]
    else:
        directives = [
            "### CORE DIRECTIVES:",
            "1. **Targeted Search**: Use `grep_search` to locate exact symbol definitions, imports, or error text across codebase files.",
            "2. **Scoped File Reading**: Use `read_file` with `symbol_name` or line ranges (`start_line`/`end_line`) to inspect target function/class definitions. Avoid reading un-sliced large files.",
            "3. **Images & Screenshots**: If the prompt includes an image or screenshot path (.png, .jpg, .jpeg, etc.), execute `read_file` immediately on Turn 1 with that exact path. Absolute file paths anywhere on the system are valid — do not question file locations.",
            "4. **Project & Feature Planning**: Proactively invoke `plan_project` (with `plan_part` set to 'design', 'architecture', 'security', 'database', 'testing', 'deployment', or 'features') for non-trivial tasks, new features, system refactors, or new application builds before implementing.",
            "5. **Think-Create-Verify**: Execute tools directly without conversational preambles or text planning. Verify edits with `run_command` (compile/build/test).",
            "6. **Execution**: Invoke native function-calling schemas directly. Never output raw JSON, <think> tags, or conversational text before tool calls.",
            "7. **Output & Summary**: Be concise, professional, and clear. Upon finishing, provide a comprehensive summary of completion.",
        ]
    # NOTE: 'Iteration Budget' directive intentionally removed.
    # Iteration limits are now enforced dynamically (window-aware) at runtime
    # via milestone warnings, not hardcoded into the system prompt.

    return "\n".join(directives)

def _lesson_relevant_to_task(lesson_line: str, active_task: str) -> bool:
    """Semantic relevance gate for a cached lesson line against the active task.

    Uses lightweight concept-overlap (no network/embedding call) so it's cheap and
    deterministic. A lesson is kept only if it shares meaningful concepts with the
    active task OR is a user-preference (which is intentionally domain-agnostic).
    """
    if not lesson_line or not active_task:
        return True
    try:
        from utim_cli.situational_scoring import extract_concepts, concept_overlap_score

        # Strip the leading tag marker (e.g. "[USER_PREF]") before concept extraction
        body = lesson_line
        for tag in ("[SHELL_CONVENTION]", "[CODING_STYLE]", "[BUG_FIX]", "[USER_PREF]", "[GENERAL_RULE]"):
            if tag in body:
                body = body.replace(tag, " ")
        body = body.strip().lstrip("-").strip()

        task_concepts = extract_concepts(active_task)
        lesson_concepts = extract_concepts(body)
        if not task_concepts or not lesson_concepts:
            return True

        overlap = concept_overlap_score(task_concepts, lesson_concepts)

        # User preferences are intentionally domain-agnostic — always keep them
        # so the model remembers the user's communication/tone/formatting style.
        if "[USER_PREF]" in lesson_line:
            return True

        # Generic rules with no specific domain vocabulary are low-risk; keep them
        # only if they share at least one concept with the task.
        if "[GENERAL_RULE]" in lesson_line:
            return overlap > 0.0

        # Domain-tagged lessons (shell/coding/bug) must share real concepts with
        # the active task to be injected.
        return overlap >= 0.12
    except Exception:
        # On any failure, be permissive (don't drop lessons due to a bug here)
        return True


def get_system_prompt(user_prompt: str = "", current_iteration: int = 0, elapsed_seconds: int = 0, turn_history: Optional[List[Dict]] = None, messages: Optional[List[Dict]] = None) -> str:
    """Gets the dynamic system prompt with active MCP servers and semantically fetched Hugging Face vector memories."""
    # If the user prompt is just a casual greeting/message, return a minimal prompt to save tokens
    if user_prompt and is_casual_message(user_prompt):
        return "You are UTIM AI. Respond warmly and concisely in under 2 sentences without repeating long introductory lists of your roles or capabilities."

    # 1. Determine base system prompt and experience token limit based on iteration count
    if current_iteration == 0:
        identity = "You are UTIM AI, a high-agency senior software engineer operating autonomously inside a CLI. You focus purely on the technical project or task at hand.\n\n"
        arch_snapshot = _get_project_architecture_snapshot()
        arch_block = f"\n\n### LOCAL PROJECT FILE TREE ###\n```\n{arch_snapshot}\n```\n"
        base_prompt = identity + _get_dynamic_directives(is_compressed=False, messages=messages) + _detect_environment() + arch_block
        exp_token_limit = 1000
        is_first = True
    else:
        identity = "You are UTIM AI, a high-agency senior CLI software engineer.\n\n"
        base_prompt = identity + _get_dynamic_directives(is_compressed=True, messages=messages) + _detect_environment_compressed()
        exp_token_limit = 2000
        is_first = False

    mcp_prompt = ""
    try:
        from utim_cli.config import config as _cfg
        _all_disabled = _cfg.get("disabled_tools") or []
        if not isinstance(_all_disabled, list):
            _all_disabled = []
        from utim_cli.tools import get_tools as _get_tools
        _all_tool_names = [t["function"]["name"] for t in _get_tools()[0]]
        _tools_all_off = bool(_all_tool_names) and all(t in _all_disabled for t in _all_tool_names)
        if not _tools_all_off:
            from utim_cli.mcp_client import mcp_manager
            mcp_context = mcp_manager.get_notification_context()
            if mcp_context:
                mcp_prompt += f"\n\n### MCP SERVERS AND TOOLS NOTIFICATION ###\n{mcp_context}\n"
    except Exception:
        pass

    exp_prompt = ""
    try:
        import os
        cache_path = ".utim_tmp/summarized_experiences_cache.txt"
        cached_summary = ""
        if os.path.exists(cache_path):
            with open(cache_path, "r", encoding="utf-8") as f:
                cached_summary = f.read().strip()
                
        # Synchronously generate if cache is missing
        if not cached_summary and user_prompt:
            cached_summary = update_experience_summary_cache(user_prompt, messages=messages)
            
        if cached_summary:
            # 1. Feature 2: Adaptive Token Budgeting
            active_task = _get_active_task(user_prompt, messages=messages) if user_prompt else ""
            from utim_cli.situational_scoring import classify_task_type
            task_type = classify_task_type(active_task)
            
            # Decide budget
            is_simple = task_type in ["general", "search"] or (user_prompt and is_casual_message(user_prompt))
            token_budget = 400 if is_simple else 2000
            char_budget = token_budget * 4
            
            # 2. Feature 3: Dynamic "Just-in-Time" Segment Injection
            active_tags = {"[USER_PREF]", "[GENERAL_RULE]"}
            
            # Let's inspect active/enabled tools
            from utim_cli.config import config as _cfg
            _disabled = _cfg.get("disabled_tools") or []
            if not isinstance(_disabled, list):
                _disabled = []
            has_run_command = "run_command" not in _disabled
            has_plan_project = "plan_project" not in _disabled
            
            # classify_task_type already uses embedding cosine similarity to determine
            # task domain — trust it directly instead of re-checking with keywords.
            _CODING_TASK_TYPES = {"setup", "testing", "file_edit", "refactoring", "debugging", "search", "ui_design"}
            _is_coding_task = task_type in _CODING_TASK_TYPES

            if _is_coding_task and has_run_command:
                active_tags.add("[SHELL_CONVENTION]")
            if _is_coding_task and has_plan_project:
                active_tags.add("[CODING_STYLE]")
                active_tags.add("[BUG_FIX]")

            # Filter cache by active tags
            lines = cached_summary.splitlines()
            filtered_lines = []
            current_len = 0
            for line in lines:
                has_any_tag = any(t in line for t in ["[SHELL_CONVENTION]", "[CODING_STYLE]", "[BUG_FIX]", "[USER_PREF]", "[GENERAL_RULE]"])
                # If it matches active tags or doesn't have a tag, keep it
                if not has_any_tag or any(tag in line for tag in active_tags):
                    # Semantic relevance gate: drop lessons that are unrelated to
                    # the SPECIFIC active task, not just the broad tag category.
                    # This prevents lessons from unrelated past tasks (which share
                    # a coarse tag like [USER_PREF] or [GENERAL_RULE]) from leaking
                    # into the current task's context based on the whole cache.
                    if active_task and not _lesson_relevant_to_task(line, active_task):
                        continue
                    # Check adaptive budget
                    if current_len + len(line) + 1 <= char_budget:
                        filtered_lines.append(line)
                        current_len += len(line) + 1
                    else:
                        break
                        
            cached_summary = "\n".join(filtered_lines).strip()
            if cached_summary:
                exp_prompt = f"\n\n[RELEVANT LESSONS]:\n{cached_summary}\n"
        
        # Query relationship-based Experience Memory using the ExperienceManager
        try:
            from utim_cli.reflection import experience_manager, extract_context_from_interaction
            from utim_cli.state import STATE
            active_task = _get_active_task(user_prompt, messages=messages)
            ctx = extract_context_from_interaction(active_task, "")
            
            # 1. Check for relevant unverified experiences that need confirmation
            unverified_nodes = []
            if ctx.get("objects"):
                for node in experience_manager.experience_nodes.values():
                    if getattr(node, "status", "verified") == "unverified" and getattr(node, "clarifying_question", None):
                        # If the node shares objects/concepts with the current task context
                        if any(obj in ctx["objects"] for obj in node.objects):
                            unverified_nodes.append(node)
                            
            if unverified_nodes:
                # Select only the first one to avoid asking multiple questions at once
                node_to_verify = unverified_nodes[0]
                question = node_to_verify.clarifying_question
                
                # Store the asked question details in STATE so the next user turn evaluates the answer
                STATE["asked_clarifying_question"] = {
                    "pattern_id": node_to_verify.pattern_id,
                    "question": question
                }
                
                question_prompt = (
                    f"\n\n[CONFIRMATION QUESTION REQUIRED]:\n"
                    f"You must ask the user this brief question in your response to verify an assumption: "
                    f"\"{question}\"\n"
                    f"Integrate this question naturally and politely into your reply. Do not mention system rules or prompts.\n"
                )
                exp_prompt = question_prompt + exp_prompt

            # 2. Query standard/verified relationship-based experiences
            if ctx.get("objects"):
                analysis = experience_manager.analyze_pattern(ctx["objects"], ctx.get("relationships", {}))
                # Only show verified experiences or high confidence ones
                if analysis and analysis.get("confidence", 0.0) > 0.4:
                    primary_id = analysis.get("primary_pattern_id")
                    is_verified = True
                    if primary_id and primary_id in experience_manager.experience_nodes:
                        is_verified = getattr(experience_manager.experience_nodes[primary_id], "status", "verified") == "verified"
                        
                    if is_verified:
                        insights = []
                        if analysis.get("interpretation"):
                            insights.append(f"Interpretation: {analysis['interpretation']}")
                        if analysis.get("suggestions"):
                            for s in analysis["suggestions"]:
                                insights.append(f"Suggestion: {s}")
                        if analysis.get("emergent_insights"):
                            for ei in analysis["emergent_insights"]:
                                insights.append(f"Emergent Insight: {ei}")
                        
                        if insights:
                            relationship_prompt = "\n\n[RELATIONSHIP EXPERIENCE INSIGHTS]:\n" + "\n".join(f"- {ins}" for ins in insights) + "\n"
                            exp_prompt = relationship_prompt + exp_prompt
        except Exception:
            pass
    except Exception:
        pass

    # 4. Situational Active Skills Scoring & Injection
    skills_prompt = ""
    try:
        from utim_cli.bootstrap import scan_available_skills
        skills = scan_available_skills()
        if skills:
            active_task = _get_active_task(user_prompt, messages=messages) if user_prompt else ""
            active_task_lower = active_task.lower()
            
            relevant_skills = []
            for skill_name, skill_info in skills.items():
                matched = False
                # Check keywords matching
                if any(kw in active_task_lower for kw in skill_info["keywords"]):
                    matched = True
                if not matched:
                    # Fallback check on name
                    if skill_name.replace("-", " ") in active_task_lower or skill_name in active_task_lower:
                        matched = True
                if matched:
                    relevant_skills.append(skill_name)
                    
            # Filter out already read/seen skills
            unread_skills = []
            for skill in relevant_skills:
                already_read = False
                if messages:
                    for m in messages:
                        # Check assistant's tool call to view_file for this skill
                        if m.get("role") == "assistant" and m.get("tool_calls"):
                            for tc in m.get("tool_calls", []):
                                if tc.get("function", {}).get("name") == "view_file":
                                    args = tc.get("function", {}).get("arguments", "")
                                    if isinstance(args, str):
                                        try:
                                            args_dict = json.loads(args)
                                        except:
                                            args_dict = {}
                                    else:
                                        args_dict = args or {}
                                    path = args_dict.get("AbsolutePath", "")
                                    if skill in path.replace("\\", "/"):
                                        already_read = True
                                        break
                        # Check if message content contains compressed skill header
                        if m.get("role") == "tool" and m.get("name") == "view_file":
                            content = str(m.get("content", ""))
                            if f"RELEVANT CORE SKILL: {skill.upper()}" in content:
                                already_read = True
                                break
                        if already_read:
                            break
                if not already_read:
                    unread_skills.append(skill)
                    
            unread_skills = unread_skills[:2]  # Cap at max 2 relevant skills to prevent context bloat
            if unread_skills:
                try:
                    from utim_cli.config import config as _scfg
                    _sdisabled = _scfg.get("disabled_tools") or []
                    _read_file_disabled = isinstance(_sdisabled, list) and "read_file" in _sdisabled
                except Exception:
                    _read_file_disabled = False
                if not _read_file_disabled:
                    lines = []
                    for name in unread_skills:
                        skill_md_path = skills[name]["path"]
                        skill_md_url = str(skill_md_path.absolute()).replace('\\', '/')
                        lines.append(f"- {skills[name]['name']}: [SKILL.md](file:///{skill_md_url})")
                    skills_prompt = (
                        "\n\n### RECOMMENDED SKILLS ###\n"
                        + "\n".join(lines) + "\n"
                    )
    except Exception:
        pass

    # ── 5. Inject Structured Session Summary Memory ──
    session_summary = ""
    import os
    from utim_cli.config import get_utim_dir
    summary_path = get_utim_dir() / "session_summary.md"
    if os.path.exists(summary_path):
        try:
            with open(summary_path, "r", encoding="utf-8") as sf:
                raw_summary = sf.read().strip()
                # Take only the last 3 lines to prevent checklist bloat
                session_summary = "\n".join(raw_summary.splitlines()[-3:])
        except Exception:
            pass
            
    if not session_summary and turn_history:
        # Generate a LEAN summary: only last 8 turns, one-line per request + changed files
        recent_turns = turn_history[-8:]
        summary_lines = []
        for idx, t in enumerate(recent_turns):
            req = t.get("user_msg", "").strip().split("\n")[0][:80]
            changes = t.get("changes", [])
            changed_names = list({os.path.basename(c.get("file_path", "") or c.get("path", "")) for c in changes if c.get("file_path") or c.get("path")})
            files_str = ", ".join(f"`{n}`" for n in changed_names[:5]) if changed_names else "—"
            summary_lines.append(f"- Turn {idx+1}: {req} → {files_str}")
        session_summary = "\n".join(summary_lines)

    session_prompt = ""
    if session_summary:
        session_prompt = f"\n\n### SESSION HISTORY ###\n{session_summary}\n"
    # ── 6. Inject Live User Hint Directives (System Prompt Override) ──
    hint_prompt = ""
    try:
        from utim_cli.state import STATE
        pending_hints = []
        if STATE.get("hint"):
            pending_hints.append(STATE.get("hint"))
        if STATE.get("hint_messages") and isinstance(STATE["hint_messages"], list):
            for hm in STATE["hint_messages"]:
                if hm and hm not in pending_hints:
                    pending_hints.append(hm)
                    
        if pending_hints:
            hint_lines = [f"- \"{h.strip()}\"" for h in pending_hints if h and h.strip()]
            if hint_lines:
                hint_prompt = (
                    "\n\n### USER LIVE HINT DIRECTIVE (HIGH-PRIORITY IMMEDIATE OVERRIDE) ###\n"
                    "The user has provided the following live guidance/directive for your execution:\n"
                    + "\n".join(hint_lines) + "\n"
                    "You MUST strictly follow and incorporate these live user hint(s) into your immediate reasoning, tool selection, and output generation for this request.\n"
                )
            # Clear pending hints once consumed into system prompt for the next request
            STATE["hint"] = None
            STATE["hint_messages"] = []
    except Exception:
        pass

    # ── 7. Brain Memory Context (two-stage RAG: MiniLM + Qwen) ──
    brain_prompt = ""
    try:
        from utim_cli.brain import get_brain_context_prompt
        brain_prompt = get_brain_context_prompt(user_prompt)
    except Exception:
        pass

    return base_prompt + mcp_prompt + exp_prompt + skills_prompt + session_prompt + brain_prompt + hint_prompt

# ── Context management settings ───────────────────────────────────────────────
KEEP_FULL_TURNS = 10      # last N turns (including current) kept with full fidelity
TOKEN_BUDGET    = 90_000  # hard token cap for messages sent to the LLM per call


# Tool display metadata
# Color constants for consolidated 3-color palette
PURPLE = "#cba6f7"
BLUE = "#42bcf5"
YELLOW = "#f9e2af"

# Accent colour per tool (subtle, no bold labels)
TOOL_COLOR: Dict[str, str] = {
    "read_file":             BLUE,
    "write_file":            YELLOW,
    "edit_file":             YELLOW,
    "move_file":             BLUE,
    "delete_file":           PURPLE,
    "run_command":           YELLOW,
    "list_directory":        PURPLE,
    "get_background_output": BLUE,
    "send_background_input": YELLOW,
    "stop_background_process": PURPLE,
    "list_background_processes": BLUE,
    "web_search":            YELLOW,
    "manage_todos":            PURPLE,
    "generate_image":          YELLOW,
}


class _ServerUnavailableError(RuntimeError):
    """Raised when the UTIM server cannot be reached and no local key is configured.
    Caught in run_task to display a clean user-facing message (no traceback).
    """


class _FatalClientError(RuntimeError):
    """Raised when a non-retryable gating or credit validation error occurs.
    Caught in run_task to immediately abort the turn without retry.
    """


class Orchestrator:
    """Runs the full ReAct agentic loop, proxying LLM calls through the UTIM server."""

    def __init__(self, console: Console):
        self.console = console
        # Start MCP Manager
        try:
            from utim_cli.mcp_client import mcp_manager
            mcp_manager.start()
        except Exception:
            pass
        self.server_url = "https://api.utim.dev"
        self.session_id: Optional[str] = None
        # Primary model — load from config or fall back to DEFAULT_MODEL
        saved_main_model = config.get("main_model") or config.get("model")
        self.model_id: str = saved_main_model if saved_main_model else DEFAULT_MODEL
        self._current_line_len = 0
        self.tool_results: List[Dict[str, Any]] = []
        self.turn_step_timings: List[Dict[str, Any]] = []
        self.session_hints: List[str] = []
        
        # Track session start for elapsed time awareness
        self._session_start_time: float = time.time()
        

        
        # Dynamic compression threshold and interval based on model's context window
        self._compression_threshold = self._get_dynamic_threshold()
        self._compression_interval = self._get_dynamic_interval()

        # Local conversation history — the single source of truth for this session.
        # Commands like /clear, /resume operate on this list directly.
        self.messages: List[Dict[str, Any]] = [
            {"role": "system", "content": get_system_prompt()}
        ]

        # ── API key / .env loading ────────────────────────────────────────────
        # Priority (highest to lowest):
        #   1. Shell environment variable already set by the user
        #   2. .env file in the CURRENT WORKING DIRECTORY  (folder-local key)
        #   3. .utim/.env  (global fallback written by /auth)
        #
        # IMPORTANT: We load the CWD .env with override=True so that a
        # project-local key always beats any key inherited from a previous
        # utim installation in a different folder (which was the root cause of
        # "Server unavailable" errors when running `utim` from random folders).
        # We also load it by EXPLICIT absolute path — not by letting dotenv
        # walk up the directory tree — so there is no ambiguity about which
        # file wins.
        _cwd_env = os.path.join(os.getcwd(), ".env")
        try:
            from dotenv import load_dotenv as _load_dotenv
            if os.path.isfile(_cwd_env):
                _load_dotenv(_cwd_env, override=True)
            else:
                # No local .env — still call load_dotenv so it picks up any
                # shell-level exports, but do NOT override them.
                _load_dotenv(override=False)
        except Exception:
            pass

        # Load user-saved API key from global ~/.utim/.env (written by the setup wizard / /auth)
        import pathlib
        _user_env = pathlib.Path.home() / ".utim" / ".env"
        if _user_env.exists():
            try:
                from dotenv import load_dotenv as _load_dotenv
                _load_dotenv(_user_env, override=False)  # override=False: env vars win
            except Exception:
                pass

        # Legacy fallback: also check cwd-relative .utim/.env (pre-global-install
        # folders) so old installs keep working, but global ~/.utim always wins.
        _legacy_env = pathlib.Path(".utim").resolve() / ".env"
        if _legacy_env.exists():
            try:
                from dotenv import load_dotenv as _load_dotenv
                _load_dotenv(_legacy_env, override=False)  # override=False: env vars win
            except Exception:
                pass

        # User identity from config (can be removed later)
        self.email = config.email or os.getenv("UTIM_EMAIL", "local@utim.dev")
        self.token = config.token

        # Local API key used for OpenRouter / Direct LLM access.
        # Read AFTER all .env files have been loaded so the correct key wins.
        self._local_api_key: Optional[str] = (
            os.getenv("OPENROUTER_API_KEY") or
            os.getenv("OPENAI_API_KEY") or
            os.getenv("ANTHROPIC_API_KEY") or
            os.getenv("UTIM_API_KEY") or
            config.get("api_key")
        )
        is_headless = os.getenv("UTIM_HEADLESS") == "1" or os.getenv("HEADLESS") == "1" or not sys.stdin.isatty()
        if not self._local_api_key and not config.get("api_key") and not is_headless:
            self.console.print(
                "\n[bold yellow]Warning: OPENROUTER_API_KEY or UTIM_API_KEY not found in environment "
                f"or .env file (looked in {_cwd_env!r} then .utim/.env).[/bold yellow]\n"
            )

        self._local_client: bool = bool(self._local_api_key)  

        # OpenRouter base URL (can be overridden per-model for custom providers)
        self._openrouter_base_url = "https://openrouter.ai/api/v1/chat/completions"
        self.model_source: Optional[str] = config.get("main_model_source")

        # Cancellation flag
        self.cancel_event = threading.Event()

        # Lock protecting self.messages from concurrent reads/writes.
        # The background summarisation thread and the main agent loop both
        # access self.messages; without this lock they can race and produce
        # hallucinated summaries or corrupt the message list.
        self._messages_lock = threading.Lock()

        # Manual-mode confirm hook
        self._get_confirm_fn = lambda: None  

        # Turn-level file-change tracking
        self.turn_history: List[Dict[str, Any]] = []
        self.redo_history: List[Dict[str, Any]] = []
        self._turn_changes: List[Dict[str, Any]] = []
        self._current_turn_start: int = 1  

        # ── @subagent tag override ───────────────────────────────────────
        # Set by utim.py when user sends a prompt prefixed with @<subagent-id>.
        # Cleared automatically after each run_task() call.
        self.active_tag: Optional[str] = None                  # e.g. '@refactor-bot'
        self.active_tag_system_prompt: Optional[str] = None    # custom system prompt text

        # ── MCP tool name registry ───────────────────────────────────────
        # Populated by _discover_mcp_tools() or left empty if MCP is disabled.
        self.mcp_tool_names: set = set()

        # Eager session create removed for local mode - sessions are created by _persist_messages

        # ── Brain System Startup ─────────────────────────────────────────────
        # Start the background brain watcher (architecture scan + memory watch)
        # and run the initial project architecture indexing — both in background
        # so they never block the CLI startup time.
        try:
            import threading as _brain_thread
            from utim_cli.brain import start_brain_watcher, index_project_architecture
            start_brain_watcher()
            _brain_thread.Thread(
                target=lambda: index_project_architecture(os.getcwd()),
                daemon=True,
                name="utim-brain-init-arch-scan",
            ).start()
        except Exception:
            pass


    def abort(self) -> None:
        """Instantly abort all LLM stream responses, running tool processes, and worker loops."""
        self.cancel_event.set()

        # 1. Force socket shutdown on active streaming LLM response
        resp = getattr(self, "active_response", None)
        if resp is not None:
            try:
                resp.close()
            except Exception:
                pass
            try:
                if hasattr(resp, "raw") and resp.raw:
                    sock = getattr(resp.raw, "_fp", None)
                    if sock and hasattr(sock, "fp") and sock.fp:
                        sock_obj = getattr(sock.fp, "_sock", None)
                        if sock_obj:
                            import socket
                            sock_obj.shutdown(socket.SHUT_RDWR)
                            sock_obj.close()
            except Exception:
                pass
            self.active_response = None

        # 2. Kill active subprocesses in tools module
        try:
            from utim_cli.tools import abort_active_command
            abort_active_command()
        except Exception:
            pass
        # NOTE: We deliberately do NOT clear cancel_event here. The stream
        # reader thread may still be draining a socket with buffered chunks,
        # and the render loops check `cancel_event.is_set()` before printing.
        # Clearing it here would let those buffered chunks print after abort.
        # The event is cleared at the START of the next turn (see the
        # `_run`/turn-reset paths that call self.cancel_event.clear()).


    # LLM calling


    def _persist_messages(self, in_progress_turn: Optional[Dict] = None) -> None:
        """Push the current full message list to the local database in a background thread.
        Silently drops on error — this is best-effort local persistence.
        """
        if not self.session_id:
            # Create a local session if we don't have one
            try:
                from utim_cli.local_db import HistoryManager
                hm = HistoryManager()
                # Use the orchestrator's email (which defaults to local@utim.dev)
                user_email = self.email or os.getenv("UTIM_EMAIL", "local@utim.dev")
                self.session_id = hm.create_session(self.model_id, email=user_email)
            except Exception:
                return
        
        # Find the first user message to use as the conversation title
        first_user = next(
            (m.get("content", "") or "" for m in self.messages if m.get("role") == "user"),
            "",
        )
        if isinstance(first_user, list):
            first_user = " ".join(p.get("text", "") for p in first_user if isinstance(p, dict))

        # Serialise the messages — exclude any private _-prefixed keys we add for tracking
        clean_messages = [
            {k: v for k, v in m.items() if not k.startswith("_")}
            for m in self.messages
        ]

        # Clean turn_history messages
        clean_turn_history = []
        for turn in self.turn_history:
            clean_turn = dict(turn)
            if "messages" in clean_turn:
                clean_turn["messages"] = [
                    {k: v for k, v in m.items() if not k.startswith("_")}
                    for m in clean_turn["messages"]
                ]
            clean_turn_history.append(clean_turn)
            
        # Append in-progress turn if provided
        if in_progress_turn:
            clean_ipt = dict(in_progress_turn)
            if "messages" in clean_ipt:
                clean_ipt["messages"] = [
                    {k: v for k, v in m.items() if not k.startswith("_")}
                    for m in clean_ipt["messages"]
                ]
            clean_turn_history.append(clean_ipt)
            
        clean_redo_history = []
        if hasattr(self, "redo_history"):
            for turn in self.redo_history:
                clean_turn = dict(turn)
                if "messages" in clean_turn:
                    clean_turn["messages"] = [
                        {k: v for k, v in m.items() if not k.startswith("_")}
                        for m in clean_turn["messages"]
                    ]
                clean_redo_history.append(clean_turn)

        # Save to local database and session_state.json
        def _save_local():
            try:
                from utim_cli.local_db import HistoryManager
                hm = HistoryManager()
                hm.add_messages(
                    self.session_id,
                    clean_messages,
                    self.email,
                    first_user,
                    turn_history=clean_turn_history,
                    redo_history=clean_redo_history
                )
                
                # Write current active session state to session_state.json
                state_data = {
                    "session_id": self.session_id,
                    "messages": clean_messages,
                    "turn_history": clean_turn_history,
                    "redo_history": clean_redo_history,
                    "model_id": self.model_id,
                    "model_source": self.model_source,
                }
                from utim_cli.config import get_utim_dir
                utim_dir = get_utim_dir()
                os.makedirs(utim_dir, exist_ok=True)
                with open(utim_dir / "session_state.json", "w", encoding="utf-8") as f:
                    json.dump(state_data, f, ensure_ascii=False, indent=4)

                # Generate a clean, readable session_summary.md
                from datetime import datetime
                summary_lines = [
                    "# UTIM Session Summary",
                    f"**Session ID:** `{self.session_id}`",
                    f"**Model:** `{self.model_id}`",
                    f"**Last Sync:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
                    "",
                    "## Completed Actions",
                ]
                if not clean_turn_history:
                    summary_lines.append("*No actions completed yet in this session.*")
                else:
                    for idx, t in enumerate(clean_turn_history):
                        req = t.get("user_msg", "").strip()
                        req_short = req.split("\n")[0][:120]
                        if len(req.split("\n")) > 1 or len(req) > 120:
                            req_short += "..."
                        
                        summary_lines.append(f"### Step {idx+1}: {req_short}")
                        
                        # Add files modified
                        changes = t.get("changes", [])
                        if changes:
                            summary_lines.append("#### Modified Files:")
                            for chg in changes:
                                fp = chg.get("file_path", "") or chg.get("path", "")
                                act = chg.get("type", "") or chg.get("action", "modified")
                                summary_lines.append(f"- `{os.path.basename(fp)}` ({act})")
                        summary_lines.append("")
                
                with open(utim_dir / "session_summary.md", "w", encoding="utf-8") as sf:
                    sf.write("\n".join(summary_lines))

                from utim_cli.backup import backup_state
                backup_state()
            except Exception:
                pass  # best-effort — never crash the agent loop

        threading.Thread(target=_save_local, daemon=True).start()

    # Pre-think marker patterns that qwen3.6-plus and similar models emit
    # OUTSIDE their <think> tags — these should be hidden too.
    _PRE_THINK_PATTERNS = re.compile(
        r"^\s*(\*\s*Thinking\.\.\.?|\.\.\.(\s*thinking)?|thinking\.\.\.?)\s*$",
        re.IGNORECASE | re.MULTILINE,
    )

    # ── Custom-provider endpoint resolution ─────────────────────────────────
    def _get_configured_model_source(self, model_id: str, *, is_primary: bool = False) -> Optional[str]:
        """Return the selected source for a model id when the picker recorded one."""
        if is_primary:
            source = getattr(self, "model_source", None) or config.get("main_model_source")
            if source in ("custom", "utim", "openrouter"):
                return source

        for key, value in config._data.items():
            if key.startswith("subagent_model_") and not key.endswith("_source") and value == model_id:
                source = config.get(f"{key}_source")
                if source in ("custom", "utim", "openrouter"):
                    return source
        return None

    def _is_custom_model_selection(self, model_id: str, *, is_primary: bool = False) -> bool:
        source = self._get_configured_model_source(model_id, is_primary=is_primary)
        if source in ("utim", "openrouter"):
            return False
        if source == "custom":
            return bool(config.get_custom_model(model_id))
        return bool(config.get_custom_model(model_id))

    def _resolve_model_endpoint(self, model_id: str, *, is_primary: bool = False) -> tuple:
        """Return (chat_completions_url, api_key) for *model_id*.

        Custom models (added via /model add) carry their own base_url and
        api_key; everything else falls back to OpenRouter.
        """
        custom = config.get_custom_model(model_id) if self._is_custom_model_selection(model_id, is_primary=is_primary) else None
        if custom:
            base = custom.get("base_url", "").rstrip("/")
            # Append /chat/completions if the caller gave us just the base path
            if not base.endswith("/chat/completions"):
                url = base + "/chat/completions"
            else:
                url = base
            key = custom.get("api_key") or self._local_api_key or ""
            return url, key
        # Built-in / OpenRouter model
        return self._openrouter_base_url, self._local_api_key or ""

    def _call_llm(self, messages: List[Dict], override_tools: Optional[List[Dict]] = None, override_model: Optional[str] = None, silent: bool = False) -> Tuple[Dict[str, Any], bool]:
        """POST /chat/completions to OpenRouter (or a custom provider) with real-time streaming."""
        if self.cancel_event.is_set():
            return {
                "role": "assistant",
                "content": "[Aborted by user]",
                "tool_calls": None,
                "was_cut_off": True,
                "aborted": True,
            }, False

        # Pre-flight quota check
        api_key = config.get("api_key")
        if api_key:
            try:
                from utim_cli.auth import SERVER_URL
                resp = requests.get(
                    f"{SERVER_URL}/quota",
                    headers={"X-API-Key": api_key},
                    timeout=5,
                )
                if resp.status_code == 200:
                    quota = resp.json()
                    chosen_model = override_model if override_model else self.model_id
                    is_custom = self._is_custom_model_selection(chosen_model, is_primary=not override_model)

                    # 1. Check if quota is exhausted (only for non-custom models)
                    used = quota.get("credits_used", quota.get("requests_used", 0.0))
                    limit = quota.get("credits_limit", quota.get("requests_limit", 1000))
                    
                    is_exhausted = quota.get("is_exhausted", False)
                    exhaustion_message = quota.get("exhaustion_message", "Credit quota exhausted.")
                    
                    if not is_custom and is_exhausted:
                        reset_time = quota.get("reset_at", "")
                        self.console.print(f"\n[bold red]✗ {exhaustion_message}[/bold red]")
                        if reset_time:
                            self.console.print(f"  Resets at: {reset_time}  •  run [bold]utim upgrade[/bold] to upgrade or visit [bold]utim.dev/pricing[/bold].\n")
                        else:
                            self.console.print(f"  run [bold]utim upgrade[/bold] to upgrade or visit [bold]utim.dev/pricing[/bold].\n")
                        return {
                            "role": "assistant",
                            "content": f"{exhaustion_message} Please upgrade your plan. utim.dev/pricing",
                            "tool_calls": None,
                        }, False
                        
                    # 2. Check if chosen model is allowed — skip entirely for BYOK/custom models
                    #    (custom models use the user's own API key, never UTIM quota)
                    models_allowed = quota["models_allowed"]
                    free_bonus_balance = quota.get("free_bonus_balance", 0.0) or 0.0
                    chosen_model = override_model if override_model else self.model_id
                    is_custom = self._is_custom_model_selection(chosen_model, is_primary=not override_model)

                    # If user has active bonus credits, all models are unlocked — skip gating entirely
                    if not is_custom and free_bonus_balance <= 0.0 and models_allowed != ["all"] and chosen_model not in models_allowed and not chosen_model.endswith(":free"):
                        if quota.get("plan") == "free" or quota.get("display_name") == "Free":
                            self.console.print(f"\n[bold red]✗ Monthly free quota exhausted and no bonus credits remaining.[/bold red]")
                            self.console.print(f"  Model '{chosen_model}' requires bonus credits or an upgraded plan.")
                            self.console.print("  Top up at [bold]utim.dev/pricing[/bold] or run [bold]utim upgrade[/bold].\n")
                            fallback_model = DEFAULT_MODEL
                            self.console.print(f"  Falling back to: [bold]{fallback_model}[/bold]")
                            if override_model:
                                override_model = fallback_model
                            else:
                                self.model_id = fallback_model
                                self.model_source = "utim"
                                config.set("main_model_source", "utim")
                        else:
                            fallback_model = DEFAULT_MODEL  # default free fallback
                            self.console.print(f"\n[bold yellow]Model '{chosen_model}' is gated under your current '{quota['display_name']}' plan.[/bold yellow]")
                            self.console.print(f"  Downgrading to default allowed model: '{fallback_model}' for this request.")
                            if override_model:
                                override_model = fallback_model
                            else:
                                self.model_id = fallback_model
                                self.model_source = "utim"
                                config.set("main_model_source", "utim")
            except SystemExit:
                raise
            except Exception:
                pass
            
        # Determine models to try for fallback support
        primary_model = override_model if override_model else self.model_id
        
        # Setup fallback for layer 2 (always include fallback models unless override_model is set)
        if not override_model:
            fallback_models = config.fallback_models
            fallback_list = [m for m in fallback_models if m != primary_model]
            models_to_try = [primary_model] + fallback_list
        else:
            models_to_try = [primary_model]

        last_exc = None
        
        for model_idx, current_model in enumerate(models_to_try):
            if self.cancel_event.is_set():
                break
                
            current_is_primary = model_idx == 0
            current_is_custom = self._is_custom_model_selection(current_model, is_primary=current_is_primary and not override_model)
            # Check for API key only if we need it for this built-in/OpenRouter model
            if not current_is_custom and not self._local_api_key and not config.get("api_key"):
                continue

            model_retries = 2
            for attempt in range(model_retries + 1):
                if self.cancel_event.is_set():
                    break
                    
                mcp_tools = []
                try:
                    from utim_cli.mcp_client import mcp_manager
                    mcp_tools = mcp_manager.get_tools()
                except Exception:
                    pass

                from utim_cli.tools import get_tools
                utim_tools, _ = get_tools()
                if override_tools is not None:
                    all_tools = override_tools
                else:
                    all_tools = utim_tools + mcp_tools
                    disabled = config.get("disabled_tools", [])
                    all_tools = [t for t in all_tools if t["function"]["name"] not in disabled]

                from utim_cli.tui.model_dialog import model_supports_reasoning
                
                settings = config.get(f"model_settings_{current_model}") or {}
                
                clean_messages = []
                for msg in messages:
                    msg_copy = dict(msg)
                    if msg_copy.get("role") == "assistant":
                        c_text = (msg_copy.get("content") or "").strip()
                        t_calls = msg_copy.get("tool_calls")
                        if not c_text and not t_calls:
                            msg_copy["content"] = "I'm ready to assist! Could you please clarify or rephrase your request?"
                    clean_messages.append(msg_copy)

                # ── Step 1 Optimization: Prompt Caching (OpenRouter / Anthropic / DeepSeek) ──
                # Inject ephemeral cache_control markers into system message and tool schema
                # so provider GPUs reuse cached KV states (saving 80-90% of input token costs).
                if attempt == 0:
                    if clean_messages and clean_messages[0].get("role") == "system":
                        clean_messages[0]["cache_control"] = {"type": "ephemeral"}
                    if all_tools:
                        all_tools = [dict(t) for t in all_tools]
                        all_tools[-1]["cache_control"] = {"type": "ephemeral"}

                payload = {
                    "model": current_model,
                    "messages": clean_messages,
                    "stream": True,
                    "max_tokens": _get_model_max_output(current_model),
                }
                
                is_reasoning = model_supports_reasoning(current_model)

                # Temperature setting: for reasoning models, omit temperature unless explicitly configured in settings
                if "temperature" in settings:
                    payload["temperature"] = settings["temperature"]
                elif not is_reasoning:
                    payload["temperature"] = 0.3
                    
                # Reasoning setting
                if is_reasoning:
                    reasoning_enabled = settings.get("reasoning_enabled", True)
                    if reasoning_enabled:
                        effort_val = settings.get("reasoning_effort", "medium")
                        payload["reasoning"] = {"effort": effort_val}
                    else:
                        payload.pop("reasoning", None)
                
                # If attempt > 0 (retry after error), strip non-standard params & cache markers for safety
                if attempt >= 1:
                    payload.pop("reasoning", None)
                    payload.pop("temperature", None)
                    for m in clean_messages:
                        m.pop("cache_control", None)
                    if all_tools:
                        for t in all_tools:
                            t.pop("cache_control", None)

                if all_tools:
                    payload["tools"] = all_tools
                printed_header = [False]
                live_printed = [False]
                in_code_block = [False]
                table_buf = []
                in_think = False
                native_reasoning = False
                display_buf = ""
                _think_buf = ""
                # Reset thinking manager for this new LLM call
                try:
                    from utim_cli.tui.thinking_display import global_thinking_manager
                    global_thinking_manager.reset()
                except Exception:
                    pass
                _proxy = sys.stdout
                _term_width = self.console.width or 80
                _line_buf = ""
                def stream_markdown_line(part_text):
                    if not part_text.strip():
                        self.console.print()
                        return
                    
                    from rich.markdown import Markdown
                    with self.console.capture() as capture:
                        self.console.print(Markdown(part_text))
                    ansi_text = capture.get().strip("\n")
                    
                    if not ansi_text:
                        self.console.print()
                        return
                    
                    from rich.text import Text
                    text_obj = Text.from_ansi(ansi_text)
                    self.console.print(text_obj)

                def flush_table():
                    if not table_buf:
                        return
                    table_text = "\n".join(table_buf)
                    table_buf.clear()
                    
                    from rich.markdown import Markdown
                    with self.console.capture() as capture:
                        self.console.print(Markdown(table_text))
                    ansi_text = capture.get().strip("\n")
                    
                    if not ansi_text:
                        return
                    
                    from rich.text import Text
                    text_obj = Text.from_ansi(ansi_text)
                    self.console.print(text_obj)

                def process_stream_part(part):
                    if not printed_header[0]:
                        printed_header[0] = True
                        self.console.print()
                    
                    if part.strip().startswith("```"):
                        flush_table()
                        in_code_block[0] = not in_code_block[0]
                        self.console.print(part)
                    elif in_code_block[0] or part.startswith("    ") or part.startswith("\t"):
                        flush_table()
                        self.console.print(part)
                    elif part.strip().startswith("|"):
                        table_buf.append(part)
                    else:
                        flush_table()
                        stream_markdown_line(part)
                    live_printed[0] = True

                # ── Markdown-aware live renderer ──
                # Tokens accumulate into `display_buf`, then a Rich `Live`
                # re-renders the *entire* Markdown tree on each chunk.  This
                # is what keeps tables (header | row | separator) coherent —
                # a token-by-token sys.stdout.write would shred them because
                # the separator row arrives many tokens *after* the header.
                try:
                    start_time = time.time()
                    # last_content_time: updated only when real content/tool-call data arrives.
                    # Intentionally NOT reset by keep-alive pings (empty lines) so stall
                    # detection isn't fooled by the server sending blank heartbeats.
                    last_content_time = start_time
                    _api_key = config.get("api_key")
                    _openrouter_key = self._local_api_key
                    _browser_ua = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
                    
                    _current_source = self._get_configured_model_source(
                        current_model,
                        is_primary=current_is_primary and not override_model,
                    )
                    use_utim_server = False
                    if _current_source == "utim":
                        use_utim_server = True
                    elif _current_source == "openrouter":
                        use_utim_server = False
                    elif _current_source == "custom" or current_is_custom:
                        use_utim_server = False
                    else:
                        use_utim_server = bool(_api_key)

                    if use_utim_server and not _api_key:
                        use_utim_server = False

                    if not use_utim_server:
                        _endpoint_url, _endpoint_key = self._resolve_model_endpoint(
                            current_model,
                            is_primary=current_is_primary and not override_model,
                        )
                        # Attribution headers — OpenRouter shows "UTIM CLI Agent"
                        # in its activity log ONLY when HTTP-Referer + X-Title are
                        # present on every outbound call. Without them the app
                        # shows as "unknown".
                        try:
                            from utim_cli.server.attribution import OPENROUTER_HEADERS as _OR_ATTR
                        except Exception:
                            _OR_ATTR = {
                                "HTTP-Referer": "https://utim.dev",
                                "X-Title": "UTIM CLI Agent",
                            }
                        _headers = {
                            "Authorization": f"Bearer {_endpoint_key}",
                            "Content-Type": "application/json",
                            "User-Agent": _browser_ua,
                            **_OR_ATTR,
                        }
                        request_payload = payload
                    else:
                        from utim_cli.auth import SERVER_URL
                        _endpoint_url = f"{SERVER_URL}/completions"
                        _headers = {
                            "X-API-Key": _api_key,
                            "Content-Type": "application/json",
                            "User-Agent": _browser_ua,
                        }
                        request_payload = {
                            "messages": messages,
                            "model_id": current_model,
                            "tools": all_tools or None,
                            "session_id": self.session_id,
                            "temperature": payload.get("temperature"),
                            "max_tokens": payload.get("max_tokens"),
                            "reasoning": payload.get("reasoning"),
                        }

                    # Check for cancel before we even open the socket
                    if self.cancel_event.is_set():
                        return {
                            "role": "assistant",
                            "content": "[Aborted by user]",
                            "tool_calls": None,
                            "was_cut_off": True,
                            "aborted": True,
                        }, False

                    with requests.post(
                        _endpoint_url,
                        json=request_payload,
                        headers=_headers,
                        stream=True,
                        timeout=(15, 900),  # 15s connect, 900s (15 mins) read — resp.close() handles abort mid-stream
                    ) as resp:
                        resp.raise_for_status()
                        resp.encoding = "utf-8"
                        self.active_response = resp
                    
                        final_content = ""
                        final_tool_calls = []
                        was_cut_off = False
                        _stream_finish_reason: str = ""
                        _stream_completion_tokens: int = 0
                        # Buffers raw <tool_call>/<|tool_call|> XML streamed as text
                        # so it never renders in the live chat output.
                        _tool_xml_buf: list = [""]

                        try:
                            # Dynamic thinking phases — cycle through contextual messages
                            # during the TTFT wait so the spinner feels alive, not stuck.
                            _THINKING_PHASES = [
                                "Analyzing context...",
                                "Reasoning through approach...",
                                "Evaluating options...",
                                "Structuring response...",
                                "Processing deeply...",
                                "Connecting patterns...",
                                "Formulating plan...",
                                "Almost there...",
                            ]
                            _phase_idx = 0
                            _last_phase_time = start_time

                            # ── Interruptible stream reader ─────────────────────────────
                            # resp.iter_lines() blocks on the socket and can't be woken by
                            # cancel_event alone.  Push lines into a queue from a daemon
                            # thread; the main loop drains it with a short timeout so
                            # cancel_event is checked every 50 ms.  Calling resp.close()
                            # from the main thread kills the socket and unblocks the reader.
                            import queue as _queue_mod
                            _line_queue: _queue_mod.Queue = _queue_mod.Queue()
                            _STREAM_SENTINEL = object()   # signals reader thread finished

                            def _reader_thread(response, q):
                                try:
                                    for _ln in response.iter_lines(decode_unicode=True):
                                        q.put(_ln)
                                except Exception:
                                    pass
                                finally:
                                    q.put(_STREAM_SENTINEL)

                            _rt = threading.Thread(
                                target=_reader_thread,
                                args=(resp, _line_queue),
                                daemon=True,
                                name="utim-stream-reader",
                            )
                            _rt.start()

                            def _iter_lines_cancelable():
                                """Yield lines from the queue; abort by closing resp when cancel fires."""
                                while True:
                                    if self.cancel_event.is_set():
                                        try:
                                            resp.close()
                                        except Exception:
                                            pass
                                        return
                                    try:
                                        item = _line_queue.get(timeout=0.05)
                                    except _queue_mod.Empty:
                                        continue
                                    if item is _STREAM_SENTINEL:
                                        return
                                    yield item

                            for raw_line in _iter_lines_cancelable():
                                if self.cancel_event.is_set():
                                    try:
                                        resp.close()
                                    except Exception:
                                        pass
                                    return {
                                        "role": "assistant",
                                        "content": "[Aborted by user]",
                                        "tool_calls": None,
                                        "was_cut_off": True,
                                        "aborted": True,
                                    }, False

                                
                                now = time.time()

                                # Cycle thinking topic every 8s during TTFT wait
                                if not final_content and not final_tool_calls:
                                    if now - _last_phase_time > 8:
                                        try:
                                            from utim_cli.state import STATE
                                            STATE["thinking_topic"] = _THINKING_PHASES[_phase_idx % len(_THINKING_PHASES)]
                                            _phase_idx += 1
                                            _last_phase_time = now
                                        except Exception:
                                            pass

                                # Stall detection runs on EVERY iteration (including empty
                                # keep-alive lines) so a true stream stall is always caught.
                                if not final_content and not final_tool_calls:
                                    # Hard 900-second timeout for Time-To-First-Token
                                    # Models often need 60-300s to process large tool outputs before streaming
                                    if now - start_time > 900:
                                        raise requests.exceptions.Timeout("Hard TTFT timeout exceeded 900s")
                                else:
                                    # Inter-content stall detection: abort if no real content
                                    # has arrived for 900 seconds (15 mins), even during keep-alive pings.
                                    if now - last_content_time > 900:
                                        raise requests.exceptions.Timeout("Inter-token stall timeout exceeded 900s")
                                        
                                if not raw_line:
                                    continue
                                
                                # NOTE: last_content_time is updated further below, only when
                                # actual content or tool-call data is parsed from the chunk.
                                    
                                # Clean and normalize the raw line
                                line_str = raw_line.strip()
                                if not line_str:
                                    continue

                                # Strip "data: " prefix if present (SSE stream prefix)
                                if line_str.startswith("data: "):
                                    line_str = line_str[6:].strip()

                                if line_str == "[DONE]":
                                    break

                                # Parse as JSON
                                try:
                                    chunk = json.loads(line_str)
                                except json.JSONDecodeError:
                                    continue

                                # ── 1. UTIM Server response format ─────────────────────────
                                if "type" in chunk:
                                    last_content_time = time.time()
                                    t = chunk["type"]
                                    if t == "thinking_delta":
                                        t_text = chunk.get("text", "")
                                        if t_text:
                                            if not in_think:
                                                in_think = True
                                                native_reasoning = True
                                                final_content += "<think>\n"
                                                try:
                                                    from utim_cli.tui.thinking_display import global_thinking_manager
                                                    global_thinking_manager.start()
                                                except Exception:
                                                    pass
                                                if not silent:
                                                    self.console.print()
                                                    self.console.print("[cyan]▸ Thinking...[/cyan]  [dim](Ctrl+O to expand)[/dim]")
                                            final_content += t_text
                                            _think_buf += t_text
                                            try:
                                                from utim_cli.tui.thinking_display import global_thinking_manager
                                                global_thinking_manager.append(t_text)
                                            except Exception:
                                                pass
                                            try:
                                                from utim_cli.state import STATE
                                                lines = [l.strip() for l in _think_buf.split('\n') if l.strip()]
                                                if lines:
                                                    topic = lines[-1]
                                                    if len(topic) > 60:
                                                        topic = topic[:57] + "..."
                                                    STATE["thinking_topic"] = topic
                                            except Exception:
                                                pass
                                        continue
                                    elif t == "content_delta":
                                        # If we were in a thinking block, close it now
                                        if native_reasoning:
                                            native_reasoning = False
                                            in_think = False
                                            final_content += "\n</think>\n"
                                            try:
                                                from utim_cli.tui.thinking_display import global_thinking_manager
                                                finished_block = global_thinking_manager.finish()
                                                if finished_block and not silent:
                                                    rendered = global_thinking_manager.render_block(finished_block)
                                                    if rendered:
                                                        self.console.print(rendered)
                                            except Exception:
                                                pass
                                        text = chunk.get("text", "")
                                        final_content += text
                                        # Never print raw tool-call XML tokens live. If the
                                        # model emits <tool_call>/<|tool_call|> as text (some
                                        # models do), we buffer it out of the visible stream
                                        # so schemas don't leak into chat; it's parsed into
                                        # real tool calls at end-of-stream (see below).
                                        _looks_like_tool_xml = (
                                            "<tool_call" in text or "</tool_call" in text
                                            or "<|tool_call" in text or "</|tool_call" in text
                                        )
                                        if _looks_like_tool_xml:
                                            _tool_xml_buf[0] += text
                                        elif not silent and text and not self.cancel_event.is_set():
                                            display_buf += text
                                            _line_buf += text
                                            if "\n" in _line_buf:
                                                parts = _line_buf.split("\n")
                                                for part in parts[:-1]:
                                                    process_stream_part(part)
                                                _line_buf = parts[-1]
                                    elif t == "done":
                                        if "error" in chunk and chunk["error"]:
                                            raise RuntimeError(f"Server completion error: {chunk['error']}")
                                        final_content = chunk.get("content") or final_content
                                        final_tool_calls = chunk.get("tool_calls") or final_tool_calls
                                        usage = chunk.get("usage")
                                        if usage:
                                            in_t = usage.get("input_tokens", 0)
                                            out_t = usage.get("output_tokens", 0)
                                            from utim_cli.server.models import estimate_cost
                                            cost = estimate_cost(current_model, in_t, out_t)
                                            from utim_cli.client_utils import update_session_usage
                                            update_session_usage("main_agent", in_t, out_t, cost)
                                        break
                                    continue

                                # ── 2. OpenAI / OpenRouter response format ─────────────────
                                if "usage" in chunk and chunk["usage"]:
                                    usage = chunk["usage"]
                                    in_t = usage.get("prompt_tokens", 0)
                                    out_t = usage.get("completion_tokens", 0)
                                    _stream_completion_tokens = out_t  # track for truncation detection
                                    from utim_cli.server.models import estimate_cost
                                    cost = estimate_cost(current_model, in_t, out_t)
                                    from utim_cli.client_utils import update_session_usage
                                    update_session_usage("main_agent", in_t, out_t, cost)

                                # Check for API errors returned mid-stream
                                if "error" in chunk:
                                    raise RuntimeError(f"OpenRouter error: {chunk['error'].get('message', str(chunk['error']))}")

                                if "choices" in chunk and len(chunk["choices"]) > 0:
                                    choice = chunk["choices"][0]
                                    _fr = choice.get("finish_reason")
                                    if _fr:
                                        _stream_finish_reason = _fr  # capture last non-null finish_reason
                                    if _fr == "length":
                                        was_cut_off = True
                                    
                                    delta = choice.get("delta", {})
                                    if delta:
                                        # Handle tool calls accumulation
                                        if "tool_calls" in delta:
                                            last_content_time = time.time()  # real data arrived
                                            for tc in delta["tool_calls"]:
                                                idx = tc.get("index", 0)
                                                while len(final_tool_calls) <= idx:
                                                    final_tool_calls.append({"id": "", "type": "function", "function": {"name": "", "arguments": ""}})
                                                if tc.get("id"):
                                                    final_tool_calls[idx]["id"] = tc["id"]
                                                if tc.get("function"):
                                                    f = tc["function"]
                                                    if "name" in f:
                                                        final_tool_calls[idx]["function"]["name"] += f["name"]
                                                    if "arguments" in f:
                                                        final_tool_calls[idx]["function"]["arguments"] += f["arguments"]
                                        
                                        # Handle content streaming — support all OpenRouter reasoning delta formats:
                                        # reasoning (OpenAI/OpenRouter), reasoning_content (DeepSeek), thinking (Claude/Qwen), thought (Gemini)
                                        chunk_text = delta.get("content")
                                        reasoning_text = delta.get("reasoning") or delta.get("reasoning_content") or delta.get("thinking") or delta.get("thought")
                                        
                                        if reasoning_text:
                                            last_content_time = time.time()  # real data arrived
                                            if not in_think:
                                                in_think = True
                                                native_reasoning = True
                                                final_content += "<think>\n"
                                                # Explicitly start the thinking manager on first token
                                                try:
                                                    from utim_cli.tui.thinking_display import global_thinking_manager
                                                    global_thinking_manager.start()
                                                except Exception:
                                                    pass
                                                # Print live "Thinking..." indicator immediately
                                                if not silent:
                                                    self.console.print()
                                                    self.console.print("[cyan]▸ Thinking...[/cyan]  [dim](Ctrl+O to expand)[/dim]")
                                            final_content += reasoning_text
                                            _think_buf += reasoning_text
                                            try:
                                                from utim_cli.tui.thinking_display import global_thinking_manager
                                                global_thinking_manager.append(reasoning_text)
                                            except Exception:
                                                pass
                                            try:
                                                from utim_cli.state import STATE
                                                lines = [l.strip() for l in _think_buf.split('\n') if l.strip()]
                                                if lines:
                                                    topic = lines[-1]
                                                    if len(topic) > 60:
                                                        topic = topic[:57] + "..."
                                                    STATE["thinking_topic"] = topic
                                            except Exception:
                                                pass
                                            continue
                                            
                                        if chunk_text is not None and chunk_text != "":
                                            last_content_time = time.time()  # real data arrived
                                            if native_reasoning:
                                                native_reasoning = False
                                                in_think = False
                                                final_content += "\n</think>\n"
                                                # Finish this block and print it immediately
                                                try:
                                                    from utim_cli.tui.thinking_display import global_thinking_manager
                                                    finished_block = global_thinking_manager.finish()
                                                    if finished_block and not silent:
                                                        rendered = global_thinking_manager.render_block(finished_block)
                                                        if rendered:
                                                            self.console.print(rendered)
                                                except Exception:
                                                    pass
                                                
                                            final_content += chunk_text
                                            
                                            display = ""
                                            remaining = chunk_text
                                            while remaining:
                                                if in_think:
                                                    for closing in ("</think>", "</thinking>", "[/THINKING]"):
                                                        end_idx = remaining.find(closing)
                                                        if end_idx >= 0:
                                                            t_part = remaining[:end_idx]
                                                            _think_buf += t_part
                                                            try:
                                                                from utim_cli.tui.thinking_display import global_thinking_manager
                                                                global_thinking_manager.append(t_part)
                                                                finished_block = global_thinking_manager.finish()
                                                                # Print this inline think block immediately
                                                                if finished_block and not silent:
                                                                    rendered = global_thinking_manager.render_block(finished_block)
                                                                    if rendered:
                                                                        self.console.print(rendered)
                                                            except Exception:
                                                                pass
                                                            remaining = remaining[end_idx + len(closing):]
                                                            in_think = False
                                                            break
                                                    else:
                                                        _think_buf += remaining
                                                        try:
                                                            from utim_cli.tui.thinking_display import global_thinking_manager
                                                            global_thinking_manager.append(remaining)
                                                        except Exception:
                                                            pass
                                                        remaining = ""
                                                        
                                                    try:
                                                        from utim_cli.state import STATE
                                                        lines = [l.strip() for l in _think_buf.split('\n') if l.strip()]
                                                        if lines:
                                                            topic = lines[-1]
                                                            if len(topic) > 60:
                                                                topic = topic[:57] + "..."
                                                            STATE["thinking_topic"] = topic
                                                    except Exception:
                                                        pass
                                                else:
                                                    open_found = False
                                                    for opening in ("<think>", "<thinking>", "[THINKING]"):
                                                        start_idx = remaining.find(opening)
                                                        if start_idx >= 0:
                                                            display += remaining[:start_idx]
                                                            remaining = remaining[start_idx + len(opening):]
                                                            in_think = True
                                                            open_found = True
                                                            try:
                                                                from utim_cli.tui.thinking_display import global_thinking_manager
                                                                global_thinking_manager.start()
                                                            except Exception:
                                                                pass
                                                            # Print live indicator for this new block
                                                            if not silent:
                                                                self.console.print()
                                                                self.console.print("[cyan]▸ Thinking...[/cyan]  [dim](Ctrl+O to expand)[/dim]")
                                                            break
                                                    if not open_found:
                                                        display += remaining
                                                        remaining = ""

                                            if display and not silent and not self.cancel_event.is_set():
                                                cleaned = self._PRE_THINK_PATTERNS.sub("", display)
                                                if cleaned:
                                                    display_buf += cleaned
                                                    _line_buf += cleaned
                                                    if "\n" in _line_buf:
                                                        parts = _line_buf.split("\n")
                                                        for part in parts[:-1]:
                                                            process_stream_part(part)
                                                        _line_buf = parts[-1]
                                    
                                    elif "message" in choice:
                                        # Catch non-streaming choices message (e.g. choice fallback)
                                        msg = choice.get("message", {})
                                        if "content" in msg and msg["content"]:
                                            last_content_time = time.time()
                                            final_content += msg["content"]
                                            if not silent:
                                                display_buf += msg["content"]
                                        if "tool_calls" in msg and msg["tool_calls"]:
                                            last_content_time = time.time()
                                            final_tool_calls = msg["tool_calls"]
                                        break

                        except Exception as stream_exc:
                            # If we have received some content/tool calls, recover gracefully
                            if final_content or final_tool_calls:
                                if not silent:
                                    self.console.print(f"\n[dim yellow]Stream interrupted: {stream_exc}. Returning partial response.[/dim yellow]\n")
                                was_cut_off = True
                            else:
                                raise stream_exc
                        finally:
                            self.active_response = None

                        if self.cancel_event.is_set():
                            return {
                                "role": "assistant",
                                "content": "[Aborted by user]",
                                "tool_calls": None,
                                "was_cut_off": True,
                                "aborted": True,
                            }, False

                        # Flush any remaining text in _line_buf and table_buf
                        flush_table()
                        if _line_buf and not silent:
                            process_stream_part(_line_buf)
                            _line_buf = ""

                        # ── Print trailing thinking block (if reasoning ended stream with no content after) ──
                        if not silent:
                            try:
                                from utim_cli.tui.thinking_display import global_thinking_manager
                                # Only print if there's an unfinished/unreprinted active block
                                if global_thinking_manager.current_block and global_thinking_manager.current_block.thought_buffer:
                                    finished_block = global_thinking_manager.finish()
                                    if finished_block:
                                        rendered = global_thinking_manager.render_block(finished_block)
                                        if rendered:
                                            self.console.print()
                                            self.console.print(rendered)
                            except Exception:
                                pass

                        # ── End of `with resp` streaming block ────────────────────────────
                        # Content was already printed live chunk-by-chunk above if streaming.
                        # Only render as Markdown if somehow nothing was printed live
                        # (e.g. very short response or non-streaming path) — safety fallback.
                        if display_buf and not silent:
                            if not live_printed[0]:
                                # Nothing was printed live: render as Markdown now (short response)
                                self.console.print()
                                self.console.print(Markdown(display_buf))
                                self.console.print()
                            else:
                                # Content was already streamed live — just add trailing newline
                                self.console.print()

                        # Merge any buffered tool-call XML back into final_content so
                        # parse_xml_tool_calls (which now handles <|tool_call|>) can
                        # turn it into real tool calls instead of leaked chat text.
                        if _tool_xml_buf[0]:
                            final_content += _tool_xml_buf[0]

                        clean_content = re.sub(
                            r"<think(?:ing)?>.*?</think(?:ing)?>", "", final_content, flags=re.DOTALL
                        ).strip()
                        clean_content = self._PRE_THINK_PATTERNS.sub("", clean_content).strip()

                        # Failsafe: if the model ONLY output reasoning and no actual content,
                        # use the reasoning as the content so the user sees it.
                        if not clean_content and final_content.strip():
                            clean_content = final_content.strip()
                            clean_content = re.sub(r"</?think(?:ing)?>", "", clean_content).strip()

                        clean_content = clean_content if clean_content else None

                        # Parse XML-style tool calls if present in the text content
                        from utim_cli.client_utils import parse_xml_tool_calls
                        parsed_content, parsed_tool_calls = parse_xml_tool_calls(clean_content)
                        if parsed_tool_calls:
                            clean_content = parsed_content
                            if final_tool_calls is None:
                                final_tool_calls = []
                            final_tool_calls.extend(parsed_tool_calls)

                        final_tool_calls = final_tool_calls if final_tool_calls else None

                        # ── Code-block → write_file recovery ─────────────────────────────
                        # If the model output a large code block as plain text instead of
                        # calling write_file/edit_file, synthesize the tool call automatically
                        # so the generated content is not wasted.
                        #
                        # Trigger conditions (ALL must be true):
                        #   • No tool calls were emitted by the model
                        #   • The response contains at least one fenced code block ≥ 40 lines
                        #   • A plausible filename can be inferred from the text
                        if not final_tool_calls and clean_content:
                            try:
                                _recovered_calls = _extract_write_file_calls(clean_content)
                                if _recovered_calls:
                                    final_tool_calls = _recovered_calls
                                    if not silent:
                                        _n = len(_recovered_calls)
                                        _names = ", ".join(
                                            c["function"].get("name", "?") for c in _recovered_calls
                                        )
                                        self.console.print(
                                            f"\n[dim cyan]↩ Auto-recovered {_n} file write(s) from model text output: "
                                            f"{_names}[/dim cyan]\n"
                                        )
                            except Exception:
                                pass

                        if not clean_content and not final_tool_calls:
                            clean_content = "I'm ready to assist! Could you please clarify or rephrase your request?"

                        # Heuristic abrupt-cutoff detector:
                        # Some providers (e.g. OpenRouter) report finish_reason="stop" even
                        # when the response is actually truncated mid-generation.  We catch
                        # two reliable signals of abrupt cutoff:
                        #   1. Unclosed code fence — an odd count of triple-backtick markers
                        #      means the last ```...``` block was never closed.
                        #   2. The response is large (>3 000 chars) and the last non-whitespace
                        #      character is NOT a normal sentence terminator, suggesting the
                        #      model was cut off mid-word or mid-line.
                        if not was_cut_off and clean_content and not final_tool_calls:
                            _backtick_count = clean_content.count("```")
                            _last_char = clean_content.rstrip()[-1] if clean_content.rstrip() else ""
                            _terminal_chars = set(".?!`'\">)]}\\")
                            if _backtick_count % 2 != 0:
                                was_cut_off = True  # unclosed code fence
                            elif len(clean_content) > 3000 and _last_char not in _terminal_chars:
                                was_cut_off = True  # large response ending abruptly

                        # Truncation diagnosis: was the stream cut short by output token limit?
                        _max_out = _get_model_max_output(current_model)
                        _was_truncated_by_limit = (
                            _stream_finish_reason in ("length", "max_tokens")
                            or (
                                _stream_completion_tokens > 0
                                and _stream_completion_tokens >= _max_out - 5
                            )
                        )

                        final_msg = {
                            "role": "assistant",
                            "content": clean_content,
                            "tool_calls": final_tool_calls,
                            "was_cut_off": was_cut_off,
                            "finish_reason": _stream_finish_reason,
                            "completion_tokens": _stream_completion_tokens,
                            "was_truncated_by_limit": _was_truncated_by_limit,
                        }
                        return final_msg, True

                except (requests.exceptions.ConnectionError, requests.exceptions.Timeout) as exc:
                    last_exc = exc
                    break  # try next model
                except requests.exceptions.HTTPError as exc:
                    last_exc = exc
                    code = exc.response.status_code if exc.response is not None else "?"
                    if code == 400 and exc.response is not None and attempt == model_retries:
                        try:
                            from rich.markup import escape
                            error_details = exc.response.json()
                            if isinstance(error_details, dict) and "error" in error_details:
                                err_obj = error_details["error"]
                                err_msg = err_obj.get("message", str(err_obj)) if isinstance(err_obj, dict) else str(err_obj)
                            else:
                                err_msg = json.dumps(error_details)
                            self.console.print(f"\n[red]HTTP 400 Error Details from {current_model}: {escape(err_msg)}[/red]")
                        except Exception:
                            from rich.markup import escape
                            self.console.print(f"\n[red]HTTP 400 Error Details from {current_model}: {escape(exc.response.text or 'Bad Request')}[/red]")
                    if code == 403:
                        # Re-check quota live to see if bonus credits are still active
                        _has_bonus = False
                        try:
                            _qr = requests.get(
                                f"{SERVER_URL}/quota",
                                headers={"X-API-Key": config.get("api_key") or ""},
                                timeout=5,
                            )
                            if _qr.status_code == 200:
                                _has_bonus = (_qr.json().get("free_bonus_balance") or 0.0) > 0.0
                        except Exception:
                            pass
                        if _has_bonus:
                            # Bonus credits still active — server may have stale state, skip to next fallback
                            break
                        self.console.print(f"\n[bold red]✗ Model '{current_model}' requires bonus credits or an upgraded plan.[/bold red]")
                        self.console.print("  Top up at [bold]utim.dev/pricing[/bold] or run [bold]utim upgrade[/bold].")
                        self.console.print("  [bold yellow]Tip: Your bonus credits are exhausted. You can still access all free models! [/bold yellow]")
                        self.console.print("  [yellow]   Press Ctrl+M or type /model to switch to a free model, or run 'utim reset'.[/yellow]\n")
                        raise _FatalClientError(f"Model '{current_model}' requires bonus credits or an upgraded plan.")
                    if code == 429:
                        msg_str = ""
                        upgrade_url = ""
                        try:
                            err_data = exc.response.json()
                            if isinstance(err_data, dict):
                                # 1. Check "detail" key
                                detail = err_data.get("detail")
                                if isinstance(detail, dict):
                                    msg_str = detail.get("message", detail.get("error", ""))
                                    upgrade_url = detail.get("upgrade_url", "")
                                elif isinstance(detail, str):
                                    msg_str = detail
                                
                                # 2. Check "error" key (UTIM / OpenRouter format)
                                if not msg_str:
                                    err = err_data.get("error")
                                    if isinstance(err, dict):
                                        msg_str = err.get("message", err.get("detail", ""))
                                    elif isinstance(err, str):
                                        msg_str = err
                                
                                # 3. Check "message" key
                                if not msg_str:
                                    msg_str = err_data.get("message", "")
                        except Exception:
                            pass

                        if not msg_str:
                            msg_str = "Quota exhausted or rate limit exceeded."

                        self.console.print(f"\n[bold red]✗ Quota Exhausted / Limit Reached:[/bold red]")
                        self.console.print(f"  [red]{msg_str}[/red]")
                        if not upgrade_url:
                            upgrade_url = "https://utim.dev/pricing"
                        self.console.print(f"  Please top up credits or upgrade your plan at: [bold]{upgrade_url}[/bold]")
                        self.console.print(f"  You can check your remaining balance by running [bold]/balance[/bold].\n")
                        
                        raise _FatalClientError(f"Quota exhausted: {msg_str}. Please upgrade at {upgrade_url}")
                    if attempt < model_retries:
                        delay = 3 * (attempt + 1)
                        # Interruptible wait — so Ctrl+C can abort immediately
                        deadline = time.time() + delay
                        while time.time() < deadline:
                            if self.cancel_event.is_set():
                                break
                            time.sleep(0.1)
                        if self.cancel_event.is_set():
                            raise _FatalClientError("Cancelled by user")
                        continue
                    break  # try next model
                except RuntimeError as exc:
                    # Mid-stream API errors (e.g. model overloaded) or custom empty response error
                    last_exc = exc
                    break  # try next model
                except Exception as exc:
                    last_exc = exc
                    break  # try next model

        # If we exit the loop, all models failed
        if isinstance(last_exc, requests.exceptions.HTTPError):
            code = last_exc.response.status_code if last_exc.response is not None else "?"
            raise _ServerUnavailableError(f"Model API returned an error after trying all fallbacks (HTTP {code}).") from last_exc
        elif last_exc:
            raise _ServerUnavailableError(f"Cannot reach model API after trying all fallback models. Last error: {last_exc}") from last_exc
        else:
            raise _ServerUnavailableError("OPENROUTER_API_KEY is missing. Please set it in your .env file.")

    # Tool display helpers

    # Icons per tool
    TOOL_ICON: Dict[str, str] = {
        "read_file":              "",
        "write_file":             "",
        "edit_file":              "",
        "move_file":              "",
        "delete_file":            "",
        "run_command":            "",
        "list_directory":         "",
        "get_background_output":  "",
        "send_background_input":  "",
        "stop_background_process":"",
        "list_background_processes": "",
        "web_search":             "",
        "plan_project":           "",
        "manage_todos":           "",
        "generate_image":         "",
    }

    # Short, Antigravity-style verb labels per tool
    TOOL_DISPLAY_NAME: Dict[str, str] = {
        "read_file":              "Read",
        "write_file":             "Write",
        "edit_file":              "Edit",
        "move_file":              "Move",
        "delete_file":            "Delete",
        "run_command":            "Bash",
        "list_directory":         "ListDir",
        "get_background_output":  "BgOutput",
        "send_background_input":  "BgInput",
        "stop_background_process": "BgStop",
        "list_background_processes": "BgList",
        "web_search":             "Search",
        "plan_project":           "Plan",
        "manage_todos":           "Todo",
        "generate_image":         "GenImage",
    }

    @staticmethod
    def _get_display_arg(func_name: str, arguments: Dict) -> str:
        """Extract the most informative single argument to display inline."""
        if "__" in func_name:
            return ", ".join(f"{k}={v}" for k, v in arguments.items())[:60]
        if func_name in ("read_file", "write_file", "delete_file"):
            path = arguments.get("filepath", arguments.get("path", ""))
            # Append line range for read_file when a range was requested
            if func_name == "read_file":
                s = arguments.get("start_line")
                e = arguments.get("end_line")
                if s or e:
                    path = f"{path}:{s or ''}–{e or ''}"
            return path
        if func_name == "edit_file":
            return arguments.get("filepath", arguments.get("path", ""))
        if func_name == "run_command":
            cmd = arguments.get("command", "")
            if not cmd:
                cmds = arguments.get("commands", [])
                if cmds and isinstance(cmds, list):
                    cmd = "; ".join(str(c) for c in cmds)
            # Defensive coercion: cmd may be a list, dict, or other non-string type
            # if the LLM emitted malformed arguments. Coerce to string safely.
            if not isinstance(cmd, str):
                if isinstance(cmd, (list, tuple)):
                    cmd = "; ".join(str(c) for c in cmd)
                elif isinstance(cmd, dict):
                    cmd = " ".join(f"{k}={v}" for k, v in cmd.items())
                else:
                    cmd = str(cmd) if cmd is not None else ""
            display = (cmd or "")[:80] + ("…" if len(cmd or "") > 80 else "")
            dir_p = arguments.get("dir_path", "")
            if dir_p:
                display += f"  [{dir_p}]"
            return display
        if func_name == "list_directory":
            return arguments.get("path", ".")
        if func_name == "move_file":
            src = arguments.get("source", arguments.get("src", ""))
            dst = arguments.get("destination", arguments.get("dst", ""))
            return f"{src} → {dst}"
        if func_name == "web_search":
            return arguments.get("prompt", arguments.get("query", ""))
        if func_name == "generate_image":
            return arguments.get("prompt", "")[:40]
        if func_name == "plan_project":
            return f"{arguments.get('plan_part', 'general')} - {arguments.get('prompt', '')[:30]}"
        if func_name == "manage_todos":
            ops = arguments.get('operations', [])
            if ops:
                return f"{len(ops)} operations"
            
            action = arguments.get('action', '')
            tid = arguments.get('task_id', '')
            desc = arguments.get('description', '')[:30]
            if action == 'add': return f"Add: {desc}"
            if action in ('mark_done', 'mark_pending', 'delete'): return f"{action}: {tid}"
            return action
        if func_name == "get_background_output":
            return f"process #{arguments.get('process_id', '?')}"
        if func_name == "send_background_input":
            return f"to #{arguments.get('process_id', '?')}: {arguments.get('input_text', '')[:30]}"
        return ""

    def _render_result(self, func_name: str, arguments: Dict, result: str, color: str, user_confirmed: bool = False, expand: bool = False, print_to_console: bool = True) -> str:
        """Render a tool result in Antigravity inline style — no box, no border.

        Collapsed:  Verb(path)
                      └ +N / -N lines
        Expanded:   Verb(path)
                      └ <full content>
        """
        display_name = self.TOOL_DISPLAY_NAME.get(func_name, func_name)
        display_arg  = self._get_display_arg(func_name, arguments)

        is_error = result.startswith("Error") or result.startswith("Pre-Commit Validation Failed")

        # ── Line 1: Verb(arg) ──────────────────────────────────────────────────
        header = Text()
        if is_error:
            header.append("\u2717 ", style="bold red")
            header.append(f"{display_name}", style="bold red")
        else:
            header.append(f"{display_name}", style=f"bold {color}")
        if display_arg:
            header.append(f"({display_arg})", style="dim white")
        if not expand and not is_error:
            header.append(" (ctrl+o to expand)", style="dim #585b70")

        # ── Body lines ─────────────────────────────────────────────────────────
        body_lines: list = []  # list of Text objects to print after header

        TREE  = "  \u2514 "
        PIPE  = "  \u2502 "
        BLANK = "    "

        def _tree(txt: Text | str, style: str = "") -> Text:
            t = Text()
            t.append(TREE, style="dim #585b70")
            if isinstance(txt, Text):
                t.append_text(txt)
            else:
                t.append(txt, style=style)
            return t

        def _pipe(txt: str, style: str = "") -> Text:
            t = Text()
            t.append(PIPE, style="dim #585b70")
            t.append(txt, style=style)
            return t

        if is_error:
            # Always show full error
            err_lines = result.strip().splitlines()
            for i, line in enumerate(err_lines):
                connector = TREE if i == 0 else PIPE
                t = Text()
                t.append(connector, style="dim #585b70")
                t.append(line, style="red")
                body_lines.append(t)

            # Permission hint for MCP
            result_lower = result.lower()
            is_permission_error = any(kw in result_lower for kw in [
                "permission denied", "not accessible by personal access token",
                "resource not accessible", "403", "unauthorized", "401",
                "insufficient scope", "bad credentials", "bad_credentials",
                "requires authentication", "token", "forbidden"
            ])
            if is_permission_error and "__" in func_name:
                server_name_hint = func_name.split("__")[0]
                hint = Text()
                hint.append(PIPE, style="dim #585b70")
                hint.append("Hint: ", style="bold yellow")
                hint.append(
                    f"Token for \'{server_name_hint}\' may lack required permissions. Go to /mcp \u2192 Update Token.",
                    style="yellow"
                )
                body_lines.append(hint)

        elif func_name == "edit_file":
            replacements = arguments.get("replacements")
            removed = 0
            added   = 0

            if replacements is not None and isinstance(replacements, list):
                for rep in replacements:
                    if isinstance(rep, dict):
                        removed += len((rep.get("old_str", "") or "").splitlines())
                        added   += len((rep.get("new_str", "") or "").splitlines())
            else:
                removed = len((arguments.get("old_str", "") or "").splitlines())
                added   = len((arguments.get("new_str", "") or "").splitlines())

            if not expand:
                # Collapsed: single stat line
                stat = Text()
                stat.append(TREE, style="dim #585b70")
                if added:
                    stat.append(f"+{added}", style="bold green")
                    stat.append(" / ", style="dim #585b70")
                if removed:
                    stat.append(f"-{removed}", style="bold red")
                    stat.append(" lines", style="dim white")
                elif added:
                    stat.append(" lines", style="dim white")
                if not added and not removed:
                    stat.append("(no changes)", style="dim")
                body_lines.append(stat)
            else:
                # Expanded: show diff hunks with 5-6 lines truncation, count footers per type
                def render_hunk(o_str, n_str, rep_index=None):
                    o_lines = o_str.splitlines()
                    n_lines = n_str.splitlines()
                    
                    if rep_index is not None:
                        body_lines.append(_pipe(f"Replacement #{rep_index}", "bold dim white"))
                        
                    # 1. Render Deleted Lines (up to 5)
                    if o_lines:
                        shown_o = o_lines[:5]
                        for line in shown_o:
                            body_lines.append(_pipe(f"- {line}", "bold red"))
                        if len(o_lines) > 5:
                            body_lines.append(_pipe(f"- ... ({len(o_lines) - 5} more lines)", "red"))
                        # Show -X lines footer under deleted lines
                        body_lines.append(_pipe(f"-{len(o_lines)} lines", "bold red"))
                        
                    # 2. Render Added Lines (up to 5)
                    if n_lines:
                        shown_n = n_lines[:5]
                        for line in shown_n:
                            body_lines.append(_pipe(f"+ {line}", "bold green"))
                        if len(n_lines) > 5:
                            body_lines.append(_pipe(f"+ ... ({len(n_lines) - 5} more lines)", "green"))
                        # Show +X lines footer under added lines
                        body_lines.append(_pipe(f"+{len(n_lines)} lines", "bold green"))

                if replacements is not None and isinstance(replacements, list):
                    for idx, rep in enumerate(replacements):
                        if not isinstance(rep, dict):
                            continue
                        o_str = rep.get("old_str", "") or ""
                        n_str = rep.get("new_str", "") or ""
                        render_hunk(o_str, n_str, rep_index=idx+1 if len(replacements) > 1 else None)
                else:
                    o_str = arguments.get("old_str", "") or ""
                    n_str = arguments.get("new_str", "") or ""
                    render_hunk(o_str, n_str)
                    
                # stat footer
                stat = Text()
                stat.append(TREE, style="dim #585b70")
                if added:
                    stat.append(f"+{added}", style="bold green")
                    stat.append(" / ", style="dim #585b70")
                if removed:
                    stat.append(f"-{removed}", style="bold red")
                    stat.append(" lines", style="dim white")
                body_lines.append(stat)

        elif func_name == "write_file":
            old_content = arguments.get("_old_content") or ""
            new_content = arguments.get("content", "")
            old_ls      = old_content.splitlines(keepends=True)
            new_ls      = new_content.splitlines(keepends=True)
            diff_lines  = list(difflib.unified_diff(old_ls, new_ls, lineterm=""))
            added_count   = sum(1 for l in diff_lines if l.startswith("+") and not l.startswith("+++"))
            removed_count = sum(1 for l in diff_lines if l.startswith("-") and not l.startswith("---"))

            if not expand:
                stat = Text()
                stat.append(TREE, style="dim #585b70")
                if not old_content and not diff_lines:
                    stat.append(f"+{len(new_ls)} lines (new file)", style="bold green")
                elif added_count or removed_count:
                    if added_count:
                        stat.append(f"+{added_count}", style="bold green")
                        stat.append(" / ", style="dim #585b70")
                    if removed_count:
                        stat.append(f"-{removed_count}", style="bold red")
                    stat.append(" lines", style="dim white")
                else:
                    stat.append("(no changes)", style="dim")
                body_lines.append(stat)
            else:
                # Clean up diff lines to exclude header lines starting with '---' or '+++' or '@@'
                clean_lines = []
                for dl in diff_lines:
                    if dl.startswith("---") or dl.startswith("+++") or dl.startswith("@@"):
                        continue
                    clean_lines.append(dl)
                
                # Show first 5 and last 5 lines with a "..." in the middle if more than 10
                if len(clean_lines) <= 10:
                    for i, dl in enumerate(clean_lines):
                        connector = TREE if i == 0 else PIPE
                        t = Text()
                        t.append(connector, style="dim #585b70")
                        if dl.startswith("+"):
                            t.append(dl, style="bold green")
                        elif dl.startswith("-"):
                            t.append(dl, style="bold red")
                        else:
                            t.append(dl, style="dim white")
                        body_lines.append(t)
                else:
                    first_five = clean_lines[:5]
                    last_five = clean_lines[-5:]
                    
                    for i, dl in enumerate(first_five):
                        connector = TREE if i == 0 else PIPE
                        t = Text()
                        t.append(connector, style="dim #585b70")
                        if dl.startswith("+"):
                            t.append(dl, style="bold green")
                        elif dl.startswith("-"):
                            t.append(dl, style="bold red")
                        else:
                            t.append(dl, style="dim white")
                        body_lines.append(t)
                        
                    # The 11th line is a '...' truncation indicator
                    t_trunc = Text()
                    t_trunc.append(PIPE, style="dim #585b70")
                    t_trunc.append("...", style="dim white")
                    body_lines.append(t_trunc)
                    
                    for dl in last_five:
                        t = Text()
                        t.append(PIPE, style="dim #585b70")
                        if dl.startswith("+"):
                            t.append(dl, style="bold green")
                        elif dl.startswith("-"):
                            t.append(dl, style="bold red")
                        else:
                            t.append(dl, style="dim white")
                        body_lines.append(t)
                        
                if not clean_lines:
                    body_lines.append(_tree("(no changes)", "dim"))

        elif func_name == "run_command":
            raw_output = result.strip()
            exit_code_val = None
            stdout_lines  = []
            stderr_lines  = []
            current_section = None
            for line in raw_output.splitlines():
                if line.startswith("[exit_code:"):
                    exit_code_val = line.strip().lstrip("[").rstrip("]").split(":", 1)[1].strip()
                elif line == "[stdout]":
                    current_section = "stdout"
                elif line == "[stderr]":
                    current_section = "stderr"
                else:
                    if current_section == "stdout":
                        stdout_lines.append(line.rstrip("\r").split("\r")[-1])
                    elif current_section == "stderr":
                        stderr_lines.append(line.rstrip("\r").split("\r")[-1])

            if not expand:
                stat = Text()
                stat.append(TREE, style="dim #585b70")
                if exit_code_val is not None:
                    code_int   = int(exit_code_val) if exit_code_val.lstrip("-").isdigit() else None
                    code_style = "bold red" if (code_int is not None and code_int != 0) else "bold green"
                    stat.append(f"exit {exit_code_val}", style=code_style)
                    if stdout_lines:
                        stat.append(f"  {len(stdout_lines)} lines", style="dim white")
                elif stdout_lines:
                    stat.append(f"{len(stdout_lines)} lines", style="dim white")
                elif stderr_lines:
                    stat.append(f"stderr: {len(stderr_lines)} lines", style="dim #f9e2af")
                else:
                    stat.append("(no output)", style="dim")
                body_lines.append(stat)
            else:
                if exit_code_val is not None:
                    code_int   = int(exit_code_val) if exit_code_val.lstrip("-").isdigit() else None
                    code_style = "bold red" if (code_int is not None and code_int != 0) else "bold green"
                    ex = Text()
                    ex.append(TREE, style="dim #585b70")
                    ex.append(f"exit {exit_code_val}", style=code_style)
                    body_lines.append(ex)
                
                # Truncate stdout to 15 lines max
                if len(stdout_lines) <= 15:
                    for i, line in enumerate(stdout_lines):
                        connector = TREE if (i == 0 and exit_code_val is None) else PIPE
                        t = Text()
                        t.append(connector, style="dim #585b70")
                        t.append_text(Text.from_ansi(line))
                        body_lines.append(t)
                else:
                    first_twelve = stdout_lines[:12]
                    for i, line in enumerate(first_twelve):
                        connector = TREE if (i == 0 and exit_code_val is None) else PIPE
                        t = Text()
                        t.append(connector, style="dim #585b70")
                        t.append_text(Text.from_ansi(line))
                        body_lines.append(t)
                    body_lines.append(_tree(f"... ({len(stdout_lines) - 12} more lines of output)", "dim white"))

                if stderr_lines:
                    se_hdr = Text()
                    se_hdr.append(PIPE, style="dim #585b70")
                    se_hdr.append("[stderr]", style="bold yellow")
                    body_lines.append(se_hdr)
                    
                    # Truncate stderr to 10 lines max
                    if len(stderr_lines) <= 10:
                        for line in stderr_lines:
                            t = Text()
                            t.append(PIPE, style="dim #585b70")
                            t.append(line, style="dim #f9e2af")
                            body_lines.append(t)
                    else:
                        first_seven = stderr_lines[:7]
                        for line in first_seven:
                            t = Text()
                            t.append(PIPE, style="dim #585b70")
                            t.append(line, style="dim #f9e2af")
                            body_lines.append(t)
                        body_lines.append(_tree(f"... ({len(stderr_lines) - 7} more lines of errors)", "dim #f9e2af"))
                        
                if not stdout_lines and not stderr_lines:
                    body_lines.append(_tree("(no output)", "dim"))

        elif func_name == "list_directory":
            lines = result.strip().splitlines()
            items = lines[1:] if lines and lines[0].startswith("Contents") else lines
            if not expand:
                body_lines.append(_tree(f"{len(items)} items", "dim white"))
            else:
                if len(items) <= 15:
                    for i, item in enumerate(items):
                        connector = TREE if i == 0 else PIPE
                        t = Text()
                        t.append(connector, style="dim #585b70")
                        t.append(item, style="dim white")
                        body_lines.append(t)
                else:
                    first_twelve = items[:12]
                    for i, item in enumerate(first_twelve):
                        connector = TREE if i == 0 else PIPE
                        t = Text()
                        t.append(connector, style="dim #585b70")
                        t.append(item, style="dim white")
                        body_lines.append(t)
                    body_lines.append(_tree(f"... ({len(items) - 12} more files)", "dim white"))

        elif func_name == "read_file":
            all_lines     = result.splitlines()
            meta_line     = all_lines[0] if all_lines and all_lines[0].startswith("[") else ""
            content_lines = all_lines[1:] if meta_line else all_lines
            if not expand:
                stat = Text()
                stat.append(TREE, style="dim #585b70")
                stat.append(f"{len(content_lines)} lines", style="dim white")
                body_lines.append(stat)
            else:
                if len(content_lines) <= 15:
                    for i, line in enumerate(content_lines):
                        connector = TREE if i == 0 else PIPE
                        t = Text()
                        t.append(connector, style="dim #585b70")
                        t.append(line, style="dim white")
                        body_lines.append(t)
                else:
                    first_twelve = content_lines[:12]
                    for i, line in enumerate(first_twelve):
                        connector = TREE if i == 0 else PIPE
                        t = Text()
                        t.append(connector, style="dim #585b70")
                        t.append(line, style="dim white")
                        body_lines.append(t)
                    body_lines.append(_tree(f"... ({len(content_lines) - 12} more lines)", "dim white"))

        elif func_name == "web_search":
            lines = result.strip().splitlines()
            if not expand:
                body_lines.append(_tree(lines[0][:80] if lines else "results retrieved", "dim white"))
            else:
                if len(lines) <= 15:
                    for i, line in enumerate(lines):
                        connector = TREE if i == 0 else PIPE
                        t = Text()
                        t.append(connector, style="dim #585b70")
                        t.append(line, style="dim white")
                        body_lines.append(t)
                else:
                    first_twelve = lines[:12]
                    for i, line in enumerate(first_twelve):
                        connector = TREE if i == 0 else PIPE
                        t = Text()
                        t.append(connector, style="dim #585b70")
                        t.append(line, style="dim white")
                        body_lines.append(t)
                    body_lines.append(_tree(f"... ({len(lines) - 12} more results)", "dim white"))

        elif func_name == "generate_image":
            body_lines.append(_tree("image generated", "dim white"))

        elif func_name == "manage_todos":
            lines = result.strip().splitlines()
            if not expand:
                body_lines.append(_tree(lines[0][:80] if lines else "done", "dim white"))
            else:
                if len(lines) <= 15:
                    for i, line in enumerate(lines):
                        connector = TREE if i == 0 else PIPE
                        t = Text()
                        t.append(connector, style="dim #585b70")
                        t.append(line, style="dim white")
                        body_lines.append(t)
                else:
                    first_twelve = lines[:12]
                    for i, line in enumerate(first_twelve):
                        connector = TREE if i == 0 else PIPE
                        t = Text()
                        t.append(connector, style="dim #585b70")
                        t.append(line, style="dim white")
                        body_lines.append(t)
                    body_lines.append(_tree(f"... ({len(lines) - 12} more lines)", "dim white"))

        else:
            lines = result.strip().splitlines()
            if not expand:
                body_lines.append(_tree(lines[0][:80] if lines else "done", "dim white"))
            else:
                if len(lines) <= 15:
                    for i, line in enumerate(lines):
                        connector = TREE if i == 0 else PIPE
                        t = Text()
                        t.append(connector, style="dim #585b70")
                        t.append(line, style="dim white")
                        body_lines.append(t)
                else:
                    first_twelve = lines[:12]
                    for i, line in enumerate(first_twelve):
                        connector = TREE if i == 0 else PIPE
                        t = Text()
                        t.append(connector, style="dim #585b70")
                        t.append(line, style="dim white")
                        body_lines.append(t)
                    body_lines.append(_tree(f"... ({len(lines) - 12} more lines)", "dim white"))

        # ── Render ─────────────────────────────────────────────────────────────
        with self.console.capture() as capture:
            self.console.print(header)
            for bl in body_lines:
                self.console.print(bl)
        rendered_text = capture.get()
        if print_to_console:
            sys.stdout.write(rendered_text)
            sys.stdout.flush()
        return rendered_text

    # Tool execution

    def _execute_tool_timed(self, tool_call: Dict) -> str:
        """Execute a tool call without measuring its duration."""
        return self._execute_tool(tool_call)

    def _execute_tool(self, tool_call: Dict) -> str:
        """Execute a single tool call and render a prominent panel indicator."""
        func_name = tool_call["function"]["name"]
        
        # Clean corrupted func_name (e.g. from buggy OpenRouter proxy XML to tool-call translations)
        # E.g. 'read_file filepath=".utim/UTIM.md" />'
        arguments = {}
        raw_args = tool_call["function"].get("arguments", "{}")
        _arg_parse_ok = True
        if raw_args:
            try:
                arguments = json.loads(raw_args)
                if not isinstance(arguments, dict):
                    arguments = {}
            except json.JSONDecodeError as _jde:
                _arg_parse_ok = False
                # Record structured failure info on self so the turn loop can react
                if not hasattr(self, "_last_tool_parse_failures"):
                    self._last_tool_parse_failures = []
                self._last_tool_parse_failures.append({
                    "tool_name": func_name,
                    "tool_call_id": tool_call.get("id", ""),
                    "argument_chars": len(raw_args),
                    "error_position": _jde.pos,
                    "error_message": _jde.msg,
                    "argument_tail": raw_args[-500:],
                })
                # Fallback: try to parse as XML-style key="value" attribute string.
                # This handles the case where some LLM providers emit raw attributes
                # instead of a JSON object, e.g.: filepath="src/foo.py" content="..."
                import re as _re
                _attrs = _re.findall(
                    r'(\w+)\s*=\s*(?:"((?:[^"\\]|\\.)*)"|\'((?:[^\'\\]|\\.)*)\'|(\S+))',
                    raw_args,
                )
                for _key, _v1, _v2, _v3 in _attrs:
                    _val = _v1 or _v2 or _v3 or ""
                    # Unescape basic backslash sequences
                    _val = _val.replace('\\"', '"').replace("\\'", "'").replace("\\n", "\n").replace("\\t", "\t")
                    arguments[_key] = _val
                # If XML fallback also produced nothing useful, return a clear error
                # instead of silently calling the tool with empty/wrong args.
                if not arguments:
                    _tc_display = func_name
                    _chars = len(raw_args)
                    return (
                        f"[TOOL PARSE ERROR] The model emitted a '{_tc_display}' call but its argument "
                        f"JSON ({_chars:,} chars) could not be parsed: {_jde.msg} at char {_jde.pos}. "
                        f"The tool was NOT executed. Do NOT retry with write_file for large files — "
                        f"use edit_file with targeted replacements instead, or split into smaller chunks."
                    )

        func_name_clean = func_name.strip("<> ")
        if func_name_clean:
            parts = func_name_clean.split(None, 1)
            actual_name = parts[0]
            if len(parts) > 1:
                attr_string = parts[1].rstrip("/> ")
                import re
                attrs = re.findall(r'(\w+)\s*=\s*(?:"([^"]*)"|\'([^\']*)\'|([^\s>]+))', attr_string)
                for key, val1, val2, val3 in attrs:
                    val = val1 or val2 or val3 or ""
                    arguments[key] = val
            func_name = actual_name

        # Map common alias tool names to actual UTIM CLI tool names
        _TOOL_NAME_ALIASES = {
            "shell": "run_command",
            "bash": "run_command",
            "cmd": "run_command",
            "execute_command": "run_command",
            "view_file": "read_file",
        }
        if func_name in _TOOL_NAME_ALIASES:
            func_name = _TOOL_NAME_ALIASES[func_name]

        # Update the tool_call dict back with the cleaned values
        tool_call["function"]["name"] = func_name
        tool_call["function"]["arguments"] = json.dumps(arguments)

        color = TOOL_COLOR.get(func_name, "#888888")
        icon  = self.TOOL_ICON.get(func_name, "")

        # The JSON arguments are now guaranteed to be clean/valid
        arguments = json.loads(tool_call["function"]["arguments"])

        # Expand user home directory paths (~) and redirect legacy relative .utim paths to global ~/.utim
        for k, v in list(arguments.items()):
            if isinstance(v, str):
                k_lower = k.lower()
                if any(p in k_lower for p in ("path", "file", "dir", "folder", "cwd")):
                    v_strip = v.strip()
                    v_norm = v_strip.replace("\\", "/")

                    # 1. First prioritize mapping skills and agentskills folder to global ~/.utim
                    if ("skills" in v_norm or "agentskills" in v_norm) and (
                        "/.utim/skills" in v_norm or 
                        "/.utim/agentskills" in v_norm or 
                        v_norm.startswith(".utim/skills") or 
                        v_norm.startswith(".utim/agentskills") or 
                        v_norm.startswith("~/skills") or 
                        v_norm.startswith("~/agentskills") or 
                        v_norm.startswith("~/.utim/skills") or 
                        v_norm.startswith("~/.utim/agentskills")
                    ):
                        from utim_cli.config import get_utim_dir
                        sub_folder = "agentskills" if "agentskills" in v_norm else "skills"
                        suffix = v_norm.split(sub_folder, 1)[1].lstrip("/")
                        arguments[k] = str((get_utim_dir() / sub_folder / suffix).resolve())
                        continue

                    # 2. Expand general ~
                    if v_strip == "~" or v_strip.startswith("~/") or v_strip.startswith("~\\"):
                        import os as _os
                        arguments[k] = _os.path.expanduser(v_strip)
                    # 3. Redirect other general .utim paths to global ~/.utim
                    elif v_strip == ".utim" or v_strip == "./.utim" or v_strip == ".\\.utim":
                        from utim_cli.config import get_utim_dir
                        arguments[k] = str(get_utim_dir())
                    elif v_strip.startswith(".utim/") or v_strip.startswith(".utim\\"):
                        from utim_cli.config import get_utim_dir
                        arguments[k] = str(get_utim_dir() / v_strip[6:])
                    elif v_strip.startswith("./.utim/") or v_strip.startswith(".\\.utim\\"):
                        from utim_cli.config import get_utim_dir
                        arguments[k] = str(get_utim_dir() / v_strip[8:])
                    elif v_strip.startswith("./.utim\\") or v_strip.startswith(".\\.utim/"):
                        from utim_cli.config import get_utim_dir
                        arguments[k] = str(get_utim_dir() / v_strip[8:])
        tool_call["function"]["arguments"] = json.dumps(arguments)

        # ── Disabled-tools enforcement (applies to ALL tools, including MCP) ───
        # Hard-block execution at this point so the user's disable settings are
        # ALWAYS honoured, regardless of what the LLM tries to call. This runs
        # before the MCP early-return so MCP tools are equally blocked.
        _disabled_now = config.get("disabled_tools") or []
        if not isinstance(_disabled_now, list):
            _disabled_now = []
        if func_name in _disabled_now:
            # Silent block — the user disabled tools intentionally.
            # Don't show any warning to the user; just tell the model quietly.
            return (
                f"Tool '{func_name}' is disabled by the user. "
                "Do NOT retry this tool call. "
                "Simply tell the user their tools are currently disabled and they can enable them via /tools."
            )

        # Check if it's an MCP tool
        if "__" in func_name:
            server_name, actual_tool_name = func_name.split("__", 1)
            try:
                from utim_cli.mcp_client import mcp_manager
                if server_name in mcp_manager.sessions:
                    color = "#cba6f7"  # purple accent for MCP
                    icon = ""
                    display_name = f"{server_name} ➔ {actual_tool_name}"
                    display_arg = self._get_display_arg(func_name, arguments)
                    result = mcp_manager.call_tool(server_name, actual_tool_name, arguments)
                    self.TOOL_DISPLAY_NAME[func_name] = display_name
                    self.TOOL_ICON[func_name] = icon
                    TOOL_COLOR[func_name] = color
                    from utim_cli.state import STATE
                    is_expanded = STATE.get("tools_expanded", False)
                    collapsed = self._render_result(func_name, arguments, result, color, expand=False, print_to_console=not is_expanded)
                    if not result.startswith("Error") and not result.startswith("Pre-Commit Validation Failed"):
                        expanded = self._render_result(func_name, arguments, result, color, expand=True, print_to_console=is_expanded)
                        self.last_tool_collapsed_text = collapsed
                        self.last_tool_expanded_text = expanded
                        self.last_tool_state = "expanded" if is_expanded else "collapsed"
                        self.last_tool_lines = len(expanded.splitlines()) if is_expanded else len(collapsed.splitlines())
                    else:
                        self.last_tool_collapsed_text = ""
                        self.last_tool_expanded_text = ""
                        self.last_tool_state = None
                        self.last_tool_lines = 0
                    return result
            except Exception as e:
                # Erase the running line first
                try:
                    width = self.console.size.width
                except Exception:
                    width = 80
                import math
                num_lines = math.ceil(getattr(self, "_last_running_indicator_len", 40) / max(1, width))
                for _ in range(num_lines):
                    self.console.print("\033[F\033[K", end="")
                self.console.print(Panel(
                    Text(f"Error executing MCP tool {func_name}: {str(e)}", style="red"),
                    border_style="red", padding=(0, 1),
                ))
                return f"Error executing MCP tool {func_name}: {str(e)}"

        from utim_cli.tools import get_tools
        utim_tools, tool_functions = get_tools()
        if func_name not in tool_functions:
            # Check if it's an MCP tool registered by name only (no __ prefix)
            if func_name in self.mcp_tool_names:
                mcp_args = {k: v for k, v in arguments.items() if not k.startswith("_")}
                return self._execute_mcp_tool(func_name, mcp_args)
            return f"Error: The tool '{func_name}' does not exist or is not available in the current context."

        display_arg = self._get_display_arg(func_name, arguments)

        # ── Capture before-state for /rewind tracking ─────────────────────────
        _rewind_entry: Optional[Dict[str, Any]] = None
        _modifying = ("write_file", "edit_file", "delete_file", "move_file")
        if func_name in _modifying:
            path = arguments.get("filepath", arguments.get("path",
                   arguments.get("dst", arguments.get("destination", ""))))
            if func_name == "write_file":
                _rewind_entry = {"action": func_name, "path": path, "before": None, "after": None}
            elif func_name in ("edit_file", "delete_file"):
                before = ""
                try:
                    with open(path, "r", encoding="utf-8") as _rf:
                        before = _rf.read()
                except Exception:
                    pass
                _rewind_entry = {"action": func_name, "path": path, "before": before, "after": None}
            elif func_name == "move_file":
                src = arguments.get("src", arguments.get("source", ""))
                dst = arguments.get("dst", arguments.get("destination", ""))
                # Capture source content before the move, and note whether src existed
                src_content = None
                src_existed = os.path.exists(src)
                if src_existed:
                    try:
                        with open(src, "r", encoding="utf-8") as _sf:
                            src_content = _sf.read()
                    except Exception:
                        src_existed = False
                _rewind_entry = {
                    "action": "move_file",
                    "path": dst,            # destination path (where file will end up)
                    "before_path": src,     # original source path
                    "before": src_content,  # content of source before move (if existed)
                    "before_existed": src_existed,
                    "after": None,
                }

        # For write_file: read old content before overwriting so we can diff later
        if func_name == "write_file":
            filepath = arguments.get("filepath", arguments.get("path", ""))
            try:
                with open(filepath, "r", encoding="utf-8") as _f:
                    arguments["_old_content"] = _f.read()
            except Exception:
                arguments["_old_content"] = None  # File didn't exist before (will trigger deletion on rewind)
            if _rewind_entry:
                _rewind_entry["before"] = arguments["_old_content"]

        # write_file doesn't accept _old_content — strip private keys before calling
        call_args = {k: v for k, v in arguments.items() if not k.startswith("_")}

        # ── Manual-mode confirmation ──────────────────────────────────────────
        _user_confirmed = False
        _CONFIRM_TOOLS = ("write_file", "edit_file", "delete_file", "move_file", "run_command")
        if func_name in _CONFIRM_TOOLS:
            _confirm_fn = self._get_confirm_fn()
            if _confirm_fn is not None:
                # Build compact diff lines for the dialog preview
                _diff_preview: list = []
                if func_name == "edit_file":
                    repls = arguments.get("replacements")
                    if repls and isinstance(repls, list):
                        for r_idx, r in enumerate(repls[:3]):
                            o_str = r.get("old_str", "") or ""
                            n_str = r.get("new_str", "") or ""
                            _diff_preview.append(f"--- Replacement #{r_idx+1} ---")
                            for _l in o_str.splitlines()[:2]:
                                _diff_preview.append(f"- {_l}")
                            for _l in n_str.splitlines()[:2]:
                                _diff_preview.append(f"+ {_l}")
                        if len(repls) > 3:
                            _diff_preview.append(f"... and {len(repls) - 3} more replacements")
                    else:
                        old_str = arguments.get("old_str", "") or ""
                        new_str = arguments.get("new_str", "") or ""
                        for _l in old_str.splitlines()[:5]:
                            _diff_preview.append(f"- {_l}")
                        for _l in new_str.splitlines()[:5]:
                            _diff_preview.append(f"+ {_l}")
                elif func_name == "write_file":
                    import difflib as _dl
                    old_c = arguments.get("_old_content") or ""
                    new_c = arguments.get("content", "")
                    _diff_preview = [
                        ln for ln in list(_dl.unified_diff(
                            old_c.splitlines(), new_c.splitlines(), lineterm="",
                        ))[:15]
                        if not ln.startswith("---") and not ln.startswith("+++")
                    ]
                _decision = _confirm_fn(func_name, arguments, _diff_preview)
                if _decision == "reject":
                    return f"[User rejected {func_name}. Do NOT retry this action — ask the user what they want instead.]"
                # 'allow' or 'allow_session' → user saw and approved the diff
                _user_confirmed = True
            else:
                # Fallback to standard CLI stdin/stdout prompt if in interactive shell
                import sys
                from rich.prompt import Confirm
                if sys.stdin.isatty():
                    self.console.print(f"\n[bold yellow]⬡ Approval Required for {func_name}:[/bold yellow]")
                    if func_name == "run_command":
                        cmd = arguments.get("command") or arguments.get("commands")
                        self.console.print(f"  Command: [bold white]{cmd}[/bold white]")
                    elif func_name in ("write_file", "edit_file", "delete_file", "move_file"):
                        filepath = arguments.get("filepath") or arguments.get("src") or arguments.get("dst")
                        self.console.print(f"  File Action: [bold white]{func_name} on {filepath}[/bold white]")
                        import difflib as _dl
                        old_c = arguments.get("_old_content") or ""
                        new_c = arguments.get("content", "")
                        if func_name == "edit_file":
                            repls = arguments.get("replacements")
                            if repls and isinstance(repls, list):
                                for r in repls[:2]:
                                    self.console.print(f"    - Replace: [red]{repr(r.get('old_str'))}[/red] with [green]{repr(r.get('new_str'))}[/green]")
                            else:
                                old_c = arguments.get("old_str", "") or ""
                                new_c = arguments.get("new_str", "") or ""
                        if func_name == "write_file" or (func_name == "edit_file" and not arguments.get("replacements")):
                            diff_lines = list(_dl.unified_diff(
                                old_c.splitlines(), new_c.splitlines(), lineterm=""
                            ))[:10]
                            for dl in diff_lines:
                                if dl.startswith("+"):
                                    self.console.print(f"    [green]{dl}[/green]")
                                elif dl.startswith("-"):
                                    self.console.print(f"    [red]{dl}[/red]")
                                else:
                                    self.console.print(f"    {dl}")
                    
                    if not Confirm.ask("Do you want to proceed?"):
                        self.console.print("[bold red]✗ Execution cancelled by user.[/bold red]")
                        return f"[User rejected {func_name}. Do NOT retry this action — ask the user what they want instead.]"

        # ── invoke_subagents — parallel nested subagent execution ─────────────
        # Dispatched here (not via the generic tool table) because it needs
        # session context: model_id, console, cancel_event, current depth.
        #
        # Nesting is now SUPPORTED up to MAX_NEST_DEPTH (default 4).
        # Each subagent can have its own:
        #   model, context window, system prompt, tools, permissions,
        #   MCP servers, and persistent ChromaDB memory collection.
        if func_name == "invoke_subagents":
            from utim_cli.subagent_manager import (
                SubAgentTask, SubAgentManager, format_subagent_results, MAX_NEST_DEPTH
            )

            current_depth = getattr(self, "_subagent_depth", 0)
            max_depth     = getattr(self, "_subagent_max_depth", MAX_NEST_DEPTH)

            # Hard ceiling guard
            if current_depth >= MAX_NEST_DEPTH:
                return (
                    f"[invoke_subagents blocked] Maximum nesting depth ({MAX_NEST_DEPTH}) reached. "
                    f"Complete your task directly using the tools available to you."
                )

            # Per-agent configurable depth guard
            if current_depth >= max_depth:
                return (
                    f"[invoke_subagents blocked] This subagent's max_depth ({max_depth}) "
                    f"does not permit further nesting. Complete your task directly."
                )

            tasks_raw = arguments.get("tasks", [])
            if not isinstance(tasks_raw, list) or not tasks_raw:
                return "[invoke_subagents error] 'tasks' must be a non-empty array."

            tasks = []
            for t in tasks_raw:
                if not isinstance(t, dict):
                    continue
                tasks.append(SubAgentTask(
                    task_id           = str(t.get("task_id", f"task-{len(tasks)+1}")),
                    role              = str(t.get("role", "Subagent")),
                    system_prompt     = str(t.get("system_prompt", "")),
                    user_prompt       = str(t.get("user_prompt", "")),
                    model_id          = str(t.get("model_id", "") or self.model_id),
                    max_iterations    = int(t.get("max_iterations", 20)),
                    timeout_seconds   = int(t.get("timeout_seconds", 300)),
                    # Per-agent capabilities (new in v2.3.0)
                    allowed_tools     = list(t.get("allowed_tools", [])),
                    blocked_tools     = list(t.get("blocked_tools", [])),
                    permission        = str(t.get("permission", "full")),
                    mcp_servers       = list(t.get("mcp_servers", [])),
                    memory_collection = str(t.get("memory_collection", "")),
                    max_depth         = int(t.get("max_depth", MAX_NEST_DEPTH)),
                    context_limit     = int(t.get("context_limit", 0)),
                ))

            if not tasks:
                return "[invoke_subagents error] No valid tasks found in 'tasks' array."

            manager = SubAgentManager(
                parent_model=self.model_id,
                console=self.console,
                cancel_event=self.cancel_event,
                current_depth=current_depth,
            )
            results = manager.run_parallel(tasks)
            return format_subagent_results(results)

        # ── Silent tools: skip all visual output ─────────────────────────────
        _SILENT_TOOLS = {"manage_memory", "recall_experience", "store_experience"}
        if func_name in _SILENT_TOOLS:
            try:
                utim_tools, tool_functions = get_tools()
                result = tool_functions[func_name](**call_args)
            except Exception as exc:
                result = f"Error executing {func_name}: {exc}"
            self.tool_results.append({
                "func_name": func_name,
                "arguments": arguments,
                "result": str(result),
                "color": color
            })
            return str(result)

        # Print a single static "running" line so the user knows which tool
        # is executing. We intentionally avoid Rich Live/Spinner here because
        # it animates at 12 fps and conflicts with prompt_toolkit's own redraws,
        # causing the double-spinner glitch and constant screen flicker.
        # Antigravity-style: ● Verb(path) (ctrl+o to expand)
        _display_name = self.TOOL_DISPLAY_NAME.get(func_name, func_name)
        _pre = Text()
        _pre.append(_display_name, style="bold white")
        if display_arg:
            _pre.append(f"({display_arg})", style="dim white")
        _pre.append(" (ctrl+o to expand)", style="dim #585b70")
        pre_plain = f"{_display_name}({display_arg}) (ctrl+o to expand)" if display_arg else f"{_display_name} (ctrl+o to expand)"
        self._last_running_indicator_len = len(pre_plain)

        try:
            # Dynamically update the thinking indicator so it shows what tool is running
            original_topic = "Thinking..."
            try:
                from utim_cli.state import STATE
                import os
                original_topic = STATE.get("thinking_topic", "Thinking...")
                
                if func_name == "run_command":
                    cmd = arguments.get("command", display_arg)
                    if len(cmd) > 30: cmd = cmd[:27] + "..."
                    STATE["thinking_topic"] = f"Running: {cmd}"
                elif func_name == "plan_project":
                    STATE["thinking_topic"] = f"Architecting {arguments.get('plan_part', 'project')}..."
                elif func_name == "search_web":
                    q = arguments.get("query", "")
                    if len(q) > 25: q = q[:22] + "..."
                    STATE["thinking_topic"] = f"Searching web for '{q}'..."
                elif func_name == "read_file":
                    STATE["thinking_topic"] = f"Reading {os.path.basename(arguments.get('filepath', 'file'))}..."
                elif func_name == "write_file":
                    STATE["thinking_topic"] = f"Writing to {os.path.basename(arguments.get('filepath', 'file'))}..."
                elif func_name in ("edit_file", "multi_replace_file_content"):
                    STATE["thinking_topic"] = f"Editing {os.path.basename(arguments.get('filepath', 'file'))}..."
                else:
                    STATE["thinking_topic"] = f"Executing {func_name}..."
            except Exception:
                pass

            try:
                import inspect
                utim_tools, tool_functions = get_tools()
                func = tool_functions[func_name]
                sig = inspect.signature(func)

                # ── Argument aliasing: remap common LLM hallucinations ─────────
                # Maps (func_name, wrong_key) → correct_key
                _ARG_ALIASES = {
                    # analyze_image: model sometimes uses 'path' instead of 'image_path'
                    ("analyze_image", "path"):      "image_path",
                    ("analyze_image", "file"):      "image_path",
                    ("analyze_image", "filepath"):  "image_path",
                    ("analyze_image", "question"):  "prompt",
                    ("analyze_image", "query"):     "prompt",
                    # plan_project: model sometimes uses 'query'/'text' instead of 'prompt'
                    ("plan_project", "query"):      "prompt",
                    ("plan_project", "text"):       "prompt",
                    ("plan_project", "type"):       "plan_part",
                    ("plan_project", "domain"):     "plan_part",
                    # read_file: model sometimes uses 'path' or 'file'
                    ("read_file", "path"):          "filepath",
                    ("read_file", "file"):          "filepath",
                    ("read_file", "filename"):      "filepath",
                    ("read_file", "start"):         "start_line",
                    ("read_file", "end"):           "end_line",
                    ("read_file", "from_line"):     "start_line",
                    ("read_file", "to_line"):       "end_line",
                    # write_file / edit_file: model sometimes uses other key names
                    ("write_file", "path"):         "filepath",
                    ("write_file", "file"):         "filepath",
                    ("write_file", "filename"):     "filepath",
                    ("write_file", "dest"):         "filepath",
                    ("write_file", "code"):         "content",
                    ("write_file", "text"):         "content",
                    ("write_file", "body"):         "content",
                    ("write_file", "data"):         "content",
                    ("write_file", "contents"):     "content",
                    ("write_file", "payload"):      "content",
                    ("write_file", "value"):        "content",
                    ("write_file", "src"):          "filepath",
                    ("write_file", "target"):       "filepath",
                    ("edit_file", "path"):          "filepath",
                    ("edit_file", "file"):          "filepath",
                    ("edit_file", "filename"):      "filepath",
                    # run_command: model sometimes uses 'cmd' or 'CommandLine'
                    ("run_command", "cmd"):              "command",
                    ("run_command", "shell"):            "command",
                    ("run_command", "script"):           "command",
                    ("run_command", "CommandLine"):      "command",
                    ("run_command", "commandLine"):      "command",
                    ("run_command", "command_line"):     "command",
                    ("run_command", "cmd_line"):         "command",
                    ("run_command", "cwd"):              "dir_path",
                    ("run_command", "directory"):        "dir_path",
                    ("run_command", "folder"):           "dir_path",
                    ("run_command", "path"):             "dir_path",
                    ("run_command", "background"):       "is_background",
                    ("run_command", "bg"):               "is_background",
                    ("run_command", "run_in_background"):"is_background",
                    # web_search: model sometimes uses 'prompt'
                    ("web_search", "prompt"):       "query",
                    ("web_search", "text"):         "query",
                }
                # Apply aliasing before filtering (don't overwrite existing correct keys)
                remapped = dict(call_args)
                for (fn, wrong_key), correct_key in _ARG_ALIASES.items():
                    if fn == func_name and wrong_key in remapped and correct_key not in remapped:
                        remapped[correct_key] = remapped.pop(wrong_key)

                # Filter out args not in the function signature
                has_var_keyword = any(p.kind == inspect.Parameter.VAR_KEYWORD for p in sig.parameters.values())
                if has_var_keyword:
                    filtered_args = dict(remapped)
                else:
                    filtered_args = {k: v for k, v in remapped.items() if k in sig.parameters}

                # Check for missing required positional args — try to fill from leftover values.
                # Order: filepath FIRST (short string, usually looks like a path),
                #        content SECOND (longest string, usually the body).
                missing_required = [
                    name for name, param in sig.parameters.items()
                    if param.default is inspect.Parameter.empty
                    and param.kind not in (inspect.Parameter.VAR_KEYWORD, inspect.Parameter.VAR_POSITIONAL)
                    and name not in filtered_args
                ]
                if missing_required:
                    leftover_values = sorted(
                        [v for k, v in call_args.items()
                         if k not in filtered_args and isinstance(v, str)],
                        key=lambda s: len(s),
                    )
                    # Prefer to fill 'filepath' with the shortest leftover (paths are short)
                    ordered_missing = sorted(
                        missing_required,
                        key=lambda n: (0 if n == "filepath" else 1),
                    )
                    for req_name in ordered_missing:
                        if leftover_values:
                            # For filepath, pop the SHORTEST leftover; for everything else, the LONGEST.
                            if req_name == "filepath":
                                filtered_args[req_name] = leftover_values.pop(0)
                            else:
                                filtered_args[req_name] = leftover_values.pop()

                # Final guard: if anything required is still missing, surface a clean error
                # instead of letting TypeError bubble out of func(**filtered_args).
                still_missing = [
                    name for name, param in sig.parameters.items()
                    if param.default is inspect.Parameter.empty
                    and param.kind not in (inspect.Parameter.VAR_KEYWORD, inspect.Parameter.VAR_POSITIONAL)
                    and name not in filtered_args
                ]
                if still_missing:
                    # ── Auto-recovery: if the LLM emitted empty args (raw_args == '{}'),
                    #    try to recover 'filepath' from recent tool-call history.
                    #    This handles the common case where the model forgets to pass
                    #    arguments on follow-up calls (e.g. "read that file again").
                    if "filepath" in still_missing and not call_args:
                        try:
                            if not hasattr(self, "_recent_filepaths"):
                                from collections import deque
                                self._recent_filepaths = deque(maxlen=20)
                            if self._recent_filepaths:
                                _recovered = self._recent_filepaths[-1]
                                filtered_args["filepath"] = _recovered
                                still_missing = [n for n in still_missing if n != "filepath"]
                        except Exception:
                            pass
                if still_missing:
                    _raw_preview = (raw_args or "")[:200]
                    result = (
                        f"Error executing tool {func_name}: missing required "
                        f"arg(s) {still_missing}. Got keys={sorted(filtered_args.keys())}, "
                        f"raw call_args keys={sorted(call_args.keys())}. "
                        f"raw_args preview={repr(_raw_preview)}. "
                        f"Check _ARG_ALIASES['{func_name}'] or the tool-call parser."
                    )
                else:
                    # Track successful filepath usage for future auto-recovery
                    if "filepath" in filtered_args and isinstance(filtered_args["filepath"], str):
                        try:
                            if not hasattr(self, "_recent_filepaths"):
                                from collections import deque
                                self._recent_filepaths = deque(maxlen=20)
                            self._recent_filepaths.append(filtered_args["filepath"])
                        except Exception:
                            pass
                    result = func(**filtered_args)
            except TypeError as e:
                import traceback
                result = (
                    f"Error executing tool {func_name}: {e}\n"
                    f"Args provided: {sorted(filtered_args.keys())}\n"
                    f"{traceback.format_exc()}"
                )
            except Exception as e:
                import traceback
                result = f"Error executing tool {func_name}: {e}\n{traceback.format_exc()}"

            
            # Restore the indicator to evaluating logic
            try:
                STATE["thinking_topic"] = "Evaluating tool results..."
            except Exception:
                pass
        except Exception as exc:
            # Erase the running line first
            try:
                width = self.console.size.width
            except Exception:
                width = 80
            import math
            num_lines = math.ceil(getattr(self, "_last_running_indicator_len", 40) / max(1, width))
            for _ in range(num_lines):
                self.console.print("\033[F\033[K", end="")
            self.console.print(Panel(
                Text(str(exc), style="red"),
                title=Text(f"✗  {func_name}", style=f"bold red"),
                title_align="left",
                border_style="red",
                padding=(0, 1),
            ))
            return f"Error executing {func_name}: {exc}"

        # Record after-state for rewind tracking
        if _rewind_entry:
            if func_name == "delete_file":
                _rewind_entry["after"] = None  # file no longer exists
            elif func_name == "move_file":
                # After move: destination exists with content, source is gone
                try:
                    with open(_rewind_entry["path"], "r", encoding="utf-8") as _af:
                        _rewind_entry["after"] = _af.read()
                except Exception:
                    _rewind_entry["after"] = None
                # Note: we don't need to track source's after state because it's gone
            else:
                try:
                    with open(_rewind_entry["path"], "r", encoding="utf-8") as _af:
                        _rewind_entry["after"] = _af.read()
                except Exception:
                    _rewind_entry["after"] = None
            self._turn_changes.append(_rewind_entry)

        # Render the result panel (compact if user already approved via dialog)
        from utim_cli.state import STATE
        is_expanded = STATE.get("tools_expanded", False)
        collapsed = self._render_result(func_name, arguments, str(result), color, user_confirmed=_user_confirmed, expand=False, print_to_console=not is_expanded)
        if not str(result).startswith("Error") and not str(result).startswith("Pre-Commit Validation Failed"):
            expanded = self._render_result(func_name, arguments, str(result), color, user_confirmed=_user_confirmed, expand=True, print_to_console=is_expanded)
            self.last_tool_collapsed_text = collapsed
            self.last_tool_expanded_text = expanded
            self.last_tool_state = "expanded" if is_expanded else "collapsed"
            self.last_tool_lines = len(expanded.splitlines()) if is_expanded else len(collapsed.splitlines())
        else:
            self.last_tool_collapsed_text = ""
            self.last_tool_expanded_text = ""
            self.last_tool_state = None
            self.last_tool_lines = 0

        self.tool_results.append({
            "func_name": func_name,
            "arguments": arguments,
            "result": str(result),
            "color": color
        })

        return str(result)

    def _execute_tools_parallel(self, tool_calls: List[Dict]) -> List[Tuple[Dict, str]]:
        """Execute multiple tool calls in parallel when possible.
        
        Groups tools by dependency type and executes independent tools concurrently.
        Tools that modify files (write_file, edit_file, delete_file) are executed
        sequentially to avoid conflicts.
        
        Returns list of (tool_call, result) tuples in original order.
        """
        # Tools that can be safely executed in parallel (read-only operations)
        PARALLEL_SAFE = {"read_file", "list_directory", "grep_search", "search", "web_search", 
                         "plan_project", "manage_todos", "manage_memory",
                         "analyze_image", "generate_image",
                         "invoke_subagents"}  # manages its own internal thread pool
        
        # Tools that must be sequential (modify state)
        SEQUENTIAL = {"write_file", "edit_file", "delete_file", "run_command",
                      "move_file"}
        
        # Build list of (original_index, tool_call, is_parallel) for ordering
        indexed_calls = []
        for i, tc in enumerate(tool_calls):
            func_name = tc.get("function", {}).get("name", "")
            is_parallel = func_name in PARALLEL_SAFE
            indexed_calls.append((i, tc, is_parallel))
        
        parallel_calls = [(i, tc) for i, tc, is_par in indexed_calls if is_par]
        sequential_calls = [(i, tc) for i, tc, is_par in indexed_calls if not is_par]
        
        results = [None] * len(tool_calls)  # Pre-allocate to preserve order
        
        # Execute parallel-safe tools concurrently
        if parallel_calls:
            executor = ThreadPoolExecutor(max_workers=min(len(parallel_calls), 8))
            try:
                future_to_idx = {executor.submit(self._execute_tool_timed, tc): (orig_idx, tc) 
                                for orig_idx, tc in parallel_calls}
                
                for future in as_completed(future_to_idx):
                    if self.cancel_event.is_set():
                        executor.shutdown(wait=False, cancel_futures=True)
                        break
                    orig_idx, tc = future_to_idx[future]
                    try:
                        result = future.result()
                        results[orig_idx] = (tc, result)
                    except Exception as e:
                        func_name = tc.get("function", {}).get("name", "unknown")
                        results[orig_idx] = (tc, f"Error executing {func_name}: {e}")
            finally:
                executor.shutdown(wait=False, cancel_futures=True)
        
        # Execute sequential tools one by one, placing in correct positions
        for orig_idx, tc in sequential_calls:
            if self.cancel_event.is_set():
                results[orig_idx] = (tc, "[Aborted by user]")
                continue
            _tools_module._cancel_event = self.cancel_event
            _tools_module._active_model_id = self.model_id
            result = self._execute_tool_timed(tc)
            self._current_line_len = 0
            results[orig_idx] = (tc, result)
        
        return results

    # ── Rewind support ────────────────────────────────────────────────────────

    @staticmethod
    def _change_stats(changes: List[Dict]) -> str:
        """Return a '+N -M lines' summary for a list of changes."""
        add_total = del_total = 0
        for ch in changes:
            before = ch.get("before") or ""
            after  = ch.get("after")  or ""
            b_lines = before.splitlines()
            a_lines = after.splitlines()
            # Simple heuristic: added = lines only in after, removed = lines only in before
            b_set = set(b_lines); a_set = set(a_lines)
            add_total += len(a_lines) - len([l for l in a_lines if l in b_set])
            del_total += len(b_lines) - len([l for l in b_lines if l in a_set])
        n_files = len({ch["path"] for ch in changes})
        parts = []
        if n_files:
            parts.append(f"{n_files} file{'s' if n_files != 1 else ''} changed")
        if add_total:
            parts.append(f"[bold green]+{add_total}[/bold green]")
        if del_total:
            parts.append(f"[bold red]-{del_total}[/bold red]")
        return "  ".join(parts) if parts else "No files changed"

    def rewind_single_turn(self, turn_idx: int, revert_code: bool = True,
                           revert_msgs: bool = True) -> Dict[str, Any]:
        """Rewind only a single turn (not all subsequent turns)."""
        if turn_idx >= len(self.turn_history):
            return {"reverted": [], "errors": []}
        
        turn = self.turn_history[turn_idx]
        res: Dict[str, Any] = {"reverted": [], "errors": []}

        if revert_code:
            # Revert code changes for this turn only
            for ch in reversed(turn["changes"]):
                path = ch["path"]
                try:
                    if ch["action"] == "move_file":
                        src = ch["before_path"]
                        if os.path.exists(path):
                            os.makedirs(os.path.dirname(os.path.abspath(src)), exist_ok=True)
                            shutil.move(path, src)
                        res["reverted"].append(f"{path} → {src}")
                    elif ch.get("before") is None:
                        # File was created (or didn't exist) — delete it if it exists now
                        if os.path.exists(path):
                            os.remove(path)
                        res["reverted"].append(path)
                    else:
                        os.makedirs(
                            os.path.dirname(os.path.abspath(path)), exist_ok=True
                        )
                        with open(path, "w", encoding="utf-8") as wf:
                            wf.write(ch["before"])
                        res["reverted"].append(path)
                except Exception as e:
                    res["errors"].append(f"{path}: {e}")

        if revert_msgs:
            # Remove messages for this turn only
            msg_start = turn["msg_start"]
            msg_end = turn["msg_end"]
            res["msgs_removed"] = msg_end - msg_start
            
            # Remove the messages for this turn
            self.messages = self.messages[:msg_start] + self.messages[msg_end:]
            
            # Update msg_start and msg_end for all subsequent turns
            msgs_removed = msg_end - msg_start
            for i in range(turn_idx + 1, len(self.turn_history)):
                self.turn_history[i]["msg_start"] -= msgs_removed
                self.turn_history[i]["msg_end"] -= msgs_removed
            
            # Remove this turn from history and add it to redo history
            undone_turn = self.turn_history.pop(turn_idx)
            if not hasattr(self, "redo_history"):
                self.redo_history = []
            self.redo_history.append(undone_turn)

        return res

    def rewind_to_turn(self, turn_idx: int, revert_code: bool = True,
                       revert_msgs: bool = True) -> Dict[str, Any]:
        """Revert everything from turn_idx onward."""
        turns = self.turn_history[turn_idx:]
        res: Dict[str, Any] = {"reverted": [], "errors": []}
        if not turns:
            return res

        if revert_code:
            # We want to restore each file to its state BEFORE the oldest turn in `turns`
            # So we traverse `turns` chronologically (forward). The first change we see for a file
            # represents its state before the reverted range began.
            file_targets = {}
            for turn in turns:
                for ch in turn["changes"]:
                    path = ch["path"]
                    if path not in file_targets:
                        file_targets[path] = ch

            for path, ch in file_targets.items():
                try:
                    if ch["action"] == "move_file":
                        src = ch["before_path"]
                        if os.path.exists(path):
                            os.makedirs(os.path.dirname(os.path.abspath(src)), exist_ok=True)
                            shutil.move(path, src)
                        res["reverted"].append(f"{path} → {src}")
                    elif ch.get("before") is None:
                        # File was created (or didn't exist) — delete it if it exists now
                        if os.path.exists(path):
                            os.remove(path)
                        res["reverted"].append(path)
                    else:
                        os.makedirs(
                            os.path.dirname(os.path.abspath(path)), exist_ok=True
                        )
                        with open(path, "w", encoding="utf-8") as wf:
                            wf.write(ch["before"])
                        res["reverted"].append(path)
                except Exception as e:
                    res["errors"].append(f"{path}: {e}")

        if revert_msgs:
            target = turns[0]["msg_start"]
            res["msgs_removed"] = len(self.messages) - target
            self.messages = self.messages[:target]
            
            # Push all popped turns onto redo_history in reverse order (so popping redos in original forward order!)
            if not hasattr(self, "redo_history"):
                self.redo_history = []
            for t in reversed(turns):
                self.redo_history.append(t)
                
            self.turn_history = self.turn_history[:turn_idx]

        return res

    def undo_last_turn(self) -> Dict[str, Any]:
        """Undo the very last turn (conversation + code changes)."""
        if not self.turn_history:
            return {"reverted": [], "errors": ["No turns to undo."]}
        
        last_idx = len(self.turn_history) - 1
        res = self.rewind_single_turn(last_idx, revert_code=True, revert_msgs=True)
        self._persist_messages()
        return res

    def redo_last_undone_turn(self) -> Dict[str, Any]:
        """Redo the most recently undone turn."""
        if not hasattr(self, "redo_history") or not self.redo_history:
            return {"reverted": [], "errors": ["No undone turns to redo."]}
            
        turn = self.redo_history.pop()
        res: Dict[str, Any] = {"redone_code": [], "errors": []}
        
        # Redo code changes
        for ch in turn.get("changes", []):
            path = ch["path"]
            action = ch["action"]
            try:
                if action == "move_file":
                    src = ch["before_path"]
                    if os.path.exists(src):
                        os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
                        shutil.move(src, path)
                    res["redone_code"].append(f"{src} → {path}")
                elif ch.get("after") is None:
                    # File was deleted
                    if os.path.exists(path):
                        os.remove(path)
                    res["redone_code"].append(f"deleted {path}")
                else:
                    # File was written/edited
                    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
                    with open(path, "w", encoding="utf-8") as wf:
                        wf.write(ch["after"])
                    res["redone_code"].append(path)
            except Exception as e:
                res["errors"].append(f"{path}: {e}")
                
        # Redo messages: append them back
        msg_start = len(self.messages)
        messages_to_add = turn.get("messages", [])
        self.messages.extend(messages_to_add)
        msg_end = len(self.messages)
        
        # Reconstruct the turn entry and append back to turn_history
        turn["msg_start"] = msg_start
        turn["msg_end"] = msg_end
        self.turn_history.append(turn)
        
        # Persist messages and redo history to DB
        self._persist_messages()
        return res

    def redo_up_to_turn(self, redo_idx: int) -> Dict[str, Any]:
        """Redo all undone turns from index 0 up to redo_idx (inclusive)."""
        if not hasattr(self, "redo_history") or not self.redo_history or redo_idx >= len(self.redo_history):
            return {"reverted": [], "errors": ["No undone turns to redo."]}
            
        # Get the slice of turns to redo
        turns_to_redo = self.redo_history[:redo_idx + 1]
        # Keep the remaining undone turns
        self.redo_history = self.redo_history[redo_idx + 1:]
        
        res: Dict[str, Any] = {"redone_code": [], "errors": []}
        
        # Redo them in order
        for turn in turns_to_redo:
            # Redo code changes
            for ch in turn.get("changes", []):
                path = ch["path"]
                action = ch["action"]
                try:
                    if action == "move_file":
                        src = ch["before_path"]
                        if os.path.exists(src):
                            os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
                            shutil.move(src, path)
                        res["redone_code"].append(f"{src} → {path}")
                    elif ch.get("after") is None:
                        if os.path.exists(path):
                            os.remove(path)
                        res["redone_code"].append(f"deleted {path}")
                    else:
                        os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
                        with open(path, "w", encoding="utf-8") as wf:
                            wf.write(ch["after"])
                        res["redone_code"].append(path)
                except Exception as e:
                    res["errors"].append(f"{path}: {e}")
                    
            # Redo messages: append them back
            msg_start = len(self.messages)
            messages_to_add = turn.get("messages", [])
            self.messages.extend(messages_to_add)
            msg_end = len(self.messages)
            
            # Reconstruct the turn entry and append back to turn_history
            turn["msg_start"] = msg_start
            turn["msg_end"] = msg_end
            self.turn_history.append(turn)
            
        self._persist_messages()
        return res

    # ── Context compression ──────────────────────────────────────────────────

    @staticmethod
    def _estimate_tokens(obj) -> int:
        """Rough token count: 1 token ≈ 4 chars of serialised JSON."""
        try:
            return len(json.dumps(obj, ensure_ascii=False)) // 4
        except Exception:
            return len(str(obj)) // 4

    def _get_dynamic_threshold(self) -> int:
        """Get dynamic compression threshold based on current model's context window."""
        try:
            from .server.models import get_model
            model_entry = get_model(self.model_id)
            return _get_compression_threshold(self.model_id, model_entry.context_window)
        except Exception:
            # Fallback to safe default if model registry unavailable
            return 65_000

    def _get_dynamic_interval(self) -> int:
        """Get iteration context compression interval (every 35 iterations)."""
        return 35

    
    def _get_iteration_budget(self) -> int:
        """Return the max iteration budget for the current model, scaled by context window.

        Uses the SAME 4-tier buckets as _get_compression_interval:
          - < 200k context:        budget = 25 (small / local models)
          - 200k - 500k context:   budget = 35
          - 500k - 1M context:     budget = 40
          - 1M+ context:           budget = 45 (Llama 4 Scout, Gemini 2.5 Pro)
        """
        try:
            from .server.models import get_model
            model_entry = get_model(self.model_id)
            cw = int(getattr(model_entry, "context_window", 0) or 0)
        except Exception:
            cw = 128_000
        if cw < 200_000:
            return 25
        if cw < 500_000:
            return 35
        if cw < 1_000_000:
            return 40
        return 45

    def _get_iteration_milestones(self) -> tuple:
        """Return (budget, halfway, last5, grant_extra) for current model."""
        budget = self._get_iteration_budget()
        halfway = max(1, budget // 2)
        last_5 = max(1, budget - 5)
        grant_extra = budget
        return budget, halfway, last_5, grant_extra

    def set_model(self, new_model_id: str) -> None:
        """Set active model ID and instantly update compression threshold and interval."""
        self._update_model_threshold(new_model_id)

    def _update_model_threshold(self, new_model_id: str) -> None:
        """Update compression threshold and interval when model changes."""
        self.model_id = new_model_id
        self._compression_threshold = self._get_dynamic_threshold()
        self._compression_interval = self._get_dynamic_interval()

    def _trigger_bg_summarization(self) -> None:
        """Background thread to compress turns older than KEEP_FULL_TURNS into a rolling LLM summary."""
        if not hasattr(self, "_llm_summary"):
            self._llm_summary = ""
            self._summarized_turns = 0
            self._summarizing = False

        if self._summarizing:
            return

        completed = self.turn_history
        unsummarized = len(completed) - self._summarized_turns

        # Only summarize if there are turns falling OUTSIDE the KEEP_FULL_TURNS window
        if unsummarized > KEEP_FULL_TURNS:
            turns_to_summarize = unsummarized - KEEP_FULL_TURNS
            turns_slice = completed[self._summarized_turns : self._summarized_turns + turns_to_summarize]
            current_summary = self._llm_summary

            self._summarizing = True

            def _summarize_task():
                try:
                    text_parts = []
                    for t in turns_slice:
                        req = t.get("user_msg", "").strip()
                        c_str = self._change_stats(t.get("changes", []))

                        # BUG 6 FIX: Read from the stored per-turn message snapshot
                        # instead of slicing self.messages with potentially stale
                        # absolute indices (which shift whenever _compress_intra_turn
                        # rewrites self.messages).
                        conclusion = ""
                        stored_msgs = t.get("messages", [])
                        if stored_msgs:
                            # Use the snapshot saved at turn-end
                            source_msgs = stored_msgs
                        else:
                            # Fallback: try live slice under lock
                            with self._messages_lock:
                                source_msgs = list(self.messages[t["msg_start"]: t["msg_end"]])
                        for m in source_msgs:
                            if m.get("role") == "assistant" and m.get("content"):
                                conclusion = m["content"].strip()

                        text_parts.append(f"User: {req}\nChanges: {c_str}\nAssistant: {conclusion}\n---")

                    raw_turns = "\n".join(text_parts)

                    sys_prompt = "You are a highly analytical AI core memory compressor. Your job is to compress conversational history into a dense, highly technical narrative paragraph. Retain all factual details, architectural decisions, file paths, and current project state. Do not use conversational filler."
                    
                    if current_summary:
                        user_prompt = f"Existing Memory Summary:\n{current_summary}\n\nNew Interactions to Merge:\n{raw_turns}\n\nUpdate the memory summary to incorporate these new interactions seamlessly. Return ONLY the new summary."
                    else:
                        user_prompt = f"New Interactions:\n{raw_turns}\n\nCreate a dense memory summary of these interactions. Return ONLY the summary."

                    # Use fallback model system from context_pruner
                    from utim_cli.context_pruner import _call_compression_model_with_fallback
                    new_summary = _call_compression_model_with_fallback(
                        messages=[
                            {"role": "system", "content": sys_prompt},
                            {"role": "user", "content": user_prompt}
                        ],
                        llm_key=self._local_api_key,
                        max_tokens=2000,
                        primary_model=self.model_id
                    )
                    
                    if new_summary:
                        self._llm_summary = new_summary
                        self._summarized_turns += len(turns_slice)
                        # Remove the old summarized messages from self.messages
                        # to prevent unbounded growth. Only remove messages that
                        # fall within the summarized turn range.
                        if turns_slice:
                            first_idx = turns_slice[0]["msg_start"]
                            last_idx  = turns_slice[-1]["msg_end"]
                            with self._messages_lock:
                                if last_idx <= len(self.messages):
                                    del self.messages[first_idx:last_idx]
                                    # Shift turn_history msg_start/msg_end pointers
                                    shift = last_idx - first_idx
                                    for t in self.turn_history:
                                        if t["msg_start"] >= last_idx:
                                            t["msg_start"] -= shift
                                            t["msg_end"]   -= shift
                                    # Also shift _current_turn_start if needed
                                    if self._current_turn_start >= last_idx:
                                        self._current_turn_start -= shift
                    else:
                        print(f"[WARNING] Context summarization returned None - all fallback models failed", file=sys.stderr)
                except Exception as e:
                    print(f"[ERROR] Context summarization failed: {e}", file=sys.stderr)
                finally:
                    self._summarizing = False

            import threading
            threading.Thread(target=_summarize_task, daemon=True).start()

    def _get_send_messages(self, turn_msg_start: Optional[int] = None) -> List[Dict]:
        """Return the context payload, injecting the rolling LLM summary (passive memory)
        and a dynamic active context checklist.

        Args:
            turn_msg_start: The absolute index in self.messages where the current
                user turn begins.  Passing this explicitly avoids relying on the
                stale self._current_turn_start class attribute, which can point to
                the wrong position after _compress_intra_turn rewrites self.messages.
        """
        # BUG 1 FIX: Prefer the caller-supplied index; fall back to the cached
        # attribute only when called from paths that haven't been updated yet.
        effective_turn_start = turn_msg_start if turn_msg_start is not None else self._current_turn_start

        # ── Safety trim: keep self.messages from growing unbounded ──────────
        # Even if the background summarization hasn't run yet, cap self.messages
        # to prevent memory bloat. Keep system prompt + last 199 messages (200 total).
        MAX_STORED_MSGS = 200
        with self._messages_lock:
            if len(self.messages) > MAX_STORED_MSGS:
                excess = len(self.messages) - MAX_STORED_MSGS
                # Keep system prompt (index 0) + newest MAX_STORED_MSGS-1 messages
                self.messages = [self.messages[0]] + self.messages[-(MAX_STORED_MSGS-1):]
                # Adjust effective_turn_start and _current_turn_start
                effective_turn_start = max(1, effective_turn_start - excess)
                self._current_turn_start = max(1, self._current_turn_start - excess)
                # Adjust turn_history pointers
                for t_entry in self.turn_history:
                    t_entry["msg_start"] = max(1, t_entry["msg_start"] - excess)
                    t_entry["msg_end"] = max(1, t_entry["msg_end"] - excess)

        with self._messages_lock:
            messages_snapshot = list(self.messages)

        system_msg = dict(messages_snapshot[0])

        # Extract current user prompt to perform dynamic keyword-based RAG search
        user_prompt = ""
        if effective_turn_start is not None and effective_turn_start < len(messages_snapshot):
            for m in messages_snapshot[effective_turn_start:]:
                if m.get("role") == "user":
                    user_prompt = m.get("content", "")
                    break

        # Reconstruct system prompt with prompt-relevant experiences
        task_elapsed = int(time.time() - getattr(self, "task_start_time", time.time()))
        task_iter = getattr(self, "current_iteration", 0)
        # If an @subagent tag is active, replace the system prompt entirely with the
        # subagent's custom system prompt (only the system prompt changes, nothing else).
        _active_tag_sp = getattr(self, "active_tag_system_prompt", None)
        if _active_tag_sp:
            system_msg["content"] = _active_tag_sp
        else:
            try:
                system_msg["content"] = get_system_prompt(user_prompt, task_iter, task_elapsed, self.turn_history, self.messages)
            except Exception:
                try:
                    system_msg["content"] = get_system_prompt(user_prompt, turn_history=self.turn_history, messages=self.messages)
                except Exception:
                    pass
        
        # Inject current timestamp so the model lives in the present
        from datetime import datetime
        current_ts = datetime.now().strftime("%A, %B %d, %Y at %I:%M %p")
        system_msg["content"] = f"Current date/time: {current_ts}\n\n" + system_msg["content"]
        
        # Exclude duration, temporal logs, consciousness state, and milestone reflections from message payload to keep it as a pure coding agent.

        

        # ── 1. ACTIVE CONTEXT CHECKLIST (Checklist-based Focus) ────────────────
        active_context = "\n\n### ACTIVE CONTEXT CHECKLIST:"

        # A. Find active file path dynamically from recent messages
        active_file = ""
        for msg in reversed(messages_snapshot):
            if msg.get("role") == "assistant" and msg.get("tool_calls"):
                for tc in msg["tool_calls"]:
                    func = tc.get("function", {})
                    if func.get("name") in ("write_file", "edit_file", "read_file"):
                        try:
                            args = json.loads(func.get("arguments", "{}"))
                            active_file = args.get("filepath", args.get("path", ""))
                            if active_file:
                                break
                        except Exception:
                            pass
                if active_file:
                    break
        if active_file:
            active_context += f"\n- **Current File**: {active_file}"

        # B. Get latest command status from the most recent run_command output
        last_command_output = ""
        for msg in reversed(messages_snapshot):
            if msg.get("role") == "tool" and msg.get("name") == "run_command":
                content = msg.get("content", "")
                lines = [l.strip() for l in content.splitlines() if l.strip()]
                if lines:
                    exit_code_line = next((l for l in lines if "exit_code:" in l), "")
                    err_lines = [l for l in lines if "error" in l.lower() or "failed" in l.lower() or "exception" in l.lower()]
                    last_command_output = f"Command exit: {exit_code_line or 'unknown'}"
                    if err_lines:
                        last_command_output += f" | Errors: {'; '.join(err_lines[:2])}"
                    else:
                        last_command_output += f" | Output: {'; '.join(lines[:2])}"
                    break
        if last_command_output:
            active_context += f"\n- **Latest Command Status**: {last_command_output}"

        # C. Read active todos from todos.json
        active_todo_checklist = ""
        todo_file = ".utim_tmp/todos.json"
        if os.path.exists(todo_file):
            try:
                with open(todo_file, "r", encoding="utf-8") as f:
                    todos = json.load(f)
                if todos and isinstance(todos, dict):
                    active_todo_checklist = "\n### ACTIVE TASK CHECKLIST:\n"
                    for tid, t in todos.items():
                        status_mark = "[x]" if t.get("status") == "done" else "[ ]"
                        active_todo_checklist += f"{status_mark} {t.get('description', '')}\n"
            except Exception:
                pass

        if active_todo_checklist:
            active_context += active_todo_checklist
        else:
            # BUG 7 FIX: Guard against effective_turn_start being out-of-bounds
            # after _compress_intra_turn shortens self.messages.  Without this
            # guard the IndexError is silently swallowed and the model gets no
            # active objective in its system prompt for the rest of the turn.
            if 0 < effective_turn_start < len(messages_snapshot):
                raw_content = messages_snapshot[effective_turn_start].get("content") or ""
                if isinstance(raw_content, list):
                    text_parts = []
                    for part in raw_content:
                        if isinstance(part, dict) and part.get("type") == "text":
                            text_parts.append(part.get("text", ""))
                    text_str = " ".join(text_parts)
                else:
                    text_str = str(raw_content)
                obj = text_str[:600]
                active_context += f"\n- **Active Objective**: {obj}..."

        system_msg["content"] += active_context

        # ── 2. PASSIVE MEMORY SUMMARY (Whole memory rollup) ───────────────────
        if getattr(self, "_llm_summary", ""):
            system_msg["content"] += "\n\n### PASSIVE MEMORY SUMMARY (Older events):\n" + self._llm_summary

        completed = self.turn_history
        n_full = max(0, len(completed) - getattr(self, "_summarized_turns", 0))
        recent = completed[-n_full:] if n_full > 0 else []

        if recent:
            rec_slice = messages_snapshot[recent[0]["msg_start"]: effective_turn_start]
        else:
            rec_slice = messages_snapshot[1: effective_turn_start]

        cur_msgs = messages_snapshot[effective_turn_start:]

        # ── Hard context-window cap ─────────────────────────────────────────
        # Prevent the send payload from ever exceeding the model's context window.
        # Strategy: always keep system_msg + all of cur_msgs (current turn),
        # then fill the remaining budget with recent rec_slice from newest to oldest.
        # This is the same sliding-window approach used by Claude Code and Cursor.
        HARD_TOKEN_CAP  = getattr(self, "_compression_threshold", 65_000)
        # Reserve ~20% for system prompt overhead + model output
        SEND_TOKEN_CAP  = int(HARD_TOKEN_CAP * 0.80)

        def _quick_token_est(msgs):
            try:
                return sum(len(json.dumps(m, ensure_ascii=False)) for m in msgs) // 4
            except Exception:
                return sum(len(str(m)) for m in msgs) // 4

        system_tokens  = _quick_token_est([system_msg])
        cur_tokens     = _quick_token_est(cur_msgs)
        budget_for_rec = max(0, SEND_TOKEN_CAP - system_tokens - cur_tokens)

        # Fill rec_slice from newest to oldest until budget exhausted
        trimmed_rec: list = []
        for rec_msg in reversed(rec_slice):
            t = _quick_token_est([rec_msg])
            if budget_for_rec - t < 0:
                break
            trimmed_rec.insert(0, rec_msg)
            budget_for_rec -= t

        from utim_cli.context_pruner import sanitize_message_sequence
        return sanitize_message_sequence([system_msg] + trimmed_rec + cur_msgs)

    # Main agentic loop

    def _compress_intra_turn(self, turn_msg_start: int, instruction: str = "") -> None:
        """Stable, synchronous compression of the current turn's tool calls if it gets too long or if requested.
        
        Uses importance-weighted pruning (score >= 0.75 = preserved verbatim) so that
        high-signal context such as file reads and error messages is carried forward
        in full, while low-signal chatter is condensed by a compression model.
        sanitize_message_sequence() is applied on the rebuilt list to keep
        assistant/tool-call pairs structurally intact.
        """
        # Compress any uncompressed skill files in the message history immediately
        for m in self.messages:
            if m.get("role") == "tool" and m.get("name") == "view_file":
                content = m.get("content", "")
                if isinstance(content, str) and "description:" in content and "---" in content[:200]:
                    import re as _re
                    match = _re.search(r"name:\s*([a-zA-Z0-9_-]+)", content)
                    skill_name = match.group(1) if match else "workspace skill"
                    
                    sys_prompt = (
                        "You are a technical context pruner. Compress this SKILL.md guide "
                        "into a dense, extremely compact summary of core design principles, HSL variables, "
                        "architectural rules, and syntax requirements (aim for 200-300 words total). "
                        "Do NOT drop HSL templates, critical rules, or exact variable names. No fluff."
                    )
                    from utim_cli.context_pruner import _call_compression_model_with_fallback
                    compressed = _call_compression_model_with_fallback(
                        messages=[
                            {"role": "system", "content": sys_prompt},
                            {"role": "user", "content": f"Skill Guide:\n{content}"}
                        ],
                        llm_key=self._local_api_key,
                        max_tokens=600,
                        content_hint=content[:500],
                        primary_model=self.model_id
                    )
                    if compressed:
                        m["content"] = f"### RELEVANT CORE SKILL: {skill_name.upper()} (COMPRESSED) ###\n{compressed}"

        current_turn_msgs = self.messages[turn_msg_start:]
        
        # We need at least 5 messages to justify compression
        if len(current_turn_msgs) < 5:
            return
            
        # If no explicit instruction is given, check multiple conditions for proactive compression:
        # 1. Token estimate > dynamic threshold (based on model's context window)
        # 2. Message count > dynamic limit (scaled based on model's context window)
        threshold = getattr(self, "_compression_threshold", 65_000)
        if not instruction:
            est_tokens = self._estimate_tokens(self.messages)
            if est_tokens < threshold:
                return
            
        tail_keep = 8

        # Build a compact state anchor so compression never drops the active objective.
        latest_user = ""
        latest_assistant = ""
        latest_tool_plan = ""
        for m in reversed(current_turn_msgs):
            if not latest_user and m.get("role") == "user":
                latest_user = (m.get("content", "") or "")[:1200]
            if m.get("role") == "assistant":
                if not latest_assistant and (m.get("content", "") or "").strip():
                    latest_assistant = (m.get("content", "") or "")[:1200]
                if not latest_tool_plan and m.get("tool_calls"):
                    tc_names = [tc.get("function", {}).get("name", "") for tc in m.get("tool_calls", [])]
                    latest_tool_plan = ", ".join([n for n in tc_names if n])[:500]
            if latest_user and latest_assistant and latest_tool_plan:
                break

        state_anchor = {
            "role": "user",
            "content": (
                "### SYSTEM NOTE: TASK STATE ANCHOR (MUST PRESERVE)\n"
                f"Current user objective (latest):\n{latest_user or '[not found]'}\n\n"
                f"Most recent assistant intent/progress:\n{latest_assistant or '[not found]'}\n\n"
                f"Most recent pending/attempted tool actions:\n{latest_tool_plan or '[none]'}\n\n"
                "Continue from this exact objective. Do not restart completed steps."
            ),
        }

        # ── Unified importance-weighted compression ──────────────────────────
        # Threshold 0.75: messages scoring at or above are kept verbatim so that
        # file-read payloads, error traces, and key facts survive into context.
        # Everything below goes to the compression model for condensation.
        try:
            from utim_cli.context_pruner import score_message_importance, sanitize_message_sequence

            candidate_msgs = current_turn_msgs[1:-tail_keep]
            scored_msgs = [(score_message_importance(m), m) for m in candidate_msgs]

            # Split into verbatim-keep (high) and compress (low) pools
            preserved_messages = [m for score, m in scored_msgs if score >= 0.75]
            to_summarize      = [m for score, m in scored_msgs if score <  0.75]

            # Cap verbatim-keep to 10 to prevent bloat; extras go to compress pool
            if len(preserved_messages) > 10:
                sorted_by_val = sorted(enumerate(scored_msgs), key=lambda x: (x[1][0], x[0]), reverse=True)
                keep_indices  = {idx for idx, _ in sorted_by_val[:10]}
                new_preserved, extra = [], []
                for idx, (score, m) in enumerate(scored_msgs):
                    (new_preserved if idx in keep_indices else extra).append(m)
                preserved_messages = new_preserved
                to_summarize.extend(extra)

            if to_summarize:
                text_parts = []
                import re as _re
                for m in to_summarize:
                    role = m.get("role", "")
                    if role == "assistant":
                        content = _re.sub(
                            r"<think(?:ing)?>.*?</think(?:ing)?>",
                            "[thought process]",
                            (m.get("content", "") or ""),
                            flags=_re.DOTALL,
                        ).strip()
                        tcs    = m.get("tool_calls", [])
                        tc_str = ", ".join(
                            f"{tc['function']['name']}({tc['function'].get('arguments', '')})"
                            for tc in tcs
                        )
                        if content or tc_str:
                            text_parts.append(f"Action: {content}\nTools Called: {tc_str}")
                    elif role == "tool":
                        name    = m.get("name", "tool")
                        content = m.get("content", "")
                        
                        # FIX #3: Intelligent truncation - preserve critical parts
                        # Detect if content has critical markers that should never be truncated
                        critical_patterns = [
                            r"error", r"exception", r"failed", r"failure",
                            r"traceback", r"undefined", r"not found",
                            r"def \w+", r"class \w+", r"import ",
                            r'"[^"]*":\s*', r"'[^']*':\s*",  # Key-value pairs
                        ]
                        
                        # Check if this is critical content that needs full preservation
                        is_critical = any(re.search(p, content, re.I) for p in critical_patterns)
                        
                        # Higher char limit for critical content, but still respect reasonable bounds
                        if len(content) > 1500:
                            if is_critical:
                                # For critical content, try to find and preserve the key part
                                # Look for error lines, function definitions, etc.
                                lines = content.split('\n')
                                critical_lines = []
                                for line in lines:
                                    if any(re.search(p, line, re.I) for p in critical_patterns):
                                        critical_lines.append(line)
                                
                                if critical_lines:
                                    # Preserve the critical lines plus context
                                    content = (content[:800] + 
                                              "\n... [critical excerpts preserved] ...\n" +
                                              "\n".join(critical_lines[:20]))
                                else:
                                    content = content[:1500] + "... [truncated]"
                            else:
                                content = content[:1200] + "... [truncated]"
                        text_parts.append(f"Result of {name}: {content}")

                if text_parts:
                    if instruction:
                        pass  # Compression indicator suppressed
                    else:
                        est_tokens = self._estimate_tokens(self.messages)
                        msg_count  = len(self.messages)
                        triggers   = []
                        if est_tokens >= threshold:
                            triggers.append(f"tokens ~{est_tokens}")
                        if msg_count >= 50:
                            triggers.append(f"msg count {msg_count}")
                        trigger_str = ", ".join(triggers) if triggers else "context"
                        self.console.print(f"\n[dim magenta]⊘ Proactive compression (high {trigger_str}): condensing intermediate tool logs...[/dim magenta]")

                    raw_log = "\n---\n".join(text_parts)

                    sys_prompt = (
                        "You are an internal context stabilizer for an autonomous AI agent.\n"
                        "The agent has been running tool calls in a loop. Summarize intermediate steps "
                        "while preserving strict technical continuity.\n"
                        "Required sections:\n"
                        "1) GOAL\n2) COMPLETED\n3) IN_PROGRESS\n4) BLOCKERS/FAILURES\n5) NEXT_ACTION\n"
                        "CRITICAL: Preserve ALL specific file paths, line numbers, variable names, "
                        "error messages, and facts learned from file reads verbatim. No filler.\n\n"
                        "HALLUCINATION PREVENTION RULES:\n"
                        "- Do NOT add facts not present in the source logs\n"
                        "- Do NOT make up file paths, variable names, or error messages\n"
                        "- Do NOT invent technical details not explicitly stated\n"
                        "- When in doubt, use verbatim quotes from the source\n"
                        "- If you cannot determine a fact, state 'not specified' rather than guessing"
                    )
                    if instruction:
                        sys_prompt += (
                            f"\n\nCRITICAL PRESERVATION RULES FROM THE AGENT:\n{instruction}\n"
                            "You MUST strictly preserve these facts, constraints, and code snippets."
                        )

                    from utim_cli.context_pruner import _call_compression_model_with_fallback
                    # Pass raw_log for deduplication tracking
                    summary = _call_compression_model_with_fallback(
                        messages=[
                            {"role": "system", "content": sys_prompt},
                            {"role": "user",   "content": f"Intermediate Logs to Compress:\n{raw_log}"},
                        ],
                        llm_key=self._local_api_key,
                        max_tokens=1500,
                        content_hint=raw_log[:1000],  # Use first 1000 chars for dedup hash
                        primary_model=self.model_id
                    )

                    if summary:
                        summary_msg = {
                            "role": "user",
                            "content": (
                                "### SYSTEM NOTE: INTERMEDIATE STEPS COMPRESSED\n"
                                "The following earlier steps in this task were compressed to save memory:\n"
                                f"{summary}\n\n"
                                "Continue from IN_PROGRESS/NEXT_ACTION and finish unresolved work."
                            ),
                        }
                        recent_tail = current_turn_msgs[-tail_keep:]

                        # BUG 3 FIX: Use object identity (id()) instead of value
                        # equality (==) for deduplication.  Dict value-equality
                        # was silently dropping preserved_messages entries whose
                        # content happened to match a message in recent_tail
                        # (e.g. repeated read_file of the same file).
                        merged_tail = []
                        seen_ids: set = set()
                        for msg in preserved_messages + recent_tail:
                            if id(msg) not in seen_ids:
                                seen_ids.add(id(msg))
                                merged_tail.append(msg)

                        with self._messages_lock:
                            new_messages = (
                                self.messages[:turn_msg_start]
                                + [current_turn_msgs[0], state_anchor, summary_msg]
                                + merged_tail
                            )
                            self.messages = sanitize_message_sequence(new_messages)
                            # BUG 1 FIX: After rewriting self.messages the
                            # turn_msg_start boundary is still valid (we only
                            # shrank the current-turn slice, not the prefix).
                            # Refresh _current_turn_start so _get_send_messages
                            # slices at the correct position on the next call.
                            self._current_turn_start = turn_msg_start
                        return
                    else:
                        self.console.print(
                            "\n[dim red]⊘ Warning: Context compression failed "
                            "(no response from fallback models). Continuing with full context.[/dim red]"
                        )
            else:
                # Nothing to compress — just sanitize the existing list
                self.messages = sanitize_message_sequence(self.messages)
                return

        except Exception as e:
            self.console.print(
                f"\n[dim red]⊘ Warning: Importance-weighted compression failed ({e}). "
                "Continuing with full context.[/dim red]"
            )


    # ── Cleanup utilities ───────────────────────────────────────────────────

    def _cleanup_tmp_folder(self, keep_current_session: bool = True) -> int:
        """Clean up the .utim_tmp folder to remove files from previous runs.
        
        Args:
            keep_current_session: If True, preserve files from the current session.
        
        Returns:
            Number of files removed.
        """
        import glob
        
        tmp_dir = ".utim_tmp"
        if not os.path.exists(tmp_dir):
            return 0
        
        removed_count = 0
        errors = []
        # Define cleanup rules - files/patterns to remove
        cleanup_patterns = [
            # Research files older than 1 day
            (os.path.join(tmp_dir, "research"), "dir"),
            # Plan files are kept for /rewind functionality
            # But we can clean up very old ones
        ]
        
        # Remove old research directory contents
        research_dir = os.path.join(tmp_dir, "research")
        if os.path.exists(research_dir):
            try:
                # Remove files older than 1 day
                now = time.time()
                for root, dirs, files in os.walk(research_dir):
                    for f in files:
                        fp = os.path.join(root, f)
                        try:
                            if os.path.getmtime(fp) < now - 86400:  # 1 day old
                                os.remove(fp)
                                removed_count += 1
                        except OSError as e:
                            errors.append(str(e))
            except Exception as e:
                errors.append(str(e))
        
        # Clean up old reflection files (keep last 10)
        reflection_file = os.path.join(tmp_dir, "task_reflections.json")
        if os.path.exists(reflection_file):
            try:
                with open(reflection_file, 'r') as f:
                    reflections = json.load(f)
                if len(reflections) > 50:
                    # Keep only the most recent 50
                    reflections = reflections[-50:]
                    with open(reflection_file, 'w') as f:
                        json.dump(reflections, f)
                    removed_count += len(reflections) - 50
            except Exception:
                pass
        
        return removed_count

    def _detect_and_run_tests(self) -> Optional[str]:
        import subprocess
        import os

        # 1. Check for Python/pytest
        if os.path.exists("pytest.ini") or os.path.exists("conftest.py") or os.path.isdir("tests"):
            try:
                res = subprocess.run(["pytest"], capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=60)
                if res.returncode != 0 and res.returncode != 5:
                    return f"pytest failed:\n{res.stdout}\n{res.stderr}"
                return None
            except subprocess.TimeoutExpired:
                return "pytest timed out (took longer than 60 seconds)"
            except Exception:
                pass

        # 2. Check for package.json / npm test
        if os.path.exists("package.json"):
            try:
                with open("package.json", "r", encoding="utf-8") as f:
                    pkg = json.load(f)
                if "scripts" in pkg and "test" in pkg["scripts"]:
                    res = subprocess.run(["npm", "test"], capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=60, shell=True)
                    if res.returncode != 0:
                        return f"npm test failed:\n{res.stdout}\n{res.stderr}"
                    return None
            except subprocess.TimeoutExpired:
                return "npm test timed out"
            except Exception:
                pass

        # 3. Check for tox.ini
        if os.path.exists("tox.ini"):
            try:
                res = subprocess.run(["tox"], capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=90)
                if res.returncode != 0:
                    return f"tox failed:\n{res.stdout}\n{res.stderr}"
                return None
            except Exception:
                pass

        # 4. Check for Cargo.toml
        if os.path.exists("Cargo.toml"):
            try:
                res = subprocess.run(["cargo", "test"], capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=60)
                if res.returncode != 0:
                    return f"cargo test failed:\n{res.stdout}\n{res.stderr}"
                return None
            except Exception:
                pass

        # 5. Check for go.mod
        if os.path.exists("go.mod"):
            try:
                res = subprocess.run(["go", "test", "./..."], capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=60)
                if res.returncode != 0:
                    return f"go test failed:\n{res.stdout}\n{res.stderr}"
                return None
            except Exception:
                pass

        return None



    def run_task(self, user_message: str, max_iterations: int = 500) -> None:
        """Append user_message to history and run the full ReAct loop until the
        model stops issuing tool calls or completes the task.
        """
        from utim_cli.config import config
        max_iterations = 500  # Continuous execution mode with milestone nudges instead of hard pauses
        self.turn_step_timings = []
        self._tool_failure_counts = {}


        # Refresh console width at start of task
        try:
            import shutil
            width = shutil.get_terminal_size().columns
            if width > 0:
                self.console.width = width
        except:
            pass

        self.cancel_event.clear()
        self.pre_prompt_text = ""
        try:
            from utim_cli.config import get_utim_dir
            pre_prompt_file = get_utim_dir() / "pre_prompt_thoughts.json"
            if os.path.exists(pre_prompt_file):
                os.remove(pre_prompt_file)
        except Exception:
            pass
        try:
            from utim_cli.state import STATE
            STATE["thinking_topic"] = ""
        except Exception:
            pass

        # Check if we asked a clarifying question in the previous turn
        try:
            from utim_cli.state import STATE
            asked = STATE.pop("asked_clarifying_question", None)
            if asked:
                from utim_cli.reflection import evaluate_clarifying_answer
                threading.Thread(
                    target=evaluate_clarifying_answer,
                    args=(asked["pattern_id"], asked["question"], user_message),
                    daemon=True,
                    name="utim-clarifying-question-evaluator"
                ).start()
        except Exception:
            pass

        turn_msg_start = len(self.messages)  # snapshot before user msg is appended
        self._current_turn_start = turn_msg_start  # used by _get_send_messages()
        self.cancel_event.clear()  # Reset cancellation event for new turn
        self._turn_changes = []
        
        # Analyze previous turn feedback and user sentiment
        prev_assistant_content = ""
        prev_iteration_count = 0
        prev_elapsed_time = 0
        if self.turn_history:
            prev_turn = self.turn_history[-1]
            prev_iteration_count = prev_turn.get("iteration_count", 0)
            prev_elapsed_time = prev_turn.get("elapsed_time", 0)

        if self.messages:
            for msg in reversed(self.messages):
                if msg.get("role") == "assistant" and msg.get("content"):
                    prev_assistant_content = msg["content"]
                    break


        try:
            from utim_cli.state import STATE
            hint = STATE.pop("hint", None)
            if hint:
                user_message = f"[Secret Hint Guidance: {hint}]\n{user_message}"
                self.session_hints.append(hint)
        except Exception:
            pass

        # Auto-detect image paths in user_message and send direct multimodal vision payload
        try:
            import re, os, base64, mimetypes
            img_matches = re.findall(r'(?:[A-Za-z]:[\\/][^\s"\']+\.(?:png|jpg|jpeg|webp|gif)|/[^\s"\']+\.(?:png|jpg|jpeg|webp|gif))', user_message, re.IGNORECASE)
            
            valid_images = []
            for img_path in img_matches:
                img_path_clean = img_path.strip('"\':;')
                if os.path.exists(img_path_clean):
                    valid_images.append(img_path_clean)

            if valid_images:
                from utim_cli.tools import is_model_vision_capable
                if is_model_vision_capable(self.model_id):
                    # Send Direct Multimodal Image URL Payload to Vision Model!
                    multimodal_content = [{"type": "text", "text": user_message}]
                    for img_p in valid_images:
                        mime, _ = mimetypes.guess_type(img_p)
                        ext = os.path.splitext(img_p)[1].lower()
                        if not mime or not mime.startswith("image/"):
                            mime = f"image/{ext[1:]}"
                            if ext == ".jpg": mime = "image/jpeg"
                        with open(img_p, "rb") as f:
                            b64 = base64.b64encode(f.read()).decode("utf-8")
                        multimodal_content.append({
                            "type": "image_url",
                            "image_url": {"url": f"data:{mime};base64,{b64}"}
                        })
                    self.messages.append({"role": "user", "content": multimodal_content})
                else:
                    # Text-only model fallback: analyze image to text context
                    for img_p in valid_images:
                        from utim_cli.tools import analyze_image
                        img_analysis = analyze_image(img_p, user_message)
                        if img_analysis and not img_analysis.startswith("Error"):
                            user_message += f"\n\n[Automatic Image Vision Context ({os.path.basename(img_p)})]:\n{img_analysis}"
                    self.messages.append({"role": "user", "content": user_message})
            else:
                self.messages.append({"role": "user", "content": user_message})
        except Exception:
            self.messages.append({"role": "user", "content": user_message})
        self.redo_history = []  # Clear redo history on new user action
        self._persist_messages(in_progress_turn={
            "user_msg": user_message,
            "msg_start": turn_msg_start,
            "msg_end": len(self.messages),
            "messages": list(self.messages[turn_msg_start:]),
            "changes": [],
        })
        task_start_time = time.time()
        self.task_start_time = task_start_time
        
        # Update the experience summary cache for this task at start
        try:
            update_experience_summary_cache(user_message, messages=self.messages)
        except Exception:
            pass

        # Update STATE so the background brain watcher pre-fetches relevant memories
        try:
            from utim_cli.state import STATE as _S
            _S["last_user_prompt"] = user_message
        except Exception:
            pass

        self._test_run_attempts = 0
        final_answer = ""
        _empty_response_streak = 0  # tracks consecutive empty (no content, no tools) responses
        turn_iteration = 0
        # ── Cross-turn 5-request reflection counter ────────────────────────────
        # Persists across user turns on self so response-end reflection at
        # request 3 doesn't reset the sequence — the next user turn picks up at
        # 3 and fires at 2 more requests (total 5).
        if not hasattr(self, "_reflect_request_counter"):
            self._reflect_request_counter = 0
        for iteration in range(max_iterations):
            self.current_iteration = iteration
            turn_iteration = iteration + 1

            # ── Milestone Warnings (Non-hardcoded iteration limits) ────────────
            # Window-aware, one-shot iteration guidance. Budget scales with the
            # model's context window using the same buckets as _get_compression_interval.
            try:
                if not hasattr(self, "_milestones_fired"):
                    self._milestones_fired = set()
                _budget, _halfway, _last5, _grant = self._get_iteration_milestones()
                _uid = f"{self.model_id}:{turn_iteration}"
                if turn_iteration == 1 and ("intro", _uid) not in self._milestones_fired:
                    self.messages.append({
                        "role": "user",
                        "content": f"[SYSTEM DIRECTIVE] Finish the task within {_budget} tool uses (scaled by model context window).",
                    })
                    self._milestones_fired.add(("intro", _uid))
                elif turn_iteration == _halfway and ("halfway", _uid) not in self._milestones_fired:
                    self.messages.append({
                        "role": "user",
                        "content": f"[SYSTEM WARNING] You have already used {turn_iteration} iterations. Task is still not finished, you have only {_budget - turn_iteration} iterations left. Try to finish within the limit (total budget: {_budget}).",
                    })
                    self._milestones_fired.add(("halfway", _uid))
                elif turn_iteration == _last5 and ("last5", _uid) not in self._milestones_fired:
                    self.messages.append({
                        "role": "user",
                        "content": f"[SYSTEM URGENT] Only 5 iterations left (of {_budget} total). Finish the task fast.",
                    })
                    self._milestones_fired.add(("last5", _uid))
                elif turn_iteration == _grant and ("grant", _uid) not in self._milestones_fired:
                    self.messages.append({
                        "role": "user",
                        "content": f"[SYSTEM NOTICE] +5 iterations granted (previous budget was {_budget}). No more will be provided. Finish the task within this limit.",
                    })
                    self._milestones_fired.add(("grant", _uid))
            except Exception:
                pass

            # Check for cancellation before each LLM call
            if self.cancel_event.is_set():
                del self.messages[turn_msg_start + 1:]
                self._persist_messages()
                break

            # ── Resilient LLM call with per-iteration retry ────────────────────
            # We allow up to 3 transient-error retries per iteration before
            # giving up for real.  This prevents a single network blip from
            # silently killing a long-running task.
            _llm_retries = 0
            _llm_max_retries = 3
            msg = None
            while _llm_retries <= _llm_max_retries:
                try:
                    # Make the thinking indicator interactive before TTFT
                    from utim_cli.state import STATE
                    if iteration == 0:
                        if is_casual_message(user_message):
                            STATE["thinking_topic"] = "Formulating greeting..."
                        else:
                            STATE["thinking_topic"] = "Formulating response..."
                        draft_text = getattr(self, "_pre_computation_text", "").strip()
                        actual_text = user_message.strip()
                        
                        def get_similarity(s1, s2):
                            s1_clean = "".join(c for c in s1.lower() if c.isalnum() or c.isspace()).strip()
                            s2_clean = "".join(c for c in s2.lower() if c.isalnum() or c.isspace()).strip()
                            s1_words = s1_clean.split()
                            s2_words = s2_clean.split()
                            if not s1_words or not s2_words:
                                return 0.0
                            w1 = set(s1_words)
                            w2 = set(s2_words)
                            intersection = w1.intersection(w2)
                            union = w1.union(w2)
                            return len(intersection) / len(union)

                        is_match = False
                        match_reason = ""
                        if draft_text:
                            if draft_text == actual_text:
                                is_match = True
                                match_reason = "exact match"
                            elif actual_text.startswith(draft_text) and len(actual_text) - len(draft_text) < 20:
                                is_match = True
                                match_reason = "prefix match"
                            else:
                                similarity = get_similarity(draft_text, actual_text)
                                if similarity >= 0.80:
                                    is_match = True
                                    match_reason = f"fuzzy match ({similarity:.1%} similarity)"

                        if is_match:
                            if (self._pre_computation_thread and 
                                    self._pre_computation_thread.is_alive() and 
                                    not self._pre_computation_done and
                                    not self.cancel_event.is_set()):
                                STATE["thinking_topic"] = "Anticipating response (finishing background reasoning)..."
                                self._pre_computation_thread.join(timeout=0.2)
                            
                            if self._pre_computation_done and self._pre_computation_result:
                                self.console.print(f"[bold green][CACHE HIT] Anticipatory Cache HIT: Reused background reasoning ({match_reason}).[/bold green]")
                                msg = self._pre_computation_result
                                was_streamed = True
                                clean_content = msg.get("content") or ""
                                if clean_content:
                                    self.console.print()
                                    self.console.print(Markdown(clean_content))
                                    self.console.print()
                                self.turn_step_timings.append({
                                    "step": turn_iteration,
                                    "reasoning_time": 0.0,
                                    "tool_time": 0.0,
                                    "tools": []
                                })
                                break
                    else:
                        STATE["thinking_topic"] = "Evaluating tool results & logic..."
                        
                    # BUG 1 FIX: Pass the live turn_msg_start so _get_send_messages
                    # always slices at the correct boundary, even after compression
                    # has rewritten self.messages and potentially shifted indices.
                    send_msgs = self._get_send_messages(turn_msg_start)
                    STATE["thinking_topic"] = "Synthesizing response..."
                    t_llm_start = time.time()
                    msg, was_streamed = self._call_llm(send_msgs)
                    reasoning_duration = time.time() - t_llm_start
                    break  # success
                except _ServerUnavailableError as exc:
                    if self.cancel_event.is_set():
                        del self.messages[turn_msg_start + 1:]
                        self._persist_messages()
                        return
                    if _llm_retries < _llm_max_retries:
                        _llm_retries += 1
                        wait_s = 5 * _llm_retries
                        self.console.print(
                            f"\n[bold yellow]All models unreachable (attempt {_llm_retries}/{_llm_max_retries}). "
                            f"Retrying in {wait_s}s...[/bold yellow]"
                        )
                        # Interruptible wait — checks cancel_event every 100ms so Ctrl+C stops instantly
                        deadline = time.time() + wait_s
                        while time.time() < deadline:
                            if self.cancel_event.is_set():
                                break
                            time.sleep(0.1)
                        if self.cancel_event.is_set():
                            if len(self.messages) == turn_msg_start + 1:
                                self.messages.append({"role": "assistant", "content": "[Aborted by user]"})
                            self._persist_messages()
                            self.cancel_event.clear()
                            return
                        continue
                    # All retries exhausted — show error and abort turn
                    self.console.print()
                    self.console.print(Panel(
                        Text.from_markup(
                            f"[bold #FFE066]UTIM Server Unavailable[/bold #FFE066]\n\n"
                            f"[white]{exc}[/white]\n\n"
                            "[dim]All retry attempts failed. The task has been paused.\n"
                            "Type your message again when the connection is restored.[/dim]"
                        ),
                        border_style="#FFE066",
                        padding=(0, 2),
                        expand=False,
                        width=min(70, self.console.width - 4),
                    ))
                    self.console.print()
                    del self.messages[turn_msg_start:]
                    return
                except _FatalClientError as exc:
                    if len(self.messages) == turn_msg_start + 1:
                        self.messages.append({"role": "assistant", "content": "[Aborted by user]"})
                    self._persist_messages()
                    self.cancel_event.clear()
                    return
                except Exception as exc:
                    if self.cancel_event.is_set():
                        del self.messages[turn_msg_start + 1:]
                        self._persist_messages()
                        return
                    if _llm_retries < _llm_max_retries:
                        _llm_retries += 1
                        wait_s = 3 * _llm_retries
                        self.console.print(
                            f"\n[dim yellow]⟳  Transient error on iteration {iteration+1} "
                            f"(attempt {_llm_retries}/{_llm_max_retries}): {exc}. "
                            f"Retrying in {wait_s}s...[/dim yellow]"
                        )
                        # Interruptible wait — checks cancel_event every 100ms so Ctrl+C stops instantly
                        deadline = time.time() + wait_s
                        while time.time() < deadline:
                            if self.cancel_event.is_set():
                                break
                            time.sleep(0.1)
                        if self.cancel_event.is_set():
                            if len(self.messages) == turn_msg_start + 1:
                                self.messages.append({"role": "assistant", "content": "[Aborted by user]"})
                            self._persist_messages()
                            self.cancel_event.clear()
                            return
                        continue
                    # All retries exhausted — log and abort turn cleanly
                    self.console.print(f"\n[bold red]Error (all retries failed):[/bold red] {exc}\n")
                    if len(self.messages) == turn_msg_start + 1:
                        self.messages.append({"role": "assistant", "content": "[Aborted by user]"})
                    self._persist_messages()
                    self.cancel_event.clear()
                    return
            
            if msg is None or msg.get("aborted") or self.cancel_event.is_set():
                if not self.cancel_event.is_set():
                    self.console.print("\n[dim yellow]⊘  Aborted.[/dim yellow]\n")
                if len(self.messages) == turn_msg_start + 1:
                    self.messages.append({"role": "assistant", "content": "[Aborted by user]"})
                self._persist_messages()
                self.cancel_event.clear()
                return



            content: str = msg.get("content") or ""
            final_answer = content
            tool_calls: List[Dict] = msg.get("tool_calls") or []

            # ── Tool-call attempt evidence from the raw stream ──────────────
            # finish_reason="tool_calls" means the model INTENDED to call a tool
            # even if JSON reconstruction failed.  We use this to block false
            # lazy-nudges when the real problem is a malformed/truncated tool call.
            _msg_finish_reason: str = msg.get("finish_reason") or ""
            _msg_was_truncated: bool = bool(msg.get("was_truncated_by_limit"))
            _msg_completion_tokens: int = msg.get("completion_tokens") or 0

            # Drain any tool-parse failures recorded by _execute_tool this iteration
            _parse_failures: list = getattr(self, "_last_tool_parse_failures", [])
            self._last_tool_parse_failures = []  # reset for next iteration

            # The model "attempted" a tool call if: native tool calls exist, OR
            # the stream ended with finish_reason=tool_calls, OR we have parse failures.
            _attempted_tool_call: bool = bool(
                tool_calls
                or _parse_failures
                or _msg_finish_reason in ("tool_calls", "function_call")
            )

            # Print content that wasn't already streamed live
            if not was_streamed and content and content.strip():
                self.console.print()
                self.console.print(Markdown(content))
                self._current_line_len = 0
                if not tool_calls:
                    self.console.print()
            elif was_streamed and content:
                # We finished streaming. The cursor is at some position on the current line.
                # No extra newline here - let the next block handle it
                pass

            # Parse text-based tool calls fallback if native tool calls are empty
            if not tool_calls and content:
                parsed_calls = []
                try:
                    from utim_cli.tools import get_tools
                    _, tool_functions = get_tools()
                    tool_names = set(tool_functions.keys())
                    decoder = json.JSONDecoder()
                    pos = 0
                    while pos < len(content):
                        start = content.find('{', pos)
                        if start == -1:
                            break
                        try:
                            obj, end_idx = decoder.raw_decode(content[start:])
                            extracted = []
                            # 1. Standard OpenAI format
                            if "function" in obj and isinstance(obj["function"], dict):
                                func_obj = obj["function"]
                                name = func_obj.get("name")
                                if name in tool_names:
                                    args = func_obj.get("arguments", "{}")
                                    if isinstance(args, dict):
                                        args = json.dumps(args)
                                    extracted = [{
                                        "id": obj.get("id", f"call_parsed_{iteration}"),
                                        "type": "function",
                                        "function": {"name": name, "arguments": args}
                                    }]
                            # 2. Simplified formats
                            if not extracted:
                                name_keys = ["name", "tool", "function", "action", "tool_name"]
                                name = None
                                for k in name_keys:
                                    if k in obj and isinstance(obj[k], str) and obj[k] in tool_names:
                                        name = obj[k]
                                        break
                                if name:
                                    args_obj = {}
                                    args_keys = ["arguments", "args", "parameters", "params"]
                                    for k in args_keys:
                                        if k in obj and isinstance(obj[k], dict):
                                            args_obj = obj[k]
                                            break
                                    else:
                                        args_obj = {k: v for k, v in obj.items() if k not in name_keys}
                                    extracted = [{
                                        "id": f"call_parsed_{iteration}",
                                        "type": "function",
                                        "function": {"name": name, "arguments": json.dumps(args_obj)}
                                    }]
                            if extracted:
                                parsed_calls.extend(extracted)
                            pos = start + end_idx
                        except json.JSONDecodeError:
                            pos = start + 1
                except Exception:
                    pass
                if parsed_calls:
                    tool_calls = parsed_calls
                    self.console.print(f"\n[bold yellow]Parsed {len(tool_calls)} tool call(s) from assistant text response.[/bold yellow]")

            # If the model response was cut off mid-turn due to length/token limits, nudge it to continue
            if msg.get("was_cut_off"):
                self.console.print("\n[bold yellow]Response truncated by token limits. Continuing response...[/bold yellow]\n")
                self.messages.append(
                    {
                        "role": "assistant",
                        "content": content or None,
                        "tool_calls": tool_calls if tool_calls else None,
                    }
                )
                self.messages.append(
                    {
                        "role": "user",
                        "content": "You were cut off mid-response (token limit reached). Please continue your response exactly where you left off. Do not repeat yourself; just resume writing from the cutoff point."
                    }
                )
                continue

            # No tool calls → potentially done
            if not tool_calls:
                # Gather recent tool names from this turn to build context-aware nudges
                _MUTATION_TOOLS = {"write_file", "edit_file", "delete_file", "move_file", "run_command"}
                _INSPECTION_TOOLS = {"read_file", "grep_search", "search", "list_directory", "web_search", "plan_project"}

                _recent_tool_names = []
                _successful_mutations_this_turn = []
                for _prev_msg in reversed(self.messages[turn_msg_start:]):
                    if _prev_msg.get("role") == "tool":
                        _tname = _prev_msg.get("name", "")
                        if _tname and _tname not in {"recall_experience", "store_experience", "manage_memory"}:
                            _recent_tool_names.append(_tname)
                            if _tname in _MUTATION_TOOLS:
                                _tc_content = _prev_msg.get("content") or ""
                                # Only count as successful if the result doesn't start with an error
                                if not _tc_content.strip().startswith(("Error:", "[!", "[TOOL PARSE ERROR]")):
                                    _successful_mutations_this_turn.append(_tname)
                    elif _prev_msg.get("role") == "user":
                        break  # don't look past the user's message
                _had_tools_this_turn = bool(_recent_tool_names)

                # Attempted mutation = parse failures on mutation tools OR
                # successful mutation tool calls this turn
                _attempted_mutations = (
                    bool(_successful_mutations_this_turn)
                    or any(f["tool_name"] in _MUTATION_TOOLS for f in _parse_failures)
                    or (_attempted_tool_call and any(t in _MUTATION_TOOLS for t in _recent_tool_names))
                )

                # If the model stopped with empty OR trivially short response after running tools
                _is_empty = not content.strip()
                _lower_content = content.lower()
                _is_lazy_transition = False
                is_planning = False

                # ── Fix 3: Never lazy-nudge when a tool call was attempted ──────
                # If we have parse failures, the model DID try to call a tool — it's
                # not lazy. We handle it separately in the parse-failure block below.
                if _attempted_tool_call and not tool_calls:
                    # Tool call was attempted but failed to parse or reconstruct — skip lazy logic
                    pass
                else:
                    _only_inspection_tools = _had_tools_this_turn and all(t in _INSPECTION_TOOLS for t in _recent_tool_names)

                    # ── Fix 4: State-based lazy detection ──────────────────────────
                    # Future-action narration patterns: model promises to act without acting.
                    _ACTION_PROMISE_PATTERNS = [
                        r"\bnow (?:i(?:'ll| will)|we(?:'ll| will))\b",
                        r"\bnow (?:updating|editing|implementing|creating|fixing|writing|building)\b",
                        r"\bnext,? (?:i(?:'ll| will)|we(?:'ll| will))\b",
                        r"\blet me (?:update|edit|implement|create|fix|write|build|start|now)\b",
                        r"\bi(?:'ll| will) now (?:update|edit|implement|create|fix|write|build|start)\b",
                        r"\bproceeding to (?:implement|create|build|write|update)\b",
                    ]
                    _response_indicates_future_action = any(
                        re.search(pat, content, re.IGNORECASE)
                        for pat in _ACTION_PROMISE_PATTERNS
                    )
                    _response_is_substantive = len(content.strip()) >= 120

                    # ── Case 1: model ran tools then went quiet ──────────────────
                    if _had_tools_this_turn:
                        if _only_inspection_tools and not _attempted_mutations:
                            # Model ONLY ran inspection/planning tools (plan_project, read_file, search)
                            # and has NOT created or modified any code files yet.
                            # Unless it explicitly provides a completion marker, it MUST continue into implementation.
                            _has_completion_marker = any(marker in _lower_content for marker in [
                                "task complete", "implementation complete", "successfully built", "finished building",
                                "summary of changes", "all files have been created", "project is ready", "here is the summary",
                                "completed the requested task", "everything has been implemented", "here is what was built"
                            ])
                            if not _has_completion_marker:
                                _is_lazy_transition = True
                        elif is_planning:
                            _is_lazy_transition = len(_lower_content) < 20
                        else:
                            _ends_with_cliffhanger = (
                                content.strip().endswith(":")
                                or content.strip().endswith("...")
                            )
                            # Primary signal: model is narrating instead of acting.
                            # Length is a secondary guard only for near-empty responses.
                            _is_lazy_transition = (
                                _response_indicates_future_action
                                or _ends_with_cliffhanger
                                or len(_lower_content) < 60
                            )

                    # ── Case 2: model has NOT called any tools yet this turn ─────
                    elif not _had_tools_this_turn and not _is_empty and not is_planning and not tool_calls:
                        _ends_with_cliffhanger = (
                            content.strip().endswith(":")
                            or content.strip().endswith("...")
                        )
                        # Only nudge when the model announces future action without
                        # having called any tools. Length alone does NOT trigger nudge.
                        if _ends_with_cliffhanger or _response_indicates_future_action:
                            _is_lazy_transition = True

                # ── Fix 3/7: Handle tool-call parse failures explicitly ──────────
                # The model emitted a tool call but the JSON was malformed/truncated.
                # Never silently convert this into a "lazy response" warning.
                if _parse_failures and not tool_calls and iteration < max_iterations - 1:
                    _empty_response_streak = 0  # this is not a lazy response
                    _fail_names = ", ".join(f["tool_name"] for f in _parse_failures)
                    _fail_chars = max(f["argument_chars"] for f in _parse_failures)
                    _has_write_fail = any(f["tool_name"] in ("write_file", "edit_file") for f in _parse_failures)

                    # Determine whether token-limit truncation was the cause
                    if _msg_was_truncated:
                        _reason = (
                            f"The tool call argument stream ({_fail_chars:,} chars) was truncated at "
                            f"the model output token limit ({_msg_completion_tokens:,} tokens). "
                            "The tool was NOT executed."
                        )
                    else:
                        _reason = (
                            f"The tool call argument JSON ({_fail_chars:,} chars) was malformed or "
                            "the stream reconstruction was incomplete. The tool was NOT executed."
                        )

                    _warn_line = f"The model returned a '{_fail_names}' tool call, but its arguments were incomplete or invalid."
                    self.console.print(f"\n[bold yellow]{_warn_line}[/bold yellow]")
                    self.console.print(f"[dim yellow]  Reason: {_reason}[/dim yellow]")

                    # Fix 7: Recovery message — specific and actionable
                    if _has_write_fail:
                        recovery = (
                            f"Your {_fail_names} call for the file was incomplete and was NOT executed. "
                            "Do NOT resend the entire file content. "
                            "Instead, read only the relevant sections of the file using read_file with start_line/end_line, "
                            "then use edit_file with targeted old_str/new_str replacements to make smaller, precise changes. "
                            "Do not narrate the action — call the tool directly."
                        )
                    else:
                        recovery = (
                            f"Your {_fail_names} call was not executed because the argument JSON was invalid or truncated. "
                            "Please retry with a smaller, more targeted call. "
                            "Do not re-describe what you will do — call the tool directly now."
                        )

                    self.messages.append({"role": "assistant", "content": content or None})
                    self.messages.append({"role": "user", "content": recovery})
                    continue

                if (_is_empty or _is_lazy_transition) and iteration < max_iterations - 1:
                    # Do NOT inject synthetic user auto-nudges; complete turn gracefully if assistant returned text
                    if content and content.strip():
                        self.messages.append({"role": "assistant", "content": content})
                    break
                
                # Got a valid response — reset streak counter
                _empty_response_streak = 0

                # ── Automated Regression Testing Loop ───────────────────────
                import utim_cli.tools as _t
                from utim_cli.config import config
                import os as _os
                if (
                    self._turn_changes 
                    and not _t._DRY_RUN 
                    and (_os.environ.get("UTIM_ENABLE_REGRESSION_TESTS") == "1" or config.get("enable_regression_tests", False))
                    and getattr(self, "_test_run_attempts", 0) < 3
                ):
                    self.console.print("\n[bold yellow][TESTS] Running automated regression tests to verify changes...[/bold yellow]")
                    test_error = self._detect_and_run_tests()
                    if test_error:
                        self._test_run_attempts = getattr(self, "_test_run_attempts", 0) + 1
                        self.console.print(f"[bold red][FAILED] Automated tests failed (Attempt {self._test_run_attempts}/3). Nudging agent to self-heal...[/bold red]")
                        self.messages.append({"role": "assistant", "content": content})
                        self.messages.append({
                            "role": "user",
                            "content": f"Automated regression testing failed after your changes. Please fix the failing test(s) or compilation error(s) shown below:\n\n{test_error}"
                        })
                        continue
                    else:
                        self.console.print("[bold green]All automated tests passed successfully![/bold green]\n")

                self.messages.append({"role": "assistant", "content": content})
                self.turn_step_timings.append({
                    "step": turn_iteration,
                    "reasoning_time": reasoning_duration,
                    "tool_time": 0.0,
                    "tools": []
                })

                break

            # Append assistant message (with tool_calls) to history
            self.messages.append(
                {
                    "role": "assistant",
                    "content": content or None,
                    "tool_calls": tool_calls,
                }
            )
            # Real-time persistence: save the assistant response & tool calls immediately
            self._persist_messages(in_progress_turn={
                "user_msg": user_message,
                "msg_start": turn_msg_start,
                "msg_end": len(self.messages),
                "messages": list(self.messages[turn_msg_start:]),
                "changes": list(self._turn_changes),
            })

            # Execute tools - use parallel execution for better performance
            t_tool_start = time.time()

            # ── Iteration-based auto-compression ─────────────────────────────
            # Compress every N iterations (default 35) to keep context lean.
            # The interval is dynamically determined by _get_dynamic_interval(),
            # which returns 35 by default but can scale with the model's context window.
            COMPRESS_INTERVAL = self._get_dynamic_interval()
            compression_instruction = ""  # kept for _compress_intra_turn API compat

            if iteration > 0 and iteration % COMPRESS_INTERVAL == 0:
                # Strip old think-blocks and deduplicate tool outputs
                try:
                    from utim_cli.context_pruner import sanitize_message_sequence
                    with self._messages_lock:
                        self.messages = sanitize_message_sequence(list(self.messages))
                except Exception:
                    pass

                # LLM-compress low-signal intra-turn messages
                if not getattr(self, "_last_auto_compress_turn", -1) == turn_msg_start:
                    try:
                        self._compress_intra_turn(turn_msg_start, compression_instruction)
                        self._last_auto_compress_turn = turn_msg_start
                    except Exception:
                        pass

                # Also trigger background turn summarization
                try:
                    self._trigger_bg_summarization()
                except Exception:
                    pass
                self.console.print(
                    f"\n[dim magenta]Iteration {iteration} — compression applied.[/dim magenta]"
                )

            # ── Pre-execution arg validation gate ──────────────────────────────
            # Validate JSON args for ALL tool calls BEFORE executing any of them.
            # This catches truncated/malformed tool call JSON at the earliest point,
            # before _execute_tool gets to call the function with wrong/empty args.
            # Malformed calls are recorded on self for the NEXT iteration's lazy check.
            _MUTATION_NAMES = {"write_file", "edit_file", "delete_file", "move_file", "run_command"}
            _valid_tool_calls   = []
            _malformed_this_run = []
            for _tc in tool_calls:
                _tc_name  = _tc.get("function", {}).get("name", "")
                _tc_id    = _tc.get("id", "")
                _tc_raw   = _tc.get("function", {}).get("arguments", "{}")
                try:
                    _parsed = json.loads(_tc_raw) if _tc_raw else {}
                    if not isinstance(_parsed, dict):
                        raise json.JSONDecodeError("Expected dict", _tc_raw, 0)
                    _valid_tool_calls.append(_tc)
                except json.JSONDecodeError as _jde:
                    _fail_info = {
                        "tool_name":       _tc_name,
                        "tool_call_id":    _tc_id,
                        "argument_length": len(_tc_raw),
                        "error_position":  _jde.pos,
                        "error_message":   _jde.msg,
                        "argument_tail":   _tc_raw[-300:],
                        "finish_reason":   _msg_finish_reason,
                    }
                    _malformed_this_run.append(_fail_info)
                    # Persist to self so the NEXT iteration's lazy check sees it
                    if not hasattr(self, "_last_tool_parse_failures"):
                        self._last_tool_parse_failures = []
                    self._last_tool_parse_failures.append(_fail_info)
                    # Emit a placeholder tool result so the API is not missing a response
                    # for a tool_call_id it was told to expect.
                    _chars = len(_tc_raw)
                    _is_trunc = _msg_was_truncated
                    _reason_str = (
                        f"truncated at token limit ({_msg_completion_tokens:,} tokens)"
                        if _is_trunc else
                        f"malformed JSON: {_jde.msg} at char {_jde.pos}"
                    )
                    self.messages.append({
                        "role":         "tool",
                        "tool_call_id": _tc_id or str(len(self.messages)),
                        "name":         _tc_name,
                        "content":      (
                            f"[TOOL PARSE ERROR] '{_tc_name}' call NOT executed — "
                            f"argument JSON ({_chars:,} chars) could not be parsed ({_reason_str}). "
                            f"Do NOT retry with write_file for large files. "
                            f"Use edit_file with targeted old_str/new_str replacements instead."
                        ),
                    })
                    # Diagnostic log
                    import logging as _log
                    _log.getLogger("utim.tool_parse").debug(
                        "tool_parse_failure model=%s finish_reason=%s "
                        "completion_tokens=%d max_tokens=%d arg_chars=%d "
                        "tool=%s error=%s pos=%d",
                        self.model_id, _msg_finish_reason,
                        _msg_completion_tokens, _get_model_max_output(self.model_id),
                        _chars, _tc_name, _jde.msg, _jde.pos,
                    )

            # If ANY calls were malformed, display a warning immediately
            if _malformed_this_run:
                _mnames = ", ".join(f["tool_name"] for f in _malformed_this_run)
                _has_write = any(f["tool_name"] in _MUTATION_NAMES for f in _malformed_this_run)
                _mchars = max(f["argument_length"] for f in _malformed_this_run)
                _warn = (
                    f"The model returned a '{_mnames}' tool call, "
                    "but its arguments were incomplete or invalid. The tool was NOT executed."
                )
                if _msg_was_truncated:
                    _detail = (
                        f"Argument stream ({_mchars:,} chars) was truncated at the model output "
                        f"token limit ({_msg_completion_tokens:,} tokens). "
                        f"Finish reason: {_msg_finish_reason!r}. "
                        "This is NOT a lazy response — the model attempted tool use."
                    )
                else:
                    _detail = (
                        f"Argument JSON ({_mchars:,} chars) could not be parsed — stream "
                        f"reconstruction was incomplete. Finish reason: {_msg_finish_reason!r}. "
                        "This is NOT a lazy response — the model attempted tool use."
                    )
                self.console.print(f"\n[bold yellow]{_warn}[/bold yellow]")
                self.console.print(f"[dim yellow]  Detail: {_detail}[/dim yellow]")

                # If ALL calls were malformed (no valid calls to execute),
                # inject a targeted recovery message and re-run immediately.
                if not _valid_tool_calls:
                    _recovery = (
                        f"Your {_mnames} call was not executed because the argument JSON was invalid or truncated. "
                    )
                    if _has_write:
                        _recovery += (
                            "Do NOT resend the entire file. "
                            "Read only the relevant sections using read_file with start_line/end_line, "
                            "then use edit_file with targeted old_str/new_str replacements. "
                            "Call the tool directly — do not describe the action first."
                        )
                    else:
                        _recovery += (
                            "Retry with a smaller, more targeted call. "
                            "Call the tool directly now without re-describing what you will do."
                        )
                    self.messages.append({"role": "user", "content": _recovery})
                    tool_duration = time.time() - t_tool_start
                    self.turn_step_timings.append({
                        "step": turn_iteration,
                        "reasoning_time": reasoning_duration,
                        "tool_time": tool_duration,
                        "tools": [f["tool_name"] for f in _malformed_this_run],
                    })
                    continue

            # Replace the original tool_calls list with only the valid subset
            tool_calls = _valid_tool_calls
            # ── Two-phase execution: Knowledge-first gate ─────────────────
            # When recall_experience is called alongside MUTATING tools
            # (run_command, write_file, edit_file, etc.), the model has already
            # decided on those tool arguments BEFORE seeing the recall results.
            # This creates a race condition where knowledge arrives too late.
            #
            # Fix: execute ONLY recall_experience first, inject its results,
            # DROP the remaining planned calls, and force a re-plan so the
            # model can use the recalled knowledge to make better decisions.
            MUTATING_TOOLS = {"run_command", "write_file", "edit_file", "delete_file", "move_file"}
            KNOWLEDGE_TOOLS = {"recall_experience"}
            
            knowledge_calls = [tc for tc in tool_calls
                               if tc.get("function", {}).get("name", "") in KNOWLEDGE_TOOLS]
            mutating_calls = [tc for tc in tool_calls
                              if tc.get("function", {}).get("name", "") in MUTATING_TOOLS]
            
            if knowledge_calls and mutating_calls:
                # Phase 1: Execute ONLY the knowledge tools (silently)
                
                for ktc in knowledge_calls:
                    result = self._execute_tool_timed(ktc)
                    tc_id = ktc.get("id") or str(ktc.get("index", "0"))
                    func_name = ktc.get("function", {}).get("name", "")
                    self.messages.append({
                        "role": "tool",
                        "tool_call_id": tc_id,
                        "name": func_name,
                        "content": result,
                    })
                
                # Phase 2: Tell the model the remaining calls were NOT executed
                # and ask it to re-plan with the new knowledge
                dropped_names = [tc.get("function", {}).get("name", "?") for tc in mutating_calls]
                for mtc in mutating_calls:
                    tc_id = mtc.get("id") or str(mtc.get("index", "0"))
                    func_name = mtc.get("function", {}).get("name", "?")
                    self.messages.append({
                        "role": "tool",
                        "tool_call_id": tc_id,
                        "name": func_name,
                        "content": f"[NOT EXECUTED] This {func_name} call was held back. "
                                   f"Review the recall_experience results above — they may "
                                   f"contain constraints that affect how you should call this tool. "
                                   f"Please re-plan and re-issue the call with any necessary adjustments.",
                    })

                # Force the model to re-plan by continuing the loop
                tool_duration = time.time() - t_tool_start
                self.turn_step_timings.append({
                    "step": turn_iteration,
                    "reasoning_time": reasoning_duration,
                    "tool_time": tool_duration,
                    "tools": [tc.get("function", {}).get("name", "") for tc in tool_calls]
                })
                continue

            # ── Compute current fill ratio (0.0 = empty, 1.0 = at threshold) ────
            _ctx_threshold   = getattr(self, "_compression_threshold", 65_000)
            _ctx_used_tokens = sum(
                len(json.dumps(m, ensure_ascii=False)) for m in self.messages
            ) // 4
            _pressure = min(1.0, _ctx_used_tokens / max(_ctx_threshold, 1))

            # ── Per-tool ceilings and floors ─────────────────────────────────────
            # Ceiling = most generous cap (used when context is empty / <40%)
            # Floor   = emergency cap (used when context is 90%+ full)
            _TOOL_MAX_CAPS = {
                "read_file":      20_000,
                "view_file":      20_000,
                "grep_search":    10_000,
                "list_directory":  5_000,
                "web_search":     12_000,
                "search":         12_000,
                "run_command":    15_000,
                "analyze_image":   6_000,
            }
            _TOOL_MIN_CAPS = {
                "read_file":       3_000,
                "view_file":       3_000,
                "grep_search":     1_500,
                "list_directory":    800,
                "web_search":      2_500,
                "search":          2_500,
                "run_command":     3_000,
                "analyze_image":   1_500,
            }
            _DEFAULT_MAX = 16_000
            _DEFAULT_MIN =  4_000
            _NO_TRUNCATE_TOOLS = {
                "write_to_file",
                "replace_file_content",
                "multi_replace_file_content",
                "compress_context",
                "ask_question",
                "ask_permission",
                "think",
            }

            def _dynamic_cap(tc_name: str) -> int:
                """Return char cap for this tool given current context pressure.
                Curve: 0-40% = max cap | 40-90% = linear scale | 90%+ = min cap
                """
                ceil  = _TOOL_MAX_CAPS.get(tc_name, _DEFAULT_MAX)
                floor = _TOOL_MIN_CAPS.get(tc_name, _DEFAULT_MIN)
                if _pressure <= 0.40:
                    return ceil
                if _pressure >= 0.90:
                    return floor
                t = (_pressure - 0.40) / 0.50   # 0.0 at 40%, 1.0 at 90%
                return int(ceil + t * (floor - ceil))

            def _cap_tool_result(tc_name: str, result: str) -> str:
                """Pressure-aware head+tail truncation of tool outputs."""
                if tc_name in _NO_TRUNCATE_TOOLS:
                    return result
                if not isinstance(result, str):
                    return result
                max_chars = _dynamic_cap(tc_name)
                if len(result) <= max_chars:
                    return result

                # run_command: 40% head / 60% tail so errors at end survive
                head_ratio = 0.40 if tc_name == "run_command" else 0.55
                head_chars = int(max_chars * head_ratio)
                tail_chars = max_chars - head_chars
                omitted    = len(result) - head_chars - tail_chars

                _line_hint = ""
                if tc_name in ("read_file", "view_file"):
                    _head_lines      = result[:head_chars].count("\n")
                    _total_lines     = result.count("\n")
                    _tail_start_line = _total_lines - result[-tail_chars:].count("\n") + 1
                    _line_hint = (
                        f"\nShowing lines 1–{_head_lines} and {_tail_start_line}–{_total_lines}. "
                        f"Lines {_head_lines + 1}–{_tail_start_line - 1} omitted. "
                        f"Use read_file with start_line={_head_lines + 1} to retrieve them."
                    )

                pressure_pct = int(_pressure * 100)
                return (
                    result[:head_chars]
                    + f"\n\n...[{omitted:,} chars omitted — context at {pressure_pct}%"
                    + (", use targeted reads" if tc_name in ("read_file", "view_file") else "")
                    + f"]...\n\n"
                    + result[-tail_chars:]
                    + (f"\n\n{_line_hint}" if _line_hint else "")
                )

            # Clear any stale vision images from a previous iteration before
            # this batch of tools runs (defensive — shouldn't normally be set).
            _tools_module._pending_vision_images.clear()

            # Execute tools in parallel when beneficial
            if len(tool_calls) > 1:
                # Use parallel execution for multiple tools
                parallel_results = self._execute_tools_parallel(tool_calls)
                for slot in parallel_results:
                    if self.cancel_event.is_set():
                        break
                    # Guard against None slots (defensive: shouldn't happen but prevents crash)
                    if slot is None:
                        continue
                    tc, result = slot
                    
                    tc_id = tc.get("id") or str(tc.get("index", "0"))
                    func_name = tc.get("function", {}).get("name", "")
                    result = _cap_tool_result(func_name, result)

                    self.messages.append(
                        {
                            "role": "tool",
                            "tool_call_id": tc_id,
                            "name": func_name,
                            "content": result,
                        }
                    )
            else:
                # Single tool - execute directly
                for tc in tool_calls:
                    if self.cancel_event.is_set():
                        break
                        
                    func_name = tc.get("function", {}).get("name", "")
                    _tools_module._cancel_event = self.cancel_event
                    _tools_module._active_model_id = self.model_id
                    result = self._execute_tool_timed(tc)
                    self._current_line_len = 0
                    tc_id = tc.get("id") or str(tc.get("index", "0"))
                    result = _cap_tool_result(func_name, result)

                    self.messages.append(
                        {
                            "role": "tool",
                            "tool_call_id": tc_id,
                            "name": func_name,
                            "content": result,
                        }
                    )

            # ── Vision image injection ────────────────────────────────────────
            # read_file encodes image bytes and pushes them to
            # _tools_module._pending_vision_images so they bypass the tool-result
            # string pipeline entirely.  Drain the queue here (after ALL tools in
            # this iteration have run) and inject each image as a "user" message
            # — the only role that providers universally accept image_url content in.
            _vision_queue = getattr(_tools_module, "_pending_vision_images", [])
            if _vision_queue:
                for _vimg in list(_vision_queue):
                    self.messages.append(
                        {
                            "role": "user",
                            "content": [
                                {"type": "text", "text": f"[Image from read_file: {_vimg['meta']}]"},
                                {"type": "image_url", "image_url": {"url": f"data:{_vimg['mime']};base64,{_vimg['b64']}"}},
                            ],
                        }
                    )
                _vision_queue.clear()

            # --- Repeated Tool Failure Loop Detection ---
            if not hasattr(self, "_tool_failure_counts"):
                self._tool_failure_counts = {}

            READ_ONLY_TOOLS = {"read_file", "view_file", "grep_search", "list_dir", "read_url_content", "search_web"}

            for tc in tool_calls:
                func_name = tc.get("function", {}).get("name", "")
                args_str = tc.get("function", {}).get("arguments", "{}")
                
                # Retrieve the result we just appended for this tool call ID
                tc_id = tc.get("id") or str(tc.get("index", "0"))
                tool_res = ""
                for msg in reversed(self.messages):
                    if msg.get("role") == "tool" and msg.get("tool_call_id") == tc_id:
                        tool_res = msg.get("content") or ""
                        break
                
                # Check if it failed
                is_fail = False
                if isinstance(tool_res, str) and tool_res.strip():
                    tool_res_strip = tool_res.strip()
                    res_prefix = tool_res_strip[:100].lower()

                    if func_name in READ_ONLY_TOOLS:
                        # For read-only tools, only explicit error prefixes count as failures.
                        # Reading source code that contains words like "error" or "failed" is NOT a failure.
                        if (tool_res_strip.startswith("Error:") or 
                            tool_res_strip.startswith("[!] Error") or 
                            tool_res_strip.startswith("FileNotFoundError") or 
                            tool_res_strip.startswith("PermissionError") or 
                            tool_res_strip.startswith("NoSuchFileError") or
                            res_prefix.startswith("invalid path")):
                            is_fail = True
                    else:
                        # For commands/writes, check explicit error markers in prefix or exit code
                        if (tool_res_strip.startswith("[!] Error") or 
                            tool_res_strip.startswith("Error:") or 
                            "exit code" in res_prefix or 
                            "syntaxerror" in res_prefix or
                            "pre-commit validation failed" in res_prefix or
                            "command failed" in res_prefix):
                            is_fail = True
                
                fingerprint = (func_name, args_str)
                if is_fail:
                    count = self._tool_failure_counts.get(fingerprint, 0) + 1
                    self._tool_failure_counts[fingerprint] = count
                    
                    if count >= 3:
                        # Reset count after issuing nudge so it doesn't repeatedly spam on subsequent steps
                        self._tool_failure_counts[fingerprint] = 0
                        warning_text = (
                            f"[SYSTEM CRITICAL NOTICE] You have attempted to execute the tool `{func_name}` "
                            f"with arguments `{args_str}` 3 times in a row, and it continues to fail with the error:\n"
                            f"{tool_res}\n\n"
                            f"Your current approach is stuck in a loop. You MUST change your parameters, check the syntax, "
                            f"or try a different tool/command. Do NOT repeat this exact call again."
                        )
                        self.messages.append({
                            "role": "user",
                            "content": warning_text
                        })
                        self.console.print(f"\n[bold red][WARNING] Tool Loop Intercepted: Nudging agent to prevent repeated `{func_name}` failures.[/bold red]")

                    # Also track general failures by tool name to catch cases where the model
                    # changes arguments slightly but keeps failing the same tool type.
                    if not hasattr(self, "_tool_name_failure_counts"):
                        self._tool_name_failure_counts = {}
                    
                    name_count = self._tool_name_failure_counts.get(func_name, 0) + 1
                    self._tool_name_failure_counts[func_name] = name_count
                    
                    if name_count >= 4:
                        self._tool_name_failure_counts[func_name] = 0
                        warning_text = (
                            f"[SYSTEM NOTICE] The tool `{func_name}` has failed 4 times with different arguments in this turn. "
                            f"Your general approach with `{func_name}` is failing. Please check if your file paths are absolute, "
                            f"if directories exist, or if command flags are correct. You MUST alter your strategy or verify "
                            f"path structure before calling `{func_name}` again."
                        )
                        self.messages.append({
                            "role": "user",
                            "content": warning_text
                        })
                        self.console.print(f"\n[bold red][WARNING] Tool Type Failure Loop Intercepted: Nudging agent for `{func_name}` general failures.[/bold red]")
                else:
                    # Successful tool run clears the failure counts
                    self._tool_failure_counts.pop(fingerprint, None)
                    if hasattr(self, "_tool_name_failure_counts"):
                        self._tool_name_failure_counts.pop(func_name, None)

            # Periodic iteration context compression (every 35 iterations)
            interval = getattr(self, "_compression_interval", None) or self._get_dynamic_interval()
            if turn_iteration > 0 and turn_iteration % interval == 0:
                try:
                    pass  # Periodic compression indicator suppressed
                    self._compress_intra_turn(turn_msg_start, f"Periodic iteration #{turn_iteration} compression")
                except Exception:
                    pass

            if compression_instruction:
                try:
                    self._compress_intra_turn(turn_msg_start, compression_instruction)
                except Exception:
                    pass
            
            # Real-time persistence: save tool results and file diffs immediately
            self._persist_messages(in_progress_turn={
                "user_msg": user_message,
                "msg_start": turn_msg_start,
                "msg_end": len(self.messages),
                "messages": list(self.messages[turn_msg_start:]),
                "changes": list(self._turn_changes),
            })
            
            tool_duration = time.time() - t_tool_start
            self.turn_step_timings.append({
                "step": turn_iteration,
                "reasoning_time": reasoning_duration,
                "tool_time": tool_duration,
                "tools": [tc.get("function", {}).get("name", "") for tc in tool_calls]
            })

            # ── Per-request experience injection is handled by _get_send_messages
            # which calls get_system_prompt() → reads from the cache on every
            # iteration. No extra call needed here.

            # ── 5-request reflection counter ──────────────────────────────────
            # Increment per model request (every iteration of this loop).
            # Fires every 5 requests regardless of errors, independent of
            # response-end reflection so the sequence is never disrupted.
            self._reflect_request_counter += 1
            if self._reflect_request_counter >= 5:
                self._reflect_request_counter = 0  # reset only when fired
                try:
                    recent_start = max(turn_msg_start, len(self.messages) - 10)
                    recent_msgs  = self.messages[recent_start:]
                    last_assistant = ""
                    last_tools     = []
                    for m in reversed(recent_msgs):
                        if m.get("role") == "assistant" and m.get("content"):
                            last_assistant = m["content"]
                            break
                    for m in recent_msgs:
                        if m.get("role") == "tool":
                            last_tools.append(m)

                    _refl_msgs    = self.messages  # capture before thread starts
                    _refl_user    = user_message
                    _refl_elapsed = int(time.time() - task_start_time)
                    _refl_iter    = iteration
                    _refl_hints   = list(self.session_hints)

                    def _run_5req_reflection_bg():
                        try:
                            from utim_cli.reflection import run_reflection_phase
                            run_reflection_phase(
                                user_message=_refl_user,
                                assistant_content=last_assistant,
                                tool_results=last_tools,
                                elapsed_seconds=_refl_elapsed,
                                iterations=_refl_iter,
                                hints=_refl_hints,
                            )
                            update_experience_summary_cache(_refl_user, messages=_refl_msgs)
                        except Exception:
                            pass

                    threading.Thread(
                        target=_run_5req_reflection_bg,
                        daemon=True,
                        name=f"utim-5req-reflector-req-{self._reflect_request_counter + 5}",
                    ).start()
                except Exception:
                    pass

        elapsed = int(time.time() - task_start_time)
        elapsed_str = (
            f"{elapsed // 60}m {elapsed % 60}s" if elapsed >= 60 else f"{elapsed}s"
        )
        self.console.print(Rule(f"[dim]{elapsed_str}[/dim]", style="dim"))

        # CRITICAL: Clear the thinking-topic spinner IMMEDIATELY after the response
        # ends so the spinner stops animating. Otherwise the spinner keeps spinning
        # while background compression runs, which looks like the agent is still working.
        try:
            from utim_cli.state import STATE
            STATE["thinking_topic"] = None
        except Exception:
            pass

        # Response-end context compression (triggered after agent response ends).
        # MUST run in background so it doesn't block the main UI loop. The thinking
        # indicator is already cleared above, so the user sees the response-end Rule
        # immediately and compression happens silently behind the scenes.
        if not self.cancel_event.is_set():
            try:
                import threading
                _compress_thread = threading.Thread(
                    target=self._compress_intra_turn,
                    args=(turn_msg_start,),
                    kwargs={"instruction": "Response end compression"},
                    daemon=True,
                    name="utim-response-compress",
                )
                _compress_thread.start()
            except Exception:
                # Fallback: if threading fails for any reason, run synchronously.
                try:
                    self._compress_intra_turn(turn_msg_start, instruction="Response end compression")
                except Exception:
                    pass

        # Save turn snapshot for /rewind (even if cancelled — partial work matters)
        # ALWAYS save the turn, even if there are no code changes, so the user can rewind the conversation
        if not self.cancel_event.is_set():
            turn_entry = {
                "user_msg": user_message,
                "msg_start": turn_msg_start,
                "msg_end": len(self.messages),
                "messages": list(self.messages[turn_msg_start:]),  # Save messages slice!
                "changes": list(self._turn_changes),
                "iteration_count": turn_iteration,
                "elapsed_time": elapsed,
                "step_timings": list(self.turn_step_timings),
            }
            self.turn_history.append(turn_entry)
            # Persist messages to server for /resume (background, non-blocking)
            self._persist_messages()
            self._trigger_bg_summarization()
            
            # Automated Reflection Phase (response-end) — fires after every response.
            # This is INDEPENDENT of the 5-request counter; it does NOT reset
            # _reflect_request_counter, so the sequence continues into the next turn.
            def bg_reflection_and_cleanup(u_msg, a_content, t_results, el, iter_count, hints, msgs_snapshot):
                try:
                    from utim_cli.reflection import run_reflection_phase
                    run_reflection_phase(
                        user_message=u_msg,
                        assistant_content=a_content,
                        tool_results=t_results,
                        elapsed_seconds=el,
                        iterations=iter_count,
                        hints=hints
                    )
                    # Rebuild experience cache after response-end reflection
                    # so the next user turn gets fresh lessons immediately.
                    update_experience_summary_cache(u_msg, messages=msgs_snapshot)
                except Exception:
                    pass

                try:
                    self._cleanup_tmp_folder()
                except Exception:
                    pass

            threading.Thread(
                target=bg_reflection_and_cleanup,
                args=(
                    user_message or "",
                    final_answer or "",
                    list(self._turn_changes) if self._turn_changes else [],
                    int(elapsed),
                    turn_iteration,
                    list(self.session_hints),
                    list(self.messages),  # snapshot so thread has stable reference
                ),
                daemon=True
            ).start()
            
        self._turn_changes = []
        # Clear the @subagent tag override so the next turn uses the default system prompt
        self.active_tag = None
        self.active_tag_system_prompt = None
