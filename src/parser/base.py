from __future__ import annotations

import abc
import logging

from src.models.content import ParsedFile

logger = logging.getLogger(__name__)


class BaseParser(abc.ABC):
    """Abstract base class for all file parsers."""

    @abc.abstractmethod
    def can_handle(self, file_path: str) -> bool:
        """Return *True* if this parser supports the given file."""

    @abc.abstractmethod
    def parse(self, file_path: str) -> ParsedFile:
        """Parse *file_path* into a :class:`ParsedFile`."""

    @abc.abstractmethod
    def rebuild(self, parsed_file: ParsedFile, output_path: str) -> str:
        """Rebuild the translated file and return the output path."""

    @staticmethod
    def _best_text(block) -> str:
        """Pick the best available text for a content block.

        Priority: reviewed_text > translated_text > source_text.
        """
        return block.reviewed_text or block.translated_text or block.source_text
