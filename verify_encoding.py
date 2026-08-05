#!/usr/bin/env python3
"""Verify the fixed marketplace_dialog.py file."""
import re, sys

filepath = "utim_cli/tui/marketplace_dialog.py"

with open(filepath, "rb") as f:
    data = f.read()

lines = data.split(b"\n")

checks = {
    "em dash (e2 80 94)": b"\xe2\x80\x94",
    "star (e2 98 85)": b"\xe2\x98\x85",
    "empty star (e2 98 86)": b"\xe2\x98\x86",
    "ellipsis (e2 80 a6)": b"\xe2\x80\xa6",
    "cross mark (e2 9c 95)": b"\xe2\x9c\x95",
    "lightning (e2 9a a1)": b"\xe2\x9a\xa1",
    "box e2 95 90": b"\xe2\x95\x90",
    "box e2 95 91": b"\xe2\x95\x91",
    "box e2 95 94": b"\xe2\x95\x94",
    "box e2 95 97": b"\xe2\x95\x97",
    "box e2 95 9a": b"\xe2\x95\x9a",
    "box e2 95 9d": b"\xe2\x95\x9d",
    "box e2 94 8c": b"\xe2\x94\x8c",
    "box e2 94 90": b"\xe2\x94\x90",
    "box e2 94 94": b"\xe2\x94\x94",
    "box e2 94 98": b"\xe2\x94\x98",
    "box e2 94 80": b"\xe2\x94\x80",
    "box e2 94 82": b"\xe2\x94\x82",
    "arrow e2 9e 94": b"\xe2\x9e\x94",
    "down arrow e2 ac 87": b"\xe2\xac\x87",
}

all_ok = True
for name, pattern in checks.items():
    found = pattern in data
    if not found:
        all_ok = False
        sys.stdout.write(f"  MISSING: {name}\n")

# Count remaining double-encoded sequences
dub_pat = b"\xc3[\xa2\xa0-\xbf]\xe2[\x82\x80-\x8f][\x80-\xbf][\x80-\xbf]"
remaining = len(re.findall(dub_pat, data))
sys.stdout.write(f"Double-encoded remaining: {remaining}\n")

# Show line 2
sys.stdout.write(f"\nLine 2: {lines[1][:80]}\n")
em_dash_pat = b'\xe2\x80\x94'
sys.stdout.write(f"Line 2 has em dash: {em_dash_pat in lines[1]}\n")

# Show banner line
box90 = b'\xe2\x95\x90'
box91 = b'\xe2\x95\x91'
for i, line in enumerate(lines):
    if b"UTIM EXTENSION STORE" in line:
        sys.stdout.write(f"Banner line {i+1}: {line[:120]}\n")
        sys.stdout.write(f"  Has box 90: {box90 in line}\n")
        sys.stdout.write(f"  Has box 91: {box91 in line}\n")
        break

# Show close marketplace
cross = b'\xe2\x9c\x95'
for i, line in enumerate(lines):
    if b"Close Marketplace" in line:
        sys.stdout.write(f"Close Marketplace line {i+1}: {line[:80]}\n")
        sys.stdout.write(f"  Has cross: {cross in line}\n")
        break

if all_ok and remaining == 0:
    sys.stdout.write("\nALL CHARACTERS FIXED SUCCESSFULLY!\n")
else:
    sys.stdout.write(f"\nChecks: {'all passed' if all_ok else 'some failed'}, Remaining: {remaining}\n")