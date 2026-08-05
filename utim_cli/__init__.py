# UTIM CLI Package
# Version is maintained in utim_cli/_version.py (single source of truth).
# scripts/sync_version.py keeps package.json, pyproject.toml, and CHANGELOG in sync.
try:
    from utim_cli._version import VERSION as __version__
except ImportError:
    # Fallback during first-install / editable-install edge cases
    __version__ = "2.1.0"

import builtins, os, pathlib, urllib.parse, re

# Import hint handling utilities lazily to avoid circular imports during CLI startup
def _get_hint_utils():
    """Lazy import of hint handling utilities."""
    from utim_cli.utilities import state, parse_hint_commands, process_hint_messages, apply_hint_context
    return state, parse_hint_commands, process_hint_messages, apply_hint_context

# Export hint utilities as properties for dynamic import
class _HintUtilsProxy:
    def __getattr__(self, name):
        if name in ['state', 'parse_hint_commands', 'process_hint_messages', 'apply_hint_context']:
            # Import on demand
            utils = _get_hint_utils()
            module_vars = {'state': utils[0], 'parse_hint_commands': utils[1], 
                         'process_hint_messages': utils[2], 'apply_hint_context': utils[3]}
            # Set the attribute on this module to cache the import
            setattr(self, name, module_vars[name])
            return module_vars[name]
        raise AttributeError(f"'module' object has no attribute '{name}'")

def _make_file_uri(path: str) -> str:
    p = pathlib.Path(path).resolve()
    encoded = urllib.parse.quote(str(p).replace('\\', '/'))
    return f"file:///{encoded}"

def _maybe_path_to_uri(text: str) -> str:
    # Detect absolute Windows paths (C:\... or /c/... )
    if re.match(r"^[a-zA-Z]:[\\/].*", text) and os.path.exists(text):
        return f"{text} ({_make_file_uri(text)})"
    # Detect relative paths that exist in cwd
    rel = os.path.abspath(text)
    if os.path.exists(rel):
        return f"{text} ({_make_file_uri(rel)})"
    return text

_orig_print = builtins.print

def _utim_print(*args, **kwargs):
    formatted = [_maybe_path_to_uri(str(a)) for a in args]
    try:
        _orig_print(*formatted, **kwargs)
    except UnicodeEncodeError:
        import sys
        encoding = sys.stdout.encoding or 'cp1252'
        safe_formatted = []
        for item in formatted:
            safe_item = item.encode(encoding, errors='backslashreplace').decode(encoding)
            safe_formatted.append(safe_item)
        try:
            _orig_print(*safe_formatted, **kwargs)
        except Exception:
            # Absolute fallback to standard ASCII if everything else fails
            ascii_formatted = [item.encode('ascii', errors='replace').decode('ascii') for item in formatted]
            _orig_print(*ascii_formatted, **kwargs)

# Override the global print for this package
builtins.print = _utim_print

# ── Monkeypatch Rich for Legacy Windows Terminals ──
try:
    import rich.rule
    import rich.markdown
    import rich.table
    import rich.box
    import rich.segment
    import sys
    
    _IS_LEGACY_WIN = (sys.platform == "win32" and "WT_SESSION" not in os.environ)
    is_legacy = _IS_LEGACY_WIN or getattr(sys.stdout, 'encoding', '').lower() not in ('utf-8', 'utf8', 'cp65001')
    
    if is_legacy:
        # 1. Patch Rule.__init__ to use '-' instead of '─'
        _original_rule_init = rich.rule.Rule.__init__
        def _patched_rule_init(self, title="", *, characters="─", style="rule.line", end="\n", align="center"):
            if characters == "─":
                characters = "-"
            _original_rule_init(self, title, characters=characters, style=style, end=end, align=align)
        rich.rule.Rule.__init__ = _patched_rule_init

        # 2. Patch Table.__init__ to force ASCII box borders
        _original_table_init = rich.table.Table.__init__
        def _patched_table_init(self, *args, **kwargs):
            if "box" in kwargs and kwargs["box"] is not None:
                kwargs["box"] = rich.box.ASCII
            elif len(args) > 0:
                args = list(args)
                if args[0] is not None:
                    args[0] = rich.box.ASCII
            _original_table_init(self, *args, **kwargs)
        rich.table.Table.__init__ = _patched_table_init

        # 3. Patch ListItem.render_bullet to use '*' instead of '•'
        _original_render_bullet = rich.markdown.ListItem.render_bullet
        def _patched_render_bullet(self, console, options):
            from rich.segment import Segment
            for item in _original_render_bullet(self, console, options):
                if hasattr(item, "text") and item.text == " \u2022 ":
                    yield Segment(" * ", item.style, item.control)
                else:
                    yield item
        rich.markdown.ListItem.render_bullet = _patched_render_bullet

except Exception:
    pass
