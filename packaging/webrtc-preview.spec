# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller spec for webrtc-preview (PyQt5 + WebEngine + FastAPI).

Modes via env WEBRTC_PREVIEW_PACK_MODE:
  onefile — single exe (preferred)
  onedir  — flat folder (contents_directory='.'), no _internal; zip afterwards
"""

from __future__ import annotations

import os
from datetime import datetime
from pathlib import Path

from PyInstaller.building.api import COLLECT, EXE, PYZ
from PyInstaller.building.datastruct import TOC
from PyInstaller.building.build_main import Analysis
from PyInstaller.utils.hooks import collect_all, collect_data_files

ROOT = Path(os.path.dirname(os.path.abspath(SPEC))).resolve().parent
ENTRY = ROOT / "src" / "webrtc_preview_app" / "desktop_entry.py"
STATIC = ROOT / "src" / "webrtc_preview_app" / "web" / "static"
RTHOOK = ROOT / "packaging" / "rthook_dll.py"
ICON = ROOT / "packaging" / "webrtc-preview.ico"
APP_NAME = "WebRTCPreview"
MODE = os.environ.get("WEBRTC_PREVIEW_PACK_MODE", "onefile").strip().lower()
STAMP = os.environ.get("WEBRTC_PREVIEW_PACK_STAMP") or datetime.now().strftime("%Y%m%d-%H%M%S")

datas = [
    (str(STATIC), "frontend-dist"),
]
if ICON.is_file():
    datas.append((str(ICON), "."))

binaries = []
hidden = [
    "PyQt5.QtWebEngineWidgets",
    "PyQt5.QtWebEngineCore",
    "PyQt5.QtWebEngine",
    "uvicorn.logging",
    "uvicorn.loops",
    "uvicorn.loops.auto",
    "uvicorn.protocols",
    "uvicorn.protocols.http",
    "uvicorn.protocols.http.auto",
    "uvicorn.protocols.websockets",
    "uvicorn.protocols.websockets.auto",
    "uvicorn.lifespan",
    "uvicorn.lifespan.on",
    "httpx",
    "webrtc_preview_app",
    "webrtc_preview_app.web.server",
    "webrtc_preview_app.service",
    "webrtc_preview_app.reexec",
    "webrtc_preview_app.cli",
    "webrtc_preview_app.paths",
]

for pkg in ("PyQt5", "PyQt5.QtWebEngineCore", "PyQt5.QtWebEngineWidgets"):
    try:
        d, b, h = collect_all(pkg)
        datas += d
        binaries += b
        hidden += h
    except Exception:
        pass

try:
    datas += collect_data_files("uvicorn")
except Exception:
    pass


def _ship(item) -> bool:
    name = item[0].replace("\\", "/").rsplit("/", 1)[-1].lower()
    src = (item[1] if len(item) > 1 else "").replace("\\", "/").lower()
    if name.startswith("api-ms-win-") or name == "ucrtbase.dll":
        return False
    if any(part in src for part in ("miniconda", "anaconda", "/conda/", "\\conda\\")):
        return False
    return True


a = Analysis(
    [str(ENTRY)],
    pathex=[str(ROOT / "src"), str(ROOT)],
    binaries=binaries,
    datas=datas,
    hiddenimports=hidden,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[str(RTHOOK)],
    excludes=["tkinter", "matplotlib", "numpy.testing"],
    noarchive=False,
)

a.binaries = TOC([item for item in a.binaries if _ship(item)])

try:
    import PyQt5

    qt_bin = Path(PyQt5.__file__).resolve().parent / "Qt5" / "bin"
    d3d = qt_bin / "d3dcompiler_47.dll"
    if d3d.is_file():
        a.binaries += TOC([(d3d.name, str(d3d), "BINARY")])
except Exception:
    pass

pyz = PYZ(a.pure)
icon_kw = {"icon": str(ICON)} if ICON.is_file() else {}

if MODE == "onedir":
    exe = EXE(
        pyz,
        a.scripts,
        [],
        exclude_binaries=True,
        contents_directory=".",
        name=APP_NAME,
        debug=False,
        bootloader_ignore_signals=False,
        strip=False,
        upx=False,
        console=False,
        disable_windowed_traceback=False,
        **icon_kw,
    )
    coll = COLLECT(
        exe,
        a.binaries,
        a.datas,
        name=APP_NAME,
        strip=False,
        upx=False,
    )
else:
    exe = EXE(
        pyz,
        a.scripts,
        a.binaries,
        a.datas,
        [],
        exclude_binaries=False,
        name=f"{APP_NAME}-{STAMP}",
        debug=False,
        bootloader_ignore_signals=False,
        strip=False,
        upx=False,
        console=False,
        disable_windowed_traceback=False,
        **icon_kw,
    )
