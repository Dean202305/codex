from __future__ import annotations

from collections.abc import Callable
from copy import deepcopy
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from threading import Event, Lock, Thread
from typing import Literal, Protocol
from uuid import uuid4

from resume_screening.config import AppConfig, load_config
from resume_screening.models import PipelineEvent, PipelineStats
from resume_screening.pipeline import ScreeningPipeline

RunState = Literal["queued", "running", "stopping", "completed", "cancelled", "failed"]


class RunnablePipeline(Protocol):
    def run(self) -> PipelineStats:
        pass


class RunAlreadyActive(RuntimeError):
    def __init__(self, run_id: str) -> None:
        super().__init__(f"run already active: {run_id}")
        self.run_id = run_id


@dataclass(frozen=True)
class RunLog:
    timestamp: str
    level: str
    message: str


@dataclass
class RunSnapshot:
    run_id: str
    state: RunState
    current: int = 0
    total: int = 0
    current_file: str = ""
    logs: list[dict[str, str]] = field(default_factory=list)
    stats: dict[str, int] = field(default_factory=dict)
    error: str = ""


def _stats_dict(stats: PipelineStats | None) -> dict[str, int]:
    if stats is None:
        return {}
    return {
        "processed": stats.processed,
        "recommend": stats.recommend,
        "consider": stats.consider,
        "manual": stats.manual,
        "reject": stats.reject,
        "duplicate": stats.duplicate,
        "model_failures": stats.model_failures,
        "extraction_failures": stats.extraction_failures,
        "non_standard_names": stats.non_standard_names,
    }


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


class RunManager:
    def __init__(
        self,
        config_path: Path,
        pipeline_factory: Callable[[AppConfig, Callable[[PipelineEvent], None], Callable[[], bool]], RunnablePipeline] | None = None,
    ) -> None:
        self.config_path = config_path
        self.pipeline_factory = pipeline_factory or (lambda config, handler, should_stop: ScreeningPipeline(config, event_handler=handler, should_stop=should_stop))
        self._lock = Lock()
        self._runs: dict[str, RunSnapshot] = {}
        self._threads: dict[str, Thread] = {}
        self._stop_events: dict[str, Event] = {}
        self._active_run_id: str | None = None

    def start(self) -> RunSnapshot:
        with self._lock:
            if self._active_run_id:
                active = self._runs[self._active_run_id]
                if active.state in {"queued", "running"}:
                    raise RunAlreadyActive(self._active_run_id)
            run_id = uuid4().hex
            snapshot = RunSnapshot(run_id=run_id, state="queued")
            self._runs[run_id] = snapshot
            self._active_run_id = run_id
            self._stop_events[run_id] = Event()
            thread = Thread(target=self._run_worker, args=(run_id,), daemon=True)
            self._threads[run_id] = thread
            thread.start()
            return deepcopy(snapshot)

    def cancel(self, run_id: str) -> RunSnapshot:
        with self._lock:
            if run_id not in self._runs:
                raise KeyError(run_id)
            snapshot = self._runs[run_id]
            if snapshot.state in {"queued", "running", "stopping"}:
                self._stop_events[run_id].set()
                snapshot.state = "stopping"
                self._append_log(run_id, "warning", "已请求停止筛选任务")
            return deepcopy(snapshot)

    def get(self, run_id: str) -> RunSnapshot:
        with self._lock:
            if run_id not in self._runs:
                raise KeyError(run_id)
            return deepcopy(self._runs[run_id])

    def wait(self, run_id: str, timeout_seconds: float) -> None:
        thread = self._threads[run_id]
        thread.join(timeout=timeout_seconds)

    def _append_log(self, run_id: str, level: str, message: str) -> None:
        snapshot = self._runs[run_id]
        snapshot.logs.append(asdict(RunLog(timestamp=_now(), level=level, message=message)))
        snapshot.logs = snapshot.logs[-200:]

    def _handle_event(self, run_id: str, event: PipelineEvent) -> None:
        with self._lock:
            snapshot = self._runs[run_id]
            snapshot.current = event.current
            snapshot.total = event.total
            snapshot.current_file = event.filename
            if event.stats is not None:
                snapshot.stats = _stats_dict(event.stats)
            self._append_log(run_id, "info", event.message)

    def _run_worker(self, run_id: str) -> None:
        try:
            with self._lock:
                self._runs[run_id].state = "running"
                self._append_log(run_id, "info", "筛选任务已启动")
            config = load_config(self.config_path)
            stop_event = self._stop_events[run_id]
            pipeline = self.pipeline_factory(config, lambda event: self._handle_event(run_id, event), stop_event.is_set)
            stats = pipeline.run()
            with self._lock:
                self._runs[run_id].state = "cancelled" if stop_event.is_set() else "completed"
                self._runs[run_id].stats = _stats_dict(stats)
                if stop_event.is_set():
                    self._append_log(run_id, "warning", "筛选任务已停止")
                else:
                    self._append_log(run_id, "info", "筛选任务已完成")
                self._active_run_id = None
        except Exception as exc:
            with self._lock:
                self._runs[run_id].state = "failed"
                self._runs[run_id].error = str(exc)
                self._append_log(run_id, "error", f"筛选任务失败：{exc}")
                self._active_run_id = None
