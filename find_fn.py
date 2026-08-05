#!/usr/bin/env python3
"""Find model variable references in run_task"""
with open("utim_cli/orchestrator.py", "rb") as f:
    data = f.read()
lines = data.split(b"\n")
for i in range(4369, min(len(lines), 5200)):
    line = lines[i].decode("utf-8", errors="replace")
    # Look for any variable containing 'model' that's not a comment
    if "model" in line.lower() and not line.strip().startswith("#"):
        print(f"L{i+1}: {line.rstrip()[:150]}")