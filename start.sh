#!/bin/bash
set -e
cd "$(dirname "$0")"
chmod +x "$0" 2>/dev/null || true

echo "============================================"
echo "  AgentTranslation - Starting..."
echo "============================================"
echo ""

# === Ensure Homebrew is available ===
ensure_brew() {
    if command -v brew &>/dev/null; then
        return
    fi
    echo "[Setup] Installing Homebrew (macOS package manager)..."
    /bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
    # Add Homebrew to PATH for Apple Silicon and Intel Macs
    if [ -f /opt/homebrew/bin/brew ]; then
        eval "$(/opt/homebrew/bin/brew shellenv)"
    elif [ -f /usr/local/bin/brew ]; then
        eval "$(/usr/local/bin/brew shellenv)"
    fi
}

# === Check Python 3 (need 3.11+) ===
need_python=false
if ! command -v python3 &>/dev/null; then
    need_python=true
else
    py_version=$(python3 -c 'import sys; print(sys.version_info.minor)')
    if [ "$py_version" -lt 11 ]; then
        echo "[Setup] Python 3.$(echo $py_version) found but 3.11+ required, upgrading..."
        need_python=true
    fi
fi
if $need_python; then
    echo "[Setup] Installing Python 3.12..."
    ensure_brew
    brew install python@3.12
    # Prefer the newly installed Python
    export PATH="$(brew --prefix python@3.12)/libexec/bin:$PATH"
fi
echo "[OK] Python: $(python3 --version)"

# === Check Node.js ===
if ! command -v node &>/dev/null; then
    echo "[Setup] Node.js not found, installing..."
    ensure_brew
    brew install node
fi
echo "[OK] Node.js: $(node --version)"

# === Setup Python venv ===
recreate_venv=false
if [ ! -f .venv/bin/activate ]; then
    recreate_venv=true
elif ! .venv/bin/python3 --version &>/dev/null; then
    echo "[Setup] Existing venv is broken (Python binary missing), recreating..."
    recreate_venv=true
fi
if $recreate_venv; then
    if [ -d .venv ]; then
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
