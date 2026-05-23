from pathlib import Path
from threading import Event
from typing import Callable

import yaml

from resume_screening.models import PipelineEvent, PipelineStats
from resume_screening.web.runs import RunAlreadyActive, RunManager


def write_config(path: Path, tmp_path: Path) -> None:
    path.write_text(
        yaml.safe_dump(
            {
                "resume_dir": str(tmp_path),
                "job_book": str(tmp_path / "jobs.xlsx"),
                "result_book": str(tmp_path / "result.xlsx"),
                "index_path": str(tmp_path / "processed_index.json"),
                "model": {"provider": "openai-compatible", "base_url": "", "api_key": "", "model": "", "allow_without_model": True},
            },
            allow_unicode=True,
        ),
        encoding="utf-8",
    )


class FakePipeline:
    def __init__(self, event_handler: Callable[[PipelineEvent], None]) -> None:
        self.event_handler = event_handler

    def run(self) -> PipelineStats:
        stats = PipelineStats(processed=1, manual=1)
        self.event_handler(PipelineEvent("run_started", "开始处理 1 个文件", total=1))
        self.event_handler(PipelineEvent("file_started", "正在处理：a.pdf", current=1, total=1, filename="a.pdf"))
        self.event_handler(PipelineEvent("run_completed", "处理完成", current=1, total=1, stats=stats))
        return stats


class CancellablePipeline:
    started = Event()
    can_finish = Event()

    def __init__(self, event_handler: Callable[[PipelineEvent], None], should_stop: Callable[[], bool]) -> None:
        self.event_handler = event_handler
        self.should_stop = should_stop

    def run(self) -> PipelineStats:
        self.event_handler(PipelineEvent("run_started", "开始处理 2 个文件", total=2))
        self.event_handler(PipelineEvent("file_started", "正在处理：a.pdf", current=1, total=2, filename="a.pdf"))
        self.started.set()
        self.can_finish.wait(timeout=2)
        stats = PipelineStats(processed=1, manual=1)
        if self.should_stop():
            self.event_handler(PipelineEvent("run_cancelled", "筛选任务已停止，已保存已完成结果", current=1, total=2, stats=stats))
        return stats


def test_run_manager_records_completed_status(tmp_path: Path) -> None:
    config_path = tmp_path / "config.yaml"
    write_config(config_path, tmp_path)
    manager = RunManager(config_path, pipeline_factory=lambda config, handler, should_stop: FakePipeline(handler))

    run = manager.start()
    manager.wait(run.run_id, timeout_seconds=2)
    snapshot = manager.get(run.run_id)

    assert snapshot.state == "completed"
    assert snapshot.stats["processed"] == 1
    assert snapshot.logs[-1]["message"] == "筛选任务已完成"


def test_run_manager_rejects_second_active_run(tmp_path: Path) -> None:
    config_path = tmp_path / "config.yaml"
    write_config(config_path, tmp_path)

    class BlockingPipeline:
        def __init__(self, event_handler: Callable[[PipelineEvent], None]) -> None:
            self.event_handler = event_handler

        def run(self) -> PipelineStats:
            self.event_handler(PipelineEvent("run_started", "开始处理", total=1))
            import time

            time.sleep(0.5)
            return PipelineStats()

    manager = RunManager(config_path, pipeline_factory=lambda config, handler, should_stop: BlockingPipeline(handler))
    first = manager.start()

    try:
        try:
            manager.start()
            raise AssertionError("second run should fail")
        except RunAlreadyActive as exc:
            assert exc.run_id == first.run_id
    finally:
        manager.wait(first.run_id, timeout_seconds=2)


def test_run_manager_can_cancel_active_run(tmp_path: Path) -> None:
    CancellablePipeline.started.clear()
    CancellablePipeline.can_finish.clear()
    config_path = tmp_path / "config.yaml"
    write_config(config_path, tmp_path)
    manager = RunManager(config_path, pipeline_factory=lambda config, handler, should_stop: CancellablePipeline(handler, should_stop))

    run = manager.start()
    assert CancellablePipeline.started.wait(timeout=2)
    cancelling = manager.cancel(run.run_id)
    assert cancelling.state == "stopping"
    CancellablePipeline.can_finish.set()
    manager.wait(run.run_id, timeout_seconds=2)
    snapshot = manager.get(run.run_id)

    assert snapshot.state == "cancelled"
    assert snapshot.stats["processed"] == 1
    assert any(log["message"] == "已请求停止筛选任务" for log in snapshot.logs)
