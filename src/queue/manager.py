"""Job queue for managing translation tasks with an asyncio worker pool."""

from __future__ import annotations

import asyncio
import logging
import shutil
import uuid
from pathlib import Path
from typing import Any

from src.models.task import TaskStatus as S
from src.queue.job_db import JobDB

logger = logging.getLogger(__name__)


class JobQueue:
    """Async task queue backed by an asyncio worker pool."""

    def __init__(self, max_workers: int = 3) -> None:
        self._max_workers = max_workers
        self._queue: asyncio.Queue[dict] | None = None
        self._lock_obj: asyncio.Lock | None = None
        self._jobs: dict[str, dict] = {}
        # Maps "{job_id}/{filename}" -> storage key (e.g., "jobs/abc/output/foo.pptx")
        self._outputs: dict[str, str] = {}
        self._active = 0
        # Phase 1 intermediate state: job_id -> {parsed, parser, work_dir, job_obj}
        self._phase1_store: dict[str, dict] = {}
        # Live Glossary objects for mutation by confirm/update endpoints
        self._glossaries: dict[str, Any] = {}
        # Persistent storage
        self._db = JobDB()
        self._storage_lazy: Any = None

    @property
    def storage(self):
        if self._storage_lazy is None:
            from src.storage import get_storage
            self._storage_lazy = get_storage()
        return self._storage_lazy

    def _get_queue(self) -> asyncio.Queue:
        if self._queue is None:
            self._queue = asyncio.Queue()
        return self._queue

    def _get_lock(self) -> asyncio.Lock:
        if self._lock_obj is None:
            self._lock_obj = asyncio.Lock()
        return self._lock_obj

    async def submit(
        self,
        source_path: Path,
        filename: str,
        targets: list[str],
        work_dir: Path,
        use_glossary: bool = True,
        library_domain_ids: list[int] | None = None,
    ) -> str:
        """Queue a translation job and return its job_id."""

        job_id = uuid.uuid4().hex[:12]
        now = JobDB.now_iso()
        self._jobs[job_id] = {
            "job_id": job_id,
            "filename": filename,
            "source_file": str(source_path),
            "source_language": "",
            "use_glossary": use_glossary,
            "library_domain_ids": library_domain_ids or [],
            "status": S.QUEUED,
            "stage": S.QUEUED,
            "detail": "等待中...",
            "percent": 0,
            "segments_done": 0,
            "segments_total": 0,
            "units_done": 0,
            "units_total": len(targets),
            "unit_label": "language",
            "current_range": "",
            "target_languages": targets,
            "glossary": None,
            "glossary_exports": {},
            "created_at": now,
            "started_at": None,
            "completed_at": None,
            "language_runs": [
                {
                    "target_language": target_language,
                    "status": S.QUEUED,
                    "stage": S.QUEUED,
                    "detail": "等待中...",
                    "percent": 0,
                    "segments_done": 0,
                    "segments_total": 0,
                    "units_done": 0,
                    "units_total": 0,
                    "unit_label": "",
                    "current_range": "",
                    "output_file": "",
                    "download_url": "",
                    "error_message": "",
                }
                for target_language in targets
            ],
            "result": None,
            "error": None,
        }
        # Persist to SQLite
        self._db.save_job(self._jobs[job_id])

        await self._get_queue().put(
            {
                "job_id": job_id,
                "source_path": source_path,
                "targets": targets,
                "work_dir": work_dir,
                "use_glossary": use_glossary,
                "library_domain_ids": library_domain_ids or [],
                "phase": 1,
            }
        )
        asyncio.create_task(self._ensure_workers())
        return job_id

    def get(self, job_id: str) -> dict | None:
        return self._jobs.get(job_id)

    def list_all(self) -> list[dict]:
        """Return all jobs: in-memory active ones + persisted history, newest first."""
        # Start with in-memory jobs (they have the most up-to-date state)
        in_memory_ids = set(self._jobs.keys())
        result = list(self._jobs.values())

        # Add historical jobs from DB that aren't currently in memory
        for db_job in self._db.load_all():
            if db_job["job_id"] not in in_memory_ids:
                # Fill in fields that only exist in-memory for active jobs
                db_job.setdefault("segments_done", 0)
                db_job.setdefault("segments_total", 0)
                db_job.setdefault("units_done", 0)
                db_job.setdefault("units_total", 0)
                db_job.setdefault("unit_label", "")
                db_job.setdefault("current_range", "")
                db_job.setdefault("glossary", None)
                db_job.setdefault("glossary_exports", {})
                db_job.setdefault("language_runs", [])
                db_job.setdefault("source_file", "")
                result.append(db_job)

        # Sort by created_at descending (newest first); fallback to started_at/completed_at
        result.sort(
            key=lambda j: j.get("created_at") or j.get("started_at") or j.get("completed_at") or "",
            reverse=True,
        )
        return result

    async def cancel(self, job_id: str) -> bool:
        job = self._jobs.get(job_id)
        if job and job["status"] in (S.QUEUED, S.AWAITING_GLOSSARY_REVIEW):
            job.update({"status": S.CANCELLED, "stage": S.CANCELLED, "detail": "已取消"})
            # Clean up phase 1 store if waiting for review
            self._phase1_store.pop(job_id, None)
            self._glossaries.pop(job_id, None)
            self._persist_final(job_id)
            return True
        return False

    def delete(self, job_id: str) -> bool:
        """Permanently delete a job from memory, database, and storage."""
        self._jobs.pop(job_id, None)
        self._phase1_store.pop(job_id, None)
        self._glossaries.pop(job_id, None)
        # Drop in-memory output mappings
        for key in [k for k in self._outputs if k.startswith(f"{job_id}/")]:
            self._outputs.pop(key, None)
        # Wipe storage objects under this job
        try:
            self.storage.delete_prefix(f"jobs/{job_id}")
        except Exception as exc:  # noqa: BLE001
            logger.warning("storage delete_prefix failed for %s: %s", job_id, exc)
        self._db.delete_job(job_id)
        return True

    def delete_batch(self, job_ids: list[str]) -> int:
        """Delete multiple jobs. Returns count of deleted."""
        count = 0
        for job_id in job_ids:
            if self.delete(job_id):
                count += 1
        return count

    def update_glossary_term(
        self,
        job_id: str,
        term_id: str,
        strategy: str | None,
        targets: dict | None,
        save_to_library: bool | None = None,
    ) -> dict | None:
        """Update a single term's strategy and/or translations. Returns updated term dict."""
        glossary = self._glossaries.get(job_id)
        if not glossary:
            return None
        for term in glossary.terms:
            if term.id == term_id:
                if strategy is not None:
                    term.strategy = strategy
                if targets is not None:
                    for lang, value in targets.items():
                        term.targets[lang] = value
                if save_to_library is not None:
                    term.save_to_library = save_to_library
                return term.model_dump()
        return None

    async def reextract_glossary(self, job_id: str) -> bool:
        """Re-run terminology extraction for a job that is awaiting glossary review.

        Discards all current terms and replaces them with a fresh extraction.
        The job stays in awaiting_glossary_review state.
        Returns True on success, False if the job is not in the right state.
        """
        from src.terminology.agent import TerminologyAgent
        from src.utils.glossary_export import build_glossary_exports

        job = self._jobs.get(job_id)
        if not job or job.get("status") != S.AWAITING_GLOSSARY_REVIEW:
            return False

        phase1_data = self._phase1_store.get(job_id)
        if not phase1_data:
            return False

        parsed = phase1_data["parsed"]
        job_obj = phase1_data["job_obj"]

        # Keep status as awaiting_glossary_review throughout — changing it would
        # cause the frontend to unmount the review panel mid-extraction.
        job.update({"detail": "重新提取术语中...", "percent": 10})

        try:
            agent = TerminologyAgent()
            glossary = await agent.run(
                text=parsed.plain_text,
                source_language=job_obj.source_language,
                target_languages=[run.target_language for run in job_obj.language_runs],
                source_file=job_obj.source_file,
            )
            job_obj.glossary = glossary
            job_obj.glossary_exports = build_glossary_exports(glossary)
            self._glossaries[job_id] = glossary

            # Rebuild the serialized job dict from the updated job_obj,
            # preserving fields that only live in the dict (not in TranslationJob).
            updated = job_obj.model_dump(mode="json")
            updated["job_id"] = job_id
            updated["filename"] = job.get("filename", "")
            updated["source_file"] = job.get("source_file", "")
            updated["use_glossary"] = job.get("use_glossary", True)
            updated["error"] = None
            self._jobs[job_id] = updated
            return True
        except Exception as exc:
            logger.exception("reextract_glossary failed for %s: %s", job_id, exc)
            job.update({"detail": f"重新提取失败：{exc}", "percent": 20})
            return False

    async def confirm_glossary(
        self,
        job_id: str,
        term_ids: list[str] | None = None,
        update_library_term_ids: list[str] | None = None,
    ) -> bool:
        """Mark terms as confirmed and trigger phase 2 translation.

        If term_ids is None or empty, confirms all non-skipped terms.
        update_library_term_ids: IDs of library terms whose edits should sync back to library.
        Returns True if phase 2 was queued, False if job not found/wrong state.
        """
        job = self._jobs.get(job_id)
        if not job or job.get("status") != S.AWAITING_GLOSSARY_REVIEW:
            return False

        glossary = self._glossaries.get(job_id)
        phase1_data = self._phase1_store.get(job_id)
        if not glossary or not phase1_data:
            return False

        # Mark terms as confirmed
        for term in glossary.terms:
            if term_ids is None or not term_ids:
                # Confirm all non-skipped terms
                if term.strategy != "skip":
                    term.confirmed = True
            elif term.id in term_ids:
                term.confirmed = True

        # Save terms to library if applicable
        save_new_ids = {t.id for t in glossary.terms if t.save_to_library and t.library_term_id is None}
        update_lib_ids = set(update_library_term_ids or [])

        if save_new_ids or update_lib_ids:
            try:
                from src.terminology.library_service import TermLibraryService

                service = TermLibraryService()
                new_count, updated_count = service.save_confirmed_terms(
                    glossary,
                    save_new_term_ids=save_new_ids,
                    update_library_term_ids=update_lib_ids,
                    user_selected_domain_ids=job.get("library_domain_ids", []),
                    document_domains=glossary.document_domains,
                )
                logger.info(
                    "Library save-back for job %s: %d new, %d updated",
                    job_id, new_count, updated_count,
                )
            except Exception as exc:
                logger.exception("Library save-back failed for job %s: %s", job_id, exc)

        # Update job dict to reflect confirmation
        job.update({
            "status": S.QUEUED,
            "stage": S.QUEUED,
            "detail": "术语已确认，等待翻译...",
        })

        # Queue phase 2 work
        await self._get_queue().put({
            "job_id": job_id,
            "phase": 2,
            "work_dir": phase1_data["work_dir"],
        })
        asyncio.create_task(self._ensure_workers())
        return True

    def _persist_final(self, job_id: str) -> None:
        """Persist a job that has reached a terminal state (done/error/cancelled)."""
        job = self._jobs.get(job_id)
        if not job:
            return
        if not job.get("completed_at"):
            job["completed_at"] = JobDB.now_iso()
        # Carry over timestamps
        self._db.save_job(job)

    @property
    def outputs(self) -> dict[str, str]:
        return self._outputs

    async def _ensure_workers(self) -> None:
        async with self._get_lock():
            while self._active < self._max_workers and not self._get_queue().empty():
                self._active += 1
                asyncio.create_task(self._worker())

    async def _worker(self) -> None:
        try:
            while True:
                try:
                    item = self._get_queue().get_nowait()
                except asyncio.QueueEmpty:
                    break
                job = self._jobs.get(item["job_id"])
                if not job or job["status"] == S.CANCELLED:
                    continue
                if item.get("phase") == 2:
                    await self._execute_phase2(item, job)
                else:
                    await self._execute(item, job)
        finally:
            async with self._get_lock():
                self._active -= 1
            if not self._get_queue().empty():
                asyncio.create_task(self._ensure_workers())

    async def _execute(self, item: dict, job: dict) -> None:
        from src.orchestrator.agent import Orchestrator

        job_id: str = item["job_id"]
        source_path: Path = item["source_path"]
        targets: list[str] = item["targets"]
        work_dir: Path = item["work_dir"]
        use_glossary: bool = item.get("use_glossary", True)
        library_domain_ids: list[int] = item.get("library_domain_ids", [])

        job.update({"status": S.PARSING, "stage": S.PARSING, "detail": "解析文件中...", "started_at": job.get("started_at") or JobDB.now_iso()})
        self._db.update_job(job_id, status=S.PARSING, started_at=job["started_at"])

        # Preserve timestamps across progress callbacks
        timestamps = {
            "created_at": job.get("created_at"),
            "started_at": job.get("started_at"),
            "completed_at": job.get("completed_at"),
        }

        def on_progress(snapshot) -> None:
            payload = snapshot.model_dump(mode="json")
            payload["job_id"] = job_id
            payload["filename"] = job.get("filename", payload.get("filename", ""))
            payload["source_file"] = job.get("source_file", payload.get("source_file", ""))
            payload["result"] = self._build_legacy_result(job_id, payload)
            payload["error"] = payload.get("error_message") or None
            payload.update(timestamps)
            self._jobs[job_id] = payload

        try:
            orchestrator = Orchestrator()

            if use_glossary:
                # Phase 1: parse + extract → pause at awaiting_glossary_review
                translation_job, parsed, parser_inst = await orchestrator.run_phase1(
                    source_file=str(source_path),
                    target_languages=targets,
                    output_dir=str(work_dir),
                    quiet=True,
                    progress_callback=on_progress,
                    library_domain_ids=library_domain_ids or None,
                )

                if translation_job.status == S.ERROR:
                    finalized = translation_job.model_dump(mode="json")
                    finalized["job_id"] = job_id
                    finalized["filename"] = job.get("filename", "")
                    finalized["source_file"] = job.get("source_file", "")
                    finalized["result"] = self._build_legacy_result(job_id, finalized)
                    finalized["error"] = finalized.get("error_message") or None
                    finalized.update(timestamps)
                    self._jobs[job_id] = finalized
                    self._persist_final(job_id)
                    shutil.rmtree(work_dir, ignore_errors=True)
                    return

                if translation_job.status == S.DONE:
                    # No translatable content — done in phase 1
                    finalized = translation_job.model_dump(mode="json")
                    finalized["job_id"] = job_id
                    finalized["filename"] = job.get("filename", "")
                    finalized["source_file"] = job.get("source_file", "")
                    finalized["result"] = self._build_legacy_result(job_id, finalized)
                    finalized["error"] = None
                    finalized.update(timestamps)
                    self._jobs[job_id] = finalized
                    self._persist_final(job_id)
                    return

                # Store phase 1 results for later use in phase 2
                self._phase1_store[job_id] = {
                    "parsed": parsed,
                    "parser": parser_inst,
                    "work_dir": work_dir,
                    "job_obj": translation_job,
                }
                # Store live Glossary object for mutation via API
                if translation_job.glossary:
                    self._glossaries[job_id] = translation_job.glossary

                # Serialize job dict for API (status = awaiting_glossary_review)
                finalized = translation_job.model_dump(mode="json")
                finalized["job_id"] = job_id
                finalized["filename"] = job.get("filename", "")
                finalized["source_file"] = job.get("source_file", "")
                finalized["use_glossary"] = True
                finalized["result"] = self._build_legacy_result(job_id, finalized)
                finalized["error"] = None
                self._jobs[job_id] = finalized

            else:
                # Direct translation (no glossary review step)
                translation_job = await orchestrator.run_multi(
                    source_file=str(source_path),
                    target_languages=targets,
                    output_dir=str(work_dir),
                    quiet=True,
                    progress_callback=on_progress,
                    use_glossary=False,
                )

                finalized = translation_job.model_dump(mode="json")
                finalized["job_id"] = job_id
                finalized["filename"] = job.get("filename", "")
                finalized["source_file"] = job.get("source_file", "")
                self._attach_downloads(job_id, finalized)
                finalized["result"] = self._build_legacy_result(job_id, finalized)
                finalized["error"] = finalized.get("error_message") or None
                finalized.update(timestamps)
                self._jobs[job_id] = finalized
                self._persist_final(job_id)

                # Outputs already uploaded to storage; the local work dir is
                # purely scratch and can be cleaned up either way.
                shutil.rmtree(work_dir, ignore_errors=True)

        except Exception as exc:
            logger.exception("Job %s failed: %s", job_id, exc)
            shutil.rmtree(work_dir, ignore_errors=True)
            job.update({"status": S.ERROR, "stage": S.ERROR, "detail": str(exc), "error": str(exc)})
            job.update(timestamps)
            self._persist_final(job_id)

    async def _execute_phase2(self, item: dict, job: dict) -> None:
        from src.orchestrator.agent import Orchestrator

        job_id: str = item["job_id"]
        work_dir: Path = item["work_dir"]

        # Preserve timestamps
        timestamps = {
            "created_at": job.get("created_at"),
            "started_at": job.get("started_at"),
            "completed_at": job.get("completed_at"),
        }

        phase1_data = self._phase1_store.pop(job_id, None)
        if not phase1_data:
            job.update({"status": S.ERROR, "stage": S.ERROR, "detail": "Phase 1 data missing", "error": "Phase 1 data missing"})
            job.update(timestamps)
            self._persist_final(job_id)
            return

        translation_job = phase1_data["job_obj"]
        parsed = phase1_data["parsed"]
        parser_inst = phase1_data["parser"]

        # Apply the confirmed glossary (which may have been updated via API calls)
        if job_id in self._glossaries:
            translation_job.glossary = self._glossaries[job_id]

        job.update({"status": S.TRANSLATING, "stage": S.TRANSLATING, "detail": "译员已确认术语，开始翻译..."})

        def on_progress(snapshot) -> None:
            payload = snapshot.model_dump(mode="json")
            payload["job_id"] = job_id
            payload["filename"] = job.get("filename", payload.get("filename", ""))
            payload["source_file"] = job.get("source_file", payload.get("source_file", ""))
            payload["result"] = self._build_legacy_result(job_id, payload)
            payload["error"] = payload.get("error_message") or None
            payload.update(timestamps)
            self._jobs[job_id] = payload

        try:
            orchestrator = Orchestrator()
            completed_job = await orchestrator.run_phase2(
                job=translation_job,
                parsed=parsed,
                parser=parser_inst,
                output_dir=str(work_dir),
                quiet=True,
                progress_callback=on_progress,
            )

            finalized = completed_job.model_dump(mode="json")
            finalized["job_id"] = job_id
            finalized["filename"] = job.get("filename", finalized.get("filename", ""))
            finalized["source_file"] = job.get("source_file", finalized.get("source_file", ""))
            self._attach_downloads(job_id, finalized)
            finalized["result"] = self._build_legacy_result(job_id, finalized)
            finalized["error"] = finalized.get("error_message") or None
            finalized.update(timestamps)
            self._jobs[job_id] = finalized
            self._persist_final(job_id)

            succeeded = [run for run in finalized["language_runs"] if run["status"] == S.DONE]
            if not succeeded and finalized["status"] == S.ERROR:
                shutil.rmtree(work_dir, ignore_errors=True)
            else:
                self._outputs[f"_dir_{job_id}"] = work_dir

        except Exception as exc:
            logger.exception("Phase 2 for job %s failed: %s", job_id, exc)
            shutil.rmtree(work_dir, ignore_errors=True)
            job.update({"status": S.ERROR, "stage": S.ERROR, "detail": str(exc), "error": str(exc)})
            job.update(timestamps)
            self._persist_final(job_id)

        finally:
            self._glossaries.pop(job_id, None)

    def _attach_downloads(self, job_id: str, payload: dict) -> None:
        """Upload finalized translation outputs to storage and record their keys."""
        for run in payload.get("language_runs", []):
            output_file = run.get("output_file")
            if run.get("status") != S.DONE or not output_file:
                continue
            path = Path(output_file)
            if not path.exists():
                continue
            filename = path.name
            storage_key = f"jobs/{job_id}/output/{filename}"
            try:
                self.storage.upload_file(storage_key, path)
            except Exception as exc:  # noqa: BLE001
                logger.exception("Failed to upload %s: %s", storage_key, exc)
                continue
            run["download_url"] = f"/api/download/{job_id}/{filename}"
            self._outputs[f"{job_id}/{filename}"] = storage_key

            draft_file = run.get("draft_output_file")
            if draft_file:
                draft_path = Path(draft_file)
                if draft_path.exists():
                    draft_filename = draft_path.name
                    draft_key = f"jobs/{job_id}/output/{draft_filename}"
                    try:
                        self.storage.upload_file(draft_key, draft_path)
                    except Exception as exc:  # noqa: BLE001
                        logger.exception("Failed to upload draft %s: %s", draft_key, exc)
                        continue
                    run["draft_download_url"] = f"/api/download/{job_id}/{draft_filename}"
                    self._outputs[f"{job_id}/{draft_filename}"] = draft_key

    def _build_legacy_result(self, job_id: str, payload: dict) -> dict:
        outputs: list[dict] = []
        for run in payload.get("language_runs", []):
            if run.get("status") != S.DONE or not run.get("output_file"):
                continue
            filename = Path(run["output_file"]).name
            outputs.append(
                {
                    "language": run.get("target_language", ""),
                    "filename": filename,
                    "url": run.get("download_url") or f"/api/download/{job_id}/{filename}",
                }
            )

        glossary_rows = (payload.get("glossary_exports") or {}).get("rows") or []
        return {"outputs": outputs, "glossary": glossary_rows[:20]}
