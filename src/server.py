"""FastAPI server for Web translation interface.

Usage:
    python -m src.server
    # or: uvicorn src.server:app --reload --port 8000
"""

from __future__ import annotations

import logging
import os
import secrets
import shutil
import uuid
from pathlib import Path
from typing import Any, Optional

from fastapi import FastAPI, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse, Response
from pydantic import BaseModel
from starlette.middleware.sessions import SessionMiddleware
import yaml

from src.models.task import TaskStatus as S
from src.queue.manager import JobQueue
from src.utils.file_utils import get_temp_dir, validate_file
from src.utils.paths import get_config_dir, get_frontend_dist_dir
from src.utils.style_loader import list_styles as load_style_configs

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def _load_dotenv() -> None:
    """Load `.env` from the project root into os.environ (does not overwrite existing values)."""
    env_file = Path(__file__).resolve().parents[1] / ".env"
    if not env_file.exists():
        return
    for raw in env_file.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if key and not os.getenv(key):
            os.environ[key] = value


_load_dotenv()

SUPPORTED_EXTENSIONS = [
    ".pptx", ".srt", ".vtt", ".ass", ".docx", ".doc",
    ".md",
    ".json",
    ".yaml", ".yml",
    ".po", ".pot",
    ".xliff", ".xlf",
    ".xml",
    ".html", ".htm",
    ".txt", ".text",
]
FRONTEND_DIST_DIR = get_frontend_dist_dir()
CONFIG_DIR = get_config_dir()
PROMPTS_DIR = CONFIG_DIR / "prompts"
UNIFIED_PROMPT_ID = "translator"

app = FastAPI(title="多语种翻译 Agent", version="2.0.0")

# ── Auth: shared password gate ───────────────────────────────────────
ACCESS_PASSWORD = os.getenv("ACCESS_PASSWORD", "")
_SESSION_SECRET = os.getenv("SESSION_SECRET") or secrets.token_urlsafe(32)
if not ACCESS_PASSWORD:
    logger.warning(
        "ACCESS_PASSWORD is not set — every /api/* request will return 401. "
        "Set ACCESS_PASSWORD in .env to enable login."
    )

PUBLIC_API_PATHS = {"/api/login", "/api/auth-status"}


# Note: starlette's add_middleware prepends — the LAST add_middleware call
# becomes the OUTERMOST middleware. SessionMiddleware must be added AFTER
# auth_gate so it wraps auth_gate and injects `request.session` first.
@app.middleware("http")
async def auth_gate(request: Request, call_next):
    path = request.url.path
    if not path.startswith("/api/"):
        return await call_next(request)
    if path in PUBLIC_API_PATHS:
        return await call_next(request)
    if not request.session.get("authenticated"):
        return JSONResponse({"detail": "未登录"}, status_code=401)
    return await call_next(request)


app.add_middleware(
    SessionMiddleware,
    secret_key=_SESSION_SECRET,
    session_cookie="agent_translation_session",
    max_age=60 * 60 * 24 * 7,  # 7 days
    same_site="lax",
)


class LoginRequest(BaseModel):
    password: str


@app.post("/api/login")
async def login(request: Request, payload: LoginRequest) -> dict:
    if not ACCESS_PASSWORD:
        raise HTTPException(
            status_code=503,
            detail="服务端未配置 ACCESS_PASSWORD，无法登录",
        )
    # Constant-time comparison to avoid timing attacks
    if not secrets.compare_digest(payload.password, ACCESS_PASSWORD):
        raise HTTPException(status_code=401, detail="密码错误")
    request.session["authenticated"] = True
    return {"success": True}


@app.get("/api/auth-status")
async def auth_status(request: Request) -> dict:
    return {
        "authenticated": bool(request.session.get("authenticated")),
        "configured": bool(ACCESS_PASSWORD),
    }


cfg_path = CONFIG_DIR / "settings.yaml"
if cfg_path.exists():
    with open(cfg_path, encoding="utf-8") as f:
        _SERVER_CFG = yaml.safe_load(f) or {}
else:
    _SERVER_CFG = {}

# Global job queue – single instance for the lifetime of the server process
job_queue = JobQueue(
    max_workers=int(_SERVER_CFG.get("server", {}).get("max_job_workers", 4))
)


class GlossaryTermPatch(BaseModel):
    strategy: Optional[str] = None   # "hard" | "keep_original" | "skip"
    targets: Optional[dict] = None
    save_to_library: Optional[bool] = None


class GlossaryConfirmRequest(BaseModel):
    term_ids: Optional[list] = None  # None or [] = confirm all non-skipped
    update_library_term_ids: Optional[list] = None  # IDs of library terms to sync edits back


class DomainCreate(BaseModel):
    name: str
    description: str = ""


class DomainUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None


class LibraryTermCreate(BaseModel):
    source: str
    targets: dict = {}
    strategy: str = "hard"
    ai_category: str = ""
    context: str = ""


class LibraryTermUpdate(BaseModel):
    source: Optional[str] = None
    targets: Optional[dict] = None
    strategy: Optional[str] = None
    ai_category: Optional[str] = None
    context: Optional[str] = None


class BatchDeleteRequest(BaseModel):
    term_ids: list[int]


def _build_prompt_registry() -> dict[str, dict[str, Any]]:
    return {
        UNIFIED_PROMPT_ID: {
            "label": "统一翻译 Prompt",
            "path": PROMPTS_DIR / "translator_unified.md",
            "type": "markdown",
        }
    }


def _get_prompt_config(config_id: str) -> dict[str, Any]:
    registry = _build_prompt_registry()
    item = registry.get(config_id)
    if not item:
        raise HTTPException(status_code=404, detail="Prompt 配置不存在")
    return item


def _serialize_prompt_config(config_id: str, item: dict[str, Any]) -> dict[str, Any]:
    path = item["path"]
    return {
        "id": config_id,
        "label": item["label"],
        "path": str(path.relative_to(CONFIG_DIR.parent)),
        "type": item["type"],
        "content": path.read_text(encoding="utf-8"),
    }



# ── Static files ─────────────────────────────────────────────────────

def _frontend_index_path() -> Path:
    dist_index = FRONTEND_DIST_DIR / "index.html"
    if dist_index.exists():
        return dist_index
    raise HTTPException(status_code=404, detail="Web frontend not found")


def _resolve_frontend_asset(path: str) -> Path | None:
    normalized = path.strip("/")
    if not normalized:
        return None

    if ".." in normalized:
        raise HTTPException(status_code=400, detail="无效的静态资源路径")

    dist_path = (FRONTEND_DIST_DIR / normalized).resolve()
    if dist_path.is_file() and FRONTEND_DIST_DIR.resolve() in dist_path.parents:
        return dist_path

    return None

@app.get("/", response_class=HTMLResponse)
async def index() -> HTMLResponse:
    p = _frontend_index_path()
    return HTMLResponse(content=p.read_text(encoding="utf-8"))


@app.get("/app.js")
async def serve_js() -> FileResponse:
    p = _resolve_frontend_asset("app.js")
    if p is None:
        raise HTTPException(status_code=404)
    return FileResponse(p, media_type="application/javascript")


@app.get("/style.css")
async def serve_css() -> FileResponse:
    p = _resolve_frontend_asset("style.css")
    if p is None:
        raise HTTPException(status_code=404)
    return FileResponse(p, media_type="text/css")


@app.get("/health")
async def health() -> dict:
    return {"status": "ok", "version": "2.0.0"}


# ── Resource lists ────────────────────────────────────────────────────

@app.get("/api/languages")
async def list_languages() -> dict:
    cfg_path = CONFIG_DIR / "settings.yaml"
    with open(cfg_path, encoding="utf-8") as f:
        cfg = yaml.safe_load(f)
    return {"languages": cfg.get("supported_languages", [])}


@app.get("/api/styles")
async def api_list_styles() -> dict:
    styles = load_style_configs()
    return {
        "styles": [
            {"key": k, "name": v.get("name", k), "description": v.get("description", "")}
            for k, v in styles.items()
        ]
    }


@app.get("/api/prompt-configs")
async def list_prompt_configs() -> dict:
    registry = _build_prompt_registry()
    items = []
    for config_id, item in registry.items():
        path = item["path"]
        items.append(
            {
                "id": config_id,
                "label": item["label"],
                "path": str(path.relative_to(CONFIG_DIR.parent)),
                "type": item["type"],
            }
        )
    return {"items": items}


@app.get("/api/prompt-configs/{config_id}")
async def get_prompt_config(config_id: str) -> dict:
    item = _get_prompt_config(config_id)
    path = item["path"]
    if not path.exists():
        raise HTTPException(status_code=404, detail="Prompt 文件不存在")
    return _serialize_prompt_config(config_id, item)


@app.get("/api/prompt")
async def get_unified_prompt() -> dict:
    item = _get_prompt_config(UNIFIED_PROMPT_ID)
    path = item["path"]
    if not path.exists():
        raise HTTPException(status_code=404, detail="统一 Prompt 文件不存在")
    return _serialize_prompt_config(UNIFIED_PROMPT_ID, item)


# ── LLM config endpoints ─────────────────────────────────────────────

@app.get("/api/llm-config")
async def get_llm_config() -> dict:
    with open(cfg_path, encoding="utf-8") as f:
        cfg = yaml.safe_load(f) or {}
    sudo_cfg = cfg.get("sudo", {})
    models_cfg = cfg.get("models", {})
    raw_key = sudo_cfg.get("api_key", "")
    # Resolve env var placeholder (e.g. ${SUDO_API_KEY})
    if raw_key.startswith("${") and raw_key.endswith("}"):
        raw_key = os.getenv(raw_key[2:-1], "")
    # Mask the key: show only last 4 chars
    if raw_key and raw_key != "${SUDO_API_KEY}" and len(raw_key) > 4:
        masked = "•" * (len(raw_key) - 4) + raw_key[-4:]
    else:
        masked = raw_key
    # All tasks share the same model; just surface translation model as representative
    model = models_cfg.get("translation", "gpt-5.5")
    return {
        "api_key_masked": masked,
        "base_url": sudo_cfg.get("base_url", "https://sudocode.us/v1"),
        "model": model,
    }


# ── Job queue endpoints ───────────────────────────────────────────────

@app.post("/api/jobs")
async def submit_jobs(
    files: list[UploadFile] = File(...),
    target_languages: str = Form(...),
    use_glossary: str = Form("true"),
    library_domain_ids: str = Form(""),
) -> dict:
    """Submit one or more files for translation. Returns list of job_ids."""
    targets = [t.strip() for t in target_languages.split(",") if t.strip()]
    if not targets:
        raise HTTPException(status_code=400, detail="至少选择一个目标语言")

    glossary_mode = use_glossary.lower() not in ("false", "0", "no")

    # Parse library domain IDs from comma-separated string
    parsed_domain_ids: list[int] = []
    if library_domain_ids.strip():
        try:
            parsed_domain_ids = [int(x.strip()) for x in library_domain_ids.split(",") if x.strip()]
        except ValueError:
            raise HTTPException(status_code=400, detail="library_domain_ids 格式错误")

    temp_dir = get_temp_dir()
    job_ids: list[str] = []

    for file in files:
        suffix = Path(file.filename or "").suffix.lower()
        if suffix not in SUPPORTED_EXTENSIONS:
            raise HTTPException(
                status_code=400,
                detail=f"不支持的文件格式: {suffix}。当前支持: {', '.join(SUPPORTED_EXTENSIONS)}",
            )

        work_dir = temp_dir / f"job_{uuid.uuid4().hex[:10]}"
        work_dir.mkdir(parents=True, exist_ok=True)
        source_path = work_dir / (file.filename or f"upload{suffix}")

        try:
            content = await file.read()
            source_path.write_bytes(content)
            validate_file(str(source_path), SUPPORTED_EXTENSIONS)
        except ValueError as e:
            shutil.rmtree(work_dir, ignore_errors=True)
            raise HTTPException(status_code=400, detail=str(e))
        except Exception as e:
            shutil.rmtree(work_dir, ignore_errors=True)
            raise HTTPException(status_code=500, detail=f"保存文件失败: {e}")

        job_id = await job_queue.submit(
            source_path=source_path,
            filename=file.filename or source_path.name,
            targets=targets,
            work_dir=work_dir,
            use_glossary=glossary_mode,
            library_domain_ids=parsed_domain_ids or None,
        )
        job_ids.append(job_id)

    return {"job_ids": job_ids}


@app.get("/api/jobs")
async def list_jobs() -> dict:
    """List all jobs, newest first."""
    return {"jobs": job_queue.list_all()}


@app.get("/api/jobs/{job_id}")
async def get_job(job_id: str) -> dict:
    """Get status and result for a single job."""
    job = job_queue.get(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="任务不存在")
    return job


@app.delete("/api/jobs/{job_id}")
async def cancel_job(job_id: str) -> dict:
    """Cancel a queued job (no-op if already running or done)."""
    success = await job_queue.cancel(job_id)
    return {"success": success}


@app.post("/api/jobs/batch-delete")
async def batch_delete_jobs(payload: dict) -> dict:
    """Permanently delete jobs from history."""
    job_ids: list = payload.get("job_ids", [])
    deleted = job_queue.delete_batch(job_ids)
    return {"deleted": deleted}


@app.patch("/api/jobs/{job_id}/glossary/{term_id}")
async def update_glossary_term(
    job_id: str,
    term_id: str,
    payload: GlossaryTermPatch,
) -> dict:
    """Update a single glossary term's strategy and/or translations."""
    job = job_queue.get(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="任务不存在")
    if job.get("status") != S.AWAITING_GLOSSARY_REVIEW:
        raise HTTPException(status_code=409, detail="术语表只能在 awaiting_glossary_review 阶段修改")

    updated = job_queue.update_glossary_term(
        job_id=job_id,
        term_id=term_id,
        strategy=payload.strategy,
        targets=payload.targets,
        save_to_library=payload.save_to_library,
    )
    if updated is None:
        raise HTTPException(status_code=404, detail="术语不存在")
    return {"term": updated}


@app.post("/api/jobs/{job_id}/glossary/reextract")
async def reextract_glossary(job_id: str) -> dict:
    """Discard current terms and re-run terminology extraction for this job."""
    job = job_queue.get(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="任务不存在")
    if job.get("status") != S.AWAITING_GLOSSARY_REVIEW:
        raise HTTPException(status_code=409, detail="只能在术语审核阶段重新提取")
    success = await job_queue.reextract_glossary(job_id)
    if not success:
        raise HTTPException(status_code=500, detail="重新提取失败")
    return {"success": True, "message": "术语已重新提取"}


@app.post("/api/jobs/{job_id}/glossary/confirm")
async def confirm_glossary(
    job_id: str,
    payload: GlossaryConfirmRequest,
) -> dict:
    """Confirm glossary terms and trigger translation (Phase 2)."""
    job = job_queue.get(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="任务不存在")
    if job.get("status") != S.AWAITING_GLOSSARY_REVIEW:
        raise HTTPException(status_code=409, detail="任务不在术语确认阶段")

    success = await job_queue.confirm_glossary(
        job_id=job_id,
        term_ids=payload.term_ids if payload.term_ids else None,
        update_library_term_ids=payload.update_library_term_ids,
    )
    if not success:
        raise HTTPException(status_code=500, detail="确认术语表失败")
    return {"success": True, "message": "术语已确认，翻译任务已加入队列"}


@app.get("/api/jobs/{job_id}/glossary")
async def get_glossary(job_id: str) -> dict:
    """Get the full glossary for a job (including unconfirmed terms)."""
    job = job_queue.get(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="任务不存在")
    glossary_data = job.get("glossary") or {}
    return {"glossary": glossary_data}


# ── File download ─────────────────────────────────────────────────────

@app.get("/api/download/{job_id}/{filename}")
async def download(job_id: str, filename: str) -> FileResponse:
    """Download a translated file."""
    if ".." in filename or "/" in filename or "\\" in filename:
        raise HTTPException(status_code=400, detail="无效的文件名")

    key = f"{job_id}/{filename}"
    path = job_queue.outputs.get(key)
    if not path or not path.exists():
        raise HTTPException(status_code=404, detail="文件不存在或已过期")

    return FileResponse(path, filename=filename)



# ── Terminology Library endpoints ─────────────────────────────────────

def _get_library_service():
    from src.terminology.library_service import TermLibraryService
    return TermLibraryService()


def _get_library_db():
    from src.terminology.library_db import TermLibraryDB
    return TermLibraryDB()


@app.get("/api/library/domains")
async def list_library_domains() -> dict:
    db = _get_library_db()
    return {"domains": db.list_domains()}


@app.post("/api/library/domains")
async def create_library_domain(payload: DomainCreate) -> dict:
    db = _get_library_db()
    try:
        domain_id = db.create_domain(payload.name, payload.description)
    except Exception as exc:
        if "UNIQUE" in str(exc):
            raise HTTPException(status_code=409, detail="领域名称已存在")
        raise
    return {"id": domain_id, "name": payload.name}


@app.put("/api/library/domains/{domain_id}")
async def update_library_domain(domain_id: int, payload: DomainUpdate) -> dict:
    db = _get_library_db()
    ok = db.update_domain(domain_id, name=payload.name, description=payload.description)
    if not ok:
        raise HTTPException(status_code=404, detail="领域不存在")
    return {"success": True}


@app.delete("/api/library/domains/{domain_id}")
async def delete_library_domain(domain_id: int) -> dict:
    db = _get_library_db()
    ok = db.delete_domain(domain_id)
    if not ok:
        raise HTTPException(status_code=404, detail="领域不存在")
    return {"success": True}


@app.get("/api/library/domains/{domain_id}/terms")
async def list_library_terms(
    domain_id: int,
    search: str = "",
    offset: int = 0,
    limit: int = 50,
) -> dict:
    db = _get_library_db()
    terms = db.get_terms_by_domain(domain_id, search=search, offset=offset, limit=limit)
    total = db.count_terms_by_domain(domain_id, search=search)
    return {"terms": terms, "total": total}


@app.post("/api/library/domains/{domain_id}/terms")
async def create_library_term(domain_id: int, payload: LibraryTermCreate) -> dict:
    db = _get_library_db()
    term_id = db.upsert_term(
        domain_id=domain_id,
        source=payload.source,
        targets=payload.targets,
        strategy=payload.strategy,
        ai_category=payload.ai_category,
        context=payload.context,
    )
    return {"id": term_id}


@app.put("/api/library/terms/{term_id}")
async def update_library_term(term_id: int, payload: LibraryTermUpdate) -> dict:
    db = _get_library_db()
    fields = {k: v for k, v in payload.model_dump().items() if v is not None}
    if not fields:
        raise HTTPException(status_code=400, detail="没有可更新的字段")
    ok = db.update_term(term_id, **fields)
    if not ok:
        raise HTTPException(status_code=404, detail="术语不存在")
    return {"success": True}


@app.delete("/api/library/terms/{term_id}")
async def delete_library_term(term_id: int) -> dict:
    db = _get_library_db()
    ok = db.delete_term(term_id)
    if not ok:
        raise HTTPException(status_code=404, detail="术语不存在")
    return {"success": True}


@app.post("/api/library/terms/batch-delete")
async def batch_delete_library_terms(payload: BatchDeleteRequest) -> dict:
    db = _get_library_db()
    count = db.delete_terms_batch(payload.term_ids)
    return {"deleted": count}


@app.get("/api/library/import-template")
async def download_import_template():
    langs = _SERVER_CFG.get("supported_languages", [])
    lang_codes = [l["code"] for l in langs if "code" in l] or ["en", "zh-CN", "ja"]
    # Ensure 'en' comes first
    if "en" in lang_codes:
        lang_codes.remove("en")
    lang_codes.insert(0, "en")
    header = ",".join(lang_codes + ["strategy", "context"])
    example_vals = {
        "en": "example term", "zh-CN": "示例术语", "zh-TW": "範例術語",
        "ja": "用語例", "ko": "용어 예", "fr": "terme exemple",
        "de": "Beispielbegriff", "es": "término ejemplo",
    }
    row = ",".join(example_vals.get(c, "") for c in lang_codes) + ",hard,"
    content = header + "\n" + row + "\n"
    return Response(
        content=content, media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=import_template.csv"},
    )


@app.post("/api/library/domains/{domain_id}/import")
async def import_library_terms(
    domain_id: int,
    file: UploadFile = File(...),
) -> dict:
    svc = _get_library_service()

    raw = await file.read()
    if len(raw) > 10 * 1024 * 1024:
        raise HTTPException(status_code=400, detail="File too large (max 10MB) / 文件过大（最大 10MB）")

    # Try decoding with BOM-aware UTF-8 first, then plain UTF-8
    for encoding in ("utf-8-sig", "utf-8"):
        try:
            content = raw.decode(encoding)
            break
        except UnicodeDecodeError:
            continue
    else:
        raise HTTPException(
            status_code=400,
            detail="File encoding not supported. Please save as UTF-8. / 文件编码不支持，请另存为 UTF-8 格式。",
        )

    filename = (file.filename or "").lower()
    try:
        if filename.endswith(".tsv"):
            result = svc.import_tsv(domain_id, content)
        else:
            result = svc.import_csv(domain_id, content)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    return result


@app.get("/api/library/domains/{domain_id}/export")
async def export_library_terms(domain_id: int, format: str = "csv") -> Any:
    svc = _get_library_service()
    if format == "tsv":
        content = svc.export_tsv(domain_id)
        return Response(content=content, media_type="text/tab-separated-values",
                        headers={"Content-Disposition": f"attachment; filename=terms_{domain_id}.tsv"})
    elif format == "json":
        content = svc.export_json(domain_id)
        return Response(content=content, media_type="application/json",
                        headers={"Content-Disposition": f"attachment; filename=terms_{domain_id}.json"})
    else:
        content = svc.export_csv(domain_id)
        return Response(content=content, media_type="text/csv",
                        headers={"Content-Disposition": f"attachment; filename=terms_{domain_id}.csv"})


@app.get("/{full_path:path}")
async def frontend_routes(full_path: str):
    if full_path.startswith("api/") or full_path == "health":
        raise HTTPException(status_code=404, detail="资源不存在")

    asset = _resolve_frontend_asset(full_path)
    if asset is not None:
        return FileResponse(asset)

    index_path = _frontend_index_path()
    return HTMLResponse(content=index_path.read_text(encoding="utf-8"))


def main() -> None:
    import uvicorn
    port = int(os.getenv("PORT", "8000"))
    reload = os.getenv("RELOAD", "").lower() in ("1", "true", "yes")
    uvicorn.run("src.server:app", host="0.0.0.0", port=port, reload=reload)


if __name__ == "__main__":
    main()
