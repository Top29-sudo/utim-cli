f = open('orchestrator.py', encoding='utf-8').read()
# Find all "role": "tool" append blocks
import re
for m in re.finditer(r'role":\s*"tool"', f):
    start = max(0, m.start() - 100)
    end = min(len(f), m.end() + 300)
    snippet = f[start:end]
    print(f"--- Match at {m.start()} ---")
    print(snippet)
    print()