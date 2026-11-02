"""CLI: ``webrtc-preview web`` | ``webrtc-preview desktop``."""

from __future__ import annotations

import argparse
import os
from urllib.parse import quote

from webrtc_preview_app.paths import DEFAULT_WEB_HOST, DEFAULT_WEB_PORT
from webrtc_preview_app.reexec import read_active_catalog
from webrtc_preview_app.service import PreviewService, normalize_catalog_url


def _resolve_catalog(args: argparse.Namespace) -> str:
    catalog = (
        getattr(args, "catalog", None)
        or os.environ.get("WEBRTC_PREVIEW_CATALOG")
        or read_active_catalog()
        or ""
    )
    return normalize_catalog_url(catalog) if catalog else ""


def _service(args: argparse.Namespace, *, launch_mode: str, ui: bool = False) -> PreviewService:
    return PreviewService(
        default_catalog=_resolve_catalog(args),
        web_host=getattr(args, "host", None) or os.environ.get("WEBRTC_PREVIEW_HOST") or DEFAULT_WEB_HOST,
        web_port=int(getattr(args, "port", None) or os.environ.get("WEBRTC_PREVIEW_PORT") or DEFAULT_WEB_PORT),
        launch_mode=launch_mode,
        ui=ui,
    )


def cmd_web(args: argparse.Namespace) -> int:
    from webrtc_preview_app.web.server import main as web_main

    service = _service(args, launch_mode="web", ui=False)
    url = f"http://127.0.0.1:{service.web_port}/"
    if service.default_catalog:
        url = f"{url}?catalog={quote(service.default_catalog, safe='')}"
    print(f"[webrtc-preview] web {url}", flush=True)
    if service.web_host in ("0.0.0.0", "::"):
        print(
            f"[webrtc-preview] listening on {service.web_host}:{service.web_port} "
            f"(LAN: http://<this-host-ip>:{service.web_port}/)",
            flush=True,
        )
    if getattr(args, "open", False):
        import webbrowser

        webbrowser.open(url)
    try:
        web_main(service, host=service.web_host, port=service.web_port)
    except KeyboardInterrupt:
        service.request_shutdown()
    return 0


def cmd_desktop(args: argparse.Namespace) -> int:
    from webrtc_preview_app.desktop_entry import main as desktop_main

    return desktop_main(
        host=getattr(args, "host", None),
        port=getattr(args, "port", None),
        catalog=getattr(args, "catalog", None) or _resolve_catalog(args) or None,
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="webrtc-preview", description="Multi-station WebRTC preview")
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_web = sub.add_parser("web", help="Start local FastAPI backend (no browser unless --open)")
    p_web.add_argument("--host", default=None)
    p_web.add_argument("--port", type=int, default=None)
    p_web.add_argument("--catalog", default=None, help="Default master catalog URL")
    p_web.add_argument(
        "--open",
        action="store_true",
        help="Open system browser after start (opt-in; start_web.bat does not use this)",
    )
    p_web.set_defaults(func=cmd_web)

    p_desk = sub.add_parser("desktop", help="PyQt WebEngine shell")
    p_desk.add_argument("--host", default=None)
    p_desk.add_argument("--port", type=int, default=None)
    p_desk.add_argument("--catalog", default=None)
    p_desk.set_defaults(func=cmd_desktop)

    args = parser.parse_args(argv)
    return int(args.func(args) or 0)


if __name__ == "__main__":
    raise SystemExit(main())
