"""Final fix v2: handle the smart-quote variant and ensure 'dim' tag drops cleanly."""
from pathlib import Path
import re

p = Path(r"utim_cli/tui/marketplace_dialog.py")
src = p.read_text(encoding="utf-8")
orig = src

# 1) Parser: replace any 'st_list.append("class:dim")' after a `dim` check
#    with 'continue' to drop the token. Smart quotes are handled by using
#    a regex on the unique trailing line.
pat = re.compile(
    r'elif p == "dim":.*?st_list\.append\("class:dim"\)\n',
    re.DOTALL,
)
new_block = (
    'elif p == "dim":\n'
    '                    # prompt_toolkit does NOT accept "dim" as a bare\n'
    '                    # token before a color; raises "Wrong color\n'
    '                    # format dim". Drop the token; callers usually\n'
    '                    # pair [dim] with a muted hex color anyway.\n'
    '                    continue\n'
)
src2, n = pat.subn(new_block, src)
print(f"[1] Parser block: {n} replacement(s)")
src = src2

# 2) Strip any *remaining* ' class:dim' substrings in style strings,
#    AND any leading 'dim ' tokens in style strings, in case any slipped through.
patterns = [
    (re.compile(r'f"dim '), 'f"'),
    (re.compile(r' class:dim'), ''),
    (re.compile(r'^dim ', re.MULTILINE), ''),
]
for pat, repl in patterns:
    src, n = pat.subn(repl, src)
    print(f"[2] {pat.pattern!r}: {n} replacement(s)")

p.write_text(src, encoding="utf-8")
print(f"\nFile changed: {src != orig}")
