from __future__ import annotations

import json
from typing import Any

import uvicorn
from fastapi import FastAPI, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, JSONResponse, Response
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from webrtc_preview_app.paths import APP_TITLE, static_dir
from webrtc_preview_app.reexec import (
    schedule_reexec,
    validate_catalog_url,
    write_active_catalog,
)
from webrtc_preview_app.service import PreviewService


def _json_ascii(data: Any, status_code: int = 200) -> Response:
    body = json.dumps(data, ensure_ascii=True, separators=(",", ":"), allow_nan=False)
    return Response(
        content=body,
        status_code=status_code,
        media_type="application/json; charset=utf-8",
    )


class CatalogBody(BaseModel):
    url: str = Field(default="")


class ApplyConfigBody(BaseModel):
    """``path`` holds the master catalog URL (same field name as DCS/CCS H2)."""

    path: str = Field(default="")


def create_app(service: PreviewService) -> FastAPI:
    app = FastAPI(title=APP_TITLE, version="0.1.0")
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=False,
        allow_methods=["GET", "POST", "OPTIONS"],
        allow_headers=["*"],
    )
    static = static_dir()
    if static.is_dir():
        app.mount("/static", StaticFiles(directory=str(static)), name="static")

    @app.get("/", response_class=HTMLResponse)
    def index() -> Any:
        index_path = static / "index.html"
        if index_path.is_file():
            text = index_path.read_text(encoding="utf-8")
            if not text.startswith("\ufeff"):
                text = "\ufeff" + text
            return HTMLResponse(content=text, media_type="text/html; charset=utf-8")
        return HTMLResponse("<h1>webrtc-preview</h1><p>static/index.html missing</p>")

    @app.get("/api/health")
    def health() -> Response:
        return _json_ascii({"ok": True, "app": "webrtc-preview-host"})

    @app.get("/api/status")
    def status() -> Response:
        return _json_ascii(service.status())

    @app.get("/api/catalog")
    def catalog_get(url: str | None = Query(default=None)) -> Response:
        return _json_ascii(service.fetch_catalog(url))

    @app.post("/api/catalog")
    def catalog_post(body: CatalogBody) -> Response:
        return _json_ascii(service.fetch_catalog(body.url))

    @app.post("/api/shutdown")
    def shutdown() -> JSONResponse:
        # Plain JSONResponse so the body is flushed before os._exit.
        return JSONResponse(service.request_shutdown())

    @app.post("/api/runtime/apply-config")
    def apply_config(body: ApplyConfigBody) -> Response:
        try:
            catalog = validate_catalog_url(body.path or service.default_catalog or "")
            write_active_catalog(catalog)
        except Exception as exc:  # noqa: BLE001
            return _json_ascii({"ok": False, "error": str(exc)}, status_code=400)
        service.default_catalog = catalog
        schedule_reexec(
            catalog,
            mode=service.launch_mode,
            host=service.web_host,
            port=service.web_port,
            ui=service.ui or service.launch_mode == "desktop",
            before=lambda: None,
        )
        return _json_ascii({"ok": True, "restarting": True, "path": catalog})

    return app


def main(service: PreviewService, *, host: str, port: int) -> None:
    app = create_app(service)
    config = uvicorn.Config(app, host=host, port=int(port), log_level="info")
    server = uvicorn.Server(config)
    service.attach_server(server)
    try:
        server.run()
    except KeyboardInterrupt:
        service.request_shutdown()
        # Force-exit threads will end the process; brief wait for response path.
        import time

        time.sleep(1.2)
