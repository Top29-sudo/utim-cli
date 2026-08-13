#!/usr/bin/env bash
# UTIM CLI macOS / Linux / Termux Installation Script
set -e

echo "🚀 Installing UTIM CLI..."

if command -v npm >/dev/null 2>&1; then
    echo "📦 Installing @emend-ai/utim globally via npm..."
    npm install -g @emend-ai/utim
elif command -v python3 >/dev/null 2>&1; then
    echo "🐍 Installing utim via python3 pip..."
    python3 -m pip install utim
elif command -v pip >/dev/null 2>&1; then
    echo "🐍 Installing utim via pip..."
    pip install utim
else
    echo "❌ Error: Neither Node.js (npm) nor Python (pip) was found."
    echo "Please install Node.js (18+) or Python (3.9+) and rerun this script."
    exit 1
fi

echo ""
echo "✔ UTIM CLI installation complete! Run 'utim' to start."
