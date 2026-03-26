from __future__ import annotations

from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


class BlockType(str, Enum):
    HEADING = "heading"
    PARAGRAPH = "paragraph"
    TABLE = "table"
    LIST = "list"
    IMAGE = "image"
    CODE = "code"
    SUBTITLE = "subtitle"
    SLIDE_NOTE = "slide_note"
    KEY_VALUE = "key_value"           # JSON / YAML / XML key-value pairs
    TRANSLATION_UNIT = "translation_unit"  # XLIFF / PO translation units


class ContentBlock(BaseModel):
    """A single translatable content unit extracted from a file."""

    id: str
    type: BlockType
    source_text: str = ""
    translated_text: str = ""
    reviewed_text: str = ""
    translatable: bool = True
    style: dict[str, Any] = Field(default_factory=dict)
    metadata: dict[str, Any] = Field(default_factory=dict)


class FileMeta(BaseModel):
    original_name: str
    file_type: str
    detected_language: str = ""
    word_count: int = 0


class ParsedFile(BaseModel):
    """Result of parsing a file: content blocks + opaque format template."""

    meta: FileMeta
    blocks: list[ContentBlock] = Field(default_factory=list)
    format_template: Any = None

    @property
    def translatable_blocks(self) -> list[ContentBlock]:
        return [b for b in self.blocks if b.translatable and b.source_text.strip()]

    @property
    def plain_text(self) -> str:
        return "\n".join(b.source_text for b in self.translatable_blocks)
