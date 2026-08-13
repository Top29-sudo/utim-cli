import os
import re
import shutil
import subprocess
import difflib
import threading
import time
import queue
import requests
import json
import urllib.parse
import pathlib
import sqlite3
from typing import Dict, Optional
from .constants import DEFAULT_MODEL

# Strip ANSI/VT100 escape sequences from terminal output
_ANSI_RE = re.compile(r"\x1b(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])")

def _strip_ansi(text: str) -> str:
    return _ANSI_RE.sub("", text)


def clean_clixml(text: str) -> str:
    """Parse and extract clean error messages from PowerShell's CLIXML stream dump."""
    if not text:
        return text

    if "#< CLIXML" not in text and not re.search(r'</?(?:Objs?|MS|PR|SD|SR|S)\b', text):
        return text

    text = text.replace("#< CLIXML", "")

    s_matches = re.findall(r'<S[^>]*>(.*?)</S>', text, re.DOTALL)
    if s_matches:
        raw_text = "".join(s_matches)
    else:
        raw_text = re.sub(r'<[^>]+>', '', text)

    decoded = (
        raw_text.replace("&lt;", "<")
        .replace("&gt;", ">")
        .replace("&amp;", "&")
        .replace("&quot;", '"')
        .replace("&apos;", "'")
    )

    def replace_hex_escape(match):
        try:
            return chr(int(match.group(1), 16))
        except Exception:
            return match.group(0)

    decoded = re.sub(r'_x([0-9A-Fa-f]{4})_', replace_hex_escape, decoded)

    # Fix surrogate pairs that PowerShell CLIXML produces for emoji/astral chars.
    # PowerShell escapes e.g. U+1F9E0 () as two UTF-16 surrogates: _xD83E__DDE0_.
    # chr(0xD83E) + chr(0xDDE0) is a valid Python surrogate pair; encode+decode
    # with surrogatepass recombines them into the proper astral character.
    try:
        decoded = decoded.encode("utf-8", errors="surrogatepass").decode("utf-8", errors="replace")
    except Exception:
        pass
    decoded = re.sub(r'</?[A-Za-z0-9_]+[^>]*>', '', decoded)
    return decoded.strip()


def is_user_paid() -> bool:
    """Helper to check if the current user has a paid subscription tier."""
    import requests
    from utim_cli.config import config
    from utim_cli.client_utils import get_server_url
    
    api_key = config.get("api_key")
    if not api_key:
        return False
        
    try:
        resp = requests.get(f"{get_server_url()}/quota", headers={"X-API-Key": api_key}, timeout=5)
        if resp.status_code == 200:
            plan_data = resp.json().get("plan")
            plan_id = plan_data.get("id") if isinstance(plan_data, dict) else plan_data
            return plan_id in ("hobby", "pro", "max", "ultimate")
    except Exception:
        pass
    return False


def is_user_starter_or_higher() -> bool:
    """Helper to check if the current user has Starter plan or higher."""
    import requests
    from utim_cli.config import config
    from utim_cli.client_utils import get_server_url
    
    api_key = config.get("api_key")
    if not api_key:
        return False
        
    try:
        resp = requests.get(f"{get_server_url()}/quota", headers={"X-API-Key": api_key}, timeout=5)
        if resp.status_code == 200:
            plan_data = resp.json().get("plan")
            plan_id = plan_data.get("id") if isinstance(plan_data, dict) else plan_data
            return plan_id in ("pro", "max", "ultimate")
    except Exception:
        pass
    return False

def _make_file_uri(path: str) -> str:
    """Convert a Windows path to a clickable `file://` URI.
    Handles spaces and backslashes correctly for terminals that auto‑link URIs.
    """
    # Resolve absolute path and normalise to POSIX style
    p = pathlib.Path(path).resolve()
    # Percent‑encode characters (e.g., spaces) and replace backslashes
    encoded = urllib.parse.quote(str(p).replace('\\', '/'))
    return f"file:///{encoded}"


# ─── Background Process Management ─────────────────────────────────────────────
import uuid


# Stores running background processes: {process_id: {process, output_queue, stopped}}
_BACKGROUND_PROCESSES: Dict[int, dict] = {}
_PROCESS_COUNTER = 0
_PROCESS_LOCK = threading.Lock()

def resolve_project_path(filepath: str) -> str:
    r"""Normalizes file paths relative to the current project working directory (os.getcwd()).
    
    Prevents leading slashes like '/social-media-manager/src/app.py' or '/src/index.js'
    from being mapped to the root of drive C:\ instead of the active project working directory.
    """
    if not filepath:
        return os.getcwd()

    clean_path = str(filepath).strip()

    # On Windows, if path starts with drive letter (e.g. C:\ or c:/) or UNC path (e.g. \\...), it's a true absolute path
    if os.name == "nt":
        if re.match(r'^[a-zA-Z]:[/\\]', clean_path) or clean_path.startswith(("\\\\", "//")):
            return os.path.abspath(clean_path)
            
        # If it starts with leading slash or backslash (e.g. /src/app.py or \project\file.py)
        if clean_path.startswith(("/", "\\")):
            clean_path = clean_path.lstrip("/\\")

        return os.path.abspath(os.path.join(os.getcwd(), clean_path))
    else:
        # On POSIX (Linux / macOS / Termux)
        SYSTEM_ROOTS = ("/home/", "/Users/", "/tmp/", "/var/", "/usr/", "/etc/", "/opt/", "/mnt/", "/sdcard/", "/data/")
        if clean_path.startswith(SYSTEM_ROOTS):
            return os.path.abspath(clean_path)
            
        if clean_path.startswith("/"):
            if os.path.exists(clean_path):
                return os.path.abspath(clean_path)
_VISION_MODELS_CACHE = None

def is_model_vision_capable(model_id: str = None) -> bool:
    """Determine if a model is vision-capable (Vision: True/False) based on MODEL_REGISTRY and models.txt input_modalities."""
    global _VISION_MODELS_CACHE
    if not model_id:
        # Prefer the slot injected by the orchestrator; fall back to config as last resort.
        model_id = _active_model_id or ""
        if not model_id:
            try:
                from utim_cli.config import config
                model_id = config.get("main_model") or config.get("model") or ""
            except Exception:
                model_id = ""

    model_id_str = str(model_id).strip()
    if not model_id_str:
        return False  # unknown model → treat as non-vision (safe default)

    model_id_lower = model_id_str.lower()

    # 1. Check server MODEL_REGISTRY first
    try:
        from utim_cli.server.models import MODEL_REGISTRY
        if model_id_str in MODEL_REGISTRY:
            return MODEL_REGISTRY[model_id_str].vision
        for k, entry in MODEL_REGISTRY.items():
            if k.lower() == model_id_lower:
                return entry.vision
    except Exception:
        pass

    # 2. Build / query models.txt cache (authoritative list from OpenRouter metadata)
    if _VISION_MODELS_CACHE is None:
        _VISION_MODELS_CACHE = {}
        try:
            import json, os
            root_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            models_txt_path = os.path.join(root_dir, "models.txt")
            if not os.path.exists(models_txt_path):
                models_txt_path = "models.txt"
            if os.path.exists(models_txt_path):
                with open(models_txt_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                items = data.get("data", []) if isinstance(data, dict) else data
                for m in items:
                    mid = m.get("id", "")
                    if not mid:
                        continue
                    in_mods = m.get("architecture", {}).get("input_modalities", []) or []
                    _VISION_MODELS_CACHE[mid.lower()] = ("image" in in_mods)
        except Exception:
            _VISION_MODELS_CACHE = {}

    if model_id_lower in _VISION_MODELS_CACHE:
        return _VISION_MODELS_CACHE[model_id_lower]

    # 3. Fallback for custom / unlisted model names
    vision_keywords = ["vision", "-vl", "llava", "pixtral", "image", "multimodal", "gpt-4o", "gemini", "claude-3", "claude-4", "claude-5", "qwen3"]
    if any(kw in model_id_lower for kw in vision_keywords):
        if not any(non_v in model_id_lower for non_v in ["text-only", "coder-air", "kat-coder"]):
            return True

    return False


def _extract_file_symbols(filepath: str, file_content: str) -> list:
    """Extract symbol definitions (classes, functions, methods, headings) with line numbers."""
    symbols = []
    ext = os.path.splitext(filepath)[1].lower()
    lines = file_content.splitlines()

    if ext == ".py":
        try:
            import ast
            tree = ast.parse(file_content, filename=filepath)
            for node in ast.walk(tree):
                if isinstance(node, ast.ClassDef):
                    symbols.append({"name": node.name, "kind": "class", "start": node.lineno, "end": getattr(node, "end_lineno", node.lineno)})
                elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    symbols.append({"name": node.name, "kind": "function", "start": node.lineno, "end": getattr(node, "end_lineno", node.lineno)})
        except Exception:
            pass

    if not symbols:
        import re
        patterns = [
            (r'^\s*(?:async\s+)?def\s+([A-Za-z_]\w*)', "function"),
            (r'^\s*class\s+([A-Za-z_]\w*)', "class"),
            (r'^\s*(?:export\s+)?(?:async\s+)?function\s+([A-Za-z_]\w*)', "function"),
            (r'^\s*(?:export\s+)?class\s+([A-Za-z_]\w*)', "class"),
            (r'^\s*(?:export\s+)?const\s+([A-Za-z_]\w*)\s*=\s*(?:async\s*)?\(', "function"),
            (r'^\s*fn\s+([A-Za-z_]\w*)', "function"),
            (r'^\s*func\s+(?:\([^)]+\)\s*)?([A-Za-z_]\w*)', "function"),
            (r'^(#{1,4})\s+(.+)', "heading"),
        ]
        for idx, line in enumerate(lines, 1):
            for pat, kind in patterns:
                m = re.search(pat, line)
                if m:
                    sym_name = m.group(1) if kind != "heading" else m.group(2).strip()
                    symbols.append({"name": sym_name, "kind": kind, "start": idx, "end": idx})
                    break

    symbols.sort(key=lambda s: s["start"])
    return symbols


def _generate_file_outline_text(filepath: str, file_content: str) -> str:
    """Generate a compact structural outline of symbols and sections in a file."""
    symbols = _extract_file_symbols(filepath, file_content)
    lines = file_content.splitlines()
    total_lines = len(lines)

    if not symbols:
        return f"[FILE OUTLINE: {os.path.basename(filepath)} | {total_lines} lines | No AST symbols found]\n"

    outline_lines = [f"[FILE OUTLINE: {os.path.basename(filepath)} | {total_lines} lines | {len(symbols)} symbols found]:"]
    for s in symbols[:25]:
        kind_tag = s["kind"].upper()
        if s["start"] != s["end"] and s["end"] > s["start"]:
            outline_lines.append(f"  - [{kind_tag}] {s['name']} (Lines {s['start']}-{s['end']})")
        else:
            outline_lines.append(f"  - [{kind_tag}] {s['name']} (Line {s['start']})")
    if len(symbols) > 25:
        outline_lines.append(f"  - ... ({len(symbols) - 25} more symbols)")

    return "\n".join(outline_lines) + "\n\n"

def compress_image_base64(raw_bytes: bytes, filepath: str = "", max_dim: int = 1600, quality: int = 82) -> str:
    """
    Downscales and compresses raw image bytes into a lightweight JPEG base64 string.
    Prevents HTTP connection drops and '413 Payload Too Large' errors when uploading high-res images.
    """
    import base64 as _b64mod, io as _iomod
    try:
        from PIL import Image as _PILImage, ImageOps as _PILOps
        _img = _PILImage.open(_iomod.BytesIO(raw_bytes))
        
        # Auto-orient EXIF orientation tag if present
        try:
            _img = _PILOps.exif_transpose(_img)
        except Exception:
            pass

        _w, _h = _img.size
        # Resize if dimensions exceed max_dim or raw bytes > 1 MB
        if max(_w, _h) > max_dim or len(raw_bytes) > 1 * 1024 * 1024:
            _img.thumbnail((max_dim, max_dim), _PILImage.Resampling.LANCZOS)

        # Convert to RGB mode for JPEG format
        if _img.mode in ("RGBA", "P", "LA"):
            _bg = _PILImage.new("RGB", _img.size, (255, 255, 255))
            if _img.mode == "RGBA":
                _bg.paste(_img, mask=_img.split()[3])
            else:
                _bg.paste(_img.convert("RGBA"))
            _img = _bg
        elif _img.mode != "RGB":
            _img = _img.convert("RGB")

        _buf = _iomod.BytesIO()
        _img.save(_buf, format="JPEG", quality=quality, optimize=True)
        return _b64mod.b64encode(_buf.getvalue()).decode("utf-8")
    except Exception:
        # Fallback if Pillow is unavailable: limit payload size to max 3.5 MB
        if len(raw_bytes) > 3.5 * 1024 * 1024:
            raw_bytes = raw_bytes[: 3 * 1024 * 1024]
        return _b64mod.b64encode(raw_bytes).decode("utf-8")

def read_file(filepath: str, start_line: int = None, end_line: int = None, symbol_name: str = None, show_outline: bool = None) -> str:
    """Reads the content of a file, with optional range slicing, symbol extraction, or structural outline."""
    filepath = resolve_project_path(filepath)
    MAX_LINES = 500
    import re as _re

    _fp = filepath
    _suffix_match = _re.search(
        r'(?::\[?|(?<=\w)\[)'
        r'\s*(\d+)?\s*'
        r'(?:[,\-–—]\s*(\d+)?)?'
        r'\s*\]?$',
        _fp
    )
    if _suffix_match and _suffix_match.group(0).strip(': []'):
        if _suffix_match.group(1) or _suffix_match.group(2):
            fp_candidate = _fp[:_suffix_match.start()].strip()
            if fp_candidate:
                _fp = fp_candidate
                if start_line is None and _suffix_match.group(1):
                    start_line = int(_suffix_match.group(1))
                if end_line is None and _suffix_match.group(2):
                    end_line = int(_suffix_match.group(2))
                filepath = _fp
    
    if _fp == filepath and start_line is None:
        _naked_match = _re.search(r':(\d+)\s*$', filepath)
        if _naked_match:
            fp_candidate = filepath[:_naked_match.start()].strip()
            if fp_candidate:
                filepath = fp_candidate
                start_line = int(_naked_match.group(1))

    import os as _os
    if _os.path.isdir(filepath):
        return f"Error: '{filepath}' is a directory. To view its contents, please use list_directory."

    ext = _os.path.splitext(filepath)[1].lower()
    image_extensions = {'.png', '.jpg', '.jpeg', '.webp', '.gif', '.bmp'}
    if ext in image_extensions:
        # Collect image metadata (size, dimensions) for the text portion of the response.
        try:
            file_size = _os.path.getsize(filepath)
            size_kb = file_size / 1024.0
            size_str = f"{size_kb:.1f} KB" if size_kb < 1024 else f"{size_kb/1024:.2f} MB"
        except Exception:
            size_str = "unknown size"

        meta = f"[Image: {_os.path.basename(filepath)} | {ext.lstrip('.').upper()} | {size_str} | URI: {_make_file_uri(filepath)}]"

        # Try to also read image dimensions (pure stdlib where possible, else Pillow)
        dim_str = ""
        try:
            with open(filepath, "rb") as _f:
                _head = _f.read(64)
            # PNG: width@16, height@20 (big-endian uint32)
            if _head.startswith(b"\x89PNG\r\n\x1a\n") and len(_head) >= 24:
                import struct
                w, h = struct.unpack(">II", _head[16:24])
                dim_str = f" | {w}x{h}px"
            # GIF: width@6, height@8 (little-endian uint16)
            elif _head.startswith(b"GIF8") and len(_head) >= 10:
                import struct
                w, h = struct.unpack("<HH", _head[6:10])
                dim_str = f" | {w}x{h}px"
            # JPEG: parse SOF marker to find dimensions
            elif _head.startswith(b"\xff\xd8\xff"):
                import struct
                _f2 = open(filepath, "rb")
                try:
                    soi = _f2.read(2)
                    while True:
                        marker = _f2.read(2)
                        if len(marker) < 2:
                            break
                        if marker[0] != 0xFF:
                            break
                        # Skip SOI / EOI / RST markers
                        if marker[1] in (0xD8, 0xD9) or 0xD0 <= marker[1] <= 0xD7:
                            continue
                        seg_len_bytes = _f2.read(2)
                        if len(seg_len_bytes) < 2:
                            break
                        seg_len = struct.unpack(">H", seg_len_bytes)[0]
                        # SOFn markers (Start of Frame): 0xC0-0xCF except 0xC4,0xC8,0xCC
                        if 0xC0 <= marker[1] <= 0xCF and marker[1] not in (0xC4, 0xC8, 0xCC):
                            _f2.read(1)  # precision
                            h, w = struct.unpack(">HH", _f2.read(4))
                            dim_str = f" | {w}x{h}px"
                            break
                        else:
                            _f2.read(seg_len - 2)
                finally:
                    _f2.close()
            # WebP: 'RIFF....WEBP' then VP8 / VP8L / VP8X chunk
            elif _head.startswith(b"RIFF") and _head[8:12] == b"WEBP":
                with open(filepath, "rb") as _f3:
                    _f3.read(12)
                    chunk_hdr = _f3.read(4)
                    if chunk_hdr == b"VP8 ":
                        _f3.read(10)  # frame tag + start code
                        w = int.from_bytes(_f3.read(2), "little") & 0x3FFF
                        h = int.from_bytes(_f3.read(2), "little") & 0x3FFF
                        dim_str = f" | {w}x{h}px"
                    elif chunk_hdr == b"VP8L":
                        _f3.read(1)  # signature byte
                        b1, b2, b3, b4 = _f3.read(4)
                        w = ((b2 & 0x3F) << 8 | b1) + 1
                        h = (((b4 & 0x0F) << 10) | (b3 << 2) | ((b2 & 0xC0) >> 6)) + 1
                        dim_str = f" | {w}x{h}px"
                    elif chunk_hdr == b"VP8X":
                        _f3.read(8)
                        w = int.from_bytes(_f3.read(3), "little") + 1
                        h = int.from_bytes(_f3.read(3), "little") + 1
                        dim_str = f" | {w}x{h}px"
        except Exception:
            pass

        meta += dim_str

        # Route image to model based on vision capability:
        #
        # Vision-capable model → encode bytes here, push to _pending_vision_images.
        #   The orchestrator drains this queue after all tools complete and injects a
        #   "user" message with the raw base64 image so the model truly sees it.
        #   (image_url blocks are NOT supported inside "tool" role messages by most
        #   providers — they must live in a "user" message.)
        #
        # Non-vision model → call analyze_image() in the background and return its
        #   text description so the model has useful context.
        if is_model_vision_capable():
            import mimetypes as _mtmod
            _mime_v, _ = _mtmod.guess_type(filepath)
            _ext_v = _os.path.splitext(filepath)[1].lower()
            if not _mime_v or not _mime_v.startswith("image/"):
                _mime_v = f"image/{_ext_v[1:]}"
                if _ext_v == ".jpg":
                    _mime_v = "image/jpeg"
            try:
                with open(filepath, "rb") as _fv:
                    _raw_v = _fv.read()
                _b64_v = compress_image_base64(_raw_v, filepath)
                # Push to queue — orchestrator injects the user message after tools complete
                _pending_vision_images.append({"meta": meta, "b64": _b64_v, "mime": "image/jpeg"})
                return meta  # return clean metadata text only; no sentinel needed
            except Exception as _venc_err:
                pass  # return clean metadata text only; no sentinel needed
            except Exception as _venc_err:
                # Encoding failed — fall through to analyze_image text fallback below
                pass

        # Non-vision model (or encoding failed): describe image via external vision sub-model.
        try:
            description = analyze_image(
                filepath,
                "Identify and describe this image in detail, listing any people, actors, characters, "
                "text, UI elements, colors, visual layout, code or terminal output shown, and any "
                "visible error messages or stack traces verbatim."
            )
            return f"{meta}\n{description}"
        except Exception as _e2:
            return f"{meta}\n(Vision description unavailable: {_e2})"

    try:
        with open(filepath, "rb") as f:
            chunk = f.read(2048)
            if b"\x00" in chunk:
                return f"Error: '{filepath}' appears to be a binary file and cannot be read as text."
            
            decode_success = False
            try:
                chunk.decode("utf-8")
                decode_success = True
            except UnicodeDecodeError:
                for i in range(1, min(5, len(chunk))):
                    try:
                        chunk[:-i].decode("utf-8")
                        decode_success = True
                        break
                    except UnicodeDecodeError:
                        continue
            
            if not decode_success:
                ext = _os.path.splitext(filepath)[1].lower()
                text_extensions = {'.txt', '.md', '.py', '.js', '.ts', '.jsx', '.tsx', '.json', '.yaml', '.yml', '.ini', '.cfg', '.conf', '.sh', '.bat', '.ps1', '.html', '.css', '.csv', '.xml', '.toml'}
                if ext not in text_extensions:
                    return f"Error: '{filepath}' uses an unsupported encoding and cannot be read as text."

        with open(filepath, "r", encoding="utf-8", errors="replace") as f:
            all_lines = f.readlines()
    except Exception as e:
        return f"Error reading file {filepath}: {str(e)}"

    total = len(all_lines)
    full_content = "".join(all_lines)

    # ── Handle Symbol Search Request ──────────────────────────────────────────
    symbol_hdr = ""
    if symbol_name:
        symbols = _extract_file_symbols(filepath, full_content)
        target_sym = None
        s_lower = str(symbol_name).lower()
        for sym in symbols:
            if sym["name"].lower() == s_lower:
                target_sym = sym
                break
        if not target_sym:
            # Fallback substring match
            for sym in symbols:
                if s_lower in sym["name"].lower():
                    target_sym = sym
                    break

        if target_sym:
            start_line = target_sym["start"]
            end_line = target_sym["end"]
            symbol_hdr = f"[SYMBOL DEFINITION: '{target_sym['name']}' ({target_sym['kind'].upper()}) | Lines {start_line}-{end_line} of {total} in {filepath}]\n"
        else:
            symbol_hdr = f"[SYMBOL SEARCH: Symbol '{symbol_name}' not found in {filepath} — falling back to full file read]\n"

    parsed_start = None
    parsed_end = None
    import re

    def extract_numbers(val):
        if val is None:
            return []
        if isinstance(val, (int, float)):
            return [int(val)]
        val_str = str(val).strip()
        if not val_str:
            return []
        nums = re.findall(r"\d+", val_str)
        return [int(x) for x in nums]

    start_nums = extract_numbers(start_line)
    end_nums = extract_numbers(end_line)

    if start_nums and not end_nums and len(start_nums) >= 2:
        parsed_start = start_nums[0]
        parsed_end = start_nums[-1]
    else:
        if start_nums:
            parsed_start = start_nums[0]
            if len(start_nums) > 1 and not end_nums:
                parsed_end = start_nums[1]
        if end_nums:
            if len(end_nums) > 1:
                if parsed_start is None:
                    parsed_start = end_nums[0]
                parsed_end = end_nums[-1]
            else:
                parsed_end = end_nums[0]

    # Generate outline block if requested or automatically for code files over 60 lines
    outline_prefix = ""
    if show_outline is True or (show_outline is not False and symbol_name is None and parsed_start is None and total > 60):
        outline_prefix = _generate_file_outline_text(filepath, full_content)

    if parsed_start is not None or parsed_end is not None:
        s = max(1, parsed_start or 1)
        e = min(total, parsed_end or total)
        selected = all_lines[s - 1 : e]
        header = f"[File: {filepath} ({_make_file_uri(filepath)}) | Lines {s}-{e} of {total}]\n"
        return outline_prefix + symbol_hdr + header + "".join(selected)
    else:
        if total <= MAX_LINES:
            header = f"[File: {filepath} ({_make_file_uri(filepath)}) | {total} lines]\n"
            return outline_prefix + symbol_hdr + header + "".join(all_lines)
        elif total <= MAX_LINES * 2:
            selected = all_lines[:MAX_LINES]
            header = (
                f"[File: {filepath} ({_make_file_uri(filepath)}) | Showing lines 1-{MAX_LINES} of {total} — "
                f"use start_line/end_line or symbol_name to read further]\n"
            )
            return outline_prefix + symbol_hdr + header + "".join(selected)
        else:
            first_part = all_lines[:MAX_LINES]
            last_part = all_lines[-MAX_LINES:]
            omitted = total - (MAX_LINES * 2)
            header = (
                f"[File: {filepath} ({_make_file_uri(filepath)}) | Showing lines 1-{MAX_LINES} AND {total-MAX_LINES+1}-{total} "
                f"({omitted} lines omitted in between) of {total} total — use start_line/end_line or symbol_name to read specific sections]\n"
            )
            return (
                outline_prefix
                + symbol_hdr
                + header
                + "".join(first_part)
                + f"\n... [{omitted} lines omitted — call read_file with start_line={MAX_LINES+1} end_line={total-MAX_LINES} to read middle] ...\n\n"
                + "".join(last_part)
            )
            header = (
                f"[File: {filepath} ({_make_file_uri(filepath)}) | Showing lines 1-{MAX_LINES} and {total-MAX_LINES+1}-{total} of {total} — "
                f"critical end section preserved]\n"
            )
            result = "".join(first_part)
            # Add separator to indicate continuation
            result += f"\n... [lines {MAX_LINES+1} through {total-MAX_LINES} omitted] ...\n"
            result += "".join(last_part)
            return header + result

def _extract_patterns_after_write(filepath: str, content: str, old_content: str = ""):
    """Extract patterns from file content after write/edit operation. Runs asynchronously."""
    try:
        from .pattern_extractor import extract_patterns
        extract_patterns(filepath, content, "write" if not old_content else "edit")
    except Exception:
        pass  # Pattern extraction failures should be silent


def view_symbol(filepath: str, symbol_name: str) -> str:
    """Extracts and returns the source code of a specific class, function, or method from a Python file
    using AST analysis. Much cheaper than reading the entire file.

    Parameters
    ----------
    filepath : str
        Absolute or relative path to the target Python (.py) file.
    symbol_name : str
        The symbol to extract. Use dot notation for methods: 'ClassName.method_name'.
        For a top-level function: 'function_name'. For a class: 'ClassName'.
    """
    filepath = resolve_project_path(filepath)
    import ast
    try:
        with open(filepath, "r", encoding="utf-8") as f:
            source = f.read()
        lines = source.splitlines(keepends=True)
        tree = ast.parse(source, filename=filepath)
    except FileNotFoundError:
        return f"Error: File not found: {filepath}"
    except SyntaxError as e:
        return f"Error: Cannot parse {filepath} — SyntaxError at line {e.lineno}: {e.msg}"
    except Exception as e:
        return f"Error reading {filepath}: {e}"

    parts = symbol_name.split(".")
    target_class: str | None = None
    target_method: str | None = None

    if len(parts) == 1:
        target_method = parts[0]
    elif len(parts) == 2:
        target_class, target_method = parts
    else:
        return f"Error: symbol_name must be 'FunctionName' or 'ClassName.method_name', got: {symbol_name!r}"

    def _extract_node(node, start_line: int, end_line: int) -> str:
        snippet = "".join(lines[start_line - 1 : end_line])
        header = (
            f"[Symbol: {symbol_name} | {filepath} | Lines {start_line}-{end_line} "
            f"({end_line - start_line + 1} lines)]\n"
        )
        return header + snippet

    for node in ast.walk(tree):
        if target_class is None:
            # Top-level function
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name == target_method:
                return _extract_node(node, node.lineno, node.end_lineno)
        else:
            # Class or class method
            if isinstance(node, ast.ClassDef) and node.name == target_class:
                if target_method == target_class or target_method is None:
                    # Return the whole class
                    return _extract_node(node, node.lineno, node.end_lineno)
                # Search for method inside the class
                for item in node.body:
                    if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)) and item.name == target_method:
                        return _extract_node(item, item.lineno, item.end_lineno)
                return (
                    f"Error: Method '{target_method}' not found in class '{target_class}' in {filepath}.\n"
                    f"Available methods: " +
                    ", ".join(
                        n.name for n in node.body
                        if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))
                    )
                )

    return (
        f"Error: Symbol '{symbol_name}' not found in {filepath}.\n"
        f"Tip: Use view_file_outline('{filepath}') to see all available symbols."
    )


def view_file_outline(filepath: str) -> str:
    """Returns a compact structural outline of a file — class names, method/function names,
    and their line numbers — without returning any code body. Supports Python,
    JavaScript, TypeScript, HTML, CSS, JSON, and Markdown. Use this to cheaply map
    a large file before reading specific sections.
    """
    import os
    import re

    def outline_js(source: str, filepath: str) -> str:
        lines = source.splitlines()
        total_lines = len(lines)
        lines_out = [f"[Outline: {filepath} | {total_lines} lines | JavaScript/TypeScript]"]
        
        # Match class Name
        class_pat = re.compile(r'^\s*(?:export\s+(?:default\s+)?)?class\s+([a-zA-Z0-9_$]+)')
        # Match function name(...) or async function name(...)
        func_pat = re.compile(r'^\s*(?:export\s+(?:default\s+)?)?(?:async\s+)?function\s+([a-zA-Z0-9_$]+)\s*\(')
        # Match const name = ... =>
        arrow_pat = re.compile(r'^\s*(?:export\s+)?(?:const|let|var)\s+([a-zA-Z0-9_$]+)\s*=\s*(?:async\s*)?\(.*?\)\s*=>')
        # Match name(...) { inside class
        method_pat = re.compile(r'^\s*(?:async\s+)?([a-zA-Z0-9_$]+)\s*\([^)]*\)\s*\{')
        
        reserved = {"if", "for", "while", "switch", "catch", "function", "constructor"}

        for idx, line in enumerate(lines, start=1):
            line_strip = line.strip()
            if not line_strip or line_strip.startswith("//") or line_strip.startswith("/*") or line_strip.startswith("*"):
                continue
            
            m = class_pat.match(line)
            if m:
                lines_out.append(f"  class {m.group(1)}  [L{idx}]")
                continue
                
            m = func_pat.match(line)
            if m:
                lines_out.append(f"  function {m.group(1)}()  [L{idx}]")
                continue
                
            m = arrow_pat.match(line)
            if m:
                lines_out.append(f"  const {m.group(1)}()  [L{idx}]")
                continue
                
            m = method_pat.match(line)
            if m:
                name = m.group(1)
                if name not in reserved:
                    lines_out.append(f"    method {name}()  [L{idx}]")
                    
        return "\n".join(lines_out)

    def outline_html(source: str, filepath: str) -> str:
        lines = source.splitlines()
        total_lines = len(lines)
        lines_out = [f"[Outline: {filepath} | {total_lines} lines | HTML]"]
        
        tag_pat = re.compile(r'<\s*([a-zA-Z0-9_-]+)([^>]*)/?>')
        id_pat = re.compile(r'id=["\']([^"\']+)["\']')
        class_pat = re.compile(r'class=["\']([^"\']+)["\']')
        
        for idx, line in enumerate(lines, start=1):
            line_strip = line.strip()
            if not line_strip or line_strip.startswith("<!--"):
                continue
                
            for match in tag_pat.finditer(line):
                tag_name = match.group(1)
                attrs = match.group(2)
                
                is_significant_tag = tag_name.lower() in {
                    "head", "body", "script", "style", "main", "header", 
                    "footer", "section", "nav", "aside", "template"
                }
                
                tag_id = id_pat.search(attrs)
                tag_class = class_pat.search(attrs)
                
                if is_significant_tag or tag_id or tag_class:
                    desc = f"<{tag_name}"
                    if tag_id:
                        desc += f" id=\"{tag_id.group(1)}\""
                    if tag_class:
                        desc += f" class=\"{tag_class.group(1)}\""
                    desc += ">"
                    lines_out.append(f"  {desc}  [L{idx}]")
                    
        return "\n".join(lines_out)

    def outline_css(source: str, filepath: str) -> str:
        lines = source.splitlines()
        total_lines = len(lines)
        lines_out = [f"[Outline: {filepath} | {total_lines} lines | CSS]"]
        
        selector_pat = re.compile(r'^([^{]+)\{')
        
        for idx, line in enumerate(lines, start=1):
            line_strip = line.strip()
            if not line_strip or line_strip.startswith("/*") or line_strip.startswith("*"):
                continue
            
            m = selector_pat.match(line_strip)
            if m:
                selector = m.group(1).strip()
                selector = re.sub(r'/\*.*?\*/', '', selector).strip()
                if selector:
                    lines_out.append(f"  {selector}  [L{idx}]")
                    
        return "\n".join(lines_out)

    def outline_json(source: str, filepath: str) -> str:
        import json
        lines = source.splitlines()
        total_lines = len(lines)
        
        try:
            data = json.loads(source)
        except Exception as e:
            return f"Error: Cannot parse JSON {filepath} — {e}"
            
        lines_out = [f"[Outline: {filepath} | {total_lines} lines | JSON]"]
        
        if isinstance(data, dict):
            for k, v in data.items():
                val_type = type(v).__name__
                if isinstance(v, (dict, list)):
                    lines_out.append(f"  key \"{k}\"  ({val_type}, len={len(v)})")
                else:
                    lines_out.append(f"  key \"{k}\"  ({val_type})")
        elif isinstance(data, list):
            lines_out.append(f"  Array of {len(data)} items")
            
        return "\n".join(lines_out)

    def outline_markdown(source: str, filepath: str) -> str:
        lines = source.splitlines()
        total_lines = len(lines)
        lines_out = [f"[Outline: {filepath} | {total_lines} lines | Markdown]"]
        
        for idx, line in enumerate(lines, start=1):
            if line.startswith("#"):
                lines_out.append(f"  {line.strip()}  [L{idx}]")
                
        return "\n".join(lines_out)

    def outline_generic(source: str, filepath: str) -> str:
        lines = source.splitlines()
        total_lines = len(lines)
        return f"[Outline: {filepath} | {total_lines} lines | Supported extensions: .py, .js, .jsx, .ts, .tsx, .html, .css, .json, .md]"

    try:
        with open(filepath, "r", encoding="utf-8") as f:
            source = f.read()
    except FileNotFoundError:
        return f"Error: File not found: {filepath}"
    except Exception as e:
        return f"Error reading {filepath}: {e}"

    ext = os.path.splitext(filepath)[1].lower()
    
    if ext == ".py":
        import ast
        try:
            tree = ast.parse(source, filename=filepath)
            total_lines = source.count("\n") + 1
            lines_out = [f"[Outline: {filepath} | {total_lines} lines]"]
            for node in ast.iter_child_nodes(tree):
                if isinstance(node, ast.ClassDef):
                    lines_out.append(f"  class {node.name}  [L{node.lineno}-L{node.end_lineno}]")
                    for item in node.body:
                        if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)):
                            prefix = "async def" if isinstance(item, ast.AsyncFunctionDef) else "def"
                            lines_out.append(
                                f"    {prefix} {item.name}()  [L{item.lineno}-L{item.end_lineno}]"
                            )
                elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    prefix = "async def" if isinstance(node, ast.AsyncFunctionDef) else "def"
                    lines_out.append(f"  {prefix} {node.name}()  [L{node.lineno}-L{node.end_lineno}]")
                elif isinstance(node, ast.Assign):
                    for target in node.targets:
                        if isinstance(target, ast.Name) and target.id.isupper():
                            lines_out.append(f"  CONST {target.id}  [L{node.lineno}]")
            return "\n".join(lines_out)
        except SyntaxError as e:
            return f"Error: Cannot parse {filepath} — SyntaxError at line {e.lineno}: {e.msg}"
        except Exception as e:
            return f"Error parsing Python file {filepath}: {e}"
            
    elif ext in (".js", ".jsx", ".ts", ".tsx"):
        return outline_js(source, filepath)
    elif ext in (".html", ".htm", ".xml"):
        return outline_html(source, filepath)
    elif ext in (".css", ".scss", ".less"):
        return outline_css(source, filepath)
    elif ext == ".json":
        return outline_json(source, filepath)
    elif ext == ".md":
        return outline_markdown(source, filepath)
    else:
        return outline_generic(source, filepath)

_DRY_RUN: bool = False

def validate_syntax(filepath: str, content: str) -> Optional[str]:
    """Validates syntax of content based on file extension.
    Returns error string if invalid, None if valid or unsupported.
    """
    ext = os.path.splitext(filepath)[1].lower()
    if ext == ".py":
        import ast
        try:
            ast.parse(content, filename=filepath)
        except SyntaxError as e:
            # Include surrounding lines for context
            source_lines = content.splitlines()
            err_line = e.lineno or 1
            ctx_start = max(0, err_line - 3)
            ctx_end = min(len(source_lines), err_line + 2)
            snippet_lines = []
            for i, ln in enumerate(source_lines[ctx_start:ctx_end], start=ctx_start + 1):
                marker = " --> " if i == err_line else "     "
                snippet_lines.append(f"{marker}{i:4d}: {ln}")
            snippet = "\n".join(snippet_lines)
            return (
                f"Syntax Error in {filepath}: {e.msg}\n"
                f"  at line {e.lineno}, column {e.offset}\n\n"
                f"Context:\n{snippet}"
            )
        except Exception as e:
            return f"Parse Error in {filepath}: {str(e)}"
    elif ext == ".json":
        import json
        try:
            json.loads(content)
        except json.JSONDecodeError as e:
            return f"JSON Syntax Error: {e.msg} at line {e.lineno}, column {e.colno} in {filepath}"
        except Exception as e:
            return f"JSON Parse Error in {filepath}: {str(e)}"
    elif ext in (".yaml", ".yml"):
        try:
            import yaml
            try:
                yaml.safe_load(content)
            except Exception as e:
                return f"YAML Syntax Error in {filepath}: {str(e)}"
        except ImportError:
            pass
    elif ext == ".js":
        import shutil
        import subprocess
        import tempfile
        if shutil.which("node"):
            with tempfile.NamedTemporaryFile(suffix=".js", delete=False, mode="w", encoding="utf-8") as f:
                f.write(content)
                temp_name = f.name
            try:
                res = subprocess.run(["node", "--check", temp_name], capture_output=True, text=True, encoding="utf-8", errors="replace")
                if res.returncode != 0:
                    err = res.stderr.replace(temp_name, filepath)
                    return f"JavaScript Syntax Error in {filepath}:\n{err}"
            finally:
                try:
                    os.unlink(temp_name)
                except Exception:
                    pass
    elif ext == ".ts":
        import shutil
        import subprocess
        import tempfile
        if shutil.which("tsc"):
            with tempfile.NamedTemporaryFile(suffix=".ts", delete=False, mode="w", encoding="utf-8") as f:
                f.write(content)
                temp_name = f.name
            try:
                res = subprocess.run(["tsc", "--noEmit", "--skipLibCheck", temp_name], capture_output=True, text=True, encoding="utf-8", errors="replace")
                if res.returncode != 0:
                    err = res.stdout.replace(temp_name, filepath) + res.stderr.replace(temp_name, filepath)
                    return f"TypeScript Compilation Error in {filepath}:\n{err}"
            finally:
                try:
                    os.unlink(temp_name)
                except Exception:
                    pass
    return None

def write_file(filepath: str, content: str, force: bool = False) -> str:
    """Writes complete content to a file, overwriting any existing file. Use this to create or modify code.
    Pass force=True only when intentionally writing syntactically invalid content (e.g. test fixtures).
    """
    try:
        filepath = resolve_project_path(filepath)
        old_content = ""
        if os.path.exists(filepath):
            with open(filepath, "r", encoding="utf-8") as f:
                old_content = f.read()

        # Pre-commit syntax check — BLOCKS the write unless force=True
        syntax_error = validate_syntax(filepath, content)
        if syntax_error and not force:
            return (
                f"Pre-Commit Validation Failed: write_file aborted for {filepath}.\n"
                f"{syntax_error}\n\n"
                f"Fix the syntax error above and retry. "
                f"Pass force=True only if broken syntax is intentional."
            )

        # syntax_warning is only set when force=True bypasses a known error
        syntax_warning = f"\n\nSyntax Warning: {syntax_error}" if (syntax_error and force) else ""

        if _DRY_RUN:
            old_lines = old_content.splitlines() if old_content else []
            new_lines = content.splitlines()
            diff = list(difflib.unified_diff(old_lines, new_lines, n=0))
            added = sum(1 for line in diff if line.startswith('+') and not line.startswith('+++'))
            removed = sum(1 for line in diff if line.startswith('-') and not line.startswith('---'))
            if old_content:
                return f"[Dry Run] Successfully simulated modifying {filepath}. Projected changes: +{added} -{removed} lines."
            else:
                return f"[Dry Run] Successfully simulated creating {filepath}. Projected: {len(new_lines)} lines."

        os.makedirs(os.path.dirname(os.path.abspath(filepath)), exist_ok=True)
        with open(filepath, "w", encoding="utf-8") as f:
            f.write(content)

        # Extract patterns asynchronously after write
        import threading
        threading.Thread(target=_extract_patterns_after_write, args=(filepath, content, old_content), daemon=True).start()

        # Calculate a simple diff
        old_lines = old_content.splitlines()
        new_lines = content.splitlines()
        diff = list(difflib.unified_diff(old_lines, new_lines, n=0))
        
        added = sum(1 for line in diff if line.startswith('+') and not line.startswith('+++'))
        removed = sum(1 for line in diff if line.startswith('-') and not line.startswith('---'))

        if old_content:
            return f"Successfully modified {filepath}. Changes: +{added} -{removed} lines.{syntax_warning}"
        else:
            return f"Successfully created {filepath}. Added {len(new_lines)} lines.{syntax_warning}"
    except Exception as e:
        return f"Error writing file {filepath}: {str(e)}"

def edit_file(filepath: str, old_str: str = None, new_str: str = None, replacements: list = None, force: bool = False) -> str:
    """Replaces specific strings in a file. Can perform a single replacement or multiple non-contiguous replacements in batch.
    Pass force=True only when intentionally writing syntactically invalid content.
    """
    try:
        filepath = resolve_project_path(filepath)
        if not os.path.exists(filepath):
            return f"Error: File {filepath} does not exist."

        with open(filepath, "r", encoding="utf-8") as f:
            content = f.read()

        if replacements is not None:
            if not isinstance(replacements, list):
                return "Error: replacements must be a list of objects with 'old_str' and 'new_str' keys."
            if not replacements:
                return "Error: replacements list is empty."
            
            # Verify all replacements are valid and occur exactly once first
            # to prevent partial edits leaving the file in a broken intermediate state.
            current_content = content
            for i, rep in enumerate(replacements):
                if not isinstance(rep, dict) or "old_str" not in rep or "new_str" not in rep:
                    return f"Error: Replacement at index {i} must be a dictionary with 'old_str' and 'new_str'."
                
                o_str = rep["old_str"]
                n_str = rep["new_str"]
                
                count = current_content.count(o_str)
                if count == 0:
                    return f"Error (Replacement #{i+1}): The target string to replace was not found in the file."
                if count > 1:
                    return f"Error (Replacement #{i+1}): The target string is ambiguous as it occurs {count} times in the file. Please provide more context."
                
                current_content = current_content.replace(o_str, n_str, 1)
            
            # Pre-commit syntax check — BLOCKS the write unless force=True
            syntax_error = validate_syntax(filepath, current_content)
            if syntax_error and not force:
                return (
                    f"Pre-Commit Validation Failed: edit_file aborted for {filepath}.\n"
                    f"{syntax_error}\n\n"
                    f"Fix the syntax error above and retry. "
                    f"Pass force=True only if broken syntax is intentional."
                )
            syntax_warning = f"\n\nSyntax Warning: {syntax_error}" if syntax_error else ""

            if _DRY_RUN:
                return f"[Dry Run] Successfully simulated applying {len(replacements)} replacements in batch to {filepath}."

            # All checks passed, apply edits
            with open(filepath, "w", encoding="utf-8") as f:
                f.write(current_content)

            import difflib
            old_lines = content.splitlines()
            new_lines = current_content.splitlines()
            diff = list(difflib.unified_diff(old_lines, new_lines, n=0))
            added = sum(1 for line in diff if line.startswith('+') and not line.startswith('+++'))
            removed = sum(1 for line in diff if line.startswith('-') and not line.startswith('---'))

            return f"Successfully applied {len(replacements)} replacements in batch to {filepath}. Changes: +{added} -{removed} lines.{syntax_warning}"
        
        else:
            if old_str is None or new_str is None:
                return "Error: Must specify either 'replacements' or both 'old_str' and 'new_str'."
            
            count = content.count(old_str)
            if count == 0:
                return f"Error: The string to replace was not found in {filepath}."
            if count > 1:
                return f"Error: The string to replace occurs {count} times in {filepath}. Please provide more context in `old_str` to make it unique."

            new_content = content.replace(old_str, new_str, 1)

            # Pre-commit syntax check — BLOCKS the write unless force=True
            syntax_error = validate_syntax(filepath, new_content)
            if syntax_error and not force:
                return (
                    f"Pre-Commit Validation Failed: edit_file aborted for {filepath}.\n"
                    f"{syntax_error}\n\n"
                    f"Fix the syntax error above and retry. "
                    f"Pass force=True only if broken syntax is intentional."
                )
            syntax_warning = f"\n\nSyntax Warning: {syntax_error}" if syntax_error else ""

            if _DRY_RUN:
                return f"[Dry Run] Successfully edited {filepath} (Simulated)."

            with open(filepath, "w", encoding="utf-8") as f:
                f.write(new_content)            

            import difflib
            old_lines = content.splitlines()
            new_lines = new_content.splitlines()
            diff = list(difflib.unified_diff(old_lines, new_lines, n=0))
            added = sum(1 for line in diff if line.startswith('+') and not line.startswith('+++'))
            removed = sum(1 for line in diff if line.startswith('-') and not line.startswith('---'))

            return f"Successfully edited {filepath}. Changes: +{added} -{removed} lines.{syntax_warning}"
    except Exception as e:
        return f"Error editing file {filepath}: {str(e)}"




# Module-level cancel-event slot.  The orchestrator injects its own
# threading.Event here before each tool call so run_command can be aborted.
_cancel_event = None   # type: threading.Event | None

# Active model ID slot — injected by the orchestrator before each tool call
# (same pattern as _cancel_event). read_file reads this to decide whether to
# push image bytes to _pending_vision_images or call analyze_image instead.
_active_model_id: str = ""

# Queue for vision images: read_file pushes here when the active model is
# vision-capable; the orchestrator drains it after each tool-call batch and
# injects a "user" message containing the raw image bytes so the model can
# actually see the image (most providers reject image_url in "tool" messages).
_pending_vision_images: list = []  # list of {"meta": str, "b64": str, "mime": str}

# ─── Intelligent Sandbox mode ──────────────────────────────────────────────────
# Set to True via --sandbox CLI flag. When active, run_command uses static analysis
# to check commands for safety. Risky commands are blocked unless approved.
_SANDBOX_MODE: bool = False
_SANDBOX_IMAGE: str = "ubuntu:22.04"   # unused legacy parameter

_APPROVED_COMMANDS = set()

def approve_command(command: str):
    """Mark a specific command string as approved by the user for execution."""
    _APPROVED_COMMANDS.add(command)

def is_command_approved(command: str) -> bool:
    """Check if a command has been explicitly approved by the user."""
    return command in _APPROVED_COMMANDS

def analyze_command_safety(command: str) -> tuple:
    """Analyze a shell command for file/directory deletion or removal security risks.
    
    Only commands that remove or delete files, directories, untracked git files,
    or processes are marked as risky. Python script executions are marked risky ONLY
    if they include deletion or removal operations.
    
    Returns a tuple of (is_safe, reason).
    """
    if not command:
        return True, ""
        
    cmd_lower = command.lower().strip()
    
    # ── Deletion / Destruction Patterns ─────────────────────────────────────
    destructive_patterns = [
        (r"\brm\b", "File deletion (rm)"),
        (r"\bdel\b", "File deletion (del)"),
        (r"\berase\b", "File deletion (erase)"),
        (r"\brd\b", "Directory removal (rd)"),
        (r"\brmdir\b", "Directory removal (rmdir)"),
        (r"\bremove-item\b", "File deletion (Remove-Item)"),
        (r"\bunlink\b", "File unlinking (unlink)"),
        (r"\brmtree\b", "Recursive directory removal (rmtree)"),
        (r"\bos\.remove\b", "Python file deletion (os.remove)"),
        (r"\bos\.unlink\b", "Python file unlinking (os.unlink)"),
        (r"\bos\.rmdir\b", "Python directory removal (os.rmdir)"),
        (r"\bshutil\.rmtree\b", "Python directory deletion (shutil.rmtree)"),
        (r"\bgit\s+clean\b", "Git untracked file removal (git clean)"),
        (r"(?<!['\"-])\bformat\s+[A-Za-z]:\b", "Disk formatting (format C:)"),
        (r"^format\b", "Disk formatting (format)"),
        (r"\bkill\b", "Process termination (kill)"),
        (r"\btaskkill\b", "Process termination (taskkill)"),
        (r"\bstop-process\b", "Process termination (Stop-Process)"),
        (r"\bgit\s+push\b.*--force\b", "Force git push (overwrites remote history)"),
        (r"\bgit\s+push\b.*-f\b", "Force git push (overwrites remote history)"),
        (r"\bgit\s+reset\b.*--hard\b", "Hard git reset (discards local changes)"),
    ]
    
    # Check direct deletion patterns
    for pattern, name in destructive_patterns:
        if re.search(pattern, cmd_lower):
            return False, name

    # All non-destructive commands (including standard python script executions) are safe
    return True, ""


# ─── Live shell state (shared with utim.py UI) ────────────────────────────────
_SHELL_STATE = {
    "proc":         None,
    "cmd":          "",
    "cwd":          "",
    "output_lines": [],
    "focused":      False,
    "active":       False,
    "_app_ref":     [None],
}

_MAX_SHELL_LINES = 50


def _build_shell_argv(command: str, cwd: str) -> tuple:
    """Return the argv list that executes *command* in the correct shell.

    Returns a tuple of (argv_list, error_message). If error_message is not None,
    the caller should return it instead of executing the command.

    Dispatch rules
    ──────────────
    - Windows (native)  → powershell.exe -NoProfile -NonInteractive -EncodedCommand …
    - macOS / Linux     → bash -c …
    """
    if os.name == "nt":
        import base64
        import re

        # 1. Block bash-style here-docs or stdin redirection which fail on Windows
        #    Only block actual heredoc patterns (<<), not legitimate python -c/-m flags.
        if "<<" in command:
            return None, (
                "Error: Bash-style here-docs (<< 'EOF') and stdin script redirection are not supported on Windows PowerShell. "
                "To write or modify files, always use the dedicated 'write_file' or 'edit_file' tools. "
                "Do not attempt to write multi-line scripts via command-line redirection."
            )
        # Also block explicit stdin redirect via python - (no args after dash)
        import re as _re_heredoc
        if _re_heredoc.search(r'\bpython(?:3)?\s+-\s*(?:$|[<|])', command):
            return None, (
                "Error: Stdin script redirection (python -) is not supported on Windows PowerShell. "
                "To write or modify files, always use the dedicated 'write_file' or 'edit_file' tools."
            )

        sanitized = command
        # Replace python3 command with python
        sanitized = re.sub(r'\bpython3\b', 'python', sanitized)

        # 2. Translate 'mkdir -p' Unix-ism
        def _repl_mkdir(match):
            paths_str = match.group(1).strip()
            paths = [p for p in paths_str.split() if p]
            resolved = []
            for p in paths:
                if p.startswith("~/"):
                    p = p.replace("~/", "$env:USERPROFILE/", 1)
                elif p == "~":
                    p = "$env:USERPROFILE"
                resolved.append(f'"{p}"')
            return f"New-Item -ItemType Directory -Force -Path {', '.join(resolved)}"

        sanitized = re.sub(r'\bmkdir\s+-p\s+([^\s;&|]+(?:\s+[^\s;&|]+)*)', _repl_mkdir, sanitized)

        # 3. Translate 'rm -rf' Unix-ism
        def _repl_rm(match):
            paths_str = match.group(1).strip()
            paths = [p for p in paths_str.split() if p]
            resolved = []
            for p in paths:
                if p.startswith("~/"):
                    p = p.replace("~/", "$env:USERPROFILE/", 1)
                elif p == "~":
                    p = "$env:USERPROFILE"
                resolved.append(f'"{p}"')
            return f"Remove-Item -Recurse -Force -Path {', '.join(resolved)}"

        sanitized = re.sub(r'\brm\s+-rf\s+([^\s;&|]+(?:\s+[^\s;&|]+)*)', _repl_rm, sanitized)

        # 4. Handle '&&' and '||' separators
        if "&&" in sanitized:
            sanitized = sanitized.replace("&&", ";")
        if "||" in sanitized:
            sanitized = sanitized.replace("||", ";")

        try:
            encoded_cmd = base64.b64encode(sanitized.encode('utf-16-le')).decode('ascii')
            return ["powershell.exe", "-NoProfile", "-NonInteractive", "-EncodedCommand", encoded_cmd], None
        except Exception as e:
            return None, f"Error encoding command for PowerShell: {e}"
    return ["bash", "-c", command], None


# ── Background Process Registry ───────────────────────────────────────────────
_BACKGROUND_PROCESSES = {}
_BG_COUNTER = 0
_BG_LOCK = threading.Lock()

def shell_send_to_background() -> str:
    """Flag current running shell command to detach into background immediately."""
    with _BG_LOCK:
        _SHELL_STATE["detach_to_bg"] = True
    _invalidate_ui()
    return "Signalled command to continue in background."

def _register_bg_process(proc, cmd: str, cwd: str, start_time: float, stdout_parts: list, stderr_parts: list) -> dict:
    global _BG_COUNTER
    with _BG_LOCK:
        _BG_COUNTER += 1
        bg_id = f"bg-{_BG_COUNTER}"
        info = {
            "id": bg_id,
            "proc": proc,
            "cmd": cmd,
            "cwd": cwd,
            "start_time": start_time,
            "stdout_lines": stdout_parts,
            "stderr_lines": stderr_parts,
        }
        _BACKGROUND_PROCESSES[bg_id] = info
        return info

def list_background_processes() -> str:
    """Lists all active and completed background processes."""
    with _BG_LOCK:
        if not _BACKGROUND_PROCESSES:
            return "No background processes currently registered."
        
        lines = [f"{'ID':<8} | {'PID':<7} | {'Status':<18} | {'Runtime':<8} | {'Command'}"]
        lines.append("-" * 72)
        now = time.time()
        for bg_id, info in _BACKGROUND_PROCESSES.items():
            proc = info["proc"]
            cmd = info["cmd"]
            rc = proc.poll()
            if rc is None:
                status = "Running"
                elapsed = int(now - info["start_time"])
            else:
                status = f"Exited (code {rc})"
                elapsed = int(info.get("end_time", now) - info["start_time"])
            
            runtime_str = f"{elapsed}s"
            cmd_disp = cmd[:35] + "..." if len(cmd) > 35 else cmd
            lines.append(f"{bg_id:<8} | {proc.pid:<7} | {status:<18} | {runtime_str:<8} | {cmd_disp}")
            
        return "\n".join(lines)

def get_background_output(process_id: str = "", tail_lines: int = 100) -> str:
    """Returns recent stdout/stderr log output lines from a background process."""
    if not process_id:
        return "Error: process_id is required (e.g. 'bg-1' or '1')."
    
    clean_id = str(process_id).strip()
    if not clean_id.startswith("bg-") and clean_id.isdigit():
        clean_id = f"bg-{clean_id}"
        
    with _BG_LOCK:
        info = _BACKGROUND_PROCESSES.get(clean_id)
        if not info:
            for bid, binfo in _BACKGROUND_PROCESSES.items():
                if str(binfo["proc"].pid) == clean_id:
                    clean_id = bid
                    info = binfo
                    break
        if not info:
            return f"Error: Background process '{process_id}' not found. Use list_background_processes() to see valid IDs."
        
        proc = info["proc"]
        rc = proc.poll()
        if rc is not None and "end_time" not in info:
            info["end_time"] = time.time()
            
        status = "Running" if rc is None else f"Exited with code {rc}"
        stdout_buf = list(info.get("stdout_lines", []))
        stderr_buf = list(info.get("stderr_lines", []))
        
    tail = tail_lines or 100
    recent_stdout = stdout_buf[-tail:] if stdout_buf else []
    recent_stderr = stderr_buf[-tail:] if stderr_buf else []
    
    res = [f"--- Background Process: {clean_id} (PID: {info['proc'].pid}) ---"]
    res.append(f"Command: {info['cmd']}")
    res.append(f"Status: {status}\n")
    
    if recent_stdout:
        res.append("[stdout]")
        res.append("".join(recent_stdout).rstrip())
    if recent_stderr:
        res.append("[stderr]")
        res.append("".join(recent_stderr).rstrip())
    if not recent_stdout and not recent_stderr:
        res.append("(no log output captured yet)")
        
    return "\n".join(res)

def send_background_input(process_id: str = "", text: str = "") -> str:
    """Sends text input to stdin of a background process."""
    if not process_id:
        return "Error: process_id is required."
    clean_id = str(process_id).strip()
    if not clean_id.startswith("bg-") and clean_id.isdigit():
        clean_id = f"bg-{clean_id}"
        
    with _BG_LOCK:
        info = _BACKGROUND_PROCESSES.get(clean_id)
        if not info:
            return f"Error: Background process '{process_id}' not found."
        proc = info["proc"]
        
    if proc.poll() is not None:
        return f"Error: Background process '{clean_id}' has already exited."
        
    if proc.stdin and not proc.stdin.closed:
        try:
            in_text = text if text.endswith("\n") else text + "\n"
            proc.stdin.write(in_text)
            proc.stdin.flush()
            return f"Successfully sent input to background process '{clean_id}'."
        except Exception as e:
            return f"Error sending input to background process: {e}"
    return f"Error: Process '{clean_id}' stdin is closed or unavailable."

def stop_background_process(process_id: str = "") -> str:
    """Stops a background process."""
    if not process_id:
        return "Error: process_id is required."
    clean_id = str(process_id).strip()
    if not clean_id.startswith("bg-") and clean_id.isdigit():
        clean_id = f"bg-{clean_id}"
        
    with _BG_LOCK:
        info = _BACKGROUND_PROCESSES.get(clean_id)
        if not info:
            return f"Error: Background process '{process_id}' not found."
        proc = info["proc"]
        
    if proc.poll() is not None:
        return f"Background process '{clean_id}' was already terminated (code: {proc.poll()})."
        
    _kill_proc(proc)
    info["end_time"] = time.time()
    return f"✓ Background process '{clean_id}' (PID: {proc.pid}) terminated."


def background_tasks(action: str = "list", process_id: str = "", text: str = "", tail_lines: int = 100) -> str:
    """Unified management tool for background processes/tasks.
    Actions: 'list', 'output', 'input', 'stop'.
    """
    act = str(action).lower().strip()
    if act in ("list", "ls", "status", "all"):
        return list_background_processes()
    elif act in ("output", "log", "logs", "read", "get"):
        return get_background_output(process_id, tail_lines)
    elif act in ("input", "write", "send", "stdin"):
        return send_background_input(process_id, text)
    elif act in ("stop", "kill", "terminate", "cancel", "close"):
        return stop_background_process(process_id)
    else:
        return f"Error: Unknown action '{action}'. Valid actions are: 'list', 'output', 'input', 'stop'."


def _run_single_command_internal(command: str, dir_path: str = "", timeout: int = 120, is_background: bool = False, wait_seconds: int = 5) -> tuple:
    """Core process runner logic returning (output_string, exit_code)."""
    # Resolve working directory — fall back to process cwd
    if dir_path:
        cwd = resolve_project_path(dir_path)
        if not os.path.isdir(cwd):
            return f"Error: dir_path '{dir_path}' is not a valid directory.", -1
    else:
        cwd = os.getcwd()

    argv, error_msg = _build_shell_argv(command, cwd)
    if error_msg:
        return error_msg, -1

    try:
        # On Windows with the subprocess list form, CREATE_NEW_PROCESS_GROUP
        # lets us send CTRL_BREAK_EVENT to terminate the child tree cleanly.
        _pg_flag = subprocess.CREATE_NEW_PROCESS_GROUP if os.name == "nt" else 0
        proc = subprocess.Popen(
            argv,
            shell=False,          # argv is already fully formed — no shell wrapper
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,   # capture stderr separately
            text=True,
            encoding="utf-8",
            errors="replace",
            cwd=cwd,
            creationflags=_pg_flag,
        )
    except FileNotFoundError as e:
        # Docker/PowerShell/bash not found — give a clear error
        binary = argv[0]
        return (
            f"Error: could not start '{binary}'. "
            f"Make sure it is installed and on your PATH.\nDetail: {e}", -1
        )
    except Exception as e:
        return f"Error starting command: {e}", -1

    # ── Update shell state so the UI panel can render immediately ─────────────
    _SHELL_STATE["proc"]         = proc
    _SHELL_STATE["cmd"]          = command
    _SHELL_STATE["cwd"]          = cwd
    _SHELL_STATE["output_lines"] = []
    _SHELL_STATE["focused"]      = False
    _SHELL_STATE["active"]       = True
    _SHELL_STATE.setdefault("detach_to_bg", False)
    _invalidate_ui()

    stdout_parts: list = []
    stderr_parts: list = []
    cancel = _cancel_event  # snapshot so it can't change mid-run

    # ── Stdout reader ─────────────────────────────────────────────────────────
    _last_invalidate = [0.0]
    _INVALIDATE_INTERVAL = 0.05  # max 20 fps
    _reader_detached = [False]  # set True when command detaches to bg

    def _stdout_reader():
        try:
            for raw in proc.stdout:
                line = _strip_ansi(raw.rstrip("\n"))
                stdout_parts.append(raw)
                if not _reader_detached[0]:
                    _SHELL_STATE["output_lines"].append(line)
                    if len(_SHELL_STATE["output_lines"]) > _MAX_SHELL_LINES:
                        _SHELL_STATE["output_lines"].pop(0)
                    now = time.time()
                    if now - _last_invalidate[0] >= _INVALIDATE_INTERVAL:
                        _last_invalidate[0] = now
                        _invalidate_ui()
        except Exception:
            pass
        finally:
            if not _reader_detached[0]:
                _invalidate_ui()

    # ── Stderr reader ─────────────────────────────────────────────────────────
    def _stderr_reader():
        try:
            for raw in proc.stderr:
                stderr_parts.append(raw)
        except Exception:
            pass

    stdout_t = threading.Thread(target=_stdout_reader, daemon=True)
    stderr_t = threading.Thread(target=_stderr_reader, daemon=True)
    stdout_t.start()
    stderr_t.start()

    # ── Poll until process exits, is cancelled, detaches to bg, or times out ──
    exit_code: int = 0
    start_time = time.time()
    is_detached = False

    try:
        while True:
            # 1. User interactive detach request (Ctrl+B)
            if _SHELL_STATE.get("detach_to_bg"):
                _SHELL_STATE["detach_to_bg"] = False
                is_detached = True
                _reader_detached[0] = True
                _SHELL_STATE["active"] = False
                _SHELL_STATE["focused"] = False
                _SHELL_STATE["proc"] = None
                bg_info = _register_bg_process(proc, command, cwd, start_time, stdout_parts, stderr_parts)
                init_out = "".join(stdout_parts[-30:]) if stdout_parts else "(no output)"
                return (
                    f"[Command detached to background: {bg_info['id']} (PID: {proc.pid})]\n"
                    f"Status: Active / Running\n"
                    f"Command: {command}\n\n"
                    f"Initial Output Captured:\n{init_out}\n\n"
                    f"ℹ The agent can now continue execution. Use get_background_output(), list_background_processes(), or stop_background_process().", 0
                )

            # 2. Check if process finished naturally
            rc = proc.poll()
            if rc is not None:
                exit_code = rc
                break

            # 3. Check for cancel
            if cancel is not None and cancel.is_set():
                _kill_proc(proc)
                return "[Command aborted by user]", -1


            # 4. Auto-detach to background if process runs past max_fg_wait (3.0s max)
            # This ensures run_command NEVER blocks the agent or waits for eternity when commands hang!
            max_fg_wait = min(float(wait_seconds or 3), 3.0)
            if (time.time() - start_time >= max_fg_wait):
                is_detached = True
                _reader_detached[0] = True
                _SHELL_STATE["active"] = False
                _SHELL_STATE["focused"] = False
                _SHELL_STATE["proc"] = None
                bg_info = _register_bg_process(proc, command, cwd, start_time, stdout_parts, stderr_parts)
                init_out = "".join(stdout_parts[-40:]) if stdout_parts else "(no initial stdout)"
                init_err = "".join(stderr_parts[-20:]) if stderr_parts else ""
                res_str = (
                    f"[Command running in background: {bg_info['id']} (PID: {proc.pid})]\n"
                    f"Status: Active / Running\n"
                    f"Command: {command}\n\n"
                    f"[Initial Output (first {int(max_fg_wait)}s)]\n{init_out}"
                )
                if init_err.strip():
                    res_str += f"\n[Initial Stderr]\n{init_err}"
                res_str += "\n\nℹ The command is running in the background. The agent can now continue execution without waiting. Use background_tasks (or list_background_processes / get_background_output) to check status."
                return res_str, 0

            time.sleep(0.05)
    finally:
        if not is_detached:
            _SHELL_STATE["active"]  = False
            _SHELL_STATE["focused"] = False
            _SHELL_STATE["proc"]    = None
            _invalidate_ui()

    # Close pipes to unblock reader threads before joining (prevents "(no output)" on fast commands)
    try:
        proc.stdout.close()
    except Exception:
        pass
    try:
        proc.stderr.close()
    except Exception:
        pass
    stdout_t.join(timeout=1)
    stderr_t.join(timeout=1)

    stdout_raw = clean_clixml("".join(stdout_parts))
    stderr_raw = clean_clixml("".join(stderr_parts))

    # Strip PowerShell startup/redirect noise from stderr
    # These are PowerShell internal messages (module loading, redirect errors, type noise)
    # that leak into stderr but are not real command errors.
    _PS_NOISE_RE = re.compile(
        r'System\.Management\.Automation\..*?(?:Completed-\d+|$)|'
        r'Preparing modules for first use\..*?(?:Completed-\d+|$)|'
        r'out-file\s*:\s*FileStream was asked to open a device.*?(?:$|\n)|'
        r'For support for devices like.*?(?:$|\n)|'
        r'call CreateFile, then use the FileStream.*?(?:$|\n)|'
        r'CategoryInfo\s*:\s*OpenError.*?(?:$|\n)|'
        r'FullyQualifiedErrorId\s*:\s*FileOpenFailure.*?(?:$|\n)|'
        r'At line:\d+ char:\d+.*?(?:$|\n)',
        re.IGNORECASE | re.DOTALL
    )
    stderr_raw = _PS_NOISE_RE.sub("", stderr_raw).strip()

    MAX_CHAR_LIMIT = 80000

    def truncate_text(text, name):
        if len(text) <= MAX_CHAR_LIMIT:
            return text
        half = MAX_CHAR_LIMIT // 2
        omitted = len(text) - MAX_CHAR_LIMIT
        return (
            text[:half] +
            f"\n\n... [Omitted {omitted} characters of {name} output to prevent token bloat] ...\n\n" +
            text[-half:]
        )

    stdout_text = truncate_text(stdout_raw, "stdout")
    stderr_text = truncate_text(stderr_raw, "stderr")


    # ── Build structured result ───────────────────────────────────────────────
    parts = []
    parts.append(f"[exit_code: {exit_code}]")
    if stdout_text.strip():
        parts.append("[stdout]")
        parts.append(stdout_text.rstrip())
    if stderr_text.strip():
        parts.append("[stderr]")
        parts.append(stderr_text.rstrip())
    if not stdout_text.strip() and not stderr_text.strip():
        parts.append("(no output)")

    return "\n".join(parts), exit_code


def run_command(command: str = "", dir_path: str = "", timeout: int = 120, commands: list = None, is_background: bool = True, wait_seconds: int = 3) -> str:
    """Execute a shell command (or list of commands sequentially) and return stdout, stderr, and exit code.
    Fast commands finish synchronously; commands taking >3s automatically detach to run in the background so execution never pauses or hangs.

    Parameters
    ──────────
    command       : the shell command string to run (single command)
    dir_path      : directory to run the command in (defaults to current working dir)
    timeout       : maximum execution time in seconds (defaults to 120)
    commands      : list of shell commands to run in sequence (stops on first failure)
    is_background : defaults to True. Automatically detaches commands to background after wait_seconds if still running.
    wait_seconds  : initial output capture duration before detaching (defaults to 3s).
    """
    if commands is None:
        if not command:
            return "Error: No command specified."
        commands = [command]
    elif not commands:
        return "Error: No commands specified in list."

    if _DRY_RUN:
        results = []
        for cmd in commands:
            results.append(f"--- Command: {cmd} ---\n[Dry Run] Simulated execution of: {cmd}\n(Exit Code: 0)")
        return "\n\n".join(results)

    results = []
    for cmd in commands:
        if _SANDBOX_MODE:
            is_safe, reason = analyze_command_safety(cmd)
            if not is_safe and not is_command_approved(cmd):
                return f"Error: Command execution blocked by Intelligent Sandbox. Reason: {reason}."
            _APPROVED_COMMANDS.discard(cmd)

        res, code = _run_single_command_internal(cmd, dir_path, timeout, is_background=is_background, wait_seconds=wait_seconds)
        results.append(f"--- Command: {cmd} ---\n{res}")
        if code != 0:
            results.append(f"\n[Execution halted due to non-zero exit code: {code}]")
            break

    return "\n\n".join(results)


def _kill_proc(proc):
    """Terminate a Popen process and all its children cross-platform instantly."""
    if proc is None:
        return
    try:
        pid = proc.pid
        if os.name == "nt":
            import subprocess
            subprocess.run(
                ["taskkill", "/F", "/T", "/PID", str(pid)],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                creationflags=0x08000000 if hasattr(subprocess, "CREATE_NO_WINDOW") else 0
            )
        else:
            try:
                import signal
                os.killpg(os.getpgid(pid), signal.SIGKILL)
            except Exception:
                proc.kill()
    except Exception:
        try:
            proc.kill()
        except Exception:
            pass

    # Immediately close pipes to unblock reader threads without waiting
    try:
        if proc.stdout and not proc.stdout.closed:
            proc.stdout.close()
    except Exception:
        pass
    try:
        if proc.stderr and not proc.stderr.closed:
            proc.stderr.close()
    except Exception:
        pass


def abort_active_command():
    """Instantly kill any currently running foreground subprocess."""
    proc = _SHELL_STATE.get("proc")
    if proc is not None:
        _kill_proc(proc)
        _SHELL_STATE["proc"] = None
        _SHELL_STATE["active"] = False
        _SHELL_STATE["focused"] = False



# Global rate limiter for _invalidate_ui — prevents UI corruption from
# multiple background threads (shell reader, spinner) racing each other.
_LAST_INVALIDATE_TIME = [0.0]
_INVALIDATE_MIN_INTERVAL = 0.04  # max ~25 fps

def _invalidate_ui():
    """Ask the prompt_toolkit app to redraw (called from background threads).
    Globally rate-limited to prevent UI corruption from concurrent invalidations.
    """
    now = time.time()
    if now - _LAST_INVALIDATE_TIME[0] < _INVALIDATE_MIN_INTERVAL:
        return
    _LAST_INVALIDATE_TIME[0] = now
    app = _SHELL_STATE["_app_ref"][0]
    if app is not None:
        try:
            if app.renderer and not getattr(app.renderer, "waiting_for_cpr", False):
                app.invalidate()
        except Exception:
            pass


def shell_send_input(text: str):
    """Write text to the running shell process stdin (called from UI key handler)."""
    proc = _SHELL_STATE.get("proc")
    if proc and proc.stdin and not proc.stdin.closed:
        try:
            proc.stdin.write(text)
            proc.stdin.flush()
        except Exception:
            pass


def shell_send_ctrl_c():
    """Kill the running shell process instantly (Ctrl+C scoped to shell only).

    On Windows: uses 'taskkill /f /t' to force-kill the entire process tree
    (cmd.exe + any child processes like npm/node) — equivalent to closing a
    terminal window. This is more reliable than CTRL_BREAK_EVENT which can
    be slow or ignored by grandchild processes when shell=True is used.

    On Unix: sends SIGINT to the process group so all children receive it.
    """
    import signal as _sig
    proc = _SHELL_STATE.get("proc")
    if proc is None:
        return
    try:
        if os.name == "nt":
            # Force-kill the whole process tree instantly
            subprocess.run(
                ["taskkill", "/f", "/t", "/pid", str(proc.pid)],
                capture_output=True,
            )
        else:
            # Send SIGINT to the entire process group (pid < 0 targets group)
            try:
                os.killpg(os.getpgid(proc.pid), _sig.SIGINT)
            except Exception:
                os.kill(proc.pid, _sig.SIGINT)
    except Exception:
        try:
            proc.terminate()
        except Exception:
            pass


def list_directory(path: str = ".") -> str:
    """Lists the files and directories in a given path, formatted with type/size. Caps at 150 items to prevent token bloat."""
    try:
        abs_path = resolve_project_path(path)
        if not os.path.exists(abs_path):
            return f"Error: Path '{path}' does not exist."
        if not os.path.isdir(abs_path):
            return f"Error: Path '{path}' is a file, not a directory."

        # Excluded noisy directories unless targeted explicitly
        target_name = os.path.basename(abs_path.rstrip("/\\"))
        noise_dirs = {
            "node_modules", ".git", ".venv", "env", "__pycache__",
            ".next", ".nuxt", ".turbo", "dist", "build", "package-lock.json",
            "pnpm-lock.yaml", "yarn.lock"
        }
        
        items = os.listdir(abs_path)
        
        # Sort so directories come first, then files
        dirs = []
        files = []
        
        for item in items:
            # Check if this item is a noise dir and path is NOT targeting it directly
            if item in noise_dirs and target_name not in noise_dirs:
                is_dir = os.path.isdir(os.path.join(abs_path, item))
                if is_dir:
                    dirs.append(f"  [dir]  {item}/  (ignored contents)")
                else:
                    files.append(f"  [file] {item}  (ignored lockfile)")
                continue
                
            item_path = os.path.join(abs_path, item)
            try:
                is_dir = os.path.isdir(item_path)
                if is_dir:
                    dirs.append(f"  [dir]  {item}/")
                else:
                    size_bytes = os.path.getsize(item_path)
                    if size_bytes < 1024:
                        size_str = f"{size_bytes} B"
                    elif size_bytes < 1024 * 1024:
                        size_str = f"{size_bytes / 1024:.1f} KB"
                    else:
                        size_str = f"{size_bytes / (1024 * 1024):.1f} MB"
                    files.append(f"  [file] {item} ({size_str})")
            except Exception:
                dirs.append(f"  [unknown] {item}")
                
        all_listed = dirs + files
        total_items = len(all_listed)
        LIMIT = 150
        
        if total_items > LIMIT:
            truncated = all_listed[:LIMIT]
            remaining = total_items - LIMIT
            result = f"Contents of {path} (showing {LIMIT} of {total_items} items):\n" + "\n".join(truncated)
            result += f"\n  ... [and {remaining} more items truncated to prevent token bloat]"
            return result
        else:
            return f"Contents of {path} ({total_items} items):\n" + "\n".join(all_listed)
    except Exception as e:
        return f"Error listing directory: {str(e)}"


def web_search(prompt: str, level: str = "medium") -> str:
    """Performs an agentic deep web research based on the prompt and level.
    
    Concurrent scraping is used to fetch raw web page contents in parallel to enrich Tavily search snippets.
    """
    import concurrent.futures
    import re
    import html as html_lib
    import time
    
    from utim_cli.config import config
    api_key = os.getenv("TAVILY_API_KEY") or config.get("tavily_api_key") or config.get("TAVILY_API_KEY")
    llm_key = os.getenv("OPENROUTER_API_KEY") or config.get("api_key")
    if not llm_key:
        return "Error: Neither UTIM API key nor OPENROUTER_API_KEY environment variable is set. The research agent needs an LLM key."

    num_queries = {"low": 1, "medium": 4, "high": 8}.get(level.lower(), 4)

    # 1. Generate search queries optimized for keyword-matching search engines
    try:
        from utim_cli.bootstrap import get_subagent_rag_context
        subagent_rag_ctx = get_subagent_rag_context("web_search", prompt)
    except Exception:
        subagent_rag_ctx = ""
        
    system_prompt = (
        "You are a search engine query optimizer. Generate exactly {num_queries} distinct, short, "
        "keyword-based search queries (not full sentences) optimized for a standard keyword-matching "
        "search engine to research the following prompt. Keep each query under 5-6 words. "
        "Output ONLY the queries, one per line. Do not use quotes, bullet points, numbering, or extra text."
    ).format(num_queries=num_queries)
    if subagent_rag_ctx:
        system_prompt += f"\n\n{subagent_rag_ctx}"
    
    from utim_cli.config import config
    sub_model = config.get("subagent_model_web_search")
    if not is_user_paid():
        sub_model = "__non_agent__"
    
    queries = []
    # Non-agent mode: skip LLM query expansion, use heuristic keywords directly
    if sub_model == "__non_agent__":
        import re as _re
        s = _re.sub(r"[^\w\s\-\/\.]", " ", prompt)
        words = s.split()
        stop_words = {"find", "search", "specifically", "the", "a", "an", "and", "or", "but", "in",
                      "on", "at", "to", "for", "with", "by", "about", "from", "how", "what", "which",
                      "who", "why", "where", "when", "are", "is", "was", "were"}
        keywords = [w for w in words if w.lower() not in stop_words]
        queries = [" ".join(keywords[:6]) if keywords else " ".join(words[:6])]
    else:
        models_to_try = [
            DEFAULT_MODEL,
        ]
        if sub_model:
            models_to_try = [sub_model] + [m for m in models_to_try if m != sub_model]
        
        for model in models_to_try:
            try:
                query_gen_payload = {
                    "model": model,
                    "messages": [
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": prompt}
                    ]
                }
                from utim_cli.client_utils import proxy_openrouter_request
                resp = proxy_openrouter_request(json_data=query_gen_payload, stream=False, timeout=20)
                if resp.status_code == 200:
                    queries_text = resp.json()["choices"][0]["message"]["content"]
                    lines = [q.strip("- *1234567890.\"") for q in queries_text.splitlines() if q.strip()]
                    queries = [q for q in lines if len(q.split()) <= 8][:num_queries]
                    if queries:
                        break
            except Exception:
                continue

    if not queries:
        # Heuristic fallback to turn prompt into keywords if LLMs are down or returned empty results
        import re
        s = re.sub(r"[^\w\s\-\/\.]", " ", prompt)
        words = s.split()
        stop_words = {
            "find", "search", "specifically", "the", "a", "an", "and", "or", "but", "in", "on", 
            "at", "to", "for", "with", "by", "about", "against", "from", "how", "what", "which", 
            "who", "why", "where", "when", "are", "is", "was", "were", "be", "been", "being", 
            "have", "has", "had", "do", "does", "did", "recommendations", "recommendation",
            "reputable", "review", "reviews", "sites", "site", "sources", "source", "top", "picks",
            "include", "source", "names", "links", "link"
        }
        keywords = [w for w in words if w.lower() not in stop_words]
        fallback_query = " ".join(keywords[:6]) if keywords else " ".join(words[:6])
        queries = [fallback_query]

    # 2. Execute searches in parallel
    search_results = []
    
    def fetch_query(q):
        results = []
        # Try UTIM server proxy first if logged in
        utim_api_key = config.get("api_key")
        if utim_api_key:
            try:
                from utim_cli.client_utils import get_server_url
                proxy_url = f"{get_server_url()}/completions/search"
                proxy_headers = {
                    "X-API-Key": utim_api_key,
                    "Content-Type": "application/json"
                }
                proxy_payload = {
                    "query": q,
                    "level": level
                }
                tavily_resp = requests.post(proxy_url, json=proxy_payload, headers=proxy_headers, timeout=25)
                if tavily_resp.status_code == 200:
                    results = tavily_resp.json().get("results", [])
                    if results:
                        return results
            except Exception:
                pass

        # Local fallback if local key is available
        if api_key:
            try:
                tavily_resp = requests.post("https://api.tavily.com/search", json={
                    "api_key": api_key,
                    "query": q,
                    "search_depth": "advanced",
                    "include_raw_content": False,
                    "max_results": 10
                }, timeout=20)
                if tavily_resp.status_code == 200:
                    results = tavily_resp.json().get("results", [])
            except Exception:
                pass
            
        if not results:
            # Fallback 1: Try Mojeek Search (very friendly to scrapers, returns status 200)
            try:
                from bs4 import BeautifulSoup
                import urllib.parse
                headers = {
                    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36',
                    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8',
                    'Accept-Language': 'en-US,en;q=0.5',
                }
                encoded_q = urllib.parse.quote(q)
                mojeek_url = f"https://www.mojeek.com/search?q={encoded_q}"
                resp = requests.get(mojeek_url, headers=headers, timeout=10)
                if resp.status_code == 200:
                    soup = BeautifulSoup(resp.text, 'html.parser')
                    items = soup.find_all('li')
                    for r in items:
                        title_el = r.find('h2') or r.find('a', class_='title')
                        if not title_el:
                            continue
                        link_el = title_el.find('a') if title_el.name == 'h2' else title_el
                        desc_el = r.find('p', class_='s') or r.find('p', class_='snippet') or r.find('p')
                        
                        if link_el:
                            link = link_el.get('href', '')
                            if link.startswith('/') or 'mojeek.com' in link:
                                continue
                            title = title_el.get_text(strip=True)
                            desc = desc_el.get_text(strip=True) if desc_el else ""
                            results.append({
                                'url': link,
                                'title': title,
                                'content': desc
                            })
            except Exception:
                pass

        if not results:
            # Fallback 2: Try Yahoo Search (returns status 200, highly reliable index)
            try:
                from bs4 import BeautifulSoup
                import urllib.parse
                headers = {
                    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36',
                    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8',
                }
                encoded_q = urllib.parse.quote(q)
                yahoo_url = f"https://search.yahoo.com/search?p={encoded_q}"
                resp = requests.get(yahoo_url, headers=headers, timeout=10)
                if resp.status_code == 200:
                    soup = BeautifulSoup(resp.text, 'html.parser')
                    items = soup.find_all('div', class_='algo')
                    for r in items:
                        link_el = r.find('a')
                        desc_el = r.find('div', class_='compText') or r.find('span', class_='compText') or r.find('p')
                        
                        if link_el:
                            link = link_el.get('href', '')
                            # Unquote Yahoo redirect URL if present
                            if "/RU=" in link:
                                try:
                                    parts = link.split("/RU=")
                                    if len(parts) > 1:
                                        target = parts[1].split("/RK=")[0]
                                        link = urllib.parse.unquote(target)
                                except:
                                    pass
                            
                            title = link_el.get_text(strip=True)
                            desc = desc_el.get_text(strip=True) if desc_el else ""
                            results.append({
                                'url': link,
                                'title': title,
                                'content': desc
                            })
            except Exception as e:
                pass
                
        return results

    with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
        futures = [executor.submit(fetch_query, q) for q in queries]
        for future in concurrent.futures.as_completed(futures):
            search_results.extend(future.result())

    if not search_results:
        return "No results found during research. The search APIs or fallback endpoints may be blocked or unreachable."

    # 3. Extract unique URLs to scrape raw content in parallel
    unique_urls = []
    seen_urls = set()
    for r in search_results:
        url = r.get("url")
        if url and url not in seen_urls:
            seen_urls.add(url)
            unique_urls.append(url)
            
    # Take top 4 URLs to scrape using enhanced Scrapy-based scraper
    urls_to_scrape = unique_urls[:4]
    scraped_contents = {}

    # Try to use Scrapy-enhanced scraper for better crawling
    try:
        from .scrapy_search import enhanced_scrape_urls
        scraped_contents = enhanced_scrape_urls(urls_to_scrape, use_js=False, timeout=10)
    except ImportError:
        # Fall back to original requests-based scraping if Scrapy not available
        def scrape_url_raw(url):
            try:
                headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
                r = requests.get(url, headers=headers, timeout=10)
                if r.status_code == 200:
                    html_content = r.text
                    # Remove scripts, styles
                    html_content = re.sub(r'<(script|style).*?>.*?</\1>', '', html_content, flags=re.DOTALL | re.IGNORECASE)
                    # Remove html tags
                    text = re.sub(r'<.*?>', ' ', html_content)
                    text = html_lib.unescape(text)
                    # Format whitespace
                    lines = [l.strip() for l in text.splitlines() if l.strip()]
                    return url, "\n".join(lines)[:6000]
            except Exception:
                pass
            return url, ""

        with concurrent.futures.ThreadPoolExecutor(max_workers=4) as executor:
            scrape_futures = [executor.submit(scrape_url_raw, url) for url in urls_to_scrape]
            for future in concurrent.futures.as_completed(scrape_futures):
                url, content = future.result()
                if content:
                    scraped_contents[url] = content

    # 4. Build aggregated context payload
    aggregated_context = []
    for r in search_results[:15]:  # limit snippets to keep context clean
        url = r.get("url")
        snippet = r.get("content", "")
        scraped = scraped_contents.get(url, "")
        
        entry = f"Source URL: {url}\nSnippet: {snippet}"
        if scraped:
            entry += f"\nFull Scraped Page Body:\n{scraped}"
        aggregated_context.append(entry)

    full_context = "\n\n========================================\n\n".join(aggregated_context)[:60000]

    # 5. Summarize and reason with fallback
    from utim_cli.config import config
    sub_model = config.get("subagent_model_web_search")
    # Non-agent mode: skip LLM summarization, return raw search snippets directly
    if sub_model == "__non_agent__":
        raw_parts = []
        for entry in aggregated_context[:5]:
            raw_parts.append(entry)
        return "[Non-Agent Web Search Results]\n\n" + "\n\n---\n\n".join(raw_parts)
    models_to_try = [
        DEFAULT_MODEL,
        "cohere/north-mini-code:free",
        "openrouter/free"
    ]

    if sub_model:
        models_to_try = [sub_model] + [m for m in models_to_try if m != sub_model]
    last_err = None
    
    for model in models_to_try:
        model_retries = 2
        for attempt in range(model_retries + 1):
            try:
                try:
                    from utim_cli.bootstrap import get_subagent_rag_context
                    subagent_rag_ctx = get_subagent_rag_context("web_search", prompt)
                except Exception:
                    subagent_rag_ctx = ""
                
                sys_prompt = "You are a Deep Research AI. Analyze the provided search results and crawler content, then create a comprehensive, detailed, and properly structured technical information summary that addresses the user's research prompt. Focus on extracting exact facts, code snippets, configurations, documentation, and reasoning. Do not add conversational filler. Synthesize the data from all the sources into a highly informative report."
                if subagent_rag_ctx:
                    sys_prompt += f"\n\n{subagent_rag_ctx}"
                    
                summary_payload = {
                    "model": model,
                    "messages": [
                        {"role": "system", "content": sys_prompt},
                        {"role": "user", "content": f"Research Prompt: {prompt}\n\nSearch Results and Scraped Pages:\n{full_context}"}
                    ],
                    "stream": True
                }
                from utim_cli.client_utils import proxy_openrouter_request
                resp = proxy_openrouter_request(json_data=summary_payload, stream=True, timeout=(15, 120))
                resp.raise_for_status()
                
                summary = ""
                start_time = time.time()
                last_token_time = start_time
                for raw_line in resp.iter_lines(decode_unicode=True):
                    if _cancel_event and _cancel_event.is_set():
                        return "Error: User cancelled the research process."
                    now = time.time()
                    if now - start_time > 600:  # 10 minute absolute max
                        raise Exception("Hard timeout exceeded (10m)")
                    if now - last_token_time > 60: # 60 seconds idle timeout
                        raise Exception("Idle timeout: no tokens received for 60s")
                    if not raw_line or not raw_line.startswith("data: "):
                        continue
                    data_str = raw_line[6:]
                    if data_str == "[DONE]":
                        break
                    import json
                    try:
                        chunk = json.loads(data_str)
                    except Exception:
                        continue
                    
                    if "error" in chunk:
                        raise Exception(chunk["error"].get("message", "API Error"))
                        
                    try:
                        delta = chunk["choices"][0].get("delta", {})
                        if "content" in delta and delta["content"]:
                            summary += delta["content"]
                            last_token_time = time.time()
                    except Exception:
                        continue
                
                summary = re.sub(r"<think(?:ing)?>.*?</think(?:ing)?>", "", summary, flags=re.DOTALL).strip()
                if not summary:
                    raise Exception("Model returned empty summary after parsing.")
                
                # Save the research report to .utim_tmp/web_search_{timestamp}.md
                try:
                    os.makedirs(".utim_tmp", exist_ok=True)
                    timestamp = int(time.time())
                    report_file = f".utim_tmp/web_search_{timestamp}.md"
                    
                    # Format queries
                    queries_formatted = "\n".join(f"- `{q}`" for q in queries)
                    
                    # Format sources
                    sources_formatted = "\n".join(f"- {url}" for url in unique_urls[:15])
                    
                    report_content = f"""# Web Research Report

- **Research Prompt:** {prompt}
- **Date/Time:** {time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(timestamp))}
- **Research Level:** {level}

## Search Queries
{queries_formatted}

## Sources Explored
{sources_formatted}

---

## Research Findings

{summary}
"""
                    # Sanitize summary: strip any lone surrogates / mojibake before writing
                    _clean_summary = summary.encode("utf-8", errors="replace").decode("utf-8", errors="replace")
                    report_content = report_content.replace(summary, _clean_summary)
                    with open(report_file, "w", encoding="utf-8", errors="replace") as f:
                        f.write(report_content)
                    
                    # Append a footnote about where the file was saved
                    summary += f"\n\n*(Detailed research report saved to `{report_file}`)*"
                except Exception:
                    pass
                
                return summary
            except requests.exceptions.HTTPError as e:
                code = e.response.status_code if e.response is not None else 0
                if code == 429 and attempt < model_retries:
                    time.sleep(5 * (attempt + 1))
                    continue
                last_err = e
                break
            except Exception as e:
                last_err = e
                break
            
    return f"Error generating research summary after trying all fallback models: {last_err}"


def plan_project(plan_part: str, prompt: str, context: str = "") -> str:
    """Spawns a specialized sub-agent to plan a specific part of the project."""
    from utim_cli.config import config
    llm_key = os.getenv("OPENROUTER_API_KEY") or config.get("api_key")
    if not llm_key:
        return "Error: Neither UTIM API key nor OPENROUTER_API_KEY environment variable is set."

    # Map plan parts to specific roles (supporting 'design', 'ui', 'ux', 'ui/ux', 'ui_ux')
    ui_ux_prompt = """You are a World-Class Principal UI/UX Design Architect. Your task is to architect a comprehensive, production-ready UI/UX Plan for the requested application or feature, covering both visual interface design (UI) AND human-centered interaction experience (UX).

Do not speak in broad generalities; provide concrete, actionable specifications that engineers and designers can immediately build.

For every project, you must deliver:

1. **User Experience & Interaction Architecture (UX):**
   - **User Journeys & Key Task Flows:** Step-by-step navigational pathways for primary user personas (e.g. Onboarding, Search -> Selection -> Cart -> Checkout, Dashboard Management).
   - **Interaction Design & Feedback Loops:** Micro-interactions, hover/press animations, optimistic UI state updates, skeleton loader patterns, visual success/error toast notifications, and progress indicators.
   - **Friction Reduction & Usability:** Form field auto-formatting, inline validation timing, error prevention, keyboard navigation shortcuts, focus ring management, and cognitive load reduction strategies.
   - **Information Architecture (IA):** Navigation hierarchy, tab structures, breadcrumbs, search discoverability, filter logic, and intuitive mental model organization.
   - **Accessibility (a11y):** WCAG AA/AAA compliance, screen-reader landmarks, ARIA labels, colorblind contrast safety, and focus trap management.

2. **Visual Design System & Tokens (UI):**
   - **Design Tokens & Color Palette:** Precise color system with exact HEX/HSL codes (Primary, Secondary, Accent, Background, Surface, Muted text, Glassmorphic overlays, and Semantic status colors: Success, Warning, Danger, Info). Specify exact contrast ratios.
   - **Typography & Layout Scale:** Type scale in rem/px (Font families, weights, font-sizes, line-heights, letter-spacing for Headings, Subtitles, Body, and Captions). Specify 4px/8px base spatial grid scale, container max-widths, and border-radius tokens.
   - **Component Architecture & Hierarchy:** Break down interface into Atoms, Molecules, and Organisms (Atomic Design). Detail component nesting and layout hierarchy.

3. **Interactive States, Responsive Behavior & Edge Cases:**
   - **State Matrix:** Exact visual & interaction specs across all states: Default, Hover, Active, Focus, Disabled, Loading, Empty, and Error states.
   - **Responsive Layout Shifts:** Mobile (375px), Tablet (768px), Desktop (1280px+), and Ultrawide layout transformations.

Structure your response using clear headers, markdown tables for tokens/state matrices, and numbered flowcharts/lists for user journeys. Maintain a technical, precise, human-centric, and highly analytical tone.

If the project is a PowerPoint presentation (PPT/slide deck), document, or non-software asset, adapt the UI/UX plan to specify user engagement, slide navigation flow, visual theme, slide-by-slide hierarchy, typography, and visual content layout instead of software UI components."""

    roles = {
        "design": ui_ux_prompt,
        "ui": ui_ux_prompt,
        "ux": ui_ux_prompt,
        "ui/ux": ui_ux_prompt,
        "ui_ux": ui_ux_prompt,
        "architecture": """You are a Senior Systems Architect. Produce a production-ready architecture plan that an engineering team can act on immediately. Cover these without fluff:
- **Stack**: Recommend specific tools/frameworks/services with one-line justifications and key trade-offs
- **Structure**: Directory layout with clear separation of concerns (presentation / logic / data / infra)
- **Data Flow**: Request lifecycle, sync vs async boundaries, ASCII component diagram
- **API Design**: Endpoints, auth strategy (JWT/OAuth2), versioning, rate limiting, error contracts
- **State**: Client/server/shared state boundaries, caching layers (Redis/CDN) + invalidation strategy
- **Scalability**: Bottlenecks, failover, circuit breakers, horizontal scaling approach
- **Security**: AuthN/AuthZ model, encryption at rest/transit, top OWASP risks for this system
- **Deployment**: CI/CD shape, containerization (Docker/K8s), environment strategy (dev/staging/prod)

Rules: Be opinionated. Flag assumptions. Prefer simple over clever. No filler.

If the project is a PowerPoint presentation (PPT/slide deck), document, or non-software asset, adapt the architecture to specify the outline, slide hierarchy, layout structures, and narration/presentation flow rather than directories, APIs, and scaling strategies.""",
        "security": """You are a world-class Security Engineer and Application Security Architect. Design a comprehensive, production-grade security strategy for the entire system. Analyze the application from an attacker’s perspective and identify potential vulnerabilities, attack vectors, trust boundaries, and high-risk components. Define secure authentication and authorization flows including RBAC, ABAC, OAuth2, JWT, session management, MFA, device trust, and secure token lifecycle handling. Specify data protection strategies for data at rest, in transit, and in use using modern encryption standards, key rotation, secrets management, hashing, salting, and secure credential storage. Enforce secure coding practices aligned with OWASP Top 10, SANS, and modern AppSec standards. Include API security, rate limiting, input validation, output encoding, CSRF/XSS/SQLi prevention, SSRF protection, CSP policies, sandboxing, dependency auditing, supply chain security, and secure file handling. Design infrastructure and cloud security including network isolation, firewalls, WAF, IAM policies, zero-trust architecture, container security, CI/CD hardening, runtime monitoring, and intrusion detection. Define logging, auditing, anomaly detection, threat monitoring, incident response workflows, backup/recovery strategies, and compliance considerations (GDPR, SOC2, HIPAA if applicable). Provide actionable recommendations, architecture-level protections, and implementation-level safeguards with clear reasoning behind every security decision.

If the project is a PowerPoint presentation (PPT/slide deck), document, or non-software asset, adapt this plan to cover data confidentiality, distribution controls, or access control policies for the final document.""",
        "database": """You are an expert Database Administrator. Create a detailed database schema, relationships, indexing strategies, and query optimization plans.

If the project is a PowerPoint presentation (PPT/slide deck), document, or non-software asset, adapt this plan to detail data collection, slide tables/graphics data, or information schemas required for the content.""",
        "verification": """You are an elite QA Engineer, Senior Software Architect, and Principal Code Reviewer specializing in deep system validation, debugging, and production-grade quality assurance. Thoroughly analyze the provided codebase, runtime behavior, logs, stack traces, UI output, architecture decisions, and all available context. Compare the implementation against the original requirements, design specifications, expected workflows, and intended user experience. Detect and explain all bugs, edge-case failures, race conditions, performance bottlenecks, memory leaks, state management issues, accessibility problems, security risks, responsiveness issues, missing features, broken integrations, and architectural inconsistencies. Identify missing or incorrect CSS, layout instability, animation glitches, typography inconsistencies, spacing/alignment problems, responsive design failures, and deviations from the intended visual design system. Validate frontend, backend, APIs, database interactions, authentication flows, caching behavior, and asynchronous operations. Analyze error logs deeply to trace root causes instead of only identifying surface-level failures. Detect bad coding practices, dead code, duplicated logic, anti-patterns, scalability concerns, and maintainability risks. Verify proper handling of loading states, empty states, retries, failures, permissions, validation, and edge-case user interactions. Ensure adherence to clean architecture principles, secure coding standards, performance optimization practices, and framework best practices. Output a highly structured, strict, implementation-focused checklist of exact fixes required. Each checklist item must include: the issue, root cause, affected component/file if identifiable, severity level, exact corrective action, and why the fix is necessary. Prioritize issues intelligently from critical to low priority and ensure the output is actionable enough for direct implementation without ambiguity.

If the project is a PowerPoint presentation (PPT/slide deck), document, or non-software asset, adapt the verification checklist to cover readability, styling consistency, formatting alignment, visual appeal, grammar, and completeness of content against requirements."""
    }
    
    system_role = roles.get(plan_part.lower(), "You are an expert Technical Planner. Create a detailed implementation plan for the requested domain.")
    
    system_content = (
        f"{system_role}\n\n"
        "CRITICAL PLANNING DIRECTIVES:\n"
        "1. DO NOT WRITE CODE SNIPPETS, programming scripts, programming code, or function definitions in the plan. The goal of this planning agent is to design high-level/low-level architectures, layouts, sequential steps, schemas, and outlines. Avoid writing actual code blocks.\n"
        "2. RESPECT THE SPECIFIC PROJECT FORMAT. If the user requested a PowerPoint presentation (PPT/slide deck), document, or non-software asset, adapt the plan to match that format entirely. Do not default to website, UI components, directory structures, or API routes. Detail the slide structure, narration points, visual elements, content outlines, and page layouts instead.\n"
        "3. FORMAT DIRECTORY TREES CLEANLY: When presenting directory or file structures, use standard ASCII markers (`|-- `, `\\`-- `, `|   `) or clean indented markdown lists (`- client/`, `  - index.html`). NEVER output complex unicode box-drawing characters (like ├── or └──) to prevent terminal display encoding corruption.\n"
        "4. MARKDOWN FORMATTING REQUIREMENTS (CRITICAL): The plan is saved as a .md file and rendered as markdown. You MUST follow these rules:\n"
        "   - TABLES: Use proper GFM pipe-table syntax with aligned dashes. Example:\n"
        "     | Header 1 | Header 2 |\n"
        "     |----------|----------|\n"
        "     | Cell 1   | Cell 2   |\n"
        "   - FILE TREES: Use fenced code blocks with ```text or just indented ASCII lines. Never use unicode box-drawing chars.\n"
        "   - FLOW CHARTS / DIAGRAMS: Use ```mermaid fenced code blocks for flowcharts, sequence diagrams, or graphs.\n"
        "   - LISTS: Use proper markdown bullet (-) or numbered (1.) lists with consistent indentation.\n"
        "   - CODE: Use ```language fenced code blocks for any configuration, YAML, JSON, or command examples.\n"
        "   - HEADINGS: Use ## for sections, ### for subsections, #### for sub-subsections. Never skip levels.\n"
        "   - BOLD/ITALIC: Use **bold** and *italic* for emphasis where appropriate.\n"
        "   - BLOCKQUOTES: Use > for important callouts, warnings, or notes.\n"
        "   - HORIZONTAL RULES: Use --- between major sections for visual separation.\n"
        "   - LINKS: Use [text](url) format for any references.\n"
        "   - NEVER use raw HTML tags for formatting. Use pure markdown only.\n"
        "   - NEVER use unicode special characters (em dashes, bullet operators, etc.) — stick to ASCII or standard markdown syntax."
    )
    
    try:
        from utim_cli.bootstrap import get_subagent_rag_context
        subagent_rag_ctx = get_subagent_rag_context("plan_project", prompt)
        if subagent_rag_ctx:
            system_content += f"\n\n{subagent_rag_ctx}"
    except Exception:
        pass
    
    # Gather workspace/project context
    workspace_context = ""
    try:
        if os.path.exists("."):
            items = [item for item in os.listdir(".") if not item.startswith(".") and item not in ("__pycache__", "node_modules", "build", "dist")]
            if items:
                workspace_context += f"Existing workspace files/folders: {', '.join(items)}\n"
            # Read snippet of key project files
            for key_file in ["package.json", "requirements.txt", "setup.py", "README.md"]:
                if os.path.exists(key_file):
                    try:
                        with open(key_file, "r", encoding="utf-8") as f:
                            workspace_context += f"\nSnippet of {key_file}:\n{f.read(1500)}\n"
                    except Exception:
                        pass
    except Exception:
        pass

    user_content = f"Project Prompt: {prompt}\n"
    if workspace_context:
        user_content += f"\nWorkspace & Project Context:\n{workspace_context}\n"
    if context:
        user_content += f"\nPrevious Context/Other Plans:\n{context}\n"
        
    from utim_cli.config import config
    sub_model = config.get("subagent_model_plan_project")
    # Non-agent mode: return the prompt directly as a simple task list without LLM
    if sub_model == "__non_agent__":
        return f"[Non-Agent Planner Mode]\n\nTask: {prompt}\n\nNo LLM planning was performed. The main agent will handle all planning inline."
    models_to_try = [
        DEFAULT_MODEL,
        "cohere/north-mini-code:free",
        "openrouter/free"
    ]

    if sub_model:
        models_to_try = [sub_model] + [m for m in models_to_try if m != sub_model]
    last_err = None
    
    for model in models_to_try:
        model_retries = 2
        for attempt in range(model_retries + 1):
            try:
                payload = {
                    "model": model,
                    "messages": [
                        {"role": "system", "content": system_content},
                        {"role": "user", "content": user_content}
                    ],
                    "stream": True
                }
                import time
                from utim_cli.client_utils import proxy_openrouter_request
                resp = proxy_openrouter_request(json_data=payload, stream=True, timeout=(15, 120))
                resp.raise_for_status()
                
                plan = ""
                start_time = time.time()
                last_token_time = start_time
                for raw_line in resp.iter_lines(decode_unicode=True):
                    if _cancel_event and _cancel_event.is_set():
                        return "Error: User cancelled the planning process."
                    now = time.time()
                    if now - start_time > 900:  # 15 minute absolute max for planning
                        raise Exception("Hard timeout exceeded (15m)")
                    if now - last_token_time > 120: # 120 seconds idle timeout for planning (models can think a long time)
                        raise Exception("Idle timeout: no tokens received for 120s")
                    if not raw_line or not raw_line.startswith("data: "):
                        continue
                    data_str = raw_line[6:]
                    if data_str == "[DONE]":
                        break
                    import json
                    try:
                        chunk = json.loads(data_str)
                    except Exception:
                        continue
    
                    if "error" in chunk:
                        raise Exception(chunk["error"].get("message", "API Error"))
    
                    try:
                        delta = chunk["choices"][0].get("delta", {})
                        if "content" in delta and delta["content"]:
                            plan += delta["content"]
                            last_token_time = time.time()
                    except Exception:
                        continue
    
                # Clean up thinking tags, tool_call blocks, and corrupted unicode box characters
                import re
                plan = re.sub(r"<think(?:ing)?>.*?</think(?:ing)?>", "", plan, flags=re.DOTALL).strip()
                # Strip any raw tool_call XML blocks that leak into the plan
                plan = re.sub(r"<tool_call>.*?</tool_call>", "", plan, flags=re.DOTALL)
                plan = re.sub(r"<invoke>.*?</invoke>", "", plan, flags=re.DOTALL)
                plan = re.sub(r"<tool_calls>.*?</tool_calls>", "", plan, flags=re.DOTALL)
                # Sanitize raw/corrupted unicode box drawing characters into clean ASCII tree markers
                plan = plan.replace("├── ", "|-- ").replace("└── ", "`-- ").replace("│   ", "|   ")
                # Clean up excessive blank lines from stripping
                plan = re.sub(r"\n{3,}", "\n\n", plan).strip()
    
                if not plan:
                    raise Exception("Model returned empty plan after parsing.")            
                
                # Save the plan to disk
                os.makedirs(".utim_tmp/plans", exist_ok=True)
                plan_file = f".utim_tmp/plans/{plan_part.lower()}_plan.md"
                with open(plan_file, "w", encoding="utf-8") as f:
                    f.write(plan)
                
                return f"Plan successfully generated and saved to {plan_file}. Please read this file when you need to implement the detailed {plan_part} plan."
            except requests.exceptions.HTTPError as e:
                code = e.response.status_code if e.response is not None else 0
                if code == 429 and attempt < model_retries:
                    time.sleep(5 * (attempt + 1))
                    continue
                last_err = e
                break
            except Exception as e:
                last_err = e
                break
            
    return f"Error generating plan after trying all fallback models: {last_err}"



_GREP_STATE = {"tool_type": None, "tool_path": None, "checked": False}


def _grep_find_search_tool():
    """Locate the best available search binary (rg, ag, or grep).

    Search order:
      1. ripgrep (rg)
      2. Silver Searcher (ag)
      3. standard grep
    """
    if _GREP_STATE["checked"]:
        return _GREP_STATE["tool_type"], _GREP_STATE["tool_path"]
    try:
        import shutil as _sh
        rg_path = _sh.which("rg") or _sh.which("rg.exe")
        if rg_path:
            _GREP_STATE["tool_type"] = "rg"
            _GREP_STATE["tool_path"] = rg_path
            _GREP_STATE["checked"] = True
            return "rg", rg_path
    except Exception:
        pass
    try:
        import ripgrep as _rg_pkg
        _bin = getattr(_rg_pkg, "rg_path", None)
        if _bin and os.path.isfile(_bin):
            _GREP_STATE["tool_type"] = "rg"
            _GREP_STATE["tool_path"] = _bin
            _GREP_STATE["checked"] = True
            return "rg", _bin
    except Exception:
        pass
    try:
        import shutil as _sh
        ag_path = _sh.which("ag") or _sh.which("ag.exe")
        if ag_path:
            _GREP_STATE["tool_type"] = "ag"
            _GREP_STATE["tool_path"] = ag_path
            _GREP_STATE["checked"] = True
            return "ag", ag_path
        grep_path = _sh.which("grep") or _sh.which("grep.exe")
        if grep_path:
            _GREP_STATE["tool_type"] = "grep"
            _GREP_STATE["tool_path"] = grep_path
            _GREP_STATE["checked"] = True
            return "grep", grep_path
    except Exception:
        pass

    _GREP_STATE["checked"] = True
    return None, None


def _grep_read_text(full_file: str, max_bytes: int = 4_000_000):
    """Read a file as text with encoding detection. Returns None for binary/too-large files."""
    try:
        size = os.path.getsize(full_file)
    except OSError:
        return None
    if size > max_bytes or size == 0:
        return None
    try:
        with open(full_file, "rb") as fh:
            raw = fh.read()
    except OSError:
        return None
    # Binary sniff: NUL byte or a high ratio of control chars in the sample head
    head = raw[:8192]
    if b"\x00" in head:
        return None
    if head:
        ctrl = sum(1 for b in head if (b < 7 or 13 < b < 27) and b not in (9, 10))
        if ctrl / len(head) > 0.10:
            return None
    for enc in ("utf-8", "utf-8-sig", "cp1252", "latin-1"):
        try:
            return raw.decode(enc)
        except (UnicodeDecodeError, LookupError):
            continue
    return raw.decode("latin-1", errors="replace")


def _grep_iter_files(root_path: str, is_file: bool, include_globs, exclude_globs):
    """Yield candidate file paths, honouring glob include/exclude rules with symlink-cycle protection."""
    import fnmatch

    noise_dirs = {".git", "node_modules", "__pycache__", ".venv", "venv", "env", ".env",
                  "dist", "build", ".next", ".nuxt", ".cache", ".pytest_cache", ".mypy_cache",
                  ".tox", ".eggs", "target", ".gradle", ".idea", ".vs", ".vscode",
                  ".utim", ".utim_tmp", "coverage", "vendor", "bower_components", ".terraform"}
    noise_exts = {".png", ".jpg", ".jpeg", ".ico", ".gif", ".bmp", ".webp", ".tiff", ".pyc", ".pyo",
                  ".exe", ".dll", ".so", ".dylib", ".obj", ".o", ".a", ".lib", ".zip", ".tar",
                  ".gz", ".tgz", ".bz2", ".xz", ".7z", ".rar", ".db", ".sqlite", ".sqlite3",
                  ".pdf", ".mp3", ".mp4", ".avi", ".mov", ".wav", ".flac", ".ogg", ".woff",
                  ".woff2", ".ttf", ".eot", ".otf", ".class", ".jar", ".war", ".min.js", ".map"}

    def _matches_any(name: str, rel: str, globs):
        for g in globs:
            if fnmatch.fnmatch(name, g) or fnmatch.fnmatch(rel, g) or fnmatch.fnmatch(rel, "*/" + g):
                return True
        return False

    if is_file:
        yield root_path
        return

    seen_real = set()
    try:
        root_real = os.path.realpath(root_path)
        seen_real.add(root_real)
    except OSError:
        pass

    for cur, dirs, files in os.walk(root_path, followlinks=True):
        kept = []
        for d in dirs:
            if d in noise_dirs:
                continue
            full_d = os.path.join(cur, d)
            if os.path.islink(full_d):
                try:
                    real_d = os.path.realpath(full_d)
                except OSError:
                    continue
                if real_d in seen_real or not os.path.isdir(real_d):
                    continue  # cycle or dangling symlink
                seen_real.add(real_d)
            kept.append(d)
        dirs[:] = sorted(kept)

        for fname in sorted(files):
            if fname.lower().endswith(tuple(noise_exts)) or fname in noise_exts:
                continue
            full_f = os.path.join(cur, fname)
            rel = os.path.relpath(full_f, root_path).replace("\\", "/")
            if exclude_globs and _matches_any(fname, rel, exclude_globs):
                continue
            if include_globs and not _matches_any(fname, rel, include_globs):
                continue
            yield full_f


def grep_search(query: str, path: str = ".", is_regex: bool = False, case_sensitive: bool = False,
                includes=None, match_per_line: bool = True, max_results: int = 50) -> str:
    """Ultra-reliable, ultra-fast codebase search (literal or regex).

    Reliability guarantees:
    - Literal-first semantics: regex only when is_regex=True (no surprise auto-promotion).
    - Single-file or directory targets; missing/invalid paths report a clear error.
    - ripgrep acceleration when available, with automatic fallback to a hardened,
      multithreaded Python scanner on ANY ripgrep failure.
    - Binary files, huge files, symlink cycles and noise dirs are safely skipped.
    - Encoding ladder (utf-8 -> utf-8-sig -> cp1252 -> latin-1) so real-world files never crash the scan.
    - Glob includes/excludes ('*.py', '!*.min.js'), case control, result capping,
      line truncation, dedup and a truncation notice.

    Modes:
    - match_per_line=True  -> 'rel/path:LINE:snippet' per match (default).
    - match_per_line=False -> unique matching files with per-file match counts.
    """
    import fnmatch
    from concurrent.futures import ThreadPoolExecutor

    # ── Input validation ───────────────────────────────────────────────────────
    if query is None or str(query) == "":
        return "Error: 'query' must be a non-empty string."
    query = str(query)

    try:
        max_results = int(max_results)
    except (TypeError, ValueError):
        max_results = 50
    max_results = max(1, min(max_results, 500))

    try:
        target_path = os.path.abspath(resolve_project_path(path) if path else os.getcwd())
    except Exception as e:
        return f"Error: could not resolve path '{path}': {e}"

    if not os.path.exists(target_path):
        return f"Error: path '{path}' does not exist."
    is_file_target = os.path.isfile(target_path)
    if not is_file_target and not os.path.isdir(target_path):
        return f"Error: path '{path}' is neither a file nor a directory."

    # Smart Regex Auto-Detection:
    # If is_regex is False but query contains regex alternation '|' or operators ('\b', '^', '$'),
    # automatically enable regex mode if it compiles cleanly as a valid regex pattern!
    if not is_regex and ("|" in query or "\\b" in query or "(?" in query):
        try:
            pattern = re.compile(query, 0 if case_sensitive else re.IGNORECASE)
            is_regex = True
        except re.error:
            pattern = None
    elif is_regex:
        try:
            pattern = re.compile(query, 0 if case_sensitive else re.IGNORECASE)
        except re.error as e:
            return f"Error: invalid regex '{query}': {e}"
    else:
        pattern = None  # literal search uses str ops only

    # ── Parse include/exclude globs ────────────────────────────────────────────
    raw_globs = []
    if isinstance(includes, (list, tuple, set)):
        raw_globs = [str(x).strip() for x in includes]
    elif isinstance(includes, str) and includes.strip():
        raw_globs = [p.strip() for p in includes.split(",")]
    include_globs, exclude_globs = [], []
    for g in raw_globs:
        if not g:
            continue
        if g.startswith("!"):
            body = g[1:].strip()
            if body:
                exclude_globs.append(body)
        else:
            include_globs.append(g)

    # ── Path A: Native Search Tool Acceleration ───────────────────────────────
    tool_type, tool_path = _grep_find_search_tool()
    if tool_type:
        if tool_type == "rg":
            rg_cmd = [tool_path, "--color", "never", "--no-heading", "--no-messages", "--path-separator", "/",
                      "--with-filename"]
            if match_per_line:
                rg_cmd += ["--line-number"]
            else:
                rg_cmd += ["--count"]
            if not case_sensitive:
                rg_cmd.append("-i")
            if not (is_regex or pattern is not None):
                rg_cmd.append("--fixed-strings")
            for g in include_globs:
                rg_cmd += ["--glob", g]
            for g in exclude_globs:
                rg_cmd += ["--glob", "!" + g]
            rg_cmd += [query, target_path]
        elif tool_type == "ag":
            rg_cmd = [tool_path, "--nocolor", "--nogroup", "--filename"]
            if match_per_line:
                rg_cmd.append("--numbers")
            else:
                rg_cmd.append("-c")
            if not case_sensitive:
                rg_cmd.append("-i")
            else:
                rg_cmd.append("-s")
            if not (is_regex or pattern is not None):
                rg_cmd.append("-Q")
            for g in include_globs:
                rx = g.replace(".", "\\.").replace("*", ".*").replace("?", ".")
                rg_cmd += ["-G", f"{rx}$"]
            for g in exclude_globs:
                rg_cmd += ["--ignore", g]
            rg_cmd += [query, target_path]
        else:  # grep
            rg_cmd = [tool_path, "-r", "-I", "--color=never", "--with-filename"]
            if match_per_line:
                rg_cmd.append("-n")
            else:
                rg_cmd.append("-c")
            if not case_sensitive:
                rg_cmd.append("-i")
            if not (is_regex or pattern is not None):
                rg_cmd.append("-F")
            for g in include_globs:
                rg_cmd.append(f"--include={g}")
            for g in exclude_globs:
                rg_cmd.append(f"--exclude={g}")
            rg_cmd += [query, target_path]

        rg_usable = False
        try:
            import subprocess as _sp
            # Avoid a console window flash on Windows; absolute path already resolved above
            win_flags = _sp.CREATE_NO_WINDOW if os.name == "nt" else 0
            res = _sp.run(rg_cmd, capture_output=True, text=True, encoding="utf-8",
                          errors="replace", timeout=30, creationflags=win_flags)
            if res.returncode in (0, 1):  # 0 = matches, 1 = no matches (clean)
                rg_usable = True
                raw_lines = [ln for ln in res.stdout.splitlines() if ln.strip()] if res.stdout else []
                cwd = os.getcwd()

                if not raw_lines:
                    return f"No matches found for '{query}' in {path}."

                if not match_per_line:
                    # rg --count -> 'path:COUNT' (path separator forced to '/')
                    rows, total = [], 0
                    for ln in raw_lines[:max_results]:
                        fpath, _, cnt = ln.rpartition(":")
                        cnt = cnt.strip() if cnt.strip().isdigit() else "?"
                        rel = os.path.relpath(fpath, cwd).replace("\\", "/") if fpath else ln
                        rows.append(f"  - {rel} ({cnt} match{'es' if cnt != '1' else ''})")
                        total += int(cnt) if cnt.isdigit() else 0
                    header = f"[Matching Files for '{query}' | {len(rows)} file{'s' if len(rows) != 1 else ''} | {total} total matches]"
                    return header + "\n" + "\n".join(rows)

                formatted, seen = [], set()
                _rg_line_re = re.compile(r"^(.*?):(\d+):(.*)$")
                for ln in raw_lines:
                    m = _rg_line_re.match(ln)
                    if not m:
                        continue
                    fpath, lnum, content = m.group(1), m.group(2), m.group(3)
                    snippet = " ".join(content.split())[:400]
                    rel = os.path.relpath(fpath, cwd).replace("\\", "/")
                    key = (rel, lnum.strip())
                    if key in seen:
                        continue
                    seen.add(key)
                    formatted.append(f"{rel}:{lnum.strip()}:{snippet}")
                    if len(formatted) >= max_results:
                        break
                if not formatted:
                    return f"No matches found for '{query}' in {path}."
                truncated_note = f"\n… (+{len(raw_lines) - len(formatted)} more matches not shown; raise max_results to see more)" if len(raw_lines) > len(formatted) else ""
                return (f"[Search Results for '{query}' | {len(formatted)} matches]"
                        + "\n" + "\n".join(formatted) + truncated_note)
        except Exception:
            rg_usable = False
        if not rg_usable:
            pass  # fall through to the Python engine below

    # ── Path B: hardened multithreaded Python engine ───────────────────────────
    use_regex = pattern is not None
    if not use_regex:
        literal_lower = query.lower() if not case_sensitive else None

    def _scan_file(full_file: str):
        """Return (rel_path, [(line_no, snippet), ...]) or None."""
        text = _grep_read_text(full_file)
        if text is None:
            return None
        rel = os.path.relpath(full_file, os.getcwd()).replace("\\", "/")
        hits = []
        for i, line in enumerate(text.splitlines(), start=1):
            matched = False
            if use_regex:
                if pattern.search(line):
                    matched = True
            else:
                if case_sensitive:
                    matched = query in line
                else:
                    matched = literal_lower in line.lower()
            if matched:
                hits.append((i, " ".join(line.split())[:400]))
                if match_per_line and len(hits) >= max_results:
                    break
                if not match_per_line and len(hits) >= 5000:
                    break  # sanity cap for per-file counting
        if not hits:
            return None
        return (rel, hits)

    candidates = list(_grep_iter_files(target_path, is_file_target, include_globs, exclude_globs))
    if not candidates:
        scope = "matching the include filters" if include_globs else "scannable"
        return f"No matches found for '{query}' in {path} (no {scope} files)."

    found = []
    try:
        with ThreadPoolExecutor(max_workers=min(8, max(2, (os.cpu_count() or 4)))) as pool:
            for item in pool.map(_scan_file, candidates, chunksize=16):
                if item:
                    found.append(item)
    except Exception as e:
        return f"Error during search scan: {e}"

    display_path = path if path else "."

    if not match_per_line:
        if not found:
            return f"No matches found for '{query}' in {display_path}."
        found.sort(key=lambda t: t[0].lower())
        rows = found[:max_results]
        total = sum(len(h) for _, h in rows)
        header = f"[Matching Files for '{query}' | {len(rows)} file{'s' if len(rows) != 1 else ''} | {total} total matches]"
        body = "\n".join(f"  - {rel} ({len(h)} match{'es' if len(h) != 1 else ''})" for rel, h in rows)
        extra = f"\n… (+{len(found) - len(rows)} more files not shown)" if len(found) > len(rows) else ""
        return header + "\n" + body + extra

    formatted, seen = [], set()
    for rel, hits in found:
        for lnum, snippet in hits:
            key = (rel, lnum)
            if key in seen:
                continue
            seen.add(key)
            formatted.append(f"{rel}:{lnum}:{snippet}")
            if len(formatted) >= max_results:
                break
        if len(formatted) >= max_results:
            break

    if not formatted:
        return f"No matches found for '{query}' in {display_path}."
    truncated_note = f"\n… (results capped at {max_results}; raise max_results to see more)" if len(seen) >= max_results else ""
    return f"[Search Results for '{query}' | {len(formatted)} matches]\n" + "\n".join(formatted) + truncated_note


search = grep_search
search_codebase = grep_search






def manage_memory(action: str, key: str = "", content: str = "",
                  category: str = "fact", query: str = "") -> str:
    """Manages persistent cross-session memory stored in .utim/memory.json.

    Actions
    -------
    save        Store a memory under *key* with optional *category*.
                Categories: 'behaviour' (how user communicates/works),
                            'preference' (UI, design, style choices),
                            'fact'       (explicit facts/codes/data user stated),
                            'project'    (architecture & tech decisions).
    read        Return the full content of *key*.
    search      Keyword-search across all keys+content, return top matches
                with short previews.  Use *query* for the search terms.
    get_traits  Return ONLY 'behaviour' and 'preference' memories in compact
                form (used to seed session context without bloating the prompt).
    list        Return all keys and their categories with 60-char previews.
    delete      Remove *key* from memory.
    verify      Verify user identity using the secret code passed in *query*.
    """
    import os, json, pathlib, time as _time
    from utim_cli.state import STATE
    from utim_cli.config import get_utim_dir
    mem_file = get_utim_dir() / "memory.json"
    os.makedirs(mem_file.parent, exist_ok=True)

    memories: dict = {}
    if mem_file.exists():
        try:
            with open(mem_file, "r", encoding="utf-8") as f:
                memories = json.load(f)
        except Exception as e:
            return f"Error: memory.json is corrupted and could not be loaded: {e}. Aborting to prevent data loss. Please fix or delete .utim/memory.json."

    # Ensure all memories are synced to ChromaDB user_memories on load
    try:
        from utim_cli.vector_memory import get_user_memories_memory
        vm = get_user_memories_memory()
        if vm and vm.collection:
            from utim_cli.state import STATE
            if not STATE.get("memories_synced", False):
                for k, v in memories.items():
                    content_val = v if isinstance(v, str) else v.get("content", "")
                    cat = "fact" if isinstance(v, str) else v.get("category", "fact")
                    updated_at = "" if isinstance(v, str) else v.get("updated_at", "")
                    vm.add_text(
                        text_id=k,
                        content=content_val,
                        metadata={"category": cat, "updated_at": updated_at}
                    )
                STATE["memories_synced"] = True
    except Exception:
        pass

    def _save():
        with open(mem_file, "w", encoding="utf-8") as f:
            json.dump(memories, f, indent=2, ensure_ascii=False)

    act = action.lower()
    is_verified = STATE.get("is_verified", False)
    sensitive_keywords = {"girlfriend", "gf", "wife", "spouse", "partner", "relationship", "secret", "password", "code", "private", "personal", "anushka", "puchkuli"}

    if act == "verify":
        if not query:
            return "Error: 'query' parameter (containing the secret code) is required for verification."
        
        # Collect all possible secret codes from memories
        possible_codes = []
        for k, v in memories.items():
            if "secret_code" in k.lower() or "user_secret" in k.lower():
                val = v if isinstance(v, str) else v.get("content")
                if val:
                    possible_codes.append(val.strip())

        if not possible_codes:
            return "Error: No secret code was found in memory. Please set one first or check memory keys."

        clean_query = query.strip().lower()
        matched = False
        for code in possible_codes:
            if clean_query == code.lower():
                matched = True
                break

        if matched:
            STATE["is_verified"] = True
            return "Verification successful! User identity has been verified for this session."
        else:
            return "Verification failed. The provided code does not match the stored secret code."

    elif act == "save":
        if not key:
            return "Error: 'key' is required to save a memory."
        
        # If not verified, block saving/updating any sensitive keys or content
        if not is_verified:
            if any(w in key.lower() or w in content.lower() for w in sensitive_keywords):
                return (
                    "[VERIFICATION REQUIRED] Access to or modification of sensitive information requires identity verification. "
                    "Please ask the user for the secret code, and once provided, call the manage_memory tool with action=\"verify\" and the code as the query parameter."
                )

        allowed_cats = {"behaviour", "preference", "fact", "project"}
        cat = category.lower() if category.lower() in allowed_cats else "fact"
        memories[key] = {
            "content": content,
            "category": cat,
            "updated_at": _time.strftime("%Y-%m-%dT%H:%M:%S"),
        }
        _save()

        # Sync to Vector DB
        try:
            from utim_cli.vector_memory import get_user_memories_memory
            vm = get_user_memories_memory()
            if vm:
                vm.add_text(
                    text_id=key,
                    content=content,
                    metadata={"category": cat, "updated_at": memories[key]["updated_at"]}
                )
        except Exception:
            pass

        return f"Memory saved: [{cat}] '{key}'."

    elif act == "read":
        if not key:
            return "Error: 'key' is required to read a memory."
        
        # If not verified, block reading if the key itself contains any sensitive keywords
        if not is_verified:
            if any(w in key.lower() for w in sensitive_keywords):
                return (
                    "[VERIFICATION REQUIRED] Access to or modification of sensitive information requires identity verification. "
                    "Please ask the user for the secret code, and once provided, call the manage_memory tool with action=\"verify\" and the code as the query parameter."
                )

        entry = memories.get(key)
        if not entry:
            return f"No memory found for key '{key}'."
        
        # Support legacy flat-string entries
        if isinstance(entry, str):
            content_text = entry
            result = f"[fact] {key}:\n{entry}"
        else:
            content_text = entry.get("content", "")
            result = f"[{entry.get('category', 'fact')}] {key} (saved {entry.get('updated_at', '?')}):\n{content_text}"

        # If not verified, block reading if the content contains any sensitive keywords
        if not is_verified:
            if any(w in content_text.lower() for w in sensitive_keywords):
                return (
                    "[VERIFICATION REQUIRED] Access to or modification of sensitive information requires identity verification. "
                    "Please ask the user for the secret code, and once provided, call the manage_memory tool with action=\"verify\" and the code as the query parameter."
                )
        return result

    elif act == "search":
        if not query:
            return "Error: 'query' is required for search."

        # If not verified and query is sensitive, block immediately
        if not is_verified:
            if any(w in query.lower() for w in sensitive_keywords):
                return (
                    "[VERIFICATION REQUIRED] Access to or modification of sensitive information requires identity verification. "
                    "Please ask the user for the secret code, and once provided, call the manage_memory tool with action=\"verify\" and the code as the query parameter."
                )

        # Try semantic search using ChromaDB first
        try:
            from utim_cli.vector_memory import get_user_memories_memory
            vm = get_user_memories_memory()
            if vm and vm.collection:
                results = vm.query(query, n_results=25)
                hits = []
                for r in results:
                    m_id = r.get("id")
                    content_text = r["content"]
                    cat = r.get("metadata", {}).get("category", "fact")
                    
                    if not m_id:
                        continue
                    
                    # If hit is sensitive and user is not verified, block/skip
                    if not is_verified:
                        if any(w in m_id.lower() or w in content_text.lower() for w in sensitive_keywords):
                            continue
                    
                    preview = content_text[:80].replace("\n", " ") + ("…" if len(content_text) > 80 else "")
                    hits.append(f"[{cat}] {m_id}: {preview}")
                    if len(hits) >= 10:
                        break
                if hits:
                    return "Semantic Search results:\n" + "\n".join(hits)
        except Exception:
            pass

        # Normalise query: lowercase, strip punctuation, expand common synonyms
        _SYNONYMS: dict[str, list[str]] = {
            "color":      ["colour"],
            "colour":     ["color"],
            "favorite":   ["favourite", "fav", "fave", "preferred"],
            "favourite":  ["favorite", "fav", "fave", "preferred"],
            "fav":        ["favorite", "favourite"],
            "prefer":     ["favorite", "favourite", "like", "love", "want"],
            "preference": ["prefer", "favorite", "favourite", "like"],
            "secret":     ["code", "key", "password", "token"],
            "password":   ["secret", "code", "key", "token"],
            "code":       ["secret", "password", "key", "token"],
            "style":      ["design", "theme", "aesthetic", "look"],
            "design":     ["style", "theme", "aesthetic", "look"],
            "theme":      ["style", "design", "color", "colour"],
            "dark":       ["dark mode", "night"],
            "explain":    ["explanation", "details", "verbose"],
            "project":    ["app", "application", "codebase", "repo"],
            "wife":       ["bou", "bouer", "spouse", "partner", "girlfriend", "gf", "relationship", "marriage"],
            "bou":        ["wife", "bouer", "spouse", "partner", "girlfriend", "gf", "relationship", "marriage"],
            "bouer":      ["wife", "bou", "spouse", "partner", "girlfriend", "gf", "relationship", "marriage"],
            "girlfriend": ["gf", "wife", "bou", "bouer", "partner", "spouse", "relationship", "love", "fiancee"],
            "gf":         ["girlfriend", "wife", "bou", "partner", "spouse"],
            "partner":    ["wife", "bou", "girlfriend", "gf", "spouse"],
            "husband":    ["spouse", "partner", "boyfriend", "bf", "relationship", "marriage", "jamai", "bor"],
            "boyfriend":  ["bf", "husband", "partner", "spouse", "relationship", "love", "fiance"],
            "bf":         ["boyfriend", "husband", "partner", "spouse"],
            "jamai":      ["husband", "bor", "partner"],
            "bor":        ["husband", "jamai", "partner"],
            "name":       ["nam", "called", "identity"],
            "nam":        ["name", "called"],
        }
        raw_tokens = query.lower().split()
        q_tokens = [tok.strip("?,.!-()\"'[]{}*&^%$#@;:_+=|\\/") for tok in raw_tokens]
        q_tokens = [tok for tok in q_tokens if tok]

        expanded: set[str] = set(q_tokens)
        for tok in q_tokens:
            for syn in _SYNONYMS.get(tok, []):
                expanded.add(syn)
        expanded.add(query.lower())

        hits = []
        import re
        for k, v in memories.items():
            text = v if isinstance(v, str) else v.get("content", "")
            cat  = "fact" if isinstance(v, str) else v.get("category", "fact")
            haystack = (k + " " + text).lower()
            
            words = set(re.findall(r'[a-z0-9]+', haystack))
            matched = False
            for term in expanded:
                if ' ' in term or '_' in term or '-' in term:
                    if term in haystack:
                        matched = True
                        break
                else:
                    if term in words:
                        matched = True
                        break

            if matched:
                # If hit is sensitive and user is not verified, block immediately
                if not is_verified:
                    if any(w in k.lower() or w in text.lower() for w in sensitive_keywords):
                        return (
                            "[VERIFICATION REQUIRED] Access to or modification of sensitive information requires identity verification. "
                            "Please ask the user for the secret code, and once provided, call the manage_memory tool with action=\"verify\" and the code as the query parameter."
                        )
                preview = text[:80].replace("\n", " ") + ("…" if len(text) > 80 else "")
                hits.append(f"[{cat}] {k}: {preview}")
        if not hits:
            return f"No memories matched '{query}'."
        return "Search results:\n" + "\n".join(hits)

    elif act == "get_traits":
        trait_cats = {"behaviour", "preference"}
        entries = []
        for k, v in memories.items():
            if isinstance(v, str):
                continue
            if v.get("category") in trait_cats:
                # Extra safety: filter out sensitive key/content if not verified
                if not is_verified:
                    content_val = v.get("content", "")
                    if any(w in k.lower() or w in content_val.lower() for w in sensitive_keywords):
                        continue
                entries.append((k, v))
        
        entries.sort(key=lambda x: x[1].get("updated_at", ""), reverse=True)
        
        lines = []
        for k, v in entries[:15]:
            preview = v["content"][:120].replace("\n", " ")
            lines.append(f"• [{v['category']}] {k}: {preview}")
        if not lines:
            return "No behavioural traits stored yet."
        return "User traits:\n" + "\n".join(lines)

    elif act == "list":
        if not memories:
            return "Memory is empty."
        lines = []
        for k, v in memories.items():
            content_val = v if isinstance(v, str) else v.get("content", "")
            cat = "fact" if isinstance(v, str) else v.get("category", "fact")
            
            # Redact previews of sensitive entries if not verified
            is_key_sensitive = any(w in k.lower() or w in content_val.lower() for w in sensitive_keywords)
            if is_key_sensitive and not is_verified:
                preview = "[REDACTED - VERIFICATION REQUIRED]"
            else:
                preview = content_val[:60].replace("\n", " ")
                if len(content_val) > 60:
                    preview += "…"
            
            lines.append(f"- [{cat}] {k}: {preview}")
        return "Memories (" + str(len(lines)) + " entries):\n" + "\n".join(lines)

    elif act == "delete":
        if not key:
            return "Error: 'key' is required to delete a memory."
        if key not in memories:
            return f"No memory found for key '{key}'."

        # If not verified, block deleting any sensitive keys
        if not is_verified:
            if any(w in key.lower() for w in sensitive_keywords):
                return (
                    "[VERIFICATION REQUIRED] Access to or modification of sensitive information requires identity verification. "
                    "Please ask the user for the secret code, and once provided, call the manage_memory tool with action=\"verify\" and the code as the query parameter."
                )

        del memories[key]
        _save()

        # Delete from Vector DB too
        try:
            from utim_cli.vector_memory import get_user_memories_memory
            vm = get_user_memories_memory()
            if vm and vm.collection:
                vm.collection.delete(ids=[key])
        except Exception:
            pass

        return f"Memory deleted: '{key}'."

    return f"Error: Unknown action '{action}'. Valid actions: save, read, search, get_traits, list, delete, verify."


def analyze_image(image_path: str, prompt: str) -> str:
    """Analyzes a local image file using a vision model."""
    import os, base64, requests, mimetypes
    
    if not os.path.exists(image_path):
        return f"Error: Image file '{image_path}' not found."
        
    mime_type, _ = mimetypes.guess_type(image_path)
    if not mime_type or not mime_type.startswith("image/"):
        # Fallback if mimetypes fails
        ext = os.path.splitext(image_path)[1].lower()
        if ext in ['.png', '.jpg', '.jpeg', '.webp', '.gif']:
            mime_type = f"image/{ext[1:]}"
            if ext == '.jpg': mime_type = "image/jpeg"
        else:
            return f"Error: File '{image_path}' does not appear to be a supported image format."

    from utim_cli.config import config
    sub_model = config.get("subagent_model_analyze_image")
    if not is_user_paid():
        sub_model = "__non_agent__"
    if sub_model == "__non_agent__":
        try:
            from utim_cli.blender_agent import _phase0_local_analysis
            brief = _phase0_local_analysis(image_path)
            colors_str = ", ".join(f"[{c[0]}, {c[1]}, {c[2]}]" for c in brief.get("dominant_colors", []))
            return (
                f"[Non-Agent Image Analysis Results]\n\n"
                f"Image Path: {image_path}\n"
                f"Resolution: {brief.get('width')}x{brief.get('height')} px\n"
                f"Aspect Ratio: {brief.get('aspect_ratio')}\n"
                f"Average Brightness: {brief.get('brightness')}\n"
                f"Has Transparency: {brief.get('has_transparency')}\n"
                f"Dominant Colors (RGB): {colors_str}\n"
                f"Face Detected: {brief.get('face_landmarks', {}).get('estimated_face_present', False)}\n"
                f"Estimated Layer Depth: {brief.get('depth_hints', {}).get('estimated_layer_depth', 1)}\n"
                f"Tattoo Check Recommended: {brief.get('potential_tattoos', {}).get('check_tattoos', False)}\n"
            )
        except Exception as e:
            return f"Error performing local image analysis: {e}"

    try:
        with open(image_path, "rb") as f:
            _raw_img = f.read()
            encoded_image = compress_image_base64(_raw_img, image_path)
            mime_type = "image/jpeg"
    except Exception as e:
        return f"Error reading image file: {e}"


    from utim_cli.config import config
    llm_key = os.getenv("OPENROUTER_API_KEY") or config.get("api_key")
    if not llm_key:
        return "Error: Neither UTIM API key nor OPENROUTER_API_KEY environment variable is set."

    payload = {
        "messages": [
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": prompt},
                    {
                        "type": "image_url",
                        "image_url": {"url": f"data:{mime_type};base64,{encoded_image}"}
                    }
                ]
            }
        ]
    }

    models_to_try = [
        "google/gemma-4-31b-it:free",
        "google/gemma-4-26b-a4b-it:free",
        "nvidia/nemotron-3-nano-omni-30b-a3b-reasoning:free",
        "nvidia/nemotron-nano-12b-v2-vl:free",
        "openrouter/free"
    ]
    last_err = None
    
    for model in models_to_try:
        payload["model"] = model
        model_retries = 2
        for attempt in range(model_retries + 1):
            try:
                from utim_cli.client_utils import proxy_openrouter_request
                resp = proxy_openrouter_request(json_data=payload, stream=False, timeout=60)
                resp.raise_for_status()
                return resp.json()["choices"][0]["message"]["content"]
            except requests.exceptions.HTTPError as e:
                code = e.response.status_code if e.response is not None else 0
                if code == 429 and attempt < model_retries:
                    import time
                    time.sleep(5 * (attempt + 1))
                    continue
                last_err = e
                break
            except Exception as e:
                last_err = e
                break

    return f"Error analyzing image after trying all fallback models. Last error: {last_err}"


def is_image_mostly_black(image_path: str, threshold: float = 0.95) -> bool:
    """Check if the image is mostly black (common output when NSFW safety filters are triggered)."""
    try:
        from PIL import Image
        with Image.open(image_path) as img:
            gray_img = img.convert("L")
            pixels = list(gray_img.getdata())
            # Count pixels that are zero or near-zero (e.g. intensity < 10)
            black_pixels = sum(1 for p in pixels if p < 10)
            ratio = black_pixels / len(pixels)
            return ratio > threshold
    except Exception:
        return False


def safe_truncate_prompt(text: str, limit: int = 799) -> str:
    """Safely truncate prompt to character limit without cutting mid-word."""
    if len(text) <= limit:
        return text
    truncated = text[:limit]
    last_space = truncated.rfind(' ')
    if last_space > 0:
        return truncated[:last_space]
    return truncated


def generate_3d_model(
    type: str,
    prompt: Optional[str] = None,
    image_path: Optional[str] = None,
    image_url: Optional[str] = None,
    original_model_task_id: Optional[str] = None,
    model: Optional[str] = "v3.1",
    model_version: Optional[str] = None,
    model_seed: Optional[int] = None,
    name: Optional[str] = None,
    output_format: Optional[str] = "glb",
    **kwargs
) -> str:
    """
    Submits a 3D model generation task to Tripo AI via UTIM server proxy,
    polls until success, and downloads the resulting GLB/OBJ model file into the local `.utim_tmp/blender_assets/` folder.
    
    Parameters
    ----------
    type:
        Task type. Must be 'text_to_model', 'image_to_model', 'multiview_to_model', 'texture_model', or 'refine_model'.
    prompt:
        Text prompt for text_to_model.
    image_path:
        Local path to an image file. If provided, it is automatically uploaded to the server first to get a file_token.
    image_url:
        Public image URL for image_to_model.
    original_model_task_id:
        Task ID of the base model for texture_model or refine_model.
    model:
        Model engine version. Defaults to 'v3.1'.
    model_version:
        Tripo Open API model version (e.g. 'v3.0', 'v3.1').
    model_seed:
        Optional integer seed for reproducible generation.
    name:
        Optional custom file name for the downloaded 3D model. Defaults to a random UUID.
    output_format:
        File format for the download. Defaults to 'glb' (or matching Tripo's output).
    """
    import requests
    import os
    import time
    import uuid
    import pathlib
    import re
    from utim_cli.config import config
    from utim_cli.client_utils import get_server_url
    
    if not is_user_starter_or_higher():
        return "Error: Blender & 3D Tools are only available on the Starter plan or higher. Please upgrade your subscription."
    
    api_key = config.get("api_key")
    if not api_key:
        return "Error: No API key found. Please run 'utim login' first."

    # Load configured default model from configuration if available
    configured_model = config.get("subagent_model_blender_3d")
    if configured_model and configured_model not in ("__non_agent__", "__none__"):
        if model == "v3.1":
            model = configured_model

    # Load defaults from config if present
    defaults = config.get("subagent_blender_3d_defaults") or {}
    if prompt is None:
        prompt = defaults.get("prompt")
    if image_path is None:
        image_path = defaults.get("image_path")
    if original_model_task_id is None:
        original_model_task_id = defaults.get("original_model_task_id")
    for key, val in defaults.get("kwargs", {}).items():
        if key not in kwargs:
            kwargs[key] = val

    # Map model types to correct tasks
    if model == "rigging":
        type = "animate_rig"
    elif model == "animation":
        type = "animate_retarget"

    # Interactive manual mode configuration prompting or auto mode filtering
    mode = config.get("subagent_model_blender_3d_mode") or "auto"
    if mode == "manual":
        try:
            from utim_cli.utim import _run_in_terminal_safe

            save_for_future = defaults.get("save_for_future", False)
            _user_submitted = [False]  # set to True only when user presses Enter to submit

            def show_dialog():
                nonlocal prompt, image_path, original_model_task_id, save_for_future
                _user_submitted[0] = False  # reset each time (in case called again)
                import sys
                from prompt_toolkit import Application
                from prompt_toolkit.key_binding import KeyBindings
                from prompt_toolkit.layout import Layout, HSplit, VSplit, Window
                from prompt_toolkit.layout.controls import FormattedTextControl
                from prompt_toolkit.styles import Style as PTStyle

                # ── Build rows ───────────────────────────────────────────────
                # Each row: {"key", "label", "type": bool|enum|int|float|str|action, "value", "options"?}
                def build_rows():
                    rows = []
                    if model == "v3.1":
                        if type == "text_to_model":
                            rows.append({"key": "prompt",            "label": "Prompt Text",            "type": "str",   "value": prompt or ""})
                        elif type in ("image_to_model", "multiview_to_model"):
                            rows.append({"key": "image_path",        "label": "Image Path",             "type": "str",   "value": image_path or ""})
                        rows += [
                            {"key": "texture",              "label": "Generate Texture",       "type": "bool",  "value": kwargs.get("texture", True)},
                            {"key": "pbr",                  "label": "Generate PBR Maps",      "type": "bool",  "value": kwargs.get("pbr", True)},
                            {"key": "texture_quality",      "label": "Texture Quality",        "type": "enum",  "value": kwargs.get("texture_quality", "standard"),  "options": ["standard", "detailed", "extreme"]},
                            {"key": "texture_size",         "label": "Texture Size (px)",      "type": "enum",  "value": kwargs.get("texture_size", 2048),           "options": [1024, 2048, 4096]},
                            {"key": "texture_format",       "label": "Texture Format",         "type": "enum",  "value": kwargs.get("texture_format", "PNG"),        "options": ["PNG", "JPEG", "WEBP"]},
                            {"key": "geometry_quality",     "label": "Geometry Quality",       "type": "enum",  "value": kwargs.get("geometry_quality", "standard"), "options": ["standard", "detailed", "extreme"]},
                            {"key": "flatten_bottom",       "label": "Flatten Bottom",         "type": "bool",  "value": kwargs.get("flatten_bottom", False)},
                            {"key": "pivot_to_center_bottom","label": "Pivot to Center Bottom","type": "bool",  "value": kwargs.get("pivot_to_center_bottom", False)},
                            {"key": "scale_factor",         "label": "Scale Factor",           "type": "float", "value": kwargs.get("scale_factor", 1.0)},
                        ]
                    elif model == "p1":
                        if type == "text_to_model":
                            rows.append({"key": "prompt",       "label": "Prompt Text",        "type": "str",   "value": prompt or ""})
                        elif type in ("image_to_model", "multiview_to_model"):
                            rows.append({"key": "image_path",   "label": "Image Path",         "type": "str",   "value": image_path or ""})
                        rows += [
                            {"key": "face_limit",     "label": "Face Count Limit",   "type": "int",   "value": kwargs.get("face_limit", 10000)},
                            {"key": "quad",           "label": "Quad Mesh",          "type": "bool",  "value": kwargs.get("quad", False)},
                            {"key": "texture",        "label": "Generate Texture",   "type": "bool",  "value": kwargs.get("texture", True)},
                            {"key": "texture_quality","label": "Texture Quality",    "type": "enum",  "value": kwargs.get("texture_quality", "standard"), "options": ["standard", "detailed", "extreme"]},
                        ]
                    elif model == "rigging":
                        rows += [
                            {"key": "original_model_task_id","label": "Model Task ID",        "type": "str",   "value": original_model_task_id or ""},
                            {"key": "rig_type",       "label": "Rig Type",           "type": "enum",  "value": kwargs.get("rig_type", "biped"),   "options": ["biped", "quadruped", "avian"]},
                            {"key": "spec",           "label": "Rigging Spec",       "type": "enum",  "value": kwargs.get("spec", "tripo"),       "options": ["tripo", "mixamo"]},
                            {"key": "out_format",     "label": "Output Format",      "type": "enum",  "value": kwargs.get("out_format", "glb"),   "options": ["glb", "fbx"]},
                        ]
                    elif model == "animation":
                        rows += [
                            {"key": "original_model_task_id","label": "Model Task ID",        "type": "str",   "value": original_model_task_id or ""},
                            {"key": "animation",      "label": "Animation Preset",   "type": "str",   "value": kwargs.get("animation", "preset:walk")},
                        ]
                    rows.append({"key": "save_for_future", "label": "Save for Future Runs", "type": "bool", "value": save_for_future})
                    return rows

                rows = build_rows()
                sel = [0]           # selected row index
                editing = [False]   # True when in text-edit mode for str/int/float
                edit_buf = [""]     # current text being typed
                submitted = [False]

                # ── Render ───────────────────────────────────────────────────
                LABEL_W = 28

                def render():
                    out = [('bold #42bcf5', f'\n  Tripo 3D Parameters  —  {model.upper()} / {type.upper()}\n\n')]
                    for i, row in enumerate(rows):
                        selected = (i == sel[0])
                        label    = row["label"]
                        rtype    = row["type"]
                        val      = row["value"]

                        # Pad label to fixed width
                        padded_label = label.ljust(LABEL_W)

                        if selected:
                            prefix = ('bg:#1e1e2e bold #f9e2af', f'  ▶  {padded_label}  ')
                        else:
                            prefix = ('#6e6e8e', f'     {padded_label}  ')

                        # Value rendering
                        if selected and editing[0]:
                            # Show the live edit buffer with a cursor
                            val_str = edit_buf[0] + '█'
                            val_tok = ('bg:#1e1e2e bold #cdd6f4', val_str)
                        elif rtype == "bool":
                            if val:
                                val_tok = ('bg:#1e1e2e bold #a6e3a1' if selected else '#a6e3a1', '✔ True ')
                            else:
                                val_tok = ('bg:#1e1e2e bold #f38ba8' if selected else '#888888', '✘ False')
                        elif rtype == "enum":
                            opts = row.get("options", [])
                            cur_idx = opts.index(val) if val in opts else 0
                            parts = []
                            for j, opt in enumerate(opts):
                                if j == cur_idx:
                                    if selected:
                                        parts += [('bg:#1e1e2e bold #f9e2af', f' ◀ {opt} ▶ ')]
                                    else:
                                        parts += [('bold #cdd6f4', f' {opt} ')]
                                else:
                                    parts += [('#555577', f' {opt} ')]
                            val_tok = parts
                        elif rtype in ("int", "float", "str"):
                            disp = str(val)
                            val_tok = ('bg:#1e1e2e bold #cdd6f4' if selected else '#aaaacc', disp)
                        else:
                            val_tok = ('', str(val))

                        out.append(prefix)
                        if isinstance(val_tok, list):
                            out.extend(val_tok)
                        else:
                            out.append(val_tok)
                        out.append(('', '\n'))

                    return out

                def render_legend():
                    if editing[0]:
                        row = rows[sel[0]]
                        return [
                            ('bold #f9e2af', '  EDIT MODE  '),
                            ('class:dim', '—  Type to edit value  |  '),
                            ('bold #a6e3a1', 'ENTER'),
                            ('class:dim', ' to confirm  |  '),
                            ('bold #f38ba8', 'ESC'),
                            ('class:dim', ' to cancel'),
                        ]
                    else:
                        return [
                            ('class:dim', '  '),
                            ('bold #89b4fa', '↑↓'),
                            ('class:dim', ' navigate  |  '),
                            ('bold #cba6f7', '← →'),
                            ('class:dim', ' cycle bools/enums  |  '),
                            ('bold #cdd6f4', 'A-Z/0-9'),
                            ('class:dim', ' edit text/number  |  '),
                            ('bold #a6e3a1', 'ENTER'),
                            ('class:dim', ' submit  |  '),
                            ('bold #f38ba8', 'ESC'),
                            ('class:dim', ' cancel'),
                        ]

                # ── Key bindings ─────────────────────────────────────────────
                kb = KeyBindings()

                def _cycle(row, direction):
                    """Cycle enum/bool value by direction (+1 / -1)."""
                    rtype = row["type"]
                    if rtype == "bool":
                        row["value"] = not row["value"]
                    elif rtype == "enum":
                        opts = row.get("options", [])
                        if opts:
                            cur = opts.index(row["value"]) if row["value"] in opts else 0
                            row["value"] = opts[(cur + direction) % len(opts)]

                @kb.add('up')
                def _up(e):
                    if not editing[0]:
                        sel[0] = (sel[0] - 1) % len(rows)
                        e.app.invalidate()

                @kb.add('down')
                def _down(e):
                    if not editing[0]:
                        sel[0] = (sel[0] + 1) % len(rows)
                        e.app.invalidate()

                @kb.add('left')
                def _left(e):
                    if not editing[0]:
                        _cycle(rows[sel[0]], -1)
                        e.app.invalidate()

                @kb.add('right')
                def _right(e):
                    if not editing[0]:
                        _cycle(rows[sel[0]], +1)
                        e.app.invalidate()

                @kb.add('enter')
                def _enter(e):
                    if editing[0]:
                        # Confirm the edit
                        row = rows[sel[0]]
                        raw = edit_buf[0].strip()
                        try:
                            if row["type"] == "int":
                                row["value"] = int(raw) if raw else row["value"]
                            elif row["type"] == "float":
                                row["value"] = float(raw) if raw else row["value"]
                            else:
                                row["value"] = raw if raw else row["value"]
                        except ValueError:
                            pass
                        editing[0] = False
                        edit_buf[0] = ""
                    else:
                        # Submit the whole form
                        submitted[0] = True
                        e.app.exit()
                    e.app.invalidate()

                @kb.add('escape')
                def _escape(e):
                    if editing[0]:
                        editing[0] = False
                        edit_buf[0] = ""
                        e.app.invalidate()
                    else:
                        # Cancel dialog without submitting
                        e.app.exit()

                @kb.add('c-c')
                def _ctrlc(e):
                    e.app.exit()

                @kb.add('backspace')
                def _backspace(e):
                    if editing[0] and edit_buf[0]:
                        edit_buf[0] = edit_buf[0][:-1]
                        e.app.invalidate()

                # Any printable character starts/continues editing for str/int/float rows
                def _make_char_handler(char, insert=None):
                    actual = insert if insert is not None else char
                    @kb.add(char)
                    def _handler(e):
                        row = rows[sel[0]]
                        if row["type"] in ("str", "int", "float"):
                            if not editing[0]:
                                editing[0] = True
                                edit_buf[0] = actual
                            else:
                                edit_buf[0] += actual
                            e.app.invalidate()
                    return _handler

                PRINTABLE = (
                    'a b c d e f g h i j k l m n o p q r s t u v w x y z '
                    'A B C D E F G H I J K L M N O P Q R S T U V W X Y Z '
                    '0 1 2 3 4 5 6 7 8 9 '
                    '. - _ / \\ : @'
                ).split()
                for ch in PRINTABLE:
                    _make_char_handler(ch)
                # Space key: insert literal space
                _make_char_handler('space', insert=' ')

                # ── Layout ───────────────────────────────────────────────────
                content_window  = Window(FormattedTextControl(render, focusable=True), wrap_lines=False)
                legend_window   = Window(FormattedTextControl(render_legend), height=1, dont_extend_height=True)

                layout = Layout(HSplit([
                    content_window,
                    Window(height=1, char='─', style='#333355'),
                    legend_window,
                ]))

                dialog_app = Application(
                    layout=layout,
                    key_bindings=kb,
                    full_screen=True,
                    style=PTStyle.from_dict({
                        '': 'bg:#0d0d16 fg:#cdd6f4',
                    }),
                    mouse_support=False,
                )
                # Temporarily suppress the thinking indicator while the
                # dialog owns the screen — prevents it from printing above
                # the dialog UI.
                try:
                    from utim_cli.state import STATE as _state_ref
                    _was_busy = _state_ref.get("busy", False)
                    _state_ref["busy"] = False
                except Exception:
                    _was_busy = False
                    _state_ref = None

                try:
                    dialog_app.run()
                finally:
                    # Restore busy state so the indicator reappears if the
                    # orchestrator is still running after the dialog closes.
                    if _state_ref is not None:
                        _state_ref["busy"] = _was_busy

                # ── Write results back to nonlocals/kwargs ────────────────────
                if submitted[0]:
                    _user_submitted[0] = True
                    for row in rows:
                        k   = row["key"]
                        val = row["value"]
                        if k == "save_for_future":
                            save_for_future = val
                        elif k == "prompt":
                            prompt = val
                        elif k == "image_path":
                            image_path = val
                        elif k == "original_model_task_id":
                            original_model_task_id = val
                        else:
                            kwargs[k] = val

            _run_in_terminal_safe(show_dialog)

            # If user cancelled the dialog (ESC), abort generation entirely.
            # Also set the cancel_event so the orchestrator stops immediately
            # and does NOT call the LLM again (which would re-invoke this tool).
            if not _user_submitted[0]:
                try:
                    if _cancel_event is not None:
                        _cancel_event.set()
                except Exception:
                    pass
                return "Generation cancelled by user."

            # Post-dialog parameter sanitization
            if model == "v3.1":
                kwargs = {k: v for k, v in kwargs.items() if k in ("texture", "pbr", "texture_quality", "texture_size", "texture_format", "geometry_quality", "flatten_bottom", "pivot_to_center_bottom", "scale_factor")}
            elif model == "p1":
                kwargs = {k: v for k, v in kwargs.items() if k in ("face_limit", "quad", "texture", "texture_quality")}
            elif model == "rigging":
                kwargs = {k: v for k, v in kwargs.items() if k in ("rig_type", "spec", "out_format")}
            elif model == "animation":
                kwargs = {k: v for k, v in kwargs.items() if k == "animation"}

            # Save default configs for future runs if requested
            if save_for_future:
                saved_defaults = {
                    "prompt": prompt,
                    "image_path": image_path,
                    "original_model_task_id": original_model_task_id,
                    "save_for_future": True,
                    "kwargs": kwargs
                }
                config.set("subagent_blender_3d_defaults", saved_defaults)
            else:
                config.set("subagent_blender_3d_defaults", {"save_for_future": False})

        except Exception as e:
            print(f"Error in manual mode configuration: {e}. Falling back to default.")
    else:
        # Auto mode: omit addon parameters to save credits unless explicitly requested otherwise,
        # and automatically filter parameters that are unsupported by the selected model.
        if model == "v3.1":
            kwargs.pop("face_limit", None)
            kwargs.pop("quad", None)
            kwargs.pop("rig_type", None)
            kwargs.pop("spec", None)
            kwargs.pop("out_format", None)
            kwargs.pop("animation", None)
            if kwargs.get("texture_quality") not in ("detailed", "extreme"):
                kwargs.pop("texture_quality", None)
            if kwargs.get("geometry_quality") not in ("detailed", "extreme"):
                kwargs.pop("geometry_quality", None)
        elif model == "p1":
            kwargs.pop("pbr", None)
            kwargs.pop("texture_size", None)
            kwargs.pop("texture_format", None)
            kwargs.pop("geometry_quality", None)
            kwargs.pop("flatten_bottom", None)
            kwargs.pop("pivot_to_center_bottom", None)
            kwargs.pop("scale_factor", None)
            kwargs.pop("rig_type", None)
            kwargs.pop("spec", None)
            kwargs.pop("out_format", None)
            kwargs.pop("animation", None)
            if kwargs.get("texture_quality") not in ("detailed", "extreme"):
                kwargs.pop("texture_quality", None)

    # Load local .env file dynamically to fetch user's TRIPO_API_KEY
    _cwd_env = os.path.join(os.getcwd(), ".env")
    if os.path.isfile(_cwd_env):
        try:
            from dotenv import load_dotenv
            load_dotenv(_cwd_env, override=True)
        except Exception:
            pass

    server_url = get_server_url()
    headers = {
        "X-API-Key": api_key
    }
    tripo_key = os.getenv("TRIPO_API_KEY") or config.get("tripo_api_key")
    if tripo_key:
        headers["X-Tripo-API-Key"] = tripo_key

    # Check for cancellation before doing any network I/O
    if _cancel_event and _cancel_event.is_set():
        return "Generation cancelled by user."

    # Step 1: Upload image if local image_path is provided
    file_token = None
    if type.lower().strip() in ("image_to_model", "multiview_to_model") and image_path:
        local_path = pathlib.Path(image_path).expanduser().resolve()
        if not local_path.is_file():
            return f"Error: Local image file not found at '{image_path}'."
            
        upload_url = f"{server_url}/completions/3d/upload"
        try:
            with open(local_path, "rb") as f:
                files = {"file": (local_path.name, f, "image/jpeg" if local_path.suffix.lower() in (".jpg", ".jpeg") else "image/png")}
                upload_resp = requests.post(upload_url, files=files, headers=headers, timeout=60)
                upload_resp.raise_for_status()
                upload_json = upload_resp.json()
                data_dict = upload_json.get("data", {}) or {}
                file_token = data_dict.get("file_token") or data_dict.get("image_token")
                if not file_token:
                    return f"Error: Tripo upload succeeded but no token returned. Response: {upload_json}"
        except Exception as upload_err:
            if hasattr(upload_err, 'response') and upload_err.response is not None:
                try:
                    err_json = upload_err.response.json()
                    detail = err_json.get("detail", "")
                    if "Authentication failed" in detail:
                        return "Error: Image upload failed: 400 Client Error from server. Tripo API key configured on the Railway server is invalid or failed authentication. Please verify the TRIPO_API_KEY environment variable on your Railway server."
                except Exception:
                    pass
            return f"Error: Image upload failed: {upload_err}"

    # Check for cancellation before submitting the task
    if _cancel_event and _cancel_event.is_set():
        return "Generation cancelled by user."

    # Step 2: Submit task
    task_url = f"{server_url}/completions/3d/generations"
    payload = {
        "type": type,
        "prompt": prompt,
        "image_url": image_url,
        "file_token": file_token,
        "original_model_task_id": original_model_task_id,
        "model": model,
        "model_version": model_version,
        "model_seed": model_seed
    }
    payload.update({k: v for k, v in kwargs.items() if v is not None})
    
    try:
        resp = requests.post(task_url, json=payload, headers=headers, timeout=30)
        resp.raise_for_status()
        resp_json = resp.json()
        task_id = resp_json.get("data", {}).get("task_id")
        if not task_id:
            return f"Error: Task submitted but no task_id returned. Response: {resp_json}"
    except Exception as submit_err:
        return f"Error: Failed to submit task: {submit_err}"
        
    # Step 3: Poll status
    status_url = f"{server_url}/completions/3d/generations/{task_id}"
    
    def _cancel_tripo_task():
        """Fire-and-forget: tell the UTIM server to cancel this Tripo task."""
        try:
            import threading as _t
            def _do_cancel():
                try:
                    requests.delete(
                        f"{server_url}/completions/3d/generations/{task_id}",
                        headers=headers,
                        timeout=8
                    )
                except Exception:
                    pass
            _t.Thread(target=_do_cancel, daemon=True).start()
        except Exception:
            pass

    start_time = time.time()
    download_url = None
    
    while True:
        # Check for user cancellation on every poll iteration
        if _cancel_event and _cancel_event.is_set():
            _cancel_tripo_task()
            return f"Generation aborted by user. Tripo task '{task_id}' cancellation requested."

        if time.time() - start_time > 300: # 5 minutes timeout
            return f"Error: 3D generation timed out. You can check task status manually using task ID '{task_id}'."
            
        try:
            status_resp = requests.get(status_url, headers=headers, timeout=20)
            status_resp.raise_for_status()
            status_json = status_resp.json()
            
            task_data = status_json.get("data", {})
            status = task_data.get("status")
            
            if status == "success":
                result_data = task_data.get("result", {}) or task_data.get("output", {})
                if isinstance(result_data, str) and result_data.startswith("http"):
                    download_url = result_data
                elif isinstance(result_data, dict):
                    download_url = result_data.get("model") or result_data.get("glb") or result_data.get("obj")
                    
                if not download_url:
                    def _find_url(obj):
                        if isinstance(obj, str) and obj.startswith("http"):
                            return obj
                        if isinstance(obj, dict):
                            for v in obj.values():
                                found = _find_url(v)
                                if found: return found
                        if isinstance(obj, list):
                            for item in obj:
                                found = _find_url(item)
                                if found: return found
                        return None
                    download_url = _find_url(task_data)
                    
                if not download_url:
                    return f"Error: Task succeeded but no asset download URL found. Full response data: {status_json}"
                break
            elif status in ("failed", "cancelled", "error"):
                msg = task_data.get("message", "Tripo task failed during generation.")
                return f"Error: Tripo generation failed: {msg}"
            else:
                time.sleep(5)
        except Exception as poll_err:
            time.sleep(5)

    # Step 4: Download model and save to blender_assets/
    try:
        model_resp = requests.get(download_url, timeout=120)
        model_resp.raise_for_status()
        model_bytes = model_resp.content
    except Exception as dl_err:
        return f"Error: Failed to download generated 3D asset: {dl_err}"
        
    assets_dir = pathlib.Path(".utim_tmp/blender_assets").absolute()
    assets_dir.mkdir(parents=True, exist_ok=True)
    
    file_ext = download_url.split(".")[-1].split("?")[0].lower()
    if file_ext not in ("glb", "gltf", "obj", "fbx", "stl", "blend"):
        file_ext = output_format or "glb"
        
    safe_name = re.sub(r"[^\w\-]", "_", name) if name else f"tripo_{uuid.uuid4().hex[:8]}"
    out_file = assets_dir / f"{safe_name}.{file_ext}"
    
    try:
        with open(out_file, "wb") as f:
            f.write(model_bytes)
    except Exception as save_err:
        return f"Error: Failed to save model file locally: {save_err}"
        
    abs_path = str(out_file.resolve())
    formatted_path = abs_path.replace('\\', '/')
    file_uri = f"file:///{formatted_path.lstrip('/')}"
    if not file_uri.startswith("file:///"):
        file_uri = "file:///" + file_uri.lstrip("file:/")
        
    return f"Success: 3D model successfully generated and saved to [blender_assets]({file_uri}) (local path: {abs_path}).\nTask ID: {task_id}"


def generate_image(
    prompt: str,
    output_path: str = "",
    width: int = None,
    height: int = None,
    num_inference_steps: int = None,
    guidance_scale: float = None,
    seed: int = None
) -> str:
    """Generates an image from a text prompt using NVIDIA NIM APIs.
    
    Tries the primary model black-forest-labs/flux.1-schnell, falling back to 
    stabilityai/stable-diffusion-3.5-large, and stabilityai/stable-diffusion-xl.
    """
    import os
    import time
    import re
    import pathlib
    import requests
    import uuid
    import base64

    from utim_cli.config import config
    api_key = config.get("api_key")
    nvidia_key = os.getenv("NVIDIA_API_KEY")
    openrouter_key = os.getenv("OPENROUTER_API_KEY") or config.get("openrouter_api_key")
    if not api_key and not nvidia_key and not openrouter_key:
        return "Error: Neither UTIM API key, NVIDIA_API_KEY, nor OPENROUTER_API_KEY is set. Please set one of them to generate images."

    if not output_path:
        out_dir = pathlib.Path('.utim_tmp/images')
        out_dir.mkdir(parents=True, exist_ok=True)
        safe_prompt = re.sub(r'[^a-zA-Z0-9_-]', '_', prompt)[:30].strip('_')
        if not safe_prompt:
            safe_prompt = "generated"
        timestamp = int(time.time())
        filename = f"{timestamp}_{safe_prompt}_{uuid.uuid4().hex[:4]}.png"
        output_path = str(out_dir / filename)

    out_file = pathlib.Path(output_path)
    try:
        out_file.parent.mkdir(parents=True, exist_ok=True)
    except Exception as e:
        return f"Error creating parent directories for output_path '{output_path}': {e}"

    # 1. Agentic prompt expansion using LLM and sub-agent rules/context
    llm_key = os.getenv("OPENROUTER_API_KEY") or api_key
    expanded_prompt = prompt
    if llm_key:
        try:
            from utim_cli.bootstrap import get_subagent_rag_context
            subagent_rag_ctx = get_subagent_rag_context("generate_image", prompt)
        except Exception:
            subagent_rag_ctx = ""

        # Gather workspace context for image generation
        workspace_context = ""
        try:
            for f in ["README.md", "index.html", "package.json"]:
                if os.path.exists(f):
                    try:
                        with open(f, "r", encoding="utf-8") as file_obj:
                            workspace_context += f"\n- {f} Content snippet: {file_obj.read(1500)}"
                    except Exception:
                        pass
        except Exception:
            pass

        system_prompt = (
            "You are an expert Image Generation Prompt Optimizer. Your task is to expand and refine the user's short image request "
            "into a highly descriptive, visually rich prompt for state-of-the-art text-to-image models (like Flux, Ideogram, or Recraft V3).\n\n"
            "CRITICAL TEXT & TYPOGRAPHY PRESERVATION RULE:\n"
            "If the request contains any text, words, logo names, or slogans in quotes (e.g. 'text \"SHOP\"', 'word \"SOLAR\"', 'lettering \"WELCOME\"'), "
            "you MUST preserve the exact quoted text verbatim inside double quotes `\"EXACT TEXT\"` without altering spelling, capitalization, or punctuation. "
            "Place the text/typography description at the VERY BEGINNING of the expanded prompt (e.g. 'Sharp bold vector logo with clean typography reading \"EXACT TEXT\"...'). "
            "Do NOT alter, translate, add extra words inside the quotes, or omit the double quotes."
        )
        if subagent_rag_ctx:
            system_prompt += f"\n\nContext and Learned Rules:\n{subagent_rag_ctx}"
        if workspace_context:
            system_prompt += f"\n\nWorkspace/Project Details:\n{workspace_context}"

        from utim_cli.config import config
        sub_model = config.get("subagent_model_generate_image")
        # __none__ or __non_agent__: skip prompt expansion, use raw prompt directly
        if sub_model in ("__none__", "__non_agent__"):
            expanded_prompt = prompt
            print("⏩ Prompt expander disabled — using raw prompt.", flush=True)
        else:
            models_to_try = [
                "liquid/lfm-2.5-1.2b-instruct:free",
                DEFAULT_MODEL,
            ]
            if sub_model:
                models_to_try = [sub_model] + [m for m in models_to_try if m != sub_model]
            for model in models_to_try:
                try:
                    payload = {
                        "model": model,
                        "messages": [
                            {"role": "system", "content": system_prompt},
                            {"role": "user", "content": f"Please expand this request: {prompt}"}
                        ]
                    }
                    from utim_cli.client_utils import proxy_openrouter_request
                    resp = proxy_openrouter_request(json_data=payload, stream=False, timeout=20)
                    if resp.status_code == 200:
                        result = resp.json()["choices"][0]["message"]["content"].strip()
                        if result:
                            expanded_prompt = result
                            truncated = expanded_prompt if len(expanded_prompt) <= 100 else expanded_prompt[:100] + "..."

                            break
                except Exception:
                    continue

    # Use the expanded prompt for image generation payload
    prompt = expanded_prompt

    models_to_try = [
        "black-forest-labs/flux-1-schnell",
        "black-forest-labs/flux-1-dev",
        "recraft-ai/recraft-v3",
        "ideogram/ideogram-v2",
        "stabilityai/stable-diffusion-3.5-large",
        "black-forest-labs/flux.2-klein-4b"
    ]
    
    from utim_cli.config import config
    img_model = config.get("subagent_model_image_gen")
    if img_model:
        if img_model in ("krea/krea-2", "Krea 2 image", "krea-2") or (img_model.startswith("krea") and not any(k in img_model for k in ["turbo", "medium", "large"])):
            settings = config.get(f"model_settings_{img_model}") or config.get("model_settings_krea/krea-2") or {}
            effort = str(settings.get("reasoning_effort", "medium")).lower()
            if effort in ("minimal", "low"):
                resolved_model = "krea/krea-2-medium-turbo"
            elif effort in ("high", "xhigh", "max"):
                resolved_model = "krea/krea-2-large"
            else:
                resolved_model = "krea/krea-2-medium"
            models_to_try = [resolved_model] + [m for m in models_to_try if m != resolved_model]
        else:
            models_to_try = [img_model] + [m for m in models_to_try if m != img_model]

    last_err = None

    for model in models_to_try:
        is_openrouter = False
        if not api_key and openrouter_key and (not nvidia_key or model.startswith("openrouter/") or ("/" in model and "nvidia" not in model)):
            is_openrouter = True
        elif api_key:
            pass # Proxy will handle routing
        elif nvidia_key:
            pass # Fallback to Nvidia
            
        if is_openrouter:
            api_url = "https://openrouter.ai/api/v1/images"
            headers = {
                "Authorization": f"Bearer {openrouter_key}",
                "Content-Type": "application/json",
                "HTTP-Referer": "https://utim.dev",
                "X-Title": "UTIM Agent"
            }

        else:
            api_url = f"https://ai.api.nvidia.com/v1/genai/{model}"
            headers = {
                "Authorization": f"Bearer {nvidia_key}",
                "Accept": "application/json",
                "Content-Type": "application/json"
            }


        # Ensure prompt length is safe without unnecessarily truncating quotes for Flux / Ideogram / Recraft
        prompt_for_model = prompt
        if len(prompt_for_model) > 799 and "klein" in model.lower():
            prompt_for_model = safe_truncate_prompt(prompt_for_model, 799)
        elif len(prompt_for_model) > 2000:
            prompt_for_model = safe_truncate_prompt(prompt_for_model, 2000)

        if is_openrouter:
            payload = {
                "model": model,
                "prompt": prompt_for_model
            }
            if seed is not None:
                payload["seed"] = seed
            if width is not None:
                payload["width"] = width
            if height is not None:
                payload["height"] = height
            if num_inference_steps is not None:
                payload["steps"] = num_inference_steps
        elif "stabilityai" in model:
            # Stable Diffusion payload structure
            payload = {
                "text_prompts": [{"text": prompt_for_model, "weight": 1.0}]
            }
            if seed is not None:
                payload["seed"] = seed
            if width is not None:
                payload["width"] = width
            if height is not None:
                payload["height"] = height
            if num_inference_steps is not None:
                payload["steps"] = num_inference_steps
            if guidance_scale is not None:
                payload["cfg_scale"] = guidance_scale
        else:
            # Flux payload structure (only supports prompt, width, height, seed)
            payload = {
                "prompt": prompt_for_model
            }
            if seed is not None:
                payload["seed"] = seed
            if width is not None:
                payload["width"] = width
            if height is not None:
                payload["height"] = height

        # We try making the request. If it fails with 422/400 due to parameter schema,
        # we try a fallback with absolute minimal payload (only prompt).
        attempts_to_make = [payload]
        if is_openrouter:
            attempts_to_make.append({"model": model, "prompt": prompt_for_model})
        elif "stabilityai" in model:
            attempts_to_make.append({"text_prompts": [{"text": prompt_for_model, "weight": 1.0}]})
        else:
            attempts_to_make.append({"prompt": prompt_for_model})

        for attempt_payload in attempts_to_make:
            try:
                # Log the prompt snippet to help trace any failures
                sent_prompt = attempt_payload.get("prompt")
                if not sent_prompt and "text_prompts" in attempt_payload:
                    sent_prompt = attempt_payload["text_prompts"][0].get("text")

                
                if api_key:
                    from utim_cli.client_utils import get_server_url
                    proxy_url = f"{get_server_url()}/completions/images/generations"
                    proxy_headers = {
                        "X-API-Key": api_key,
                        "Content-Type": "application/json"
                    }
                    proxy_payload = {
                        "prompt": sent_prompt,
                        "model": model
                    }
                    if seed is not None:
                        proxy_payload["seed"] = seed
                    if len(attempt_payload) > 2 or ("text_prompts" in attempt_payload and len(attempt_payload) > 1):
                        if width is not None:
                            proxy_payload["width"] = width
                        if height is not None:
                            proxy_payload["height"] = height
                        if num_inference_steps is not None:
                            proxy_payload["steps"] = num_inference_steps
                        if guidance_scale is not None:
                            proxy_payload["cfg_scale"] = guidance_scale

                    resp = requests.post(proxy_url, json=proxy_payload, headers=proxy_headers, timeout=120)
                else:
                    resp = requests.post(api_url, json=attempt_payload, headers=headers, timeout=25)
                resp.raise_for_status()

                res_json = resp.json()
                img_b64 = None

                # Extract base64 image data from NVIDIA's response structure
                if isinstance(res_json, dict):
                    if "artifacts" in res_json and isinstance(res_json["artifacts"], list) and len(res_json["artifacts"]) > 0:
                        img_b64 = res_json["artifacts"][0].get("base64")
                    elif "data" in res_json and isinstance(res_json["data"], list) and len(res_json["data"]) > 0:
                        img_b64 = res_json["data"][0].get("b64_json") or res_json["data"][0].get("url")

                if not img_b64:
                    raise Exception(f"No image data found in response. Response: {res_json}")

                # Save image bytes
                if img_b64.startswith("http://") or img_b64.startswith("https://"):
                    img_resp = requests.get(img_b64, timeout=60)
                    img_resp.raise_for_status()
                    image_bytes = img_resp.content
                else:
                    if "," in img_b64:
                        img_b64 = img_b64.split(",", 1)[1]
                    image_bytes = base64.b64decode(img_b64)

                with open(out_file, "wb") as img_file:
                    img_file.write(image_bytes)

                # Check if the generated image is solid black (safety filter trigger)
                if is_image_mostly_black(output_path):
                    raise Exception("Generated image is solid/mostly black, likely due to NVIDIA content safety filter.")

                # Return clean formatted path using file:// protocol for clickability
                abs_path_str = str(out_file.resolve())
                abs_path_str_formatted = abs_path_str.replace('\\', '/')
                file_uri = f"file:///{abs_path_str_formatted.lstrip('/')}"
                if not file_uri.startswith("file:///"):
                    file_uri = "file:///" + file_uri.lstrip("file:/")

                return f"Success: Image generated and saved to [image]({file_uri}) (local path: {abs_path_str}) using model {model}.\nExpanded prompt used: {expanded_prompt}"

            except Exception as e:
                last_err = e
                err_str = str(e)
                if isinstance(e, requests.exceptions.HTTPError) and e.response is not None:
                    try:
                        err_json = e.response.json()
                        if isinstance(err_json, dict) and "detail" in err_json:
                            detail = err_json["detail"]
                            if isinstance(detail, dict):
                                if "message" in detail:
                                    err_str = detail["message"]
                                    if "reset_at" in detail:
                                        err_str += f" (Resets at: {detail['reset_at']})"
                                    if "upgrade_url" in detail:
                                        err_str += f" - Upgrade or purchase credits at: {detail['upgrade_url']}"
                                elif "error" in detail and isinstance(detail["error"], dict) and "message" in detail["error"]:
                                    err_str = detail["error"]["message"]
                            elif isinstance(detail, str):
                                err_str = detail
                        elif isinstance(err_json, dict) and "error" in err_json:
                            err_str = err_json["error"]
                    except Exception:
                        err_str += f" - Response body: {e.response.text}"
                
                print(f"[WARNING] Failed with model {model}: {err_str}", flush=True)
                last_err = Exception(err_str)

                # If 422/400 and we had parameter fields, retry with minimal payload
                if isinstance(e, requests.exceptions.HTTPError):
                    status_code = e.response.status_code if e.response is not None else 0
                    if (status_code == 422 or status_code == 400) and len(attempt_payload) > 1:
                        print(f"[RETRY] Retrying model {model} with minimal prompt payload...", flush=True)
                        continue
                break  # try next model

    return f"Error: All image generation models failed. Last error: {last_err}"


def create_skill(
    name: str,
    description: str,
    sections: list,
    examples: list = None,
) -> str:
    """
    Create or update a SKILL.md file in ~/.utim/agentskills/<name>/SKILL.md.
    The skill becomes immediately available to the AI on the next turn.

    Args:
        name: kebab-case skill name (e.g. 'async-subprocess', 'react-hooks').
        description: One-sentence trigger description — what this skill teaches and WHEN to activate it.
        sections: List of dicts: [{"title": "...", "rules": ["detailed rule 1", "..."]}].
                  Each rule must be at least 2 full sentences with concrete implementation detail.
        examples: Optional list of concrete code snippets or before/after comparisons.

    Returns:
        Success or error message string.
    """
    from utim_cli.reflection import apply_skill_modifications
    from utim_cli.config import get_utim_dir

    # Validate
    name = "".join(c for c in (name or "").lower() if c.isalnum() or c in ("-", "_"))
    if not name:
        return "Error: skill name is empty or contains only invalid characters. Use kebab-case (e.g. 'my-skill')."

    if not description or len(description.strip()) < 10:
        return "Error: description is too short. Provide a meaningful one-sentence description."

    if not sections or not isinstance(sections, list):
        return "Error: sections must be a non-empty list of {title, rules} objects."

    skill_data = {
        "description": description.strip(),
        "sections": sections,
        "examples": examples or [],
    }
    try:
        apply_skill_modifications({name: skill_data})
        skill_path = get_utim_dir() / "agentskills" / name / "SKILL.md"
        return (
            f"✓ Skill '{name}' created/updated at {skill_path}.\n"
            f"It is now active and will be injected into future turns when relevant."
        )
    except Exception as e:
        return f"Error creating skill '{name}': {e}"


# JSON Schema for OpenAI Tool Calling (OpenRouter format)
_BASE_UTIM_TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "create_skill",
            "description": "Create or update a reusable SKILL.md knowledge file in ~/.utim/agentskills/. Active immediately on future turns.",
            "parameters": {
                "type": "object",
                "properties": {
                    "name": {
                        "type": "string",
                        "description": "kebab-case skill name (e.g. 'react-hooks', 'async-subprocess', 'error-handling-patterns')."
                    },
                    "description": {
                        "type": "string",
                        "description": "One-sentence trigger description: what this skill teaches and WHEN it should be activated (the trigger condition)."
                    },
                    "sections": {
                        "type": "array",
                        "description": "List of section objects. Each must have a 'title' and 'rules' array. Rules must be detailed (2+ sentences each), actionable, and domain-specific.",
                        "items": {
                            "type": "object",
                            "properties": {
                                "title": {"type": "string", "description": "Section heading (e.g. 'Core Patterns', 'Error Handling', 'Performance')."},
                                "rules": {
                                    "type": "array",
                                    "items": {"type": "string"},
                                    "description": "Array of detailed rules. Each rule must be at least 2 full sentences explaining WHY and HOW."
                                }
                            },
                            "required": ["title", "rules"]
                        }
                    },
                    "examples": {
                        "type": "array",
                        "description": "Optional list of concrete code snippets or before/after comparisons demonstrating the skill in practice.",
                        "items": {"type": "string"}
                    }
                },
                "required": ["name", "description", "sections"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "generate_3d_model",
            "description": "Generates 3D assets (GLB/OBJ), rigs, or animates via Tripo AI API. Model 'v3.1' supports PBR/textures; 'p1' supports quad/face_limit; 'rigging'/'animation' use original_model_task_id.",
            "parameters": {
                "type": "object",
                "properties": {
                    "type": {
                        "type": "string",
                        "description": "The type of task: 'text_to_model', 'image_to_model', 'multiview_to_model', 'texture_model', 'refine_model', 'animate_rig', or 'animate_retarget'.",
                        "enum": ["text_to_model", "image_to_model", "multiview_to_model", "texture_model", "refine_model", "animate_rig", "animate_retarget"]
                    },
                    "prompt": {
                        "type": "string",
                        "description": "Optional. The text prompt describing the 3D asset you want to generate."
                    },
                    "image_path": {
                        "type": "string",
                        "description": "Optional. The local path to an image file to convert into 3D."
                    },
                    "image_url": {
                        "type": "string",
                        "description": "Optional. A public URL to an image file to convert into 3D."
                    },
                    "original_model_task_id": {
                        "type": "string",
                        "description": "Optional. The task ID of a previously generated model to refine, texture, rig, or animate."
                    },
                    "model": {
                        "type": "string",
                        "description": "Optional. Model version: 'v3.1' (Tripo H3.1), 'p1' (Tripo P1), 'rigging', or 'animation'. Defaults to 'v3.1'.",
                        "enum": ["v3.1", "p1", "rigging", "animation"]
                    },
                    "model_seed": {
                        "type": "integer",
                        "description": "Optional. Seed for reproducible generation."
                    },
                    "quad": {
                        "type": "boolean",
                        "description": "Optional. Convert to quad mesh (supported by P1)."
                    },
                    "face_limit": {
                        "type": "integer",
                        "description": "Optional. Target face count limit (supported by P1)."
                    },
                    "texture": {
                        "type": "boolean",
                        "description": "Optional. Generate textures (supported by H3.1 and P1)."
                    },
                    "pbr": {
                        "type": "boolean",
                        "description": "Optional. Generate PBR maps (supported by H3.1)."
                    },
                    "texture_quality": {
                        "type": "string",
                        "description": "Optional. Texture quality: 'standard', 'detailed', or 'extreme'.",
                        "enum": ["standard", "detailed", "extreme"]
                    },
                    "texture_size": {
                        "type": "integer",
                        "description": "Optional. Texture size: 1024, 2048, or 4096 (supported by H3.1)."
                    },
                    "texture_format": {
                        "type": "string",
                        "description": "Optional. Texture format: 'PNG', 'JPEG', or 'WEBP' (supported by H3.1)."
                    },
                    "geometry_quality": {
                        "type": "string",
                        "description": "Optional. Geometry quality: 'standard', 'detailed', or 'extreme' (supported by H3.1).",
                        "enum": ["standard", "detailed", "extreme"]
                    },
                    "flatten_bottom": {
                        "type": "boolean",
                        "description": "Optional. Flatten the bottom surface of the model (supported by H3.1)."
                    },
                    "pivot_to_center_bottom": {
                        "type": "boolean",
                        "description": "Optional. Move pivot to center bottom of bounds (supported by H3.1)."
                    },
                    "scale_factor": {
                        "type": "number",
                        "description": "Optional. Scale multiplier for the output model (supported by H3.1)."
                    },
                    "rig_type": {
                        "type": "string",
                        "description": "Optional. Rig type skeleton structure: 'biped', 'quadruped', or 'avian' (supported by rigging)."
                    },
                    "spec": {
                        "type": "string",
                        "description": "Optional. Rig specs: 'tripo' or 'mixamo' (supported by rigging)."
                    },
                    "out_format": {
                        "type": "string",
                        "description": "Optional. Output rig/animation format: 'glb' or 'fbx' (supported by rigging)."
                    },
                    "animation": {
                        "type": "string",
                        "description": "Optional. Preset animation to retarget (e.g. 'preset:walk') (supported by animation)."
                    },
                    "name": {
                        "type": "string",
                        "description": "Optional. A custom name for the downloaded file (without extension)."
                    }
                },
                "required": ["type"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "generate_image",
            "description": "Generates image assets from text prompt using OpenRouter & NVIDIA image models (SD, Flux, etc.). Saves locally and returns file path.",
            "parameters": {
                "type": "object",
                "properties": {
                    "prompt": {
                        "type": "string",
                        "description": "The detailed text prompt describing the image you want to generate."
                    },
                    "output_path": {
                        "type": "string",
                        "description": "Optional. The local file path where the generated image should be saved. If omitted, defaults to a path in .utim_tmp/images/."
                    },
                    "width": {
                        "type": "integer",
                        "description": "Optional. Width of the generated image (e.g. 1024)."
                    },
                    "height": {
                        "type": "integer",
                        "description": "Optional. Height of the generated image (e.g. 1024)."
                    },
                    "num_inference_steps": {
                        "type": "integer",
                        "description": "Optional. Number of denoising/inference steps."
                    },
                    "guidance_scale": {
                        "type": "number",
                        "description": "Optional. Guidance scale / CFG scale for generation."
                    },
                    "seed": {
                        "type": "integer",
                        "description": "Optional. Seed for random generation."
                    }
                },
                "required": ["prompt"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "invoke_subagents",
            "description": (
                "Spawn one or more parallel subagents. Each subagent has its OWN:\n"
                "  • context window  (isolated message history — no bleed from parent)\n"
                "  • system_prompt   (fully custom, not inherited)\n"
                "  • model           (any UTIM-supported model, can differ from parent)\n"
                "  • tools           (allowlist/denylist — restrict or expand access)\n"
                "  • permissions     (full | read_only | no_shell | no_write | isolated)\n"
                "  • mcp_servers     (list of MCP server names; empty = inherit parent's)\n"
                "  • memory          (ChromaDB collection for persistent RAG across runs)\n"
                "  • max_depth       (how many further nesting levels it may spawn, 0=leaf)\n\n"
                "All subagents run CONCURRENTLY. Results are returned when ALL complete.\n\n"
                "Use this when:\n"
                "  • A task decomposes into independent parallel workstreams\n"
                "  • You need specialised agents running simultaneously (researcher + writer + reviewer)\n"
                "  • A subagent itself needs to spawn its own sub-team (nested orchestration)\n\n"
                "Rules:\n"
                "  • Write a full, specific system_prompt and user_prompt for EACH subagent\n"
                "  • Nesting supported up to depth 4 (global hard ceiling)\n"
                "  • Max 8 subagents per invocation\n"
                "  • Results arrive in the same order as the tasks array"
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "tasks": {
                        "type": "array",
                        "description": "Array of subagent task specifications. Each element defines one subagent.",
                        "items": {
                            "type": "object",
                            "properties": {
                                "task_id": {
                                    "type": "string",
                                    "description": "Short unique identifier, e.g. 'research-1', 'write-tests', 'code-review'."
                                },
                                "role": {
                                    "type": "string",
                                    "description": "Human-readable role label, e.g. 'Researcher', 'Test Writer', 'Code Reviewer'."
                                },
                                "system_prompt": {
                                    "type": "string",
                                    "description": "Full system prompt for this subagent. Define its persona, scope, constraints, output format. Be specific and detailed."
                                },
                                "user_prompt": {
                                    "type": "string",
                                    "description": "The actual task instruction for this subagent. Be precise and complete."
                                },
                                "model_id": {
                                    "type": "string",
                                    "description": "Optional. Model for this subagent (e.g. 'anthropic/claude-sonnet-4-5'). Defaults to parent model if omitted."
                                },
                                "max_iterations": {
                                    "type": "integer",
                                    "description": "Optional. Max LLM iterations (default: 20). Increase for complex tasks."
                                },
                                "timeout_seconds": {
                                    "type": "integer",
                                    "description": "Optional. Wall-clock timeout in seconds (default: 300). Subagent is cancelled if exceeded."
                                },
                                "allowed_tools": {
                                    "type": "array",
                                    "items": {"type": "string"},
                                    "description": "Optional. If non-empty, ONLY these tool names are visible to this subagent. Acts as an allowlist."
                                },
                                "blocked_tools": {
                                    "type": "array",
                                    "items": {"type": "string"},
                                    "description": "Optional. Tool names to explicitly block for this subagent (stacks on top of the permission profile)."
                                },
                                "permission": {
                                    "type": "string",
                                    "enum": ["full", "read_only", "no_shell", "no_write", "isolated"],
                                    "description": (
                                        "Optional. Named permission profile (default: 'full'):\n"
                                        "  full       — all tools available\n"
                                        "  read_only  — may not write files, run commands, or delete\n"
                                        "  no_shell   — may not run shell commands\n"
                                        "  no_write   — may not modify files but can run read commands\n"
                                        "  isolated   — only memory/analysis tools; no filesystem or shell"
                                    )
                                },
                                "mcp_servers": {
                                    "type": "array",
                                    "items": {"type": "string"},
                                    "description": "Optional. List of MCP server names to enable for this subagent. Empty = inherit parent's active MCP connections."
                                },
                                "memory_collection": {
                                    "type": "string",
                                    "description": "Optional. ChromaDB collection name for this subagent's persistent memory. Relevant past memories are injected into context; new outputs are stored. Empty = no persistent memory."
                                },
                                "max_depth": {
                                    "type": "integer",
                                    "description": "Optional. How many further nesting levels this subagent may spawn (0 = leaf node). Capped by the global ceiling of 4."
                                },
                                "context_limit": {
                                    "type": "integer",
                                    "description": "Optional. Max context tokens for this subagent's isolated context window (0 = use model default)."
                                }
                            },
                            "required": ["task_id", "role", "system_prompt", "user_prompt"]
                        },
                        "minItems": 1,
                        "maxItems": 8
                    }
                },
                "required": ["tasks"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "read_file",
            "description": "Reads file content with line numbers. Supports range slicing (start_line/end_line), symbol_name lookup, or show_outline=True for AST structural outline.",
            "parameters": {
                "type": "object",
                "properties": {
                    "filepath": {
                        "type": "string",
                        "description": "The absolute or relative path to the file to read."
                    },
                    "start_line": {
                        "type": "integer",
                        "description": "First line to read (1-indexed). Omit to start from the beginning."
                    },
                    "end_line": {
                        "type": "integer",
                        "description": "Last line to read (1-indexed, inclusive). Omit to read to end."
                    },
                    "symbol_name": {
                        "type": "string",
                        "description": "Name of class, function, or method to view directly (e.g. 'get_system_prompt' or 'User')."
                    },
                    "show_outline": {
                        "type": "boolean",
                        "description": "Set to True to force prepend a structural file outline of all symbols."
                    }
                },
                "required": ["filepath"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "grep_search",
            "description": "Reliable, ultra-fast literal or regex search across files. Defaults to literal matching (set is_regex=True only for real regex). Supports single-file or directory targets, include/exclude globs, case control, and match_per_line=False for a file-list with counts. Binary/noisy files are safely skipped.",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "Exact text string to find, or a regex pattern when is_regex=True."
                    },
                    "path": {
                        "type": "string",
                        "description": "Target file or directory path (defaults to workspace root)."
                    },
                    "is_regex": {
                        "type": "boolean",
                        "description": "Set to True only when query is a real regular expression. Leave False for literal text."
                    },
                    "case_sensitive": {
                        "type": "boolean",
                        "description": "Set to True for case-sensitive matching (default is case-insensitive)."
                    },
                    "includes": {
                        "description": "Comma-separated glob string or list of globs to include (e.g. '*.py, *.js'). Prefix a glob with '!' to exclude it (e.g. '*.py, !*_test.py')."
                    },
                    "match_per_line": {
                        "type": "boolean",
                        "description": "If True (default), returns matching line snippets with line numbers. If False, returns unique matching file paths with per-file match counts."
                    },
                    "max_results": {
                        "type": "integer",
                        "description": "Maximum number of matches (or files, in file-list mode) to return. Default 50, hard cap 500."
                    }
                },
                "required": ["query"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "write_file",
            "description": "Creates a new file or overwrites an existing file with complete content. For modifications to existing files, prefer edit_file.",
            "parameters": {
                "type": "object",
                "properties": {
                    "filepath": {
                        "type": "string",
                        "description": "The absolute or relative path to the destination file."
                    },
                    "content": {
                        "type": "string",
                        "description": "The full code/text content to write to the file."
                    }
                },
                "required": ["filepath", "content"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "edit_file",
            "description": "Targeted search-and-replace edit on a file. Specify old_str/new_str or replacements array for batch updates.",
            "parameters": {
                "type": "object",
                "properties": {
                    "filepath": {
                        "type": "string",
                        "description": "The path to the file to edit."
                    },
                    "old_str": {
                        "type": "string",
                        "description": "Optional. The exact text to find and replace. Use for a single replacement."
                    },
                    "new_str": {
                        "type": "string",
                        "description": "Optional. The new text to replace the old text with. Use for a single replacement."
                    },
                    "replacements": {
                        "type": "array",
                        "description": "Optional. A list of search and replace pairs for batch updates.",
                        "items": {
                            "type": "object",
                            "properties": {
                                "old_str": {"type": "string", "description": "The exact unique text to find in the file."},
                                "new_str": {"type": "string", "description": "The new text to replace it with."}
                            },
                            "required": ["old_str", "new_str"]
                        }
                    }
                },
                "required": ["filepath"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "run_command",
            "description": "Executes shell command(s) and returns stdout/stderr/exit_code. Use dir_path for working dir and is_background for long-running servers/tasks.",
            "parameters": {
                "type": "object",
                "properties": {
                    "command": {
                        "type": "string",
                        "description": "Optional. The single shell command to execute."
                    },
                    "dir_path": {
                        "type": "string",
                        "description": (
                            "Optional. The directory in which to run the command. "
                            "Accepts absolute or relative paths. "
                            "Defaults to the current working directory when omitted."
                        )
                    },
                    "commands": {
                        "type": "array",
                        "description": "Optional. A list of shell commands to execute sequentially. Execution halts on the first non-zero exit code.",
                        "items": {
                            "type": "string"
                        }
                    },
                    "is_background": {
                        "type": "boolean",
                        "description": "Optional. Set to true for long-running processes, servers, or tasks (e.g. 'npm run dev', 'vite', 'npm install', 'python app.py'). Captures initial output for wait_seconds then continues in background so agent can proceed immediately."
                    },
                    "timeout": {
                        "type": "integer",
                        "description": "Optional timeout in seconds to prevent the command from hanging. Defaults to 120s."
                    },
                    "wait_seconds": {
                        "type": "integer",
                        "description": "Optional. Number of seconds to capture initial output before detaching to background mode. Defaults to 5s."
                    }
                }
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "background_tasks",
            "description": "Unified tool to list, monitor logs, send input, or stop background processes and tasks.",
            "parameters": {
                "type": "object",
                "properties": {
                    "action": {
                        "type": "string",
                        "enum": ["list", "output", "input", "stop"],
                        "description": "Action to perform: 'list' (show all running/finished tasks), 'output' (fetch stdout/stderr logs), 'input' (write to stdin), or 'stop' (kill task)."
                    },
                    "process_id": {
                        "type": "string",
                        "description": "The process/task ID (e.g. 'bg-1'). Required for 'output', 'input', and 'stop' actions."
                    },
                    "text": {
                        "type": "string",
                        "description": "The text/input to send to stdin. Required for 'input' action."
                    },
                    "tail_lines": {
                        "type": "integer",
                        "description": "Optional. Number of recent log lines to fetch when action is 'output'. Defaults to 100."
                    }
                },
                "required": ["action"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "list_directory",
            "description": "Lists the files and folders inside a given directory. Use this to explore the project structure.",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {
                        "type": "string",
                        "description": "The path to the directory to list (defaults to '.' if empty)."
                    }
                },
                "required": ["path"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "web_search",
            "description": "Deep web research tool. Spawns subagent to search, read web sources, and synthesize findings.",
            "parameters": {
                "type": "object",
                "properties": {
                    "prompt": {
                        "type": "string",
                        "description": "The detailed research prompt or question."
                    },
                    "level": {
                        "type": "string",
                        "enum": ["low", "medium", "high"],
                        "description": "The intensity of the research. Low (1-20 sites), Medium (20-80 sites), High (80-150+ sites)."
                    }
                },
                "required": ["prompt", "level"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "plan_project",
            "description": "Spawns planning subagent for project architecture, database, security, or feature plans.",
            "parameters": {
                "type": "object",
                "properties": {
                    "plan_part": {
                        "type": "string",
                        "description": "The specific domain/part to plan: 'design' (UI/UX design & interaction plan), 'architecture', 'security', 'database', 'testing', 'deployment', or 'features'."
                    },
                    "prompt": {
                        "type": "string",
                        "description": "Detailed description of the project, feature, or asset to plan."
                    },
                    "context": {
                        "type": "string",
                        "description": "Optional background context, user requirements, or existing file snippets."
                    }
                },
                "required": ["plan_part", "prompt"]
            }
        }
    }
]




def analyze_blast_radius(filepath: str) -> str:
    """Analyzes the potential impact of changes to a file using the knowledge graph.
    
    Returns files that depend on this file (imports, function calls, etc.) to help
    understand the blast radius before making edits.
    """
    try:
        from utim_cli.knowledge_graph import get_knowledge_graph
        kg = get_knowledge_graph()
        
        if kg is None:
            return "Knowledge graph not available. Tree-sitter may not be installed."
        
        # Build graph if needed
        if len(kg.entities) == 0:
            kg.build_graph()
        
        # Get blast radius
        affected_files = kg.get_blast_radius(filepath)
        
        if not affected_files:
            return f"No dependents found for `{filepath}` (file may not exist in graph)."
        
        result = f"### Potential Impact Analysis for `{filepath}`\n\n"
        result += f"**{len(affected_files)} file(s) may be affected by changes:**\n\n"
        for f in affected_files:
            result += f"- `{f}`\n"
        
        result += "\n**Recommendation:** Review these files before making changes to understand potential side effects."
        return result
    except ImportError as e:
        return f"Knowledge graph not available: {str(e)}"
    except Exception as e:
        return f"Error analyzing blast radius: {str(e)}"

def store_experience(category: str, content: str, priority: int = None, subagent: str = None) -> str:
    """
    Store learning experiences in the experiences.json file for continuous improvement.
    
    Args:
        category: Type of learning (e.g., 'logic_failure', 'success_pattern', 'user_preference', 'analytical_framework')
        content: The actual learning content or insight gained
        priority: Optional priority score (defaults to based on category)
        subagent: Optional subagent name to store experiences specifically for that subagent ('project_res', 'plan_project', 'web_search')
    
    Returns:
        Status message indicating success or failure
    """
    import json
    from datetime import datetime
    from pathlib import Path
    from utim_cli.config import get_utim_dir
    
    try:
        # Ensure .utim directory exists (global ~/.utim, resolves per-user profile)
        utim_dir = get_utim_dir()
        utim_dir.mkdir(exist_ok=True)
        exp_file = utim_dir / 'experiences.json'
        
        # Load existing experiences
        experiences = []
        if exp_file.exists():
            try:
                with open(exp_file, 'r', encoding='utf-8') as f:
                    experiences = json.load(f)
            except Exception:
                experiences = []
                
        timestamp = datetime.now().isoformat()
        entry = {
            "category": category,
            "content": content,
            "timestamp": timestamp,
            "subagent": subagent,
            "priority": priority or 0
        }
        experiences.append(entry)
        
        with open(exp_file, 'w', encoding='utf-8') as f:
            json.dump(experiences, f, indent=2)
            
        # Also store in vector memory if available
        try:
            if subagent:
                import utim_cli.vector_memory as vm_mod
                getter_name = f"get_{subagent}_experiences_memory"
                getter = getattr(vm_mod, getter_name, None)
                vm = getter() if getter else None
            else:
                from utim_cli.vector_memory import get_experiences_memory
                vm = get_experiences_memory()
                
            if vm:
                vm.add_text(
                    text_id=f"exp_{timestamp}_{category}",
                    content=content,
                    metadata={"category": category, "timestamp": timestamp, "type": "learning"}
                )
        except Exception:
            pass
            
        return f"[OK] Experience stored: {category}" + (f" for subagent {subagent}" if subagent else "")
    except Exception as e:
        return f"[ERROR] Failed to store experience: {str(e)}"

def recall_experience(query: str, limit: int = 5, subagent: str = None) -> str:
    """
    Search the RAG intelligence database (Experiences and Skills) using keyword matches and vector DB.
    
    Args:
        query: Natural language search query or keywords describing what you are looking for.
        limit: Number of results to return (default 5).
        subagent: Optional subagent name to recall memory specifically from that subagent ('project_res', 'plan_project', 'web_search').
        
    Returns:
        Formatted string containing the top matching experiences and skills.
    """
    try:
        from pathlib import Path
        import json
        from utim_cli.state import STATE
        from utim_cli.config import get_utim_dir
        
        results_str = []
        utim_dir = get_utim_dir()
        exp_file = utim_dir / 'experiences.json'
        
        # Search experiences from experiences.json
        if exp_file.exists():
            try:
                with open(exp_file, 'r', encoding='utf-8') as f:
                    experiences = json.load(f)
            except Exception:
                experiences = []
                
            query_lower = query.lower()
            matched_exps = []
            for exp in experiences:
                if subagent and exp.get("subagent") != subagent:
                    continue
                content = exp.get("content", "")
                cat = exp.get("category", "")
                if query_lower in content.lower() or query_lower in cat.lower():
                    matched_exps.append(exp)
            
            # Sort by priority and timestamp
            matched_exps.sort(key=lambda x: (x.get("priority", 0), x.get("timestamp", "")), reverse=True)
            
            if matched_exps:
                results_str.append("### RELEVANT PAST EXPERIENCES ###")
                for r in matched_exps[:limit]:
                    results_str.append(f"- [{r['category']}] {r['content']}")
                    if "injected_contexts" not in STATE:
                        STATE["injected_contexts"] = []
                    STATE["injected_contexts"].append(r['content'])
        
        # Search skills from .utim/skills/ and .agents/skills/
        matched_skills = []
        seen_skill_names = set()
        for base_dir in [utim_dir / 'skills', Path('.agents/skills')]:
            if base_dir.exists():
                for skill_path in base_dir.glob("**/SKILL.md"):
                    try:
                        skill_name = skill_path.parent.name
                        if skill_name in seen_skill_names:
                            continue
                        with open(skill_path, 'r', encoding='utf-8') as f:
                            content = f.read()
                        if query.lower() in content.lower():
                            matched_skills.append((skill_name, content))
                            seen_skill_names.add(skill_name)
                    except Exception:
                        pass
        if matched_skills:
            results_str.append("\n### RELEVANT CORE SKILLS / RULES ###")
            for name, content in matched_skills[:3]:
                if content.startswith('---'):
                    parts = content.split('---', 2)
                    if len(parts) >= 3:
                        content = parts[2].strip()
                results_str.append(f"- [{name.upper()}] {content[:300]}...")
                if "injected_contexts" not in STATE:
                    STATE["injected_contexts"] = []
                STATE["injected_contexts"].append(content)
                    
        if not results_str:
            return f"No relevant experiences or skills found for your query."
            
        return "\n".join(results_str)
    except Exception as e:
        return f"[ERROR] Failed to recall experience: {str(e)}"

# ─── Blender Helper ───────────────────────────────────────────────────────
def _blender_run_script(script_path: str, timeout: int = 120) -> str:
    """Execute a temporary Blender Python script in headless mode.

    The function builds the command using the auto‑detected Blender path
    from ``config.BLENDER_PATH`` (or environment variable). It respects the
    UTIM sandbox – if sandbox mode is active the exact command string is
    auto‑approved before execution.
    """
    from utim_cli.config import BLENDER_PATH
    if not BLENDER_PATH:
        return "Error: Blender executable not found. Set UTIM_BLENDER_PATH env var or install Blender."

    if os.name == "nt":
        cmd = f'& "{BLENDER_PATH}" -b -noaudio -P "{script_path}"'
    else:
        cmd = f'"{BLENDER_PATH}" -b -noaudio -P "{script_path}"'
    
    # Auto‑approve in sandbox mode
    if _SANDBOX_MODE and not is_command_approved(cmd):
        approve_command(cmd)
    # Execute via existing run_command utility
    result = run_command(command=cmd, timeout=timeout)
    return result

def read_file_outline(filepath: str) -> str:
    """Returns an AST structural outline of a code file (classes, functions, line numbers).
    
    If short (<60 lines), returns full content. For larger files, extracts imports,
    classes, and functions with start/end line numbers for targeted reading.
    """
    abs_path = os.path.abspath(filepath)
    if not os.path.isfile(abs_path):
        return f"Error: File not found: {filepath}"

    try:
        with open(abs_path, "r", encoding="utf-8", errors="replace") as f:
            lines = f.readlines()
    except Exception as e:
        return f"Error reading file: {e}"

    total_lines = len(lines)
    if total_lines <= 60:
        return f"File '{filepath}' is short ({total_lines} lines). Full content:\n\n" + "".join(lines)

    outline_parts = [f"File Structural Outline: '{filepath}' (Total Lines: {total_lines})"]

    # 1. Python AST Parser
    if filepath.endswith(".py"):
        try:
            import ast
            tree = ast.parse("".join(lines), filename=filepath)
            
            imports = []
            for node in tree.body:
                if isinstance(node, ast.Import):
                    names = [alias.name for alias in node.names]
                    imports.append(", ".join(names))
                elif isinstance(node, ast.ImportFrom):
                    imports.append(f"from {node.module or ''}")
            if imports:
                outline_parts.append(f"Line 1-{tree.body[0].lineno if tree.body else 1}: Imports ({', '.join(imports[:8])})")

            for node in tree.body:
                if isinstance(node, ast.ClassDef):
                    end_ln = getattr(node, "end_lineno", node.lineno + 10)
                    outline_parts.append(f"\nLine {node.lineno}-{end_ln}: class {node.name}")
                    for item in node.body:
                        if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)):
                            item_end = getattr(item, "end_lineno", item.lineno + 5)
                            args_list = [a.arg for a in item.args.args if a.arg != 'self']
                            outline_parts.append(f"  Line {item.lineno}-{item_end}: def {item.name}({', '.join(args_list[:4])})")
                elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    end_ln = getattr(node, "end_lineno", node.lineno + 10)
                    args_list = [a.arg for a in node.args.args]
                    outline_parts.append(f"\nLine {node.lineno}-{end_ln}: def {node.name}({', '.join(args_list[:4])})")

            return "\n".join(outline_parts) + "\n\nUse read_file with start_line/end_line to inspect specific sections."
        except Exception:
            pass  # Fall back to regex structural scanner below

    # 2. Universal Regex Line-Scanner for non-Python or syntax-error files
    outline_parts.append("(Regex Structural Outline)")
    class_fn_re = re.compile(r"^\s*(class|def|async def|function|const|let|var|type|interface|pub fn|fn|struct|enum)\s+([A-Za-z0-9_]+)", re.MULTILINE)
    
    found_symbols = []
    for idx, line in enumerate(lines, start=1):
        m = class_fn_re.match(line)
        if m:
            found_symbols.append(f"Line {idx}: {line.strip()[:80]}")

    if found_symbols:
        outline_parts.extend(found_symbols[:50])
    else:
        outline_parts.append(f"Line 1-20: {lines[0].strip()[:60]} ...")
        mid = total_lines // 2
        outline_parts.append(f"Line {mid}: {lines[mid].strip()[:60]} ...")
        outline_parts.append(f"Line {total_lines-10}-{total_lines}: {lines[-1].strip()[:60]}")

    return "\n".join(outline_parts) + "\n\nUse read_file with start_line/end_line to inspect specific sections."


# Map tool names to actual Python functions
_BASE_TOOL_FUNCTIONS = {
    "read_file":         read_file,
    "write_file":        write_file,
    "edit_file":         edit_file,
    "run_command":       run_command,
    "list_directory":    list_directory,
    "web_search":        web_search,
    "plan_project":      plan_project,
    "analyze_image":     analyze_image,
    "grep_search":       grep_search,
    "search":            grep_search,
    "search_codebase":    grep_search,
    "create_skill":      create_skill,

    "background_tasks":  background_tasks,

    "generate_image":    generate_image,

    "invoke_subagents":  None,  # Patched at dispatch time (needs session context)
}

def _load_miniagent_tools():
    """Load miniagent tool schemas and execution handlers from .utim/miniagents/."""
    from utim_cli.config import get_utim_dir
    mini_dir = get_utim_dir() / "miniagents"
    schemas = []
    functions = {}
    if not mini_dir.exists():
        return schemas, functions

    for entry in sorted(mini_dir.iterdir()):
        if not entry.is_dir():
            continue
        m_id = entry.name
        desc = f"Executable tool miniagent {m_id}"
        lang = "python"
        main_script = "agent.py"
        custom_params = None

        agent_json = entry / "agent.json"
        if agent_json.exists():
            try:
                data = json.loads(agent_json.read_text(encoding="utf-8"))
                m_id = data.get("id", entry.name)
                desc = data.get("description") or desc
                lang = data.get("lang", "python")
                main_script = data.get("main") or ("agent.py" if lang == "python" else "agent.js")
                custom_params = data.get("parameters")
            except Exception:
                pass

        safe_name = "miniagent_" + re.sub(r'[^a-zA-Z0-9_]', '_', m_id)

        if custom_params and isinstance(custom_params, dict):
            params_schema = custom_params
        else:
            params_schema = {
                "type": "object",
                "properties": {
                    "prompt": {
                        "type": "string",
                        "description": f"Input prompt / arguments to pass to tool miniagent @{m_id}"
                    }
                },
                "required": ["prompt"]
            }

        schema = {
            "type": "function",
            "function": {
                "name": safe_name,
                "description": f"Tool @{m_id} ({lang}): {desc}",
                "parameters": params_schema
            }
        }

        def _make_mini_handler(e_dir, l, mid, mscript):
            def handler(**kwargs) -> str:
                script_file = e_dir / mscript
                if not script_file.exists():
                    fallback_ext = "py" if l == "python" else "js"
                    script_file = e_dir / f"agent.{fallback_ext}"
                if not script_file.exists():
                    return f"Miniagent @{mid} executable script not found in {e_dir}"

                args_json_str = json.dumps(kwargs, ensure_ascii=False)
                try:
                    cmd = ["python" if l == "python" else "node", str(script_file), args_json_str]
                    res = subprocess.run(
                        cmd,
                        cwd=str(e_dir),
                        capture_output=True,
                        text=True,
                        timeout=30
                    )
                    stdout = res.stdout.strip()
                    stderr = res.stderr.strip()
                    out = stdout
                    if stderr:
                        out += f"\n[stderr]: {stderr}"
                    return out if out else f"Miniagent tool @{mid} executed with status code {res.returncode}."
                except Exception as err:
                    return f"Error executing miniagent tool @{mid}: {err}"
            return handler

        schemas.append(schema)
        functions[safe_name] = _make_mini_handler(entry, lang, m_id, main_script)
    return schemas, functions


def _prioritize_tool_params(schemas: list) -> list:
    """Reorder 'properties' in every tool schema so critical parameters appear FIRST.
    
    LLMs (especially smaller ones) tend to forget required parameters or emit empty
    argument objects when schemas list many properties in arbitrary order. By forcing
    critical params to the top of the properties dict, we:
      1. Signal to the LLM which args are most important (primacy bias).
      2. Make schema diffing easier (critical args come first in diffs).
      3. Reduce the chance the model truncates a required arg while emitting a long
         optional one (like 'prompt') early in its JSON.
    
    This is a defensive layer that complements _execute_tool's alias recovery.
    """
    # Priority order: param names that MUST appear first if present in the schema.
    PRIORITY_PARAMS = [
        "filepath", "path", "file_path",         # file-targeting tools
        "command", "commands", "cmd",             # shell-execution tools
        "prompt", "query", "input",               # generative / search tools
        "image_path", "image_url",                # image input tools
        "url", "target",                          # network/redirect tools
    ]
    for schema in schemas:
        try:
            params = schema.get("function", {}).get("parameters", {})
            props = params.get("properties")
            if not isinstance(props, dict) or not props:
                continue
            # Build new ordered dict: priority params first (in PRIORITY_PARAMS order),
            # then everything else preserving original order.
            ordered = {}
            for pname in PRIORITY_PARAMS:
                if pname in props:
                    ordered[pname] = props[pname]
            for pname, pval in props.items():
                if pname not in ordered:
                    ordered[pname] = pval
            params["properties"] = ordered
            # Also make sure 'required' list preserves all required keys (don't drop any).
            if "required" in params and isinstance(params["required"], list):
                # Ensure required params are listed first too (best-practice)
                req = params["required"]
                # Stable sort: required items go first, preserve relative order within each group
                seen = set(req)
                new_req = [r for r in req if r in seen] + [r for r in req if r not in seen]
                params["required"] = new_req
        except Exception:
            # Schema reordering is best-effort; never break tool loading.
            continue
    return schemas


def get_tools(include_disabled: bool = False):
    """Dynamically returns the list of UTIM_TOOLS schemas and TOOL_FUNCTIONS dictionary based on current configuration."""
    from utim_cli.config import config
    import copy
    
    schemas = copy.deepcopy(_BASE_UTIM_TOOLS)
    functions = dict(_BASE_TOOL_FUNCTIONS)

    # Dynamic miniagent executable tools
    mini_schemas, mini_funcs = _load_miniagent_tools()
    schemas.extend(mini_schemas)
    functions.update(mini_funcs)

    # Filter out disabled tools unless include_disabled=True (used by /tools dialog)
    if not include_disabled:
        disabled_tools = config.get("disabled_tools") or []
        if isinstance(disabled_tools, list) and disabled_tools:
            schemas = [s for s in schemas if s["function"]["name"] not in disabled_tools]
            functions = {k: v for k, v in functions.items() if k not in disabled_tools}
    
    # Strictly deduplicate tool schemas by function name (prevents Provider 400 errors)
    deduped_schemas = []
    seen_names = set()
    for s in schemas:
        fname = s.get("function", {}).get("name")
        if fname and fname not in seen_names:
            seen_names.add(fname)
            deduped_schemas.append(s)
    schemas = deduped_schemas
    
    # If a subagent is in non-agent mode, swap its tool description so the main agent uses it correctly
    if config.get("subagent_model_web_search") == "__non_agent__":
        for tool in schemas:
            if tool["function"]["name"] == "web_search":
                tool["function"]["description"] = "Performs a direct web search and returns raw snippet results. MUST provide exact keywords or a short search query. Do NOT provide complex tasks, instructions, or long sentences."
                
    if config.get("subagent_model_plan_project") == "__non_agent__":
        for tool in schemas:
            if tool["function"]["name"] == "plan_project":
                tool["function"]["description"] = "Directly returns the task provided without any LLM expansion or planning. No subagent will run. Use only to quickly record a task string."
                

    if config.get("subagent_model_analyze_image") == "__non_agent__":
        for tool in schemas:
            if tool["function"]["name"] == "analyze_image":
                tool["function"]["description"] = "Performs a local Pillow-based analysis of the image and returns raw image statistics without using a Vision LLM. Give exact image path."
                
    return schemas, functions

