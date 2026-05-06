"""Orchestrator: drives the streamlined translation pipeline.

parse -> terminology -> translate -> rebuild
"""

from __future__ import annotations

import asyncio
import copy
import logging
import time
import uuid
from pathlib import Path
from typing import Callable, Literal

from rich.console import Console
import yaml

from src.models.glossary import Glossary
from src.models.task import TaskStatus, TranslationJob, TranslationTask
from src.terminology.glossary import GlossaryManager
from src.parser import get_parser
from src.terminology.agent import TerminologyAgent
from src.translator.agent import TranslatorAgent
from src.utils.file_utils import ensure_output_path, validate_file
from src.utils.glossary_export import build_glossary_exports
from src.utils.language_detect import detect_language, get_language_name

logger = logging.getLogger(__name__)
console = Console()

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
from src.utils.paths import get_config_dir

_SETTINGS_PATH = get_config_dir() / "settings.yaml"

ProgressCallback = Callable[[TranslationJob], None]


def _load_translation_settings() -> dict:
    try:
        with open(_SETTINGS_PATH, encoding="utf-8") as f:
            settings = yaml.safe_load(f) or {}
        return settings.get("translation", {})
    except Exception:
        return {}


class Orchestrator:
    """End-to-end translation orchestration."""

    def __init__(self) -> None:
        self._terminology_agent = TerminologyAgent()
        self._translator_agent = TranslatorAgent()
        self._translation_settings = _load_translation_settings()

    async def run(
        self,
        source_file: str,
        target_language: str,
        output_file: str | None = None,
    ) -> TranslationTask:
        job = await self._run_job(
            source_file=source_file,
            target_languages=[target_language],
            output_dir=str(Path(output_file).parent) if output_file else None,
            output_overrides={target_language: output_file} if output_file else None,
            quiet=False,
            progress_callback=None,
        )
        if not job.language_runs:
            return TranslationTask(
                task_id=uuid.uuid4().hex[:12],
                source_file=source_file,
                target_language=target_language,
                status=job.status,
                error_message=job.error_message,
                detail=job.detail,
                progress=job.detail,
            )
        run = job.language_runs[0]
        run.glossary = job.glossary
        return run

    async def run_multi(
        self,
        source_file: str,
        target_languages: list[str],
        output_dir: str | None = None,
        quiet: bool = False,
        progress_callback: ProgressCallback | None = None,
        use_glossary: bool = True,
    ) -> TranslationJob:
        return await self._run_job(
            source_file=source_file,
            target_languages=target_languages,
            output_dir=output_dir,
            output_overrides=None,
            quiet=quiet,
            progress_callback=progress_callback,
            use_glossary=use_glossary,
        )

    async def run_phase1(
        self,
        source_file: str,
        target_languages: list[str],
        output_dir: str | None = None,
        quiet: bool = True,
        progress_callback: ProgressCallback | None = None,
        library_domain_ids: list[int] | None = None,
    ) -> tuple[TranslationJob, object | None, object | None]:
        """Phase 1: parse file and extract terminology candidates.

        Returns (job, parsed_file, parser_instance).
        Job status is set to AWAITING_GLOSSARY_REVIEW on success.
        On error, job status is ERROR and parsed/parser are None.
        """
        job = TranslationJob(
            job_id=uuid.uuid4().hex[:12],
            filename=Path(source_file).name,
            source_file=source_file,
            use_glossary=True,
            language_runs=[
                TranslationTask(
                    task_id=uuid.uuid4().hex[:12],
                    source_file=source_file,
                    target_language=target_language,
                    status=TaskStatus.QUEUED,
                    stage=TaskStatus.QUEUED.value,
                    detail="等待中...",
                    progress="等待中...",
                )
                for target_language in target_languages
            ],
            units_total=len(target_languages),
        )

        try:
            validate_file(source_file, SUPPORTED_EXTENSIONS)
            self._update_job(
                job,
                TaskStatus.PARSING,
                "解析文件中...",
                percent=5,
                units_done=0,
                units_total=len(target_languages),
                unit_label="language",
                progress_callback=progress_callback,
            )
            if not quiet:
                self._log_step("解析文件", source_file)

            parser = get_parser(source_file)
            parsed = parser.parse(source_file)
            src_lang = parsed.meta.detected_language or detect_language(parsed.plain_text)
            parsed.meta.detected_language = src_lang
            job.source_language = src_lang

            if not quiet:
                console.print(
                    f"  文件类型: [cyan]{parsed.meta.file_type}[/cyan]  "
                    f"字数: [cyan]{parsed.meta.word_count}[/cyan]  "
                    f"检测语言: [cyan]{get_language_name(src_lang)}[/cyan]"
                )

            for run in job.language_runs:
                run.source_language = src_lang

            if not parsed.translatable_blocks:
                message = "文件中没有可翻译的文本内容。"
                if not quiet:
                    console.print(f"[yellow]{message}[/yellow]")
                for run in job.language_runs:
                    run.set_status(TaskStatus.DONE, message, percent=100, units_done=0, units_total=0)
                self._update_job(
                    job,
                    TaskStatus.DONE,
                    message,
                    percent=100,
                    units_done=len(target_languages),
                    units_total=len(target_languages),
                    unit_label="language",
                    progress_callback=progress_callback,
                )
                return job, None, None

            self._update_job(
                job,
                TaskStatus.TERMINOLOGY,
                "提取共享术语中...",
                percent=15,
                units_done=0,
                units_total=len(target_languages),
                unit_label="language",
                progress_callback=progress_callback,
            )
            if not quiet:
                self._log_step("术语提取", f"共享术语 ({len(target_languages)} 种语言)")

            glossary = await self._terminology_agent.run(
                text=parsed.plain_text,
                source_language=src_lang,
                target_languages=target_languages,
                source_file=Path(source_file).name,
                library_domain_ids=library_domain_ids,
            )
            job.glossary = glossary
            job.glossary_exports = build_glossary_exports(glossary)

            lib_count = sum(1 for t in glossary.terms if t.library_term_id is not None)
            new_count = sum(1 for t in glossary.terms if t.library_term_id is None)
            detail_parts = [f"{len(glossary.terms)} 个候选术语"]
            if lib_count:
                detail_parts.append(f"{lib_count} 个来自术语库")
            self._update_job(
                job,
                TaskStatus.AWAITING_GLOSSARY_REVIEW,
                f"术语表待译员确认（{'，'.join(detail_parts)}）",
                percent=20,
                units_done=0,
                units_total=len(target_languages),
                unit_label="language",
                progress_callback=progress_callback,
            )
            return job, parsed, parser

        except Exception as exc:
            job.error_message = str(exc)
            self._update_job(
                job,
                TaskStatus.ERROR,
                str(exc),
                percent=100,
                current_range="",
                progress_callback=progress_callback,
            )
            logger.exception("Phase 1 failed: %s", exc)
            if not quiet:
                console.print(f"\n[bold red]❌ 术语提取失败: {exc}[/bold red]\n")
            return job, None, None

    async def run_phase2(
        self,
        job: TranslationJob,
        parsed: object,
        parser: object,
        output_dir: str | None = None,
        quiet: bool = True,
        progress_callback: ProgressCallback | None = None,
    ) -> TranslationJob:
        """Phase 2: translate using confirmed terms from job.glossary.

        Updates job in place and returns it.
        """
        try:
            source_file = job.source_file
            src_lang = job.source_language
            target_languages = [run.target_language for run in job.language_runs]
            glossary = job.glossary or Glossary(
                source_language=src_lang, target_languages=target_languages
            )

            # Rebuild glossary_exports from the user-confirmed/edited glossary
            job.glossary_exports = build_glossary_exports(glossary)

            for run in job.language_runs:
                output_path = self._resolve_output_path(
                    source_file=source_file,
                    target_language=run.target_language,
                    output_dir=output_dir,
                    output_override=None,
                )
                run.output_file = output_path
                self._set_run_status(
                    run,
                    TaskStatus.PENDING,
                    "等待并行翻译资源...",
                    stage=TaskStatus.PENDING.value,
                    percent=0,
                    current_range="",
                )

            language_limit = self._resolve_language_concurrency(len(job.language_runs))
            self._refresh_job_from_runs(job, progress_callback)
            if not quiet:
                self._log_step(
                    "翻译",
                    f"{src_lang} → {', '.join(run.target_language for run in job.language_runs)} "
                    f"(并发 {language_limit})",
                )

            semaphore = asyncio.Semaphore(language_limit)

            async def _translate_language(index: int, run: TranslationTask) -> None:
                async with semaphore:
                    output_path = run.output_file
                    self._set_run_status(
                        run,
                        TaskStatus.TRANSLATING,
                        f"翻译准备中 ({index}/{len(job.language_runs)})",
                        percent=self._estimate_run_percent(0, 1),
                    )
                    self._refresh_job_from_runs(job, progress_callback)

                    parsed_copy = copy.deepcopy(parsed)

                    def _on_translate_progress(progress: dict) -> None:
                        status_key = progress.get("status")
                        if status_key == "review_complete":
                            run.review_changes = progress.get("review_changes", [])
                            self._refresh_job_from_runs(job, progress_callback)
                            return
                        segments_done = int(progress.get("segments_done", 0))
                        segments_total = max(1, int(progress.get("segments_total", 0)))
                        units_done = int(progress.get("units_done", 0))
                        units_total = int(progress.get("units_total", 0))
                        unit_label = str(progress.get("unit_label", "segment"))
                        current_range = str(progress.get("current_range", ""))
                        if status_key == "reviewing":
                            task_status = TaskStatus.REVIEWING
                            detail = f"审校中 ({segments_done}/{segments_total} 段)"
                            pct = self._estimate_run_percent(segments_done, segments_total, phase="reviewing")
                        else:
                            task_status = TaskStatus.TRANSLATING
                            detail = f"翻译中 ({segments_done}/{segments_total} 段)"
                            pct = self._estimate_run_percent(segments_done, segments_total, phase="translating")
                        self._set_run_status(
                            run,
                            task_status,
                            detail,
                            percent=pct,
                            segments_done=segments_done,
                            segments_total=segments_total,
                            units_done=units_done,
                            units_total=units_total,
                            unit_label=unit_label,
                            current_range=current_range,
                        )
                        self._refresh_job_from_runs(job, progress_callback)

                    try:
                        translated = await self._translator_agent.translate(
                            parsed_file=parsed_copy,
                            glossary=glossary,
                            target_language=run.target_language,
                            source_language=src_lang,
                            progress_callback=_on_translate_progress,
                        )
                        self._set_run_status(run, TaskStatus.REBUILDING, "重建文件中...", percent=95)
                        self._refresh_job_from_runs(job, progress_callback)
                        if not quiet:
                            self._log_step("重建文件", output_path)
                        run.output_file = parser.rebuild(translated, output_path)
                        if any(b.reviewed_text for b in translated.blocks):
                            _p = Path(output_path)
                            draft_path = str(_p.parent / f"{_p.stem}_draft{_p.suffix}")
                            draft_copy = copy.deepcopy(translated)
                            for b in draft_copy.blocks:
                                b.reviewed_text = ""
                            run.draft_output_file = parser.rebuild(draft_copy, draft_path)
                        self._set_run_status(
                            run,
                            TaskStatus.DONE,
                            "完成",
                            percent=100,
                            segments_done=max(run.segments_done, run.segments_total),
                            units_done=max(run.units_done, run.units_total),
                            current_range="",
                        )
                    except Exception as exc:
                        run.error_message = str(exc)
                        self._set_run_status(
                            run,
                            TaskStatus.ERROR,
                            str(exc),
                            stage=TaskStatus.ERROR.value,
                            percent=100,
                            current_range="",
                        )
                        logger.exception("Translation failed for %s: %s", run.target_language, exc)
                        if not quiet:
                            console.print(f"[bold red]❌ {run.target_language} 翻译失败: {exc}[/bold red]")
                    finally:
                        self._refresh_job_from_runs(job, progress_callback)

            await asyncio.gather(
                *[_translate_language(i, run) for i, run in enumerate(job.language_runs, start=1)]
            )

            succeeded = [run for run in job.language_runs if run.status == TaskStatus.DONE]
            failed = [run for run in job.language_runs if run.status == TaskStatus.ERROR]

            if succeeded and not failed:
                self._update_job(
                    job, TaskStatus.DONE, "翻译完成",
                    percent=100, units_done=len(job.language_runs),
                    units_total=len(job.language_runs), unit_label="language",
                    current_range="", progress_callback=progress_callback,
                )
            elif succeeded:
                detail = (
                    f"部分完成：成功 {', '.join(run.target_language for run in succeeded)}；"
                    f"失败 {', '.join(run.target_language for run in failed)}"
                )
                self._update_job(
                    job, TaskStatus.DONE, detail,
                    percent=100, units_done=len(succeeded),
                    units_total=len(job.language_runs), unit_label="language",
                    current_range="", progress_callback=progress_callback,
                )
            else:
                detail = "; ".join(
                    f"{run.target_language}: {run.error_message or run.detail}" for run in failed
                ) or "翻译失败"
                job.error_message = detail
                self._update_job(
                    job, TaskStatus.ERROR, detail,
                    percent=100, units_done=0, units_total=len(job.language_runs),
                    unit_label="language", current_range="", progress_callback=progress_callback,
                )

            if not quiet and succeeded:
                console.print(
                    f"\n[bold green]✅ 完成 {len(succeeded)}/{len(job.language_runs)} 种语言翻译[/bold green]\n"
                )
            return job

        except Exception as exc:
            job.error_message = str(exc)
            self._update_job(
                job, TaskStatus.ERROR, str(exc),
                percent=100, current_range="", progress_callback=progress_callback,
            )
            logger.exception("Phase 2 failed: %s", exc)
            if not quiet:
                console.print(f"\n[bold red]❌ 翻译失败: {exc}[/bold red]\n")
            return job

    async def _run_job(
        self,
        *,
        source_file: str,
        target_languages: list[str],
        output_dir: str | None,
        output_overrides: dict[str, str | None] | None,
        quiet: bool,
        progress_callback: ProgressCallback | None,
        use_glossary: bool = True,
    ) -> TranslationJob:
        job = TranslationJob(
            job_id=uuid.uuid4().hex[:12],
            filename=Path(source_file).name,
            source_file=source_file,
            language_runs=[
                TranslationTask(
                    task_id=uuid.uuid4().hex[:12],
                    source_file=source_file,
                    target_language=target_language,
                    status=TaskStatus.QUEUED,
                    stage=TaskStatus.QUEUED.value,
                    detail="等待中...",
                    progress="等待中...",
                )
                for target_language in target_languages
            ],
            units_total=len(target_languages),
        )

        try:
            validate_file(source_file, SUPPORTED_EXTENSIONS)
            self._update_job(
                job,
                TaskStatus.PARSING,
                "解析文件中...",
                percent=5,
                units_done=0,
                units_total=len(target_languages),
                unit_label="language",
                progress_callback=progress_callback,
            )
            if not quiet:
                self._log_step("解析文件", source_file)

            parser = get_parser(source_file)
            parsed = parser.parse(source_file)
            src_lang = parsed.meta.detected_language or detect_language(parsed.plain_text)
            parsed.meta.detected_language = src_lang
            job.source_language = src_lang

            if not quiet:
                console.print(
                    f"  文件类型: [cyan]{parsed.meta.file_type}[/cyan]  "
                    f"字数: [cyan]{parsed.meta.word_count}[/cyan]  "
                    f"检测语言: [cyan]{get_language_name(src_lang)}[/cyan]"
                )

            for run in job.language_runs:
                run.source_language = src_lang

            if not parsed.translatable_blocks:
                message = "文件中没有可翻译的文本内容。"
                if not quiet:
                    console.print(f"[yellow]{message}[/yellow]")
                for run in job.language_runs:
                    run.set_status(
                        TaskStatus.DONE,
                        message,
                        percent=100,
                        units_done=0,
                        units_total=0,
                    )
                self._update_job(
                    job,
                    TaskStatus.DONE,
                    message,
                    percent=100,
                    units_done=len(target_languages),
                    units_total=len(target_languages),
                    unit_label="language",
                    progress_callback=progress_callback,
                )
                return job

            if use_glossary:
                self._update_job(
                    job,
                    TaskStatus.TERMINOLOGY,
                    "提取共享术语中...",
                    percent=15,
                    units_done=0,
                    units_total=len(target_languages),
                    unit_label="language",
                    progress_callback=progress_callback,
                )
                if not quiet:
                    self._log_step("术语提取", f"共享术语 ({len(target_languages)} 种语言)")

                glossary = await self._terminology_agent.run(
                    text=parsed.plain_text,
                    source_language=src_lang,
                    target_languages=target_languages,
                    source_file=Path(source_file).name,
                )
                # Auto-confirm all terms for direct (non-phase-split) mode
                GlossaryManager.confirm_all(glossary)
            else:
                if not quiet:
                    self._log_step("跳过术语提取", "直接翻译模式")
                glossary = Glossary(source_language=src_lang, target_languages=target_languages)

            job.glossary = glossary
            job.glossary_exports = build_glossary_exports(glossary)
            for run in job.language_runs:
                output_path = self._resolve_output_path(
                    source_file=source_file,
                    target_language=run.target_language,
                    output_dir=output_dir,
                    output_override=(output_overrides or {}).get(run.target_language),
                )
                run.output_file = output_path
                self._set_run_status(
                    run,
                    TaskStatus.PENDING,
                    "等待并行翻译资源...",
                    stage=TaskStatus.PENDING.value,
                    percent=0,
                    current_range="",
                )

            language_limit = self._resolve_language_concurrency(len(job.language_runs))
            self._refresh_job_from_runs(job, progress_callback)
            if not quiet:
                self._log_step(
                    "翻译",
                    f"{src_lang} → {', '.join(run.target_language for run in job.language_runs)} "
                    f"(并发 {language_limit})",
                )

            semaphore = asyncio.Semaphore(language_limit)

            async def _translate_language(index: int, run: TranslationTask) -> None:
                async with semaphore:
                    output_path = run.output_file
                    self._set_run_status(
                        run,
                        TaskStatus.TRANSLATING,
                        f"翻译准备中 ({index}/{len(job.language_runs)})",
                        percent=self._estimate_run_percent(0, 1),
                    )
                    self._refresh_job_from_runs(job, progress_callback)

                    parsed_copy = copy.deepcopy(parsed)

                    def _on_translate_progress(progress: dict[str, int | str]) -> None:
                        status_key = progress.get("status")
                        if status_key == "review_complete":
                            run.review_changes = progress.get("review_changes", [])
                            self._refresh_job_from_runs(job, progress_callback)
                            return
                        segments_done = int(progress.get("segments_done", 0))
                        segments_total = max(1, int(progress.get("segments_total", 0)))
                        units_done = int(progress.get("units_done", 0))
                        units_total = int(progress.get("units_total", 0))
                        unit_label = str(progress.get("unit_label", "segment"))
                        current_range = str(progress.get("current_range", ""))
                        if status_key == "reviewing":
                            task_status = TaskStatus.REVIEWING
                            detail = f"审校中 ({segments_done}/{segments_total} 段)"
                            pct = self._estimate_run_percent(segments_done, segments_total, phase="reviewing")
                        else:
                            task_status = TaskStatus.TRANSLATING
                            detail = f"翻译中 ({segments_done}/{segments_total} 段)"
                            pct = self._estimate_run_percent(segments_done, segments_total, phase="translating")
                        self._set_run_status(
                            run,
                            task_status,
                            detail,
                            percent=pct,
                            segments_done=segments_done,
                            segments_total=segments_total,
                            units_done=units_done,
                            units_total=units_total,
                            unit_label=unit_label,
                            current_range=current_range,
                        )
                        self._refresh_job_from_runs(job, progress_callback)

                    try:
                        translated = await self._translator_agent.translate(
                            parsed_file=parsed_copy,
                            glossary=glossary,
                            target_language=run.target_language,
                            source_language=src_lang,
                            progress_callback=_on_translate_progress,
                        )

                        self._set_run_status(
                            run,
                            TaskStatus.REBUILDING,
                            "重建文件中...",
                            percent=95,
                        )
                        self._refresh_job_from_runs(job, progress_callback)
                        if not quiet:
                            self._log_step("重建文件", output_path)

                        run.output_file = parser.rebuild(translated, output_path)
                        if any(b.reviewed_text for b in translated.blocks):
                            _p = Path(output_path)
                            draft_path = str(_p.parent / f"{_p.stem}_draft{_p.suffix}")
                            draft_copy = copy.deepcopy(translated)
                            for b in draft_copy.blocks:
                                b.reviewed_text = ""
                            run.draft_output_file = parser.rebuild(draft_copy, draft_path)
                        self._set_run_status(
                            run,
                            TaskStatus.DONE,
                            "完成",
                            percent=100,
                            segments_done=max(run.segments_done, run.segments_total),
                            units_done=max(run.units_done, run.units_total),
                            current_range="",
                        )
                    except Exception as exc:
                        run.error_message = str(exc)
                        self._set_run_status(
                            run,
                            TaskStatus.ERROR,
                            str(exc),
                            stage=TaskStatus.ERROR.value,
                            percent=100,
                            current_range="",
                        )
                        logger.exception(
                            "Translation failed for %s: %s",
                            run.target_language,
                            exc,
                        )
                        if not quiet:
                            console.print(
                                f"[bold red]❌ {run.target_language} 翻译失败: {exc}[/bold red]"
                            )
                    finally:
                        self._refresh_job_from_runs(job, progress_callback)

            await asyncio.gather(
                *[
                    _translate_language(index, run)
                    for index, run in enumerate(job.language_runs, start=1)
                ]
            )

            succeeded = [run for run in job.language_runs if run.status == TaskStatus.DONE]
            failed = [run for run in job.language_runs if run.status == TaskStatus.ERROR]

            if succeeded and not failed:
                self._update_job(
                    job,
                    TaskStatus.DONE,
                    "翻译完成",
                    percent=100,
                    units_done=len(job.language_runs),
                    units_total=len(job.language_runs),
                    unit_label="language",
                    current_range="",
                    progress_callback=progress_callback,
                )
            elif succeeded:
                detail = (
                    f"部分完成：成功 {', '.join(run.target_language for run in succeeded)}；"
                    f"失败 {', '.join(run.target_language for run in failed)}"
                )
                self._update_job(
                    job,
                    TaskStatus.DONE,
                    detail,
                    percent=100,
                    units_done=len(succeeded),
                    units_total=len(job.language_runs),
                    unit_label="language",
                    current_range="",
                    progress_callback=progress_callback,
                )
            else:
                detail = "; ".join(
                    f"{run.target_language}: {run.error_message or run.detail}"
                    for run in failed
                ) or "翻译失败"
                job.error_message = detail
                self._update_job(
                    job,
                    TaskStatus.ERROR,
                    detail,
                    percent=100,
                    units_done=0,
                    units_total=len(job.language_runs),
                    unit_label="language",
                    current_range="",
                    progress_callback=progress_callback,
                )

            if not quiet and succeeded:
                console.print(
                    f"\n[bold green]✅ 完成 {len(succeeded)}/{len(job.language_runs)} 种语言翻译[/bold green]\n"
                )
            return job

        except Exception as exc:
            job.error_message = str(exc)
            self._update_job(
                job,
                TaskStatus.ERROR,
                str(exc),
                percent=100,
                current_range="",
                progress_callback=progress_callback,
            )
            logger.exception("Translation failed: %s", exc)
            if not quiet:
                console.print(f"\n[bold red]❌ 翻译失败: {exc}[/bold red]\n")
            return job

    @staticmethod
    def _resolve_output_path(
        *,
        source_file: str,
        target_language: str,
        output_dir: str | None,
        output_override: str | None,
    ) -> str:
        if output_override:
            return output_override
        if not output_dir:
            return ensure_output_path(source_file, target_language)
        source_path = Path(source_file)
        return str(Path(output_dir) / f"{source_path.stem}_{target_language}{source_path.suffix}")

    @staticmethod
    def _estimate_run_percent(segments_done: int, segments_total: int, *, phase: Literal["translating", "reviewing"] = "translating") -> int:
        if segments_total <= 0:
            return 0 if phase == "translating" else 50
        ratio = segments_done / segments_total
        if phase == "reviewing":
            return min(99, 50 + int(ratio * 50))
        return min(50, int(ratio * 50))

    @staticmethod
    def _estimate_job_percent(
        *,
        completed_languages: int,
        total_languages: int,
        segments_done: int,
        segments_total: int,
    ) -> int:
        if total_languages <= 0:
            return 100
        base = 15
        share = 80 / total_languages
        active_ratio = 0 if segments_total <= 0 else min(1.0, segments_done / segments_total)
        return min(99, int(base + completed_languages * share + active_ratio * share))

    def _resolve_language_concurrency(self, total_languages: int) -> int:
        configured = int(
            self._translation_settings.get(
                "max_concurrent_languages_per_job",
                self._translation_settings.get("max_concurrent_requests", 3),
            )
        )
        return max(1, min(total_languages, configured))

    def _refresh_job_from_runs(
        self,
        job: TranslationJob,
        progress_callback: ProgressCallback | None = None,
    ) -> None:
        if not job.language_runs:
            return

        active_runs = [
            run
            for run in job.language_runs
            if run.status
            in {
                TaskStatus.PENDING,
                TaskStatus.QUEUED,
                TaskStatus.TRANSLATING,
                TaskStatus.REVIEWING,
                TaskStatus.REBUILDING,
            }
        ]
        done_count = sum(1 for run in job.language_runs if run.status == TaskStatus.DONE)
        terminal_count = sum(
            1
            for run in job.language_runs
            if run.status in {TaskStatus.DONE, TaskStatus.ERROR, TaskStatus.CANCELLED}
        )
        segments_done = sum(run.segments_done for run in job.language_runs)
        segments_total = sum(run.segments_total for run in job.language_runs)
        average_progress = sum(
            self._terminal_aware_run_percent(run) for run in job.language_runs
        ) / max(1, len(job.language_runs))
        percent = min(99, 15 + int(average_progress * 0.84))

        if any(run.status == TaskStatus.REBUILDING for run in active_runs):
            status = TaskStatus.REBUILDING
        elif any(run.status == TaskStatus.REVIEWING for run in active_runs):
            status = TaskStatus.REVIEWING
        elif active_runs:
            status = TaskStatus.TRANSLATING
        elif terminal_count == len(job.language_runs):
            status = TaskStatus.DONE
        else:
            status = TaskStatus.TRANSLATING

        detail = self._build_parallel_job_detail(job, active_runs, done_count)
        current_range = ", ".join(run.target_language for run in active_runs[:3])
        if len(active_runs) > 3:
            current_range = f"{current_range} +{len(active_runs) - 3}"

        self._update_job(
            job,
            status,
            detail,
            percent=percent,
            segments_done=segments_done,
            segments_total=segments_total,
            units_done=done_count,
            units_total=len(job.language_runs),
            unit_label="language",
            current_range=current_range,
            progress_callback=progress_callback,
        )

    @staticmethod
    def _terminal_aware_run_percent(run: TranslationTask) -> int:
        if run.status in {TaskStatus.DONE, TaskStatus.ERROR, TaskStatus.CANCELLED}:
            return 100
        return max(0, run.percent)

    @staticmethod
    def _build_parallel_job_detail(
        job: TranslationJob,
        active_runs: list[TranslationTask],
        done_count: int,
    ) -> str:
        total = len(job.language_runs)
        if active_runs:
            active_targets = ", ".join(run.target_language for run in active_runs[:3])
            if len(active_runs) > 3:
                active_targets = f"{active_targets} +{len(active_runs) - 3}"
            return f"并行翻译中：{active_targets}（已完成 {done_count}/{total}）"
        return f"已完成 {done_count}/{total} 种语言"

    @staticmethod
    def _set_run_status(
        run: TranslationTask,
        status: TaskStatus,
        detail: str,
        *,
        stage: str | None = None,
        percent: int | None = None,
        segments_done: int | None = None,
        segments_total: int | None = None,
        units_done: int | None = None,
        units_total: int | None = None,
        unit_label: str | None = None,
        current_range: str | None = None,
    ) -> None:
        prev_status = run.status
        run.set_status(
            status,
            detail,
            stage=stage,
            percent=percent,
            segments_done=segments_done,
            segments_total=segments_total,
            units_done=units_done,
            units_total=units_total,
            unit_label=unit_label,
            current_range=current_range,
        )
        Orchestrator._update_timing(run, prev_status)

    @staticmethod
    def _update_timing(run: TranslationTask, prev_status: TaskStatus) -> None:
        """Maintain stage_started_at / elapsed_seconds / seconds_per_segment / eta_seconds."""
        terminal = (TaskStatus.DONE, TaskStatus.ERROR, TaskStatus.CANCELLED)
        if run.status in terminal:
            run.eta_seconds = 0.0 if run.status == TaskStatus.DONE else None
            if run.stage_started_at is not None:
                run.elapsed_seconds = max(0.0, time.time() - run.stage_started_at)
            return

        # Reset clock on stage transition
        if run.status != prev_status or run.stage_started_at is None:
            run.stage_started_at = time.time()
            run.elapsed_seconds = 0.0
            run.seconds_per_segment = None
            run.eta_seconds = None
            return

        elapsed = time.time() - (run.stage_started_at or time.time())
        run.elapsed_seconds = max(0.0, elapsed)

        # Only timed stages with segment progress give a usable ETA
        timed_stages = (TaskStatus.TRANSLATING, TaskStatus.REVIEWING)
        if run.status not in timed_stages:
            run.seconds_per_segment = None
            run.eta_seconds = None
            return

        done = max(0, run.segments_done)
        total = max(0, run.segments_total)
        if done <= 0 or total <= 0:
            run.seconds_per_segment = None
            run.eta_seconds = None
            return

        spp = elapsed / done
        run.seconds_per_segment = spp
        remaining = max(0, total - done)
        run.eta_seconds = max(0.0, remaining * spp)

    @staticmethod
    def _update_job(
        job: TranslationJob,
        status: TaskStatus,
        detail: str,
        *,
        percent: int | None = None,
        segments_done: int | None = None,
        segments_total: int | None = None,
        units_done: int | None = None,
        units_total: int | None = None,
        unit_label: str | None = None,
        current_range: str | None = None,
        progress_callback: ProgressCallback | None = None,
    ) -> None:
        job.set_status(
            status,
            detail,
            percent=percent,
            segments_done=segments_done,
            segments_total=segments_total,
            units_done=units_done,
            units_total=units_total,
            unit_label=unit_label,
            current_range=current_range,
        )
        if progress_callback:
            progress_callback(job.model_copy(deep=True))

    @staticmethod
    def _log_step(step: str, detail: str = "") -> None:
        msg = f"[bold]▶ {step}[/bold]"
        if detail:
            msg += f"  [dim]{detail}[/dim]"
        console.print(msg)
