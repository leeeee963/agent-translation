# syntax=docker/dockerfile:1.6
# Production-only image. Not needed for local development — see README.

# ── Stage 1: build the frontend ──────────────────────────────────────
FROM node:20-alpine AS frontend
WORKDIR /app/frontend
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci
COPY frontend/ ./
RUN npm run build

# ── Stage 2: Python runtime ──────────────────────────────────────────
FROM python:3.12-slim AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

# System libs required by lxml / python-pptx / python-docx
RUN apt-get update && apt-get install -y --no-install-recommends \
        build-essential \
        libxml2-dev \
        libxslt1-dev \
        zlib1g-dev \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt ./
RUN pip install --upgrade pip && pip install -r requirements.txt

COPY src/ ./src/
COPY config/ ./config/
COPY pyproject.toml ./
COPY --from=frontend /app/frontend/dist ./frontend/dist

RUN mkdir -p /app/data

# Zeabur injects $PORT; default 8000 for self-hosted runs
EXPOSE 8000
CMD ["sh", "-c", "python -m uvicorn src.server:app --host 0.0.0.0 --port ${PORT:-8000}"]
