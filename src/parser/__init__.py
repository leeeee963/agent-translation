from __future__ import annotations

from src.parser.ass_parser import AssParser
from src.parser.base import BaseParser
from src.parser.docx_parser import DocxParser
from src.parser.html_parser import HtmlParser
from src.parser.json_parser import JsonParser
from src.parser.markdown_parser import MarkdownParser
from src.parser.po_parser import PoParser
from src.parser.pptx_parser import PptxParser
from src.parser.srt_parser import SrtParser
from src.parser.vtt_parser import VttParser
from src.parser.xliff_parser import XliffParser
from src.parser.xml_parser import XmlParser
from src.parser.yaml_parser import YamlParser

# Order matters: more-specific parsers must come before generic ones.
# XLIFF before XML; all others in rough priority order.
_PARSERS: list[BaseParser] = [
    PptxParser(),
    DocxParser(),
    SrtParser(),
    VttParser(),
    AssParser(),
    MarkdownParser(),
    JsonParser(),
    YamlParser(),
    PoParser(),
    XliffParser(),   # before XmlParser — .xliff/.xlf are more specific
    XmlParser(),
    HtmlParser(),
]


def get_parser(file_path: str) -> BaseParser:
    """Return the appropriate parser for *file_path*, or raise ValueError."""
    for parser in _PARSERS:
        if parser.can_handle(file_path):
            return parser
    raise ValueError(f"No parser available for: {file_path}")


__all__ = [
    "BaseParser",
    "PptxParser",
    "DocxParser",
    "SrtParser",
    "VttParser",
    "AssParser",
    "MarkdownParser",
    "JsonParser",
    "YamlParser",
    "PoParser",
    "XliffParser",
    "XmlParser",
    "HtmlParser",
    "get_parser",
]
