# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller spec for AgentTranslation Windows executable."""

import os

# Project root: build scripts always cd to project root before calling pyinstaller
ROOT = os.getcwd()

block_cipher = None

a = Analysis(
    [os.path.join(ROOT, "src/desktop_app.py")],
    pathex=[ROOT],
    binaries=[],
    datas=[
        (os.path.join(ROOT, "frontend/dist"), "frontend/dist"),
        (os.path.join(ROOT, "config"), "config"),
    ],
    hiddenimports=[
        # --- Application modules ---
        "src",
        "src.server",
        "src.main",
        "src.desktop_app",
        # models
        "src.models",
        "src.models.task",
        "src.models.glossary",
        "src.models.content",
        # queue
        "src.queue",
        "src.queue.manager",
        "src.queue.job_db",
        # llm
        "src.llm",
        "src.llm.poe_client",
        # orchestrator
        "src.orchestrator",
        "src.orchestrator.agent",
        # translator
        "src.translator",
        "src.translator.agent",
        "src.translator.segmenter",
        "src.translator.merger",
        # terminology
        "src.terminology",
        "src.terminology.agent",
        "src.terminology.extractor",
        "src.terminology.glossary",
        "src.terminology.library_db",
        "src.terminology.library_service",
        # parser
        "src.parser",
        "src.parser.base",
        "src.parser.pptx_parser",
        "src.parser.pptx_text",
        "src.parser.pptx_diagram",
        "src.parser.docx_parser",
        "src.parser.srt_parser",
        "src.parser.vtt_parser",
        "src.parser.ass_parser",
        "src.parser.markdown_parser",
        "src.parser.json_parser",
        "src.parser.yaml_parser",
        "src.parser.po_parser",
        "src.parser.xliff_parser",
        "src.parser.xml_parser",
        "src.parser.html_parser",
        # prompt
        "src.prompt",
        "src.prompt.version_manager",
        # quality
        "src.quality",
        "src.quality.regression",
        # utils
        "src.utils",
        "src.utils.paths",
        "src.utils.file_utils",
        "src.utils.style_loader",
        "src.utils.language_loader",
        "src.utils.language_detect",
        "src.utils.glossary_export",
        "src.utils.key_path",
        "src.utils.text_filters",
        "src.utils.xml_path",
        "src.utils.layout_fixer",
        # --- Third-party ---
        # uvicorn internals (dynamically loaded)
        "uvicorn.logging",
        "uvicorn.loops",
        "uvicorn.loops.auto",
        "uvicorn.loops.asyncio",
        "uvicorn.protocols",
        "uvicorn.protocols.http",
        "uvicorn.protocols.http.auto",
        "uvicorn.protocols.http.h11_impl",
        "uvicorn.protocols.http.httptools_impl",
        "uvicorn.protocols.websockets",
        "uvicorn.protocols.websockets.auto",
        "uvicorn.lifespan",
        "uvicorn.lifespan.on",
        "uvicorn.lifespan.off",
        # fastapi / starlette
        "fastapi",
        "starlette.responses",
        "starlette.staticfiles",
        "multipart",
        "multipart.multipart",
        # lxml C extensions
        "lxml",
        "lxml._elementpath",
        "lxml.etree",
        "lxml.html",
        # other deps
        "yaml",
        "pydantic",
        "httpx",
        "langdetect",
        "pptx",
        "docx",
        "pysrt",
        "webvtt",
        "mistune",
        "ruamel",
        "ruamel.yaml",
        "polib",
        "bs4",
        "webview",
        # --- Windows-specific: pywebview EdgeChromium backend ---
        "clr_loader",
        "pythonnet",
        "webview.platforms.edgechromium",
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    optimize=0,
    cipher=block_cipher,
)

pyz = PYZ(a.pure, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="AgentTranslation",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=True,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    a.zipfiles,
    strip=False,
    upx=False,
    upx_exclude=[],
    name="AgentTranslation",
)
