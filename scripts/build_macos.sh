#!/bin/bash
set -e
# Navigate to project root (one level up from scripts/)
cd "$(dirname "$0")/.."

# --- Configuration ---
PYTHON_VERSION="3.12"
UNIVERSAL_PYTHON="/usr/local/bin/python${PYTHON_VERSION}"
VENV_DIR=".venv_universal"

# === Step 0: Check for universal2 Python ===
echo "=== Step 0: Check universal2 Python ==="

if [ -f "$UNIVERSAL_PYTHON" ] && file "$UNIVERSAL_PYTHON" | grep -q "universal"; then
    echo "Found universal2 Python: $UNIVERSAL_PYTHON"
else
    echo ""
    echo "ERROR: universal2 Python not found at $UNIVERSAL_PYTHON"
    echo ""
    echo "Please install the official Python ${PYTHON_VERSION} universal2 installer from:"
    echo "  https://www.python.org/downloads/macos/"
    echo ""
    echo "Download the 'macOS 64-bit universal2 installer' (NOT Homebrew)."
    echo "After installing, re-run this script."
    exit 1
fi

# === Step 1: Setup universal2 venv ===
echo "=== Step 1: Setup universal2 venv ==="

if [ ! -d "$VENV_DIR" ]; then
    echo "Creating universal2 venv..."
    "$UNIVERSAL_PYTHON" -m venv "$VENV_DIR"
fi

source "$VENV_DIR/bin/activate"
pip install --upgrade pip -q

echo "Installing dependencies..."
pip install -r requirements.txt -q
pip install pyinstaller -q

# === Step 2: Build frontend ===
echo "=== Step 2: Build frontend ==="
(cd frontend && npm install && npm run build)

# === Step 3: Build universal .app bundle ===
echo "=== Step 3: Build universal .app bundle ==="
pyinstaller scripts/build_macos.spec --clean --noconfirm

deactivate 2>/dev/null || true

echo ""
echo "=== Done! ==="
echo "App bundle: dist/AgentTranslation.app"
echo ""

# Verify it's universal
echo "Architecture check:"
file dist/AgentTranslation.app/Contents/MacOS/AgentTranslation

echo ""
echo "To share: zip -r AgentTranslation-Mac.zip dist/AgentTranslation.app"
