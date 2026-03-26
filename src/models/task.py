from __future__ import annotations

from enum import Enum
from typing import Any, Optional

from pydantic import BaseModel, Field

from .glossary import Glossary


class TaskStatus(str, Enum):
    QUEUED = "queued"
    PENDING = "pending"
    PARSING = "parsing"
    TERMINOLOGY = "terminology"
    AWAITING_GLOSSARY_REVIEW = "awaiting_glossary_review"
    TRANSLATING = "translating"
    REVIEWING = "reviewing"
    REBUILDING = "rebuilding"
    DONE = "done"
    ERROR = "error"
    CANCELLED = "cancelled"


class TranslationTask(BaseModel):
    task_id: str = ""
    source_file: str = ""
    output_file: str = ""
    download_url: str = ""
    source_language: str = ""
    target_language: str = ""
    status: TaskStatus = TaskStatus.PENDING
    glossary: Optional[Glossary] = None
    error_message: str = ""
    stage: str = "pending"
    detail: str = ""
    percent: int = 0
    segments_done: int = 0
    segments_total: int = 0
    units_done: int = 0
    units_total: int = 0
    unit_label: str = ""
    current_range: str = ""
    review_changes: list[dict] = Field(default_factory=list)
    draft_output_file: str = ""
    draft_download_url: str = ""

    def set_status(
        self,
        status: TaskStatus,
        detail: str = "",
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
        self.status = status
        self.stage = stage or status.value
        if detail:
            self.detail = detail
        if percent is not None:
            self.percent = percent
        if segments_done is not None:
            self.segments_done = segments_done
        if segments_total is not None:
            self.segments_total = segments_total
        if units_done is not None:
            self.units_done = units_done
        if units_total is not None:
            self.units_total = units_total
        if unit_label is not None:
            self.unit_label = unit_label
        if current_range is not None:
            self.current_range = current_range


class TranslationJob(BaseModel):
    job_id: str = ""
    filename: str = ""
    source_file: str = ""
    source_language: str = ""
    use_glossary: bool = True
    status: TaskStatus = TaskStatus.QUEUED
    stage: str = "queued"
    detail: str = "等待中..."
    percent: int = 0
    segments_done: int = 0
    segments_total: int = 0
    units_done: int = 0
    units_total: int = 0
    unit_label: str = "language"
    current_range: str = ""
    glossary: Optional[Glossary] = None
    glossary_exports: dict[str, Any] = Field(default_factory=dict)
    language_runs: list[TranslationTask] = Field(default_factory=list)
    error_message: str = ""

    def set_status(
        self,
        status: TaskStatus,
        detail: str = "",
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
        self.status = status
        self.stage = stage or status.value
        if detail:
            self.detail = detail
        if percent is not None:
            self.percent = percent
        if segments_done is not None:
            self.segments_done = segments_done
        if segments_total is not None:
            self.segments_total = segments_total
        if units_done is not None:
            self.units_done = units_done
        if units_total is not None:
            self.units_total = units_total
        if unit_label is not None:
            self.unit_label = unit_label
        if current_range is not None:
            self.current_range = current_range
