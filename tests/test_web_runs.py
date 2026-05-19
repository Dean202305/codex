from pathlib import Path
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


def test_run_manager_records_completed_status(tmp_path: Path) -> None:
    config_path = tmp_path / "config.yaml"
    write_config(config_path, tmp_path)
    manager = RunManager(config_path, pipeline_factory=lambda config, handler: FakePipeline(handler))

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

    manager = RunManager(config_path, pipeline_factory=lambda config, handler: BlockingPipeline(handler))
    first = manager.start()

    try:
        try:
            manager.start()
            raise AssertionError("second run should fail")
        except RunAlreadyActive as exc:
            assert exc.run_id == first.run_id
    finally:
        manager.wait(first.run_id, timeout_seconds=2)
