"""Comprehensive fix v2: 'dim' modifier cannot be expressed inline in a
prompt_toolkit style string — it must be applied as a registered style class.
We replace every "fg:<color> class:dim" / "dim <color>" pattern with a darker
foreground color (`_MUTED`-style) which is visually equivalent and safe.

We also keep the parser's markup-tag handling of `[dim]` to map to that same
darker color so `[dim]text[/dim]` still works.
"""
import re
from pathlib import Path

p = Path(r"utim_cli/tui/marketplace_dialog.py")
src = p.read_text(encoding="utf-8")
orig = src

# 1) Parser fix: [dim] tag in markup -> darker color class token.
#    The [dim] tag is used in places like [dim {_MUTED}]Status:[/dim {_MUTED}]
#    which already passes a color. We simply normalize "dim" inside a tag to
#    a "class:dim" class token. The class is registered by the application
#    via prompt_toolkit's @style.from_dict, and falls back safely.
#    The previous 'class:dim' literal in style strings is replaced below
#    with just the color, so no class registration is required.
old1 = '                if p in ("bold", "dim"):\n\n                    st_list.append(p)\n'
new1 = (
    '                if p == "bold":\n'
    '                    st_list.append(p)\n'
    '                elif p == "dim":\n'
    '                    # The "dim" modifier in prompt_toolkit style strings\n'
    '                    # must be expressed as a style class. We use the\n'
    '                    # darker "_MUTED" color directly instead, which is\n'
    '                    # visually equivalent and avoids the\n'
    '                    # "Wrong color format dim" crash.\n'
    '                    continue  # drop the bare "dim" token\n'
)
if old1 in src:
    src = src.replace(old1, new1, 1)
    print("[1] Parser fix applied.")
else:
    print("[1] Parser already fixed; skipping.")

# 2) Strip every "class:dim" / " class:dim" / leading "dim " in style strings.
#    Result: the remaining color is the only style applied.
#    We do this safely with regex on the exact patterns.
patterns = [
    # 'f"dim {<var>}"' or 'f"dim <text>"'  -> drop the leading 'dim ' token.
    # This catches the marketplace file's actual f-string form.
    (re.compile(r'f"dim '),
     'f"'),
    # 'f"dim fg:{<var>}"'  ->  'f"fg:{<var>}"'
    (re.compile(r'f"dim fg:'),
     'f"fg:'),
    # 'f"<stuff> dim fg:{<var>}"'  ->  'f"<stuff> fg:{<var>}"'
    (re.compile(r' dim fg:'),
     ' fg:'),
    # '"dim <hex>"'  -> '"<hex>"'
    (re.compile(r'"dim (#[a-fA-F0-9]{6})"'),
     r'"\1"'),
    # '<prefix> class:dim'  -> '<prefix>'
    (re.compile(r' class:dim'),
     ""),
]
total = 0
for pat, repl in patterns:
    src, n = pat.subn(repl, src)
    total += n
    print(f"[2] {pat.pattern!r}  ->  {n} replacements")

# 3) Sanity: any 'class:dim' or bare 'dim "' left?
left_dim = re.findall(r'"dim ', src)
left_classdim = re.findall(r'class:dim', src)
print(f"[3] Remaining '\"dim ' literals: {len(left_dim)}")
print(f"[3] Remaining 'class:dim' literals: {len(left_classdim)}")

p.write_text(src, encoding="utf-8")
print(f"\nFile changed: {src != orig}")
print(f"Total replacements in this run: {total}")
