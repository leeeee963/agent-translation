#!/bin/bash
set -e
cd "$(dirname "$0")"

echo "============================================"
echo "  AgentTranslation - Starting..."
echo "============================================"
echo ""

# === Check Python 3 ===
if ! command -v python3 &>/dev/null; then
    echo "[Setup] Python not found, installing..."
    if command -v brew &>/dev/null; then
        brew install python
    else
        echo "[Setup] Installing Homebrew first..."
        /bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
        brew install python
    fi
fi
echo "[OK] Python: $(python3 --version)"

# === Check Node.js ===
if ! command -v node &>/dev/null; then
    echo "[Setup] Node.js not found, installing..."
    if command -v brew &>/dev/null; then
        brew install node
    else
        echo "[ERROR] Please install Node.js: https://nodejs.org/"
        exit 1
    fi
fi
echo "[OK] Node.js: $(node --version)"

# === Setup Python venv ===
if [ ! -f .venv/bin/activate ]; then
    if [ -d .venv ]; then
        echo "[Setup] Removing incompatible venv, recreating for macOS..."
        rm -rf .venv
    fi
    echo "[Setup] Creating Python virtual environment..."
    python3 -m venv .venv
fi
source .venv/bin/activate

if [ ! -f .venv/.deps_installed ]; then
    echo "[Setup] Installing Python dependencies (first time, may take a minute)..."
    pip install --upgrade pip -q
    pip install -r requirements.txt
    touch .venv/.deps_installed
fi
echo "[OK] Python dependencies ready"

# === Setup frontend ===
if [ ! -d frontend/node_modules ]; then
    echo "[Setup] Installing frontend dependencies..."
    (cd frontend && npm install)
fi

if [ ! -f frontend/dist/index.html ]; then
    echo "[Setup] Building frontend..."
    (cd frontend && npm run build)
fi
echo "[OK] Frontend ready"

# === Load .env ===
if [ -f .env ]; then
    set -a; source .env; set +a
fi

# === Start server ===
echo ""
echo "============================================"
echo "  Server starting at http://localhost:8000"
echo "  Press Ctrl+C to stop"
echo "============================================"
echo ""

# Open browser after a short delay
(sleep 2 && open http://localhost:8000) &

exec .venv/bin/python3 -m uvicorn src.server:app --host 127.0.0.1 --port 8000
