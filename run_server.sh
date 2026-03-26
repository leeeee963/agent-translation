#!/bin/bash
cd "$(dirname "$0")"

if [ ! -d frontend/node_modules ]; then
  (cd frontend && npm install)
fi

if [ ! -f frontend/dist/index.html ]; then
  (cd frontend && npm run build)
fi

export POE_API_KEY='L-7OykRj5UpWsNOIwkeW7c9sSVVxKWWVVHLy-_BWBHI'
exec .venv/bin/python3.9 -m uvicorn src.server:app --reload --port 8000
