#!/usr/bin/env python3
"""
Fix double-encoding in marketplace_dialog.py - targeted byte-level approach.
Only fixes specific corrupted byte sequences without touching correct ones.
"""
import sys

filepath = "utim_cli/tui/marketplace_dialog.py"

with open(filepath, "rb") as f:
    data = f.read()

# Current corrupted state analysis:
# The original file had double-encoding: UTF-8 bytes decoded as cp1252/latin-1,
# then re-saved as UTF-8. My previous fix attempts partially corrupted it further.
#
# Current corrupted patterns (in UTF-8 bytes):
# c2 97 = U+0097 → should be e2 80 94 (—) [was: — → cp1252(0x97) → UTF-8(c2 97)]
# c2 95 = U+0095 → should be e2 80 a2 (•) [was: • → cp1252(0x95) → UTF-8(c2 95)]
# c3 a2 c2 95 c2 90 = â•• → should be e2 95 90 (═) [triple-encoded]
# c3 a2 c2 95 c2 91 = â••' → should be e2 95 91 (║)
# etc.

# Strategy: read as UTF-8, find chars in U+0080-U+00FF range that are
# the result of cp1252/latin-1 decoding, encode back to bytes, decode as UTF-8.
# BUT only do this for chars that, when encoded as cp1252, produce valid UTF-8.

text = data.decode("utf-8")

def cp1252_to_utf8_byte(c):
    """Try to convert a char back through cp1252 encoding to get original UTF-8 bytes."""
    try:
        b = c.encode("cp1252")
        # Try decoding as UTF-8
        return b.decode("utf-8")
    except:
        return None

def latin1_to_utf8_byte(c):
    """Try to convert a char back through latin-1 encoding to get original UTF-8 bytes."""
    try:
        b = c.encode("latin-1")
        return b.decode("utf-8")
    except:
        return None

# Process: group consecutive chars that are in the "fixable" range
# (U+0080-U+00FF for latin-1, plus cp1252-specific chars like U+20AC, U+201A, etc.)
CP1252_CHARS = set()
for cp in [0x20AC, 0x201A, 0x0192, 0x201E, 0x2026, 0x2020, 0x2021, 0x02C6,
           0x2030, 0x0160, 0x2039, 0x0152, 0x017D, 0x2018, 0x2019, 0x201C,
           0x201D, 0x2022, 0x2013, 0x2014, 0x02DC, 0x2122, 0x0161, 0x203A,
           0x0153, 0x017E, 0x0178]:
    CP1252_CHARS.add(chr(cp))

def is_fixable(c):
    """Check if char could be from cp1252/latin-1 decoding of UTF-8 bytes."""
    cp = ord(c)
    if 0x80 <= cp <= 0xFF:
        return True  # Latin-1 range
    if c in CP1252_CHARS:
        return True  # cp1252-specific chars
    return False

result = []
buf = []
fix_count = 0

for c in text:
    if is_fixable(c):
        buf.append(c)
    else:
        if buf:
            # Try to fix the buffer as a group
            chunk = "".join(buf)
            # Try cp1252 first
            fixed = cp1252_to_utf8_byte(chunk)
            if fixed is None:
                fixed = latin1_to_utf8_byte(chunk)
            if fixed is not None:
                result.append(fixed)
                fix_count += 1
            else:
                result.append(chunk)
            buf = []
        result.append(c)

if buf:
    chunk = "".join(buf)
    fixed = cp1252_to_utf8_byte(chunk)
    if fixed is None:
        fixed = latin1_to_utf8_byte(chunk)
    if fixed is not None:
        result.append(fixed)
        fix_count += 1
    else:
        result.append(chunk)

fixed_text = "".join(result)

# Write the fixed file
with open(filepath, "w", encoding="utf-8") as f:
    f.write(fixed_text)

print(f"Fixed {fix_count} sequences")
print(f"Original: {len(text)} chars / {len(data)} bytes")
print(f"Fixed:    {len(fixed_text)} chars / {len(fixed_text.encode('utf-8'))} bytes")

# Verify
with open(filepath, "rb") as f:
    new_data = f.read()

lines = new_data.split(b"\n")

# Check key characters
checks = {
    "em dash e2 80 94": b"\xe2\x80\x94",
    "star e2 98 85": b"\xe2\x98\x85",
    "empty star e2 98 86": b"\xe2\x98\x86",
    "ellipsis e2 80 a6": b"\xe2\x80\xa6",
    "cross mark e2 9c 95": b"\xe2\x9c\x95",
    "lightning e2 9a a1": b"\xe2\x9a\xa1",
    "bullet e2 80 a2": b"\xe2\x80\xa2",
    "box 90 e2 95 90": b"\xe2\x95\x90",
    "box 91 e2 95 91": b"\xe2\x95\x91",
    "box 94 e2 95 94": b"\xe2\x95\x94",
    "box 9a e2 95 9a": b"\xe2\x95\x9a",
    "box 9d e2 95 9d": b"\xe2\x95\x9d",
    "box 8c e2 94 8c": b"\xe2\x94\x8c",
    "box 90 e2 94 90": b"\xe2\x94\x90",
    "box 94 e2 94 94": b"\xe2\x94\x94",
    "box 98 e2 94 98": b"\xe2\x94\x98",
    "box 80 e2 94 80": b"\xe2\x94\x80",
    "box 82 e2 94 82": b"\xe2\x94\x82",
    "arrow e2 9e 94": b"\xe2\x9e\x94",
    "down arr e2 ac 87": b"\xe2\xac\x87",
    "shopping f0 9f 9b 8d": b"\xf0\x9f\x9b\x8d",
    "globe f0 9f 8c 90": b"\xf0\x9f\x8c\x90",
    "fire f0 9f 94 a5": b"\xf0\x9f\x94\xa5",
    "rocket f0 9f 9a 80": b"\xf0\x9f\x9a\x80",
    "star2 e2 ad 90": b"\xe2\xad\x90",
}

all_ok = True
for name, pattern in checks.items():
    found = pattern in new_data
    if not found:
        all_ok = False
        print(f"  MISSING: {name}")

# Check for remaining corrupted patterns
import re
corrupted = len(re.findall(b"\xc3[\xa2\xa0-\xbf]", new_data))
print(f"Remaining corrupted sequences: {corrupted}")

em_dash_pat = b"\xe2\x80\x94"
print(f"\nLine 2: {lines[1][:80]}")
print(f"Line 2 has em dash: {em_dash_pat in lines[1]}")

if all_ok and corrupted == 0:
    print("\nALL CHARACTERS FIXED SUCCESSFULLY!")
else:
    print(f"\nChecks: {'all passed' if all_ok else 'some failed'}, Corrupted: {corrupted}")