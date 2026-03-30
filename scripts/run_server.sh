#!/bin/bash
# Navigate to project root (one level up from scripts/)
cd "$(dirname "$0")/.."

if [ ! -d frontend/node_modules ]; then
  (cd frontend && npm install)
fi

if [ ! -f frontend/dist/index.html ]; then
  (cd frontend && npm run build)
fi

# Load .env file if present (for POE_API_KEY etc.)
if [ -f .env ]; then
  set -a; source .env; set +a
fi

exec .venv/bin/python3 -m uvicorn src.server:app --reload --port 8000
