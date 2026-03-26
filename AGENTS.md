# AGENTS.md

## General Rules

- Before making code changes, thoroughly read and understand the existing codebase structure, especially how components interact. Never jump to code changes without confirming understanding with the user first.
- When fixing bugs, make minimal targeted changes. Do not remove or refactor surrounding code aggressively — this has caused regressions multiple times. If a broader redesign is needed, propose it as a separate step.
- For complex multi-file changes, use plan mode first: map out every file that needs to change, what changes each needs, and the order of operations.

## Tech Stack

- **Backend:** Python 3.11+, FastAPI, Pydantic 2.x, httpx (Poe API)
- **Frontend:** React 18 + TypeScript, Vite, Tailwind CSS 4, Radix UI
- Frontend builds to `frontend/dist/` and is served by FastAPI as static files
- After making frontend changes, always verify the build succeeds with `cd frontend && npm run build`

## How to Run

- **Full app:** `./run_server.sh` (installs deps, builds frontend, starts server on port 8000)
- **Backend only:** `python -m uvicorn src.server:app --reload --port 8000`
- **Frontend dev:** `cd frontend && npm run dev` (proxies API to localhost:8000)
- **Tests:** `pytest` (test framework configured but tests/ is currently empty)

## Translation & Prompts

- Translation quality and naturalness is a top priority for this project.
- When modifying translation prompts, preserve the user's creative framework and intent — do not over-engineer or rewrite from scratch unless explicitly asked.
- Prompt templates live in `src/prompt/`. Style definitions live in `config/styles/`.

## Project Structure

- `src/` — Python backend (FastAPI server, translation engine, parsers, terminology)
- `frontend/` — React/TypeScript web UI
- `config/` — settings.yaml and translation style definitions
- `data/` — samples, cache, terminology.db
- `glossaries/` — terminology library files
