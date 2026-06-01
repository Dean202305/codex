from __future__ import annotations

import os
import platform
import socket
import threading
import time
from pathlib import Path

import yaml

from resume_screening.web.app import create_app
from resume_screening.web.config_store import DEFAULT_CONFIG


APP_NAME = "小A简历筛选"
APP_HOME_ENV = "RESUME_SCREENING_APP_HOME"


def app_support_dir() -> Path:
    override = os.environ.get(APP_HOME_ENV)
    if override:
        return Path(override).expanduser()
    if platform.system() == "Darwin":
        return Path.home() / "Library" / "Application Support" / APP_NAME
    if platform.system() == "Windows":
        base = os.environ.get("APPDATA")
        if base:
            return Path(base) / APP_NAME
    return Path.home() / ".resume-screening"


def ensure_desktop_config() -> Path:
    directory = app_support_dir()
    directory.mkdir(parents=True, exist_ok=True)
    config_path = directory / "config.yaml"
    if not config_path.exists():
        config_path.write_text(yaml.safe_dump(DEFAULT_CONFIG, allow_unicode=True, sort_keys=False), encoding="utf-8")
    return config_path


def find_free_port(host: str = "127.0.0.1") -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind((host, 0))
        return int(sock.getsockname()[1])


def wait_for_server(host: str, port: int, timeout_seconds: float = 10) -> None:
    deadline = time.monotonic() + timeout_seconds
    while time.monotonic() < deadline:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            sock.settimeout(0.2)
            if sock.connect_ex((host, port)) == 0:
                return
        time.sleep(0.1)
    raise RuntimeError(f"本地服务启动超时：http://{host}:{port}")


def start_server(config_path: Path, host: str, port: int):
    import uvicorn

    app = create_app(config_path=config_path)
    config = uvicorn.Config(app, host=host, port=port, log_level="warning")
    server = uvicorn.Server(config)
    thread = threading.Thread(target=server.run, name="resume-screening-web", daemon=True)
    thread.start()
    wait_for_server(host, port)
    return server, thread


def main() -> None:
    try:
        import webview
    except ImportError as exc:
        raise SystemExit("缺少桌面窗口依赖 pywebview。请先安装：python -m pip install '.[desktop]'") from exc

    host = "127.0.0.1"
    port = find_free_port(host)
    config_path = ensure_desktop_config()
    server, thread = start_server(config_path, host, port)
    url = f"http://{host}:{port}"

    window = webview.create_window(APP_NAME, url, width=1180, height=820, min_size=(960, 680))

    def stop_server() -> None:
        server.should_exit = True
        thread.join(timeout=5)

    window.events.closed += stop_server
    webview.start()


if __name__ == "__main__":
    main()
