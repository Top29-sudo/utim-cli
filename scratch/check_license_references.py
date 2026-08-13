import os
import re

matches = []
for root, dirs, files in os.walk('.'):
    if any(x in root for x in ['node_modules', '.git', 'dist', '.venv', '.utim_backup', 'brain']):
        continue
    for file in files:
        if file.endswith(('.py', '.json', '.toml', '.md', '.jsx', '.js', '.txt', '.html', 'LICENSE')):
            path = os.path.join(root, file)
            try:
                with open(path, 'r', encoding='utf-8', errors='ignore') as f:
                    content = f.read()
                    for idx, line in enumerate(content.splitlines(), 1):
                        if re.search(r'\bMIT\b', line, re.IGNORECASE):
                            matches.append((path, idx, line.strip()))
            except Exception as e:
                pass

print(f"Total files containing MIT: {len(set(m[0] for m in matches))}")
for path, line_no, line in matches:
    print(f"{path}:{line_no} -> {line[:120]}")
