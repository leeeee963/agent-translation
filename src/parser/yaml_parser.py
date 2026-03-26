"""YAML (.yaml / .yml) parser — configuration and i18n files.

Uses ``ruamel.yaml`` to preserve comments and indentation on rebuild.
Falls back to ``pyyaml`` for parsing only (rebuild will lose comments).

Design decisions
----------------
- Same recursive leaf-string strategy as JsonParser.
- ``metadata["yaml_style"]`` records the block scalar style (``|`` / ``>``)
  so rebuild can attempt to preserve it.
- Rebuild uses ruamel.yaml's ``CommentedMap`` to update values in-place,
  which keeps all comments and indentation intact.
"""

from __future__ import annotations

import copy
import logging
import os
from pathlib import Path

from src.models.content import BlockType, ContentBlock, FileMeta, ParsedFile
from src.parser.base import BaseParser
from src.utils.key_path import iter_leaf_strings, set_by_path
from src.utils.text_filters import is_translatable

logger = logging.getLogger(__name__)

YAML_SKIP_KEYS: set[str] = {
    "url", "href", "src", "id", "uuid", "guid", "key",
    "version", "color", "colour", "type", "format", "icon",
    "class", "style", "lang", "locale",
}


class YamlParser(BaseParser):
    """Parser for YAML files (.yaml / .yml)."""

    EXTENSIONS = {".yaml", ".yml"}

    def can_handle(self, file_path: str) -> bool:
        return Path(file_path).suffix.lower() in self.EXTENSIONS

    # ------------------------------------------------------------------
    # parse
    # ------------------------------------------------------------------
    def parse(self, file_path: str) -> ParsedFile:
        raw = Path(file_path).read_text(encoding="utf-8")
        data = self._load_yaml(raw)
        if data is None:
            data = {}

        blocks: list[ContentBlock] = []
        word_count = 0

        for key_path, value in iter_leaf_strings(data, skip_keys=YAML_SKIP_KEYS):
            if not is_translatable(str(value)):
                continue
            bid = key_path.replace(".", "_").replace("[", "").replace("]", "")
            blocks.append(ContentBlock(
                id=bid,
                type=BlockType.KEY_VALUE,
                source_text=str(value),
                metadata={"key_path": key_path},
            ))
            word_count += len(str(value).split())

        return ParsedFile(
            meta=FileMeta(
                original_name=os.path.basename(file_path),
                file_type=Path(file_path).suffix.lstrip("."),
                word_count=word_count,
            ),
            blocks=blocks,
            format_template={"raw": raw, "data": copy.deepcopy(data)},
        )

    # ------------------------------------------------------------------
    # rebuild
    # ------------------------------------------------------------------
    def rebuild(self, parsed_file: ParsedFile, output_path: str) -> str:
        template = parsed_file.format_template or {}
        raw: str = template.get("raw", "")

        # Try ruamel.yaml for comment-preserving rebuild
        try:
            from ruamel.yaml import YAML
            from io import StringIO

            ryaml = YAML()
            ryaml.preserve_quotes = True
            data = ryaml.load(raw)

            for block in parsed_file.blocks:
                translated = self._best_text(block)
                key_path: str = block.metadata.get("key_path", "")
                if not key_path:
                    continue
                try:
                    set_by_path(data, key_path, translated)
                except (KeyError, IndexError, ValueError) as exc:
                    logger.warning("Could not set yaml key_path '%s': %s", key_path, exc)

            buf = StringIO()
            ryaml.dump(data, buf)
            out_text = buf.getvalue()

        except ImportError:
            # Fallback: pyyaml (loses comments)
            import yaml

            data = copy.deepcopy(template.get("data", {}))
            for block in parsed_file.blocks:
                translated = self._best_text(block)
                key_path = block.metadata.get("key_path", "")
                if not key_path:
                    continue
                try:
                    set_by_path(data, key_path, translated)
                except (KeyError, IndexError, ValueError) as exc:
                    logger.warning("Could not set yaml key_path '%s': %s", key_path, exc)

            out_text = yaml.dump(data, allow_unicode=True, default_flow_style=False)

        Path(output_path).parent.mkdir(parents=True, exist_ok=True)
        Path(output_path).write_text(out_text, encoding="utf-8")
        logger.info("Rebuilt YAML saved to %s", output_path)
        return output_path

    @staticmethod
    def _load_yaml(raw: str):
        """Load YAML using ruamel if available, else pyyaml."""
        try:
            from ruamel.yaml import YAML
            ryaml = YAML()
            return ryaml.load(raw)
        except ImportError:
            pass
        import yaml
        return yaml.safe_load(raw)
