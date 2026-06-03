from __future__ import annotations

from dataclasses import asdict, dataclass
from pathlib import Path
from threading import Event, Lock, Thread
from typing import Any, Literal
from urllib.parse import unquote, urlparse
from uuid import uuid4

from fastapi import FastAPI, HTTPException
import httpx
from pydantic import BaseModel, ValidationError

from resume_screening.config import AppConfig
from resume_screening.local_model import LocalModelDownloadPlan, LocalModelManager
from resume_screening.web.config_store import load_config_for_web

DownloadState = Literal["queued", "running", "completed", "cancelled", "failed"]


class DownloadRequest(BaseModel):
    url: str | None = None
    size_bytes: int | None = None
    sha256: str | None = None


@dataclass
class DownloadTaskSnapshot:
    task_id: str
    state: DownloadState
    display_name: str
    bytes_downloaded: int = 0
    total_bytes: int = 0
    target_path: str = ""
    error: str = ""
    message: str = ""


class LocalModelDownloadTaskManager:
    def __init__(self, config_path: Path) -> None:
        self.config_path = config_path
        self._lock = Lock()
        self._tasks: dict[str, DownloadTaskSnapshot] = {}
        self._cancel_events: dict[str, Event] = {}

    def status(self) -> dict[str, Any]:
        return self._manager().status().to_dict()

    def download_plan(self) -> dict[str, Any]:
        return self._manager().download_plan().to_dict()

    def start_download(self, request: DownloadRequest) -> DownloadTaskSnapshot:
        manager = self._manager()
        plan = self._with_request_overrides(manager.download_plan(), request)
        task_id = uuid4().hex
        snapshot = DownloadTaskSnapshot(
            task_id=task_id,
            state="queued",
            display_name=plan.display_name,
            total_bytes=plan.size_bytes,
            target_path=plan.target_path,
            message="等待下载",
        )
        cancel_event = Event()
        with self._lock:
            self._tasks[task_id] = snapshot
            self._cancel_events[task_id] = cancel_event
        thread = Thread(target=self._download_worker, args=(task_id, manager, plan, cancel_event), daemon=True)
        thread.start()
        return self.get(task_id)

    def get(self, task_id: str) -> DownloadTaskSnapshot:
        with self._lock:
            if task_id not in self._tasks:
                raise KeyError(task_id)
            return DownloadTaskSnapshot(**asdict(self._tasks[task_id]))

    def cancel(self, task_id: str) -> DownloadTaskSnapshot:
        with self._lock:
            if task_id not in self._tasks:
                raise KeyError(task_id)
            snapshot = self._tasks[task_id]
            if snapshot.state in {"queued", "running"}:
                snapshot.state = "cancelled"
                snapshot.message = "已取消下载"
                self._cancel_events[task_id].set()
            return DownloadTaskSnapshot(**asdict(snapshot))

    def check(self) -> dict[str, Any]:
        manager = self._manager()
        status = manager.status()
        if status.state != "ready":
            return {"available": False, "message": status.message, "status": status.to_dict()}
        available, message = manager.check_service(timeout_seconds=2)
        return {"available": available, "message": message, "status": status.to_dict()}

    def _download_worker(
        self,
        task_id: str,
        manager: LocalModelManager,
        plan: LocalModelDownloadPlan,
        cancel_event: Event,
    ) -> None:
        partial = Path(plan.target_path).with_suffix(Path(plan.target_path).suffix + ".part")
        try:
            partial.parent.mkdir(parents=True, exist_ok=True)
            self._update(task_id, state="running", message="正在下载模型")
            self._download_to_partial(plan.url, partial, task_id, cancel_event)
            if cancel_event.is_set():
                partial.unlink(missing_ok=True)
                self._update(task_id, state="cancelled", message="已取消下载")
                return
            target = manager.install_downloaded_model(partial, plan)
            self._update(
                task_id,
                state="completed",
                bytes_downloaded=target.stat().st_size,
                total_bytes=target.stat().st_size,
                message="模型下载并安装完成",
            )
        except Exception as exc:
            partial.unlink(missing_ok=True)
            self._update(task_id, state="failed", error=str(exc), message="模型下载失败")

    def _download_to_partial(self, url: str, partial: Path, task_id: str, cancel_event: Event) -> None:
        parsed = urlparse(url)
        if parsed.scheme == "file":
            source = Path(unquote(parsed.path))
            total = source.stat().st_size
            self._update(task_id, total_bytes=total)
            with source.open("rb") as reader, partial.open("wb") as writer:
                while not cancel_event.is_set():
                    chunk = reader.read(1024 * 1024)
                    if not chunk:
                        break
                    writer.write(chunk)
                    self._update(task_id, bytes_downloaded=writer.tell())
            return

        with httpx.stream("GET", url, follow_redirects=True, timeout=60) as response:
            response.raise_for_status()
            total = int(response.headers.get("content-length") or 0)
            if total:
                self._update(task_id, total_bytes=total)
            with partial.open("wb") as writer:
                for chunk in response.iter_bytes():
                    if cancel_event.is_set():
                        break
                    writer.write(chunk)
                    self._update(task_id, bytes_downloaded=writer.tell())

    def _manager(self) -> LocalModelManager:
        try:
            config = AppConfig.model_validate(load_config_for_web(self.config_path))
        except (ValueError, ValidationError) as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        if config.model.provider != "local-qwen":
            raise HTTPException(status_code=400, detail="当前未选择本地模型模式")
        return LocalModelManager(config.model)

    def _with_request_overrides(
        self,
        plan: LocalModelDownloadPlan,
        request: DownloadRequest,
    ) -> LocalModelDownloadPlan:
        return LocalModelDownloadPlan(
            display_name=plan.display_name,
            url=request.url or plan.url,
            target_path=plan.target_path,
            size_bytes=request.size_bytes or plan.size_bytes,
            sha256=request.sha256 if request.sha256 is not None else plan.sha256,
            source_page=plan.source_page,
        )

    def _update(self, task_id: str, **changes: Any) -> None:
        with self._lock:
            snapshot = self._tasks[task_id]
            for key, value in changes.items():
                setattr(snapshot, key, value)


def register_local_model_routes(app: FastAPI, config_path: Path) -> None:
    manager = LocalModelDownloadTaskManager(config_path)

    @app.get("/api/local-model/status")
    def get_local_model_status() -> dict[str, Any]:
        return {"status": manager.status()}

    @app.get("/api/local-model/download-plan")
    def get_local_model_download_plan() -> dict[str, Any]:
        return {"plan": manager.download_plan()}

    @app.post("/api/local-model/download")
    def start_local_model_download(payload: dict[str, Any] | None = None) -> dict[str, Any]:
        request = DownloadRequest.model_validate(payload or {})
        return {"task": asdict(manager.start_download(request))}

    @app.get("/api/local-model/download/{task_id}")
    def get_local_model_download(task_id: str) -> dict[str, Any]:
        try:
            return {"task": asdict(manager.get(task_id))}
        except KeyError as exc:
            raise HTTPException(status_code=404, detail="download task not found") from exc

    @app.post("/api/local-model/download/{task_id}/cancel")
    def cancel_local_model_download(task_id: str) -> dict[str, Any]:
        try:
            return {"task": asdict(manager.cancel(task_id))}
        except KeyError as exc:
            raise HTTPException(status_code=404, detail="download task not found") from exc

    @app.post("/api/local-model/check")
    def check_local_model() -> dict[str, Any]:
        return manager.check()
