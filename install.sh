#!/bin/bash
# UTIM CLI Auto-Installer for Unix/macOS/Android Termux
#
# Uses Pure-Python Architecture on Android Termux to ensure fast 100% Rust-free installation.

set -e

echo "=== UTIM CLI Installer ==="

# Detect Termux / Android environment
IS_TERMUX=false
if [ -d "/data/data/com.termux" ] || [ -n "$TERMUX_VERSION" ] || [[ "$PREFIX" == *"com.termux"* ]]; then
    IS_TERMUX=true
fi

if [ "$IS_TERMUX" = true ]; then
    echo "[*] Android Termux environment detected."
    echo "[*] Using Pure-Python Architecture (no Rust compiler or pydantic-core wheel building required)."
    echo "[*] Installing utim-cli..."
    pip install utim-cli
    echo "[✓] UTIM CLI installed successfully on Termux!"
    echo "    Type 'utim' to start."
else
    # Non-Termux unix environments (Linux, macOS)
    echo "[*] Standard UNIX/macOS environment detected."
    echo "[*] Installing utim-cli..."
    pip install utim-cli
    echo "[✓] UTIM CLI installed successfully!"
    echo "    Type 'utim' to start."
fi
