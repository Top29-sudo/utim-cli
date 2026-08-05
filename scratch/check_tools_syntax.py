"""Quick syntax check for tools.py after the read_file image fix."""
import ast
import sys

path = r"C:\Users\user\Desktop\New folder\New folder\utim_cli\tools.py"
try:
    with open(path, "r", encoding="utf-8") as f:
        src = f.read()
    ast.parse(src)
    print(f"OK: {path} parses cleanly ({len(src)} chars, {src.count(chr(10))} lines)")
except SyntaxError as e:
    print(f"SYNTAX ERROR: {e}")
    sys.exit(1)
