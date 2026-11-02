"""Preview host service — proxies catalog fetch (avoids some CORS/auth edge cases)."""

from __future__ import annotations

import os
import threading
import time
from typing import Any
from urllib.parse import urlparse, urlunparse

import httpx


def normalize_catalog_url(raw: str) -> str:
    s = (raw or "").strip()
    if not s:
        return ""
    if "://" not in s:
        s = "http://" + s
    parsed = urlparse(s)
    path = (parsed.path or "").rstrip("/")
    if not path or path == "":
        path = "/api/preview/catalog"
    elif path.endswith("/api/preview/catalog"):
        path = "/api/preview/catalog" if not path.startswith("/") else path
        # keep full path if nested (unlikely)
        if not path.startswith("/"):
            path = "/" + path
    elif "/api/preview/catalog" not in path:
        path = "/api/preview/catalog"
    if not path.startswith("/"):
        path = "/" + path
    return urlunparse((parsed.scheme or "http", parsed.netloc, path, "", parsed.query, ""))


class PreviewService:
    def __init__(
        self,
        *,
        default_catalog: str = "",
        web_host: str = "127.0.0.1",
        web_port: int = 7050,
        launch_mode: str = "web",
        ui: bool = False,
    ) -> None:
        self.default_catalog = normalize_catalog_url(default_catalog) if default_catalog else ""
        self.web_host = web_host
        self.web_port = int(web_port)
        self.launch_mode = launch_mode  # "web" | "desktop"
        self.ui = bool(ui)
        self._last: dict[str, Any] | None = None
        self._last_url: str = ""
        self._last_error: str | None = None
        self._last_at: float | None = None
        self._server: Any = None
        self._shutdown = False
        self._lock = threading.RLock()

    def attach_server(self, server: Any) -> None:
        self._server = server

    def status(self) -> dict[str, Any]:
        return {
            "ok": True,
            "app": "webrtc-preview-host",
            "default_catalog": self.default_catalog or None,
            "last_url": self._last_url or None,
            "last_error": self._last_error,
            "last_at": self._last_at,
            "rev": (self._last or {}).get("rev") if self._last else None,
            "stream_count": len((self._last or {}).get("streams") or []) if self._last else 0,
            "shutting_down": self._shutdown,
        }

    def fetch_catalog(self, url: str | None = None, *, timeout_s: float = 5.0) -> dict[str, Any]:
        target = normalize_catalog_url(url or self.default_catalog or "")
        if not target:
            return {"ok": False, "error": "catalog url required", "stations": [], "streams": []}
        self._last_url = target
        try:
            with httpx.Client(timeout=timeout_s, follow_redirects=True) as client:
                r = client.get(target)
            if r.status_code >= 400:
                self._last_error = f"HTTP {r.status_code}"
                return {
                    "ok": False,
                    "error": self._last_error,
                    "catalog_url": target,
                    "stations": [],
                    "streams": [],
                }
            data = r.json()
            if not isinstance(data, dict):
                self._last_error = "invalid JSON object"
                return {"ok": False, "error": self._last_error, "catalog_url": target}
            data = dict(data)
            data.setdefault("ok", True)
            data["catalog_url"] = target
            self._last = data
            self._last_error = None
            self._last_at = time.time()
            return data
        except Exception as e:  # noqa: BLE001
            self._last_error = str(e)
            return {
                "ok": False,
                "error": self._last_error,
                "catalog_url": target,
                "stations": [],
                "streams": [],
            }

    def request_shutdown(self) -> dict[str, Any]:
        """H1: signal uvicorn stop, then force ``os._exit`` off the HTTP handler."""
        if self._shutdown:
            return {"ok": True, "message": "shutdown already requested"}
        self._shutdown = True
        server = self._server
        if server is not None:
            try:
                server.should_exit = True
            except Exception as exc:  # noqa: BLE001
                print(f"[webrtc-preview] uvicorn exit signal failed: {exc}", flush=True)
        print("[webrtc-preview] shutdown requested", flush=True)

        def _force() -> None:
            time.sleep(1.0)
            os._exit(0)

        def _cleanup() -> None:
            # Let the HTTP response leave before the process image disappears.
            time.sleep(0.6)
            os._exit(0)

        threading.Thread(target=_force, name="webrtc-preview-force-exit", daemon=True).start()
        threading.Thread(target=_cleanup, name="webrtc-preview-shutdown", daemon=True).start()
        return {"ok": True, "message": "shutdown requested"}
