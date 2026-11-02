"""Persist active catalog URL and replace this process after config change (H2)."""

from __future__ import annotations

import os
import sys
import threading
import time
from pathlib import Path
from typing import Any, Callable
from urllib.parse import urlparse

from webrtc_preview_app.paths import user_data_dir
from webrtc_preview_app.service import normalize_catalog_url


def active_catalog_pointer() -> Path:
    return user_data_dir() / "configs" / "active_catalog.url"


def read_active_catalog() -> str | None:
    pointer = active_catalog_pointer()
    if not pointer.is_file():
        return None
    try:
        raw = pointer.read_text(encoding="utf-8").strip()
    except OSError:
        return None
    if not raw:
        return None
    try:
        return validate_catalog_url(raw)
    except ValueError:
        return None


def write_active_catalog(url: str) -> str:
    pointer = active_catalog_pointer()
    pointer.parent.mkdir(parents=True, exist_ok=True)
    pointer.write_text(url + "\n", encoding="utf-8")
    try:
        os.chmod(pointer, 0o600)
    except OSError:
        pass
    return url


def validate_catalog_url(raw: str) -> str:
    url = normalize_catalog_url(raw or "")
    if not url:
        raise ValueError("catalog url required")
    parsed = urlparse(url)
    if not parsed.netloc:
        raise ValueError("catalog url missing host")
    if parsed.scheme not in ("http", "https"):
        raise ValueError("catalog url must be http(s)")
    return url


def build_reexec_argv(
    catalog: str,
    *,
    mode: str,
    host: str,
    port: int,
    ui: bool,
) -> list[str]:
    """Build argv to restart with the given catalog as default."""
    if getattr(sys, "frozen", False):
        out = [sys.executable]
        args = list(sys.argv[1:])
        index = 0
        skip = {"--catalog", "--host", "--port", "--ui", "--open"}
        while index < len(args):
            arg = args[index]
            if arg in ("--catalog", "--host", "--port") and index + 1 < len(args):
                index += 2
                continue
            if arg.startswith("--catalog=") or arg.startswith("--host=") or arg.startswith("--port="):
                index += 1
                continue
            if arg in skip:
                index += 1
                continue
            out.append(arg)
            index += 1
        if ui or mode == "desktop":
            out.append("--ui")
        out.extend(["--host", host, "--port", str(port), "--catalog", catalog])
        return out

    if mode == "desktop" or ui:
        return [
            sys.executable,
            "-m",
            "webrtc_preview_app",
            "desktop",
            "--host",
            host,
            "--port",
            str(port),
            "--catalog",
            catalog,
        ]
    # Dev web reexec: backend only (no --open), matching start_web.bat.
    return [
        sys.executable,
        "-m",
        "webrtc_preview_app",
        "web",
        "--host",
        host,
        "--port",
        str(port),
        "--catalog",
        catalog,
    ]


def schedule_reexec(
    catalog: str,
    *,
    mode: str,
    host: str,
    port: int,
    ui: bool,
    before: Callable[[], Any] | None = None,
    delay_s: float = 0.45,
) -> None:
    """Replace this process after optional cleanup. Does not os._exit first."""

    def _run() -> None:
        time.sleep(max(0.05, float(delay_s)))
        if callable(before):
            try:
                before()
            except Exception as exc:  # noqa: BLE001
                print(f"[webrtc-preview] reexec prepare failed: {exc}", flush=True)
        os.environ["WEBRTC_PREVIEW_CATALOG"] = catalog
        os.environ["WEBRTC_PREVIEW_HOST"] = host
        os.environ["WEBRTC_PREVIEW_PORT"] = str(port)
        argv = build_reexec_argv(catalog, mode=mode, host=host, port=port, ui=ui)
        try:
            os.execv(argv[0], argv)
        except Exception as exc:  # noqa: BLE001
            print(f"[webrtc-preview] reexec failed: {exc}", flush=True)
            os._exit(1)

    threading.Thread(target=_run, name="webrtc-preview-reexec", daemon=True).start()
