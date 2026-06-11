from __future__ import annotations

import os
import platform
import socket
import threading
import time
from copy import deepcopy
from pathlib import Path
from typing import Any

import yaml
from pydantic import ValidationError

from resume_screening.config import AppConfig
from resume_screening.local_model import LocalModelManager
from resume_screening.web.app import create_app
from resume_screening.web.config_store import DEFAULT_CONFIG, load_config_for_web


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
        config_path.write_text(yaml.safe_dump(_desktop_default_config(directory), allow_unicode=True, sort_keys=False), encoding="utf-8")
    else:
        _migrate_desktop_config(config_path, directory)
    _register_bundled_local_model(config_path, directory)
    return config_path


def _desktop_default_config(directory: Path) -> dict[str, Any]:
    config = deepcopy(DEFAULT_CONFIG)
    config["index_path"] = str(directory / "data" / "processed_index.json")
    if platform.system() == "Windows":
        downloads = Path.home() / "Downloads"
        config["resume_dir"] = str(downloads)
        config["job_book"] = str(downloads / "岗位说明书.xlsx")
        config["result_book"] = str(downloads / "招聘结果表.xlsx")
        model = config["model"]
        model["provider"] = "local-qwen"
        model["base_url"] = ""
        model["api_key"] = ""
        model["model"] = "qwen3.5-local"
        model["timeout_seconds"] = max(int(model.get("timeout_seconds") or 0), 120)
        model["allow_without_model"] = False
        model["fallback_to_local_when_unavailable"] = True
        model["local"]["auto_start"] = True
        model["local"]["auto_download"] = False
    return config


def _migrate_desktop_config(config_path: Path, directory: Path) -> None:
    try:
        raw = yaml.safe_load(config_path.read_text(encoding="utf-8"))
    except OSError:
        return
    if not isinstance(raw, dict):
        return

    index_path = raw.get("index_path")
    if index_path:
        raw_index_path = str(index_path)
        parsed = Path(raw_index_path).expanduser()
        if parsed.is_absolute() or raw_index_path.startswith(("/", "\\")):
            return
        raw["index_path"] = str(directory / parsed)
    else:
        raw["index_path"] = str(directory / "data" / "processed_index.json")

    config_path.write_text(yaml.safe_dump(raw, allow_unicode=True, sort_keys=False), encoding="utf-8")


def _register_bundled_local_model(config_path: Path, directory: Path) -> None:
    if platform.system() != "Windows":
        return
    try:
        config = AppConfig.model_validate(load_config_for_web(config_path))
    except (OSError, ValueError, ValidationError):
        return
    if config.model.provider != "local-qwen":
        return
    LocalModelManager(config.model, app_data_dir=directory).register_bundled_model()


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
