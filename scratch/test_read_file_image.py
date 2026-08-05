"""Runtime smoke test: call the patched read_file on a real JPEG and confirm
that the result contains a real description rather than the bare `[Image: ...]`
placeholder.
"""
import os
import sys
import importlib.util

# Make the utim_cli package importable
ROOT = r"C:\Users\user\Desktop\New folder\New folder"
sys.path.insert(0, ROOT)

# Import the patched module by file path
spec = importlib.util.spec_from_file_location(
    "utim_cli.tools_patched",
    os.path.join(ROOT, "utim_cli", "tools.py"),
)
tools = importlib.util.module_from_spec(spec)
spec.loader.exec_module(tools)

# Find a real image to test with. Look in common Windows screenshot locations.
candidates = [
    os.path.join(os.path.expanduser("~"), "Desktop", "screenshot.jpeg"),
    os.path.join(os.path.expanduser("~"), "Pictures", "screenshot.jpeg"),
    os.path.join(os.path.expanduser("~"), "Desktop", "screenshot.png"),
    os.path.join(os.path.expanduser("~"), "Pictures", "screenshot.png"),
    os.path.join(ROOT, "screenshot.jpeg"),
    os.path.join(ROOT, "screenshot.png"),
]
test_path = next((p for p in candidates if os.path.isfile(p)), None)
if not test_path:
    # Synthesize a tiny valid PNG so the image branch is exercised end-to-end
    import struct, zlib, tempfile
    w, h = 4, 4
    raw = b''.join(b"\x00" + b"\xff\x00\x00" * w for _ in range(h))  # 4x4 red PNG
    def chunk(t, d):
        return struct.pack(">I", len(d)) + t + d + struct.pack(">I", zlib.crc32(t + d) & 0xFFFFFFFF)
    png = (b"\x89PNG\r\n\x1a\n"
           + chunk(b"IHDR", struct.pack(">IIBBBBB", w, h, 8, 2, 0, 0, 0))
           + chunk(b"IDAT", zlib.compress(raw))
           + chunk(b"IEND", b""))
    fd, test_path = tempfile.mkstemp(suffix=".png")
    os.write(fd, png)
    os.close(fd)
    print(f"(no real image found — synthesized tiny PNG at {test_path})")

print(f"Testing read_file on: {test_path}")
result = tools.read_file(test_path)
print("--- read_file result (first 600 chars) ---")
print(result[:600])
print("--- end ---")

# Sanity checks
if result.strip() == f"[Image: {test_path}]":
    print("\nFAIL: Still returning the bare placeholder — fix did not take effect.")
    sys.exit(1)
if "[Image:" in result and len(result) > len(f"[Image: {test_path}]") + 20:
    print("\nPASS: Returns metadata + description (longer than the bare placeholder).")
else:
    print("\nWARN: Result shape unexpected — inspect output above.")
