from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import UTC, datetime
import hashlib
import json
import os
from pathlib import Path
import platform
import shutil
import subprocess
import sys
import time
from typing import Any

import httpx

from resume_screening.config import ModelConfig


DEFAULT_MODEL_FILENAME = "Qwen3.5-9B-Q4_K_M.gguf"
DEFAULT_MODEL_URL = (
    "https://huggingface.co/jc-builds/Qwen3.5-9B-Q4_K_M-GGUF/"
    "resolve/main/Qwen3.5-9B-Q4_K_M.gguf?download=true"
)
DEFAULT_MODEL_SIZE_BYTES = 5_300_000_000
LOCAL_MODEL_MIN_STARTUP_WAIT_SECONDS = 600
LOCAL_MODEL_MAX_STARTUP_WAIT_SECONDS = 1_200


@dataclass(frozen=True)
class LocalModelStatus:
    state: str
    runtime_available: bool
    runtime_path: str
    model_installed: bool
    model_path: str
    manifest_path: str
    service_base_url: str
    manifest: dict[str, Any]
    message: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class LocalModelDownloadPlan:
    display_name: str
    url: str
    target_path: str
    size_bytes: int
    sha256: str | None
    source_page: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class LocalModelEnvironmentItem:
    id: str
    label: str
    state: str
    message: str
    path: str
    action: str = ""
    requires_confirmation: bool = False

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class LocalModelEnvironmentReport:
    ready: bool
    items: list[LocalModelEnvironmentItem]
    status: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def platform_runtime_key(system: str | None = None, machine: str | None = None) -> str:
    normalized_system = (system or platform.system()).lower()
    normalized_machine = (machine or platform.machine()).lower()
    if normalized_system == "darwin":
        return "macos-arm64" if normalized_machine in {"arm64", "aarch64"} else "macos-x64"
    if normalized_system == "windows":
        if normalized_machine in {"amd64", "x86_64", "x64"}:
            return "windows-x64"
    raise ValueError(f"unsupported local model platform: {system or platform.system()} {machine or platform.machine()}")


def local_model_startup_wait_seconds(configured_timeout_seconds: float) -> float:
    return max(
        LOCAL_MODEL_MIN_STARTUP_WAIT_SECONDS,
        min(float(configured_timeout_seconds), LOCAL_MODEL_MAX_STARTUP_WAIT_SECONDS),
    )


def default_app_data_dir() -> Path:
    override = os.environ.get("RESUME_SCREENING_HOME")
    if override:
        return Path(override).expanduser()
    if sys.platform == "darwin":
        return Path.home() / "Library" / "Application Support" / "ResumeScreening"
    if sys.platform.startswith("win"):
        base = os.environ.get("APPDATA") or str(Path.home() / "AppData" / "Roaming")
        return Path(base) / "ResumeScreening"
    return Path.home() / ".resume-screening"


def default_runtime_root() -> Path:
    override = os.environ.get("RESUME_SCREENING_RUNTIME_DIR")
    if override:
        return Path(override).expanduser()
    bundle_root = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parents[2]))
    executable_root = Path(sys.executable).resolve().parent
    candidates = [
        bundle_root / "packaging" / "runtime",
        bundle_root / "runtime",
        executable_root / "_internal" / "packaging" / "runtime",
        executable_root.parent / "Resources" / "packaging" / "runtime",
        executable_root.parent / "Frameworks" / "packaging" / "runtime",
        Path.cwd() / "packaging" / "runtime",
    ]
    for candidate in candidates:
        if candidate.exists():
            return candidate
    return candidates[0]


class LocalModelManager:
    def __init__(
        self,
        config: ModelConfig,
        *,
        app_data_dir: Path | None = None,
        runtime_root: Path | None = None,
    ) -> None:
        self.config = config
        self.app_data_dir = app_data_dir or default_app_data_dir()
        self.runtime_root = runtime_root or default_runtime_root()

    @property
    def service_base_url(self) -> str:
        local = self.config.local
        return f"http://{local.host}:{local.port}/v1"

    def runtime_path(self, *, system: str | None = None, machine: str | None = None) -> Path:
        key = platform_runtime_key(system, machine)
        executable = "llama-server.exe" if key.startswith("windows") else "llama-server"
        return self.runtime_root / key / executable

    def manifest_path(self) -> Path:
        return self._resolve_data_path(self.config.local.manifest_path)

    def target_model_path(self) -> Path:
        configured = self.config.local.model_path
        if configured is not None:
            return self._resolve_data_path(configured)
        manifest = self.read_manifest()
        manifest_path = manifest.get("path")
        if isinstance(manifest_path, str) and manifest_path:
            return self._resolve_data_path(Path(manifest_path))
        return self.app_data_dir / "models" / "qwen" / DEFAULT_MODEL_FILENAME

    def read_manifest(self) -> dict[str, Any]:
        path = self.manifest_path()
        if not path.exists():
            return {}
        try:
            raw = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return {}
        return raw if isinstance(raw, dict) else {}

    def write_manifest(self, model_path: Path, *, size_bytes: int, sha256: str | None, source_url: str) -> None:
        manifest_path = self.manifest_path()
        manifest_path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "model_family": self.config.local.model_family,
            "display_name": self.config.local.model_display_name,
            "model": self.config.model,
            "path": str(model_path),
            "size_bytes": size_bytes,
            "sha256": sha256,
            "source_url": source_url,
            "installed_at": datetime.now(UTC).isoformat(),
        }
        manifest_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    def status(self, *, system: str | None = None, machine: str | None = None) -> LocalModelStatus:
        runtime = self.runtime_path(system=system, machine=machine)
        runtime_available = runtime.exists() and runtime.is_file()
        model_path = self.target_model_path()
        model_installed = model_path.exists() and model_path.is_file()
        manifest = self.read_manifest()
        if not runtime_available:
            state = "runtime_missing"
            message = f"本地模型运行器不存在：{runtime}"
        elif not model_installed:
            state = "model_missing"
            message = f"本地模型文件不存在：{model_path}"
        else:
            state = "ready"
            message = "本地模型文件和运行器已就绪"
        return LocalModelStatus(
            state=state,
            runtime_available=runtime_available,
            runtime_path=str(runtime),
            model_installed=model_installed,
            model_path=str(model_path),
            manifest_path=str(self.manifest_path()),
            service_base_url=self.service_base_url,
            manifest=manifest,
            message=message,
        )

    def environment_check(self, *, system: str | None = None, machine: str | None = None) -> LocalModelEnvironmentReport:
        status = self.status(system=system, machine=machine)
        runtime_item = LocalModelEnvironmentItem(
            id="runtime",
            label="本地模型运行器",
            state="ready" if status.runtime_available else "missing",
            message="运行器已内置" if status.runtime_available else "安装包缺少本地模型运行器，请重新安装完整版本",
            path=status.runtime_path,
            action="" if status.runtime_available else "reinstall_app",
        )
        model_item = LocalModelEnvironmentItem(
            id="model",
            label="本地大模型",
            state="ready" if status.model_installed else "missing",
            message="模型文件已安装" if status.model_installed else "模型文件未安装，需要用户确认后联网下载",
            path=status.model_path,
            action="" if status.model_installed else "download_model",
            requires_confirmation=not status.model_installed,
        )
        data_ready, data_message = self._check_data_directory()
        data_item = LocalModelEnvironmentItem(
            id="data_dir",
            label="应用数据目录",
            state="ready" if data_ready else "error",
            message=data_message,
            path=str(self.app_data_dir),
            action="" if data_ready else "choose_writable_directory",
        )
        items = [runtime_item, model_item, data_item]
        return LocalModelEnvironmentReport(
            ready=all(item.state == "ready" for item in items),
            items=items,
            status=status.to_dict(),
        )

    def download_plan(self) -> LocalModelDownloadPlan:
        return LocalModelDownloadPlan(
            display_name=f"{self.config.local.model_display_name}（9B Q4_K_M GGUF）",
            url=DEFAULT_MODEL_URL,
            target_path=str(self.target_model_path()),
            size_bytes=DEFAULT_MODEL_SIZE_BYTES,
            sha256=None,
            source_page="https://huggingface.co/jc-builds/Qwen3.5-9B-Q4_K_M-GGUF",
        )

    def build_server_command(
        self,
        model_path: Path | None = None,
        *,
        system: str | None = None,
        machine: str | None = None,
    ) -> list[str]:
        local = self.config.local
        command = [
            str(self.runtime_path(system=system, machine=machine)),
            "-m",
            str(model_path or self.target_model_path()),
            "--host",
            local.host,
            "--port",
            str(local.port),
            "-c",
            str(local.context_size),
            "--alias",
            self.config.model,
            "--jinja",
            "--parallel",
            "1",
            "--no-ui",
            "--no-warmup",
        ]
        if local.threads > 0:
            command.extend(["-t", str(local.threads)])
        gpu_layers = "auto" if local.gpu_layers == "auto" else str(local.gpu_layers).strip()
        if gpu_layers:
            command.extend(["-ngl", gpu_layers])
        return command

    def check_service(self, timeout_seconds: float = 5) -> tuple[bool, str]:
        try:
            response = httpx.get(f"{self.service_base_url}/models", timeout=timeout_seconds)
            if response.status_code == 503:
                return False, _service_unavailable_message(response)
            response.raise_for_status()
        except httpx.HTTPStatusError as exc:
            return False, _service_unavailable_message(exc.response)
        except Exception as exc:
            return False, str(exc)
        return True, "本地模型服务可用"

    def ensure_service(self, *, wait_seconds: float = 60) -> tuple[bool, str]:
        status = self.status()
        if status.state != "ready":
            return False, status.message
        available, message = self.check_service(timeout_seconds=2)
        if available:
            return True, message
        if not self.config.local.auto_start:
            return False, f"本地模型服务未启动：{message}"
        try:
            if _is_loading_message(message):
                self._wait_for_service(wait_seconds=wait_seconds)
            else:
                self.start_service(wait_seconds=wait_seconds)
        except Exception as exc:
            return False, f"本地模型服务启动失败：{exc}"
        return True, "本地模型服务已启动并可用"

    def start_service(self, *, wait_seconds: float = 30) -> subprocess.Popen[str]:
        status = self.status()
        if status.state != "ready":
            raise RuntimeError(status.message)
        command = self.build_server_command(Path(status.model_path))
        log_path = self.app_data_dir / "logs" / "llama-server.log"
        log_path.parent.mkdir(parents=True, exist_ok=True)
        log_handle = log_path.open("a", encoding="utf-8")
        process = subprocess.Popen(
            command,
            stdout=log_handle,
            stderr=subprocess.STDOUT,
            text=True,
            env=self._server_environment(Path(status.runtime_path)),
        )
        log_handle.close()
        self._wait_for_service(process=process, log_path=log_path, wait_seconds=wait_seconds)
        return process

    def _wait_for_service(
        self,
        *,
        process: subprocess.Popen[str] | None = None,
        log_path: Path | None = None,
        wait_seconds: float = 30,
    ) -> None:
        deadline = time.monotonic() + wait_seconds
        last_message = ""
        while time.monotonic() < deadline:
            ok, message = self.check_service(timeout_seconds=2)
            if ok:
                return
            last_message = message
            if process is not None and process.poll() is not None:
                raise RuntimeError(_startup_failure_message(log_path) if log_path is not None else "本地模型服务进程已退出")
            time.sleep(1)
        if process is not None and process.poll() is None:
            process.terminate()
        suffix = f"；最后状态：{last_message}" if last_message else ""
        raise TimeoutError(f"本地模型服务启动超时{suffix}")

    def install_downloaded_model(self, downloaded_path: Path, plan: LocalModelDownloadPlan) -> Path:
        target = Path(plan.target_path)
        target.parent.mkdir(parents=True, exist_ok=True)
        if downloaded_path.resolve() != target.resolve():
            shutil.move(str(downloaded_path), target)
        sha256 = file_sha256(target)
        if plan.sha256 and sha256.lower() != plan.sha256.lower():
            target.unlink(missing_ok=True)
            raise ValueError("模型文件校验失败")
        self.write_manifest(target, size_bytes=target.stat().st_size, sha256=sha256, source_url=plan.url)
        return target

    def _resolve_data_path(self, path: Path) -> Path:
        expanded = Path(path).expanduser()
        if expanded.is_absolute():
            return expanded
        return self.app_data_dir / expanded

    def _check_data_directory(self) -> tuple[bool, str]:
        try:
            self.app_data_dir.mkdir(parents=True, exist_ok=True)
            marker = self.app_data_dir / ".write-test"
            marker.write_text("ok", encoding="utf-8")
            marker.unlink(missing_ok=True)
        except OSError as exc:
            return False, f"应用数据目录不可写：{exc}"
        return True, "应用数据目录可写"

    def _server_environment(self, runtime_path: Path) -> dict[str, str]:
        env = os.environ.copy()
        if sys.platform == "darwin":
            existing_path = env.get("DYLD_LIBRARY_PATH", "")
            env["DYLD_LIBRARY_PATH"] = os.pathsep.join([str(runtime_path.parent)] + ([existing_path] if existing_path else []))
        elif os.name == "nt":
            extra_paths = [str(runtime_path.parent), str(self.runtime_root.parent.parent)]
            existing_path = env.get("PATH", "")
            env["PATH"] = os.pathsep.join(extra_paths + ([existing_path] if existing_path else []))
        return env


def _startup_failure_message(log_path: Path) -> str:
    try:
        raw = log_path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return "进程已退出，未能读取启动日志"
    tail = raw[-1200:].strip()
    if not tail:
        return "进程已退出，启动日志为空"
    return tail


def _service_unavailable_message(response: httpx.Response) -> str:
    try:
        payload = response.json()
    except ValueError:
        payload = {}
    message = ""
    if isinstance(payload, dict):
        error = payload.get("error")
        if isinstance(error, dict):
            message = str(error.get("message") or "")
    if response.status_code == 503 and "loading model" in message.lower():
        return "本地模型正在加载"
    detail = message or response.text[:200].strip()
    return f"本地模型服务暂不可用：HTTP {response.status_code}" + (f" {detail}" if detail else "")


def _is_loading_message(message: str) -> bool:
    return "正在加载" in message or "loading model" in message.lower()


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()
