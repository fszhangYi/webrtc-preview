"""Frozen / desktop entry: FastAPI + optional PyQt5 WebEngine shell.

Packaged default (no ``--ui``): headless backend, open system browser after
``/api/health`` (pyqt-web-software-style §1). ``--ui`` opens the PyQt window.
"""

from __future__ import annotations

import argparse
import os
import socket
import sys
import threading
import time
import traceback
import webbrowser
from pathlib import Path
from urllib.parse import quote


def _prepare_env() -> Path:
    if getattr(sys, "frozen", False):
        meipass = Path(getattr(sys, "_MEIPASS", Path(sys.executable).resolve().parent))
        os.environ.setdefault("WEBRTC_PREVIEW_MEIPASS", str(meipass))
        os.environ.setdefault("WEBRTC_PREVIEW_FRONTEND", str(meipass / "frontend-dist"))
        base = Path(os.environ.get("LOCALAPPDATA") or Path.home()) / "webrtc-preview"
        base.mkdir(parents=True, exist_ok=True)
        os.environ.setdefault("WEBRTC_PREVIEW_DATA", str(base))
        log_path = base / "startup.log"
        try:
            log_f = open(log_path, "a", encoding="utf-8", buffering=1)
            sys.stdout = log_f
            sys.stderr = log_f
            print(f"\n--- start {time.strftime('%Y-%m-%d %H:%M:%S')} ---", flush=True)
        except OSError:
            if sys.stdout is None:
                sys.stdout = open(os.devnull, "w")
            if sys.stderr is None:
                sys.stderr = open(os.devnull, "w")
        return meipass
    return Path(__file__).resolve().parents[2]


def _pick_port(host: str, preferred: int) -> int:
    for candidate in (preferred, *range(preferred + 1, preferred + 20)):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            try:
                s.bind((host, candidate))
            except OSError:
                continue
            return candidate
    return preferred


def _message_box(title: str, text: str) -> None:
    try:
        import ctypes

        ctypes.windll.user32.MessageBoxW(0, text, title, 0x10)
    except Exception:  # noqa: BLE001
        pass


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(add_help=True)
    parser.add_argument(
        "--ui",
        action="store_true",
        help="Open PyQt WebEngine window (default packaged mode opens system browser only)",
    )
    parser.add_argument("--host", default=None)
    parser.add_argument("--port", type=int, default=None)
    parser.add_argument("--catalog", default=None)
    parser.add_argument(
        "--open",
        action="store_true",
        help="Force open system browser (packaged headless already opens by default)",
    )
    args, _unknown = parser.parse_known_args(argv)
    return args


def _build_service(
    *,
    host: str | None,
    port: int | None,
    catalog: str | None,
    launch_mode: str,
    ui: bool,
):
    from webrtc_preview_app.paths import DEFAULT_WEB_HOST, DEFAULT_WEB_PORT
    from webrtc_preview_app.reexec import read_active_catalog
    from webrtc_preview_app.service import PreviewService, normalize_catalog_url

    bind_host = host or os.environ.get("WEBRTC_PREVIEW_HOST") or DEFAULT_WEB_HOST
    preferred = int(port or os.environ.get("WEBRTC_PREVIEW_PORT") or DEFAULT_WEB_PORT)
    listen_port = _pick_port(bind_host, preferred)
    cat = catalog or os.environ.get("WEBRTC_PREVIEW_CATALOG") or read_active_catalog() or ""
    service = PreviewService(
        default_catalog=normalize_catalog_url(cat) if cat else "",
        web_host=bind_host,
        web_port=listen_port,
        launch_mode=launch_mode,
        ui=ui,
    )
    return service, bind_host, listen_port


def _serve(service, bind_host: str, listen_port: int):
    ready = threading.Event()
    web_error: list[str] = []

    def _run_web() -> None:
        try:
            import uvicorn

            from webrtc_preview_app.web.server import create_app

            config = uvicorn.Config(
                create_app(service),
                host=bind_host,
                port=listen_port,
                log_level="warning",
                access_log=False,
            )
            server = uvicorn.Server(config)
            server.install_signal_handlers = lambda: None  # type: ignore[method-assign]
            service.attach_server(server)
            ready.set()
            server.run()
        except Exception as e:  # noqa: BLE001
            web_error.append(str(e))
            ready.set()

    thread = threading.Thread(target=_run_web, name="webrtc-preview-web", daemon=True)
    thread.start()
    return thread, ready, web_error


def _wait_health(health_url: str, web_error: list[str], timeout_s: float = 20.0) -> bool:
    import urllib.request

    deadline = time.time() + timeout_s
    while time.time() < deadline:
        if web_error:
            return False
        try:
            with urllib.request.urlopen(health_url, timeout=0.5) as resp:
                if getattr(resp, "status", 200) == 200:
                    return True
        except Exception:  # noqa: BLE001
            time.sleep(0.15)
    return False


def _page_url(open_host: str, listen_port: int, catalog: str) -> str:
    page = f"http://{open_host}:{listen_port}/"
    if catalog:
        page = f"{page}?catalog={quote(catalog, safe='')}"
    return page


def run_server(
    *,
    open_browser: bool = True,
    host: str | None = None,
    port: int | None = None,
    catalog: str | None = None,
) -> int:
    """Headless FastAPI; optionally open the system browser after health (H1-ready)."""
    _prepare_env()
    service, bind_host, listen_port = _build_service(
        host=host, port=port, catalog=catalog, launch_mode="web", ui=False
    )
    thread, _ready, web_error = _serve(service, bind_host, listen_port)
    open_host = "127.0.0.1" if bind_host in ("0.0.0.0", "::") else bind_host
    health_url = f"http://{open_host}:{listen_port}/api/health"
    page = _page_url(open_host, listen_port, service.default_catalog)
    if web_error or not _wait_health(health_url, web_error):
        detail = web_error[0] if web_error else f"health timeout: {health_url}"
        print(detail, flush=True)
        _message_box("webrtc-preview", f"Web 服务启动失败：\n{detail[-1200:]}")
        return 1
    print(f"[webrtc-preview] listening {page}", flush=True)
    if open_browser:
        webbrowser.open(page)
    try:
        while thread.is_alive() and not service._shutdown:
            time.sleep(0.4)
    except KeyboardInterrupt:
        service.request_shutdown()
        time.sleep(1.2)
    return 0


def main(
    *,
    host: str | None = None,
    port: int | None = None,
    catalog: str | None = None,
) -> int:
    try:
        # Frozen exe: argv decides --ui vs headless+browser.
        if getattr(sys, "frozen", False) and host is None and port is None and catalog is None:
            args = _parse_args()
            if args.ui:
                return _main_impl(host=args.host, port=args.port, catalog=args.catalog)
            return run_server(
                open_browser=True,
                host=args.host,
                port=args.port,
                catalog=args.catalog,
            )
        return _main_impl(host=host, port=port, catalog=catalog)
    except Exception:  # noqa: BLE001
        tb = traceback.format_exc()
        print(tb, flush=True)
        _message_box("webrtc-preview failed", tb[-1500:])
        return 1


def _main_impl(
    *,
    host: str | None = None,
    port: int | None = None,
    catalog: str | None = None,
) -> int:
    _prepare_env()

    from PyQt5.QtCore import QUrl
    from PyQt5.QtWidgets import QApplication, QMainWindow, QMessageBox, QVBoxLayout, QWidget
    from PyQt5.QtWebEngineWidgets import QWebEngineView

    try:
        from PyQt5.QtWebEngineCore import QWebEngineProfile
    except ImportError:
        from PyQt5.QtWebEngineWidgets import QWebEngineProfile  # type: ignore

    from webrtc_preview_app.paths import APP_TITLE, user_data_dir

    service, bind_host, listen_port = _build_service(
        host=host, port=port, catalog=catalog, launch_mode="desktop", ui=True
    )
    _thread, _ready, web_error = _serve(service, bind_host, listen_port)

    open_host = "127.0.0.1" if bind_host in ("0.0.0.0", "::") else bind_host
    health_url = f"http://{open_host}:{listen_port}/api/health"
    if web_error or not _wait_health(health_url, web_error):
        msg = web_error[0] if web_error else f"health timeout: {health_url}"
        _message_box("webrtc-preview", msg)
        return 1

    page = _page_url(open_host, listen_port, service.default_catalog)

    app = QApplication(sys.argv)
    app.setApplicationName(APP_TITLE)
    data = user_data_dir()
    cache = data / "cache"
    storage = data / "storage"
    cache.mkdir(parents=True, exist_ok=True)
    storage.mkdir(parents=True, exist_ok=True)
    for p in cache.glob("*"):
        try:
            if p.is_file():
                p.unlink()
        except OSError:
            pass

    profile = QWebEngineProfile.defaultProfile()
    profile.setCachePath(str(cache))
    profile.setPersistentStoragePath(str(storage))
    try:
        profile.setHttpAcceptLanguage("zh-CN,zh;q=0.9,en;q=0.8")
    except Exception:  # noqa: BLE001
        pass

    class Shell(QMainWindow):
        def closeEvent(self, event) -> None:  # type: ignore[override]
            service.request_shutdown()
            event.accept()

    win = Shell()
    win.setWindowTitle(APP_TITLE)
    try:
        from PyQt5.QtGui import QIcon

        ico: Path | None = None
        if getattr(sys, "frozen", False):
            meipass = Path(getattr(sys, "_MEIPASS", Path(sys.executable).resolve().parent))
            for name in ("webrtc-preview.ico", "WebRTCPreview.ico"):
                cand = meipass / name
                if cand.is_file():
                    ico = cand
                    break
        if ico is None:
            cand = Path(__file__).resolve().parents[2] / "packaging" / "webrtc-preview.ico"
            if cand.is_file():
                ico = cand
        if ico is not None:
            win.setWindowIcon(QIcon(str(ico)))
    except Exception:  # noqa: BLE001
        pass
    win.resize(1280, 800)
    central = QWidget()
    layout = QVBoxLayout(central)
    layout.setContentsMargins(0, 0, 0, 0)
    view = QWebEngineView()
    layout.addWidget(view)
    win.setCentralWidget(central)
    win.setStyleSheet("background:#0b1018;")

    def _on_load(ok_flag: bool) -> None:
        if not ok_flag:
            QMessageBox.warning(win, APP_TITLE, f"Failed to load\n{page}")

    view.loadFinished.connect(_on_load)
    view.setUrl(QUrl(page))
    win.show()
    code = int(app.exec_())
    if not service._shutdown:
        service.request_shutdown()
        time.sleep(0.8)
    return code


if __name__ == "__main__":
    raise SystemExit(main())
