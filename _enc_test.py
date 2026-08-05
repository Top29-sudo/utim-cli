import subprocess, sys, os

# Force UTF-8 for our own output so the log file is clean
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

def run(argv, label, enc="utf-8"):
    try:
        p = subprocess.Popen(
            argv, shell=False, stdin=subprocess.PIPE,
            stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            text=True, encoding=enc, errors="replace",
        )
        out, err = p.communicate(timeout=15)
        print(f"=== {label} (enc={enc}) rc={p.returncode}")
        print(f"  stdout repr: {out!r}")
        print(f"  stderr repr: {err!r}")
    except Exception as e:
        print(f"=== {label} FAILED: {e!r}")

# 1. PowerShell writing an emoji to a pipe
run(["powershell", "-NoProfile", "-Command", "Write-Output '🧠 ⚠ ──'"], "powershell utf-8")

# 2. cmd /c echo with emoji
run(["cmd", "/c", "echo 🧠"], "cmd utf-8")

# 3. Python child with UTF-8 bytes
run([sys.executable, "-X", "utf8", "-c", "import sys; sys.stdout.buffer.write('🧠 ⚠ ──'.encode('utf-8'))"], "py-bytes utf-8")

# 4. Same via cmd wrapper (what run_command actually does)
run(["cmd", "/c", "powershell -NoProfile -Command \"Write-Output '🧠'\" && echo ⚠"], "cmd+powershell utf-8")

# 5. Check current console codepage
try:
    cp = subprocess.run(["powershell", "-NoProfile", "-Command", "[Console]::OutputEncoding.EncodingName; [Console]::InputEncoding.EncodingName; chcp"], capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=15)
    print(f"=== console encodings\n{cp.stdout}")
except Exception as e:
    print(f"console encodings FAILED: {e!r}")
