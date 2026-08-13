#!/bin/bash
# UTIM CLI Auto-Installer for Unix/macOS/Android Termux
#
# Uses OS-specific requirement files (requirements_android.txt, requirements_desktop.txt).

set -e

echo "=== UTIM CLI Installer ==="

# Detect Termux / Android environment
IS_TERMUX=false
if [ -d "/data/data/com.termux" ] || [ -n "$TERMUX_VERSION" ] || [[ "$PREFIX" == *"com.termux"* ]]; then
    IS_TERMUX=true
fi

SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"

if [ "$IS_TERMUX" = true ]; then
    echo "[*] Android Termux environment detected."
    echo "[*] Using 100% Pure-Python requirements_android.txt (zero Rust/C++ compilation required)."
    if [ -f "$SCRIPT_DIR/requirements_android.txt" ]; then
        pip install -r "$SCRIPT_DIR/requirements_android.txt"
        pip install --no-deps -e "$SCRIPT_DIR"
    else
        pip install utim-cli
    fi
    echo "[✓] UTIM CLI installed successfully on Termux!"
    echo "    Type 'utim' to start."
else
    # Non-Termux unix environments (Linux, macOS)
    echo "[*] Standard UNIX/macOS environment detected."
    if [ -f "$SCRIPT_DIR/requirements_desktop.txt" ]; then
        pip install -r "$SCRIPT_DIR/requirements_desktop.txt"
        pip install --no-deps -e "$SCRIPT_DIR"
    else
        pip install utim-cli
    fi
    echo "[✓] UTIM CLI installed successfully!"
    echo "    Type 'utim' to start."
fi
