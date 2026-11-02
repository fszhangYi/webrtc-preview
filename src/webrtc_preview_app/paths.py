from __future__ import annotations

import os
import sys
from pathlib import Path

APP_ID = "webrtc-preview"
APP_TITLE = "WebRTC Preview · Multi-station"
# Bind all interfaces so http://<LAN-IP>:7050 works; open URL still uses 127.0.0.1.
DEFAULT_WEB_HOST = "0.0.0.0"
DEFAULT_WEB_PORT = 7050


def package_dir() -> Path:
    return Path(__file__).resolve().parent


def project_root() -> Path:
    return package_dir().parent.parent


def meipass() -> Path | None:
    if getattr(sys, "frozen", False):
        return Path(getattr(sys, "_MEIPASS", Path(sys.executable).resolve().parent))
    env = os.environ.get("WEBRTC_PREVIEW_MEIPASS")
    return Path(env) if env else None


def static_dir() -> Path:
    env = os.environ.get("WEBRTC_PREVIEW_FRONTEND")
    if env:
        return Path(env)
    mp = meipass()
    if mp is not None:
        frozen = mp / "frontend-dist"
        if frozen.is_dir():
            return frozen
    return package_dir() / "web" / "static"


def user_data_dir() -> Path:
    env = os.environ.get("WEBRTC_PREVIEW_DATA")
    if env:
        p = Path(env)
        p.mkdir(parents=True, exist_ok=True)
        return p
    base = Path(os.environ.get("LOCALAPPDATA") or Path.home()) / APP_ID
    base.mkdir(parents=True, exist_ok=True)
    return base
