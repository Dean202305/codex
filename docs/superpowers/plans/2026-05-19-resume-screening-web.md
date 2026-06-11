# Resume Screening Web Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a double-click local web interface that lets the user configure, precheck, run, and monitor the existing resume screening automation from a React wizard.

**Architecture:** Keep the existing CLI screening pipeline as the core engine. Add a FastAPI backend that reads and writes `config.yaml`, runs lightweight prechecks, starts one background screening run at a time, and serves the React frontend. The React app only talks to the local backend; all local file access stays in Python.

**Tech Stack:** Python 3.11+, FastAPI, Uvicorn, Pydantic, PyYAML, OpenPyXL, Typer, pytest, React, Vite.

---

## File Structure

- Modify `pyproject.toml`: add FastAPI/Uvicorn dependencies and package static assets.
- Modify `src/resume_screening/cli.py`: add a `web` command for the local server.
- Modify `src/resume_screening/models.py`: add pipeline event dataclasses.
- Modify `src/resume_screening/pipeline.py`: accept an optional event handler and emit progress events.
- Create `src/resume_screening/web/__init__.py`: package marker for the web layer.
- Create `src/resume_screening/web/config_store.py`: read, merge, validate, and save local configuration.
- Create `src/resume_screening/web/precheck.py`: run lightweight local file and workbook checks.
- Create `src/resume_screening/web/runs.py`: manage background run state, logs, progress, statistics, and single-run locking.
- Create `src/resume_screening/web/app.py`: FastAPI app factory, JSON endpoints, and static React serving.
- Create `web/package.json`: frontend scripts and dependencies.
- Create `web/vite.config.js`: Vite build config that outputs static files into the Python package.
- Create `web/index.html`: React app shell.
- Create `web/src/main.jsx`: React entry point.
- Create `web/src/App.jsx`: wizard UI and API calls.
- Create `web/src/styles.css`: local app styling.
- Create `启动简历筛选网页版.command`: double-click launcher.
- Modify `README.md` and `使用说明.md`: add web startup and API configuration instructions.
- Create tests under `tests/` for web config, precheck, run manager, API endpoints, CLI help, and pipeline event emission.

## Task 1: Add Web Dependencies and Config Store

**Files:**
- Modify: `pyproject.toml`
- Create: `src/resume_screening/web/__init__.py`
- Create: `src/resume_screening/web/config_store.py`
- Test: `tests/test_web_config_store.py`

- [ ] **Step 1: Write failing config-store tests**

```python
# tests/test_web_config_store.py
from pathlib import Path

import yaml

from resume_screening.web.config_store import config_to_public_dict, load_config_for_web, save_config_for_web


def test_load_config_for_web_uses_example_defaults_when_missing(tmp_path: Path) -> None:
    config_path = tmp_path / "config.yaml"

    data = load_config_for_web(config_path)

    assert data["resume_dir"] == "/Users/mac/Downloads"
    assert data["job_book"].endswith("小A自动化岗位说明书.xlsx")
    assert data["result_book"].endswith("小A科技（北京）组织招聘.xlsx")
    assert data["model"]["allow_without_model"] is True


def test_save_config_for_web_round_trips_paths_and_model(tmp_path: Path) -> None:
    config_path = tmp_path / "config.yaml"
    saved = save_config_for_web(
        config_path,
        {
            "resume_dir": str(tmp_path / "resumes"),
            "job_book": str(tmp_path / "jobs.xlsx"),
            "result_book": str(tmp_path / "result.xlsx"),
            "default_source_channel": "Boss直聘",
            "default_interviewer": "小A",
            "index_path": str(tmp_path / "processed_index.json"),
            "ocr_command": "tesseract",
            "model": {
                "provider": "openai-compatible",
                "base_url": "https://api.example.com/v1",
                "api_key": "sk-test",
                "model": "gpt-test",
                "timeout_seconds": 30,
                "temperature": 0.1,
                "allow_without_model": False,
            },
            "screening": {
                "score_pass": 8,
                "score_excellent": 9,
                "categories": {
                    "recommend": "推荐初试",
                    "consider": "可考虑",
                    "manual": "待人工二筛",
                    "reject": "未通过",
                },
            },
        },
    )

    raw = yaml.safe_load(config_path.read_text(encoding="utf-8"))

    assert saved.resume_dir == tmp_path / "resumes"
    assert raw["model"]["api_key"] == "sk-test"
    assert raw["default_source_channel"] == "Boss直聘"


def test_config_to_public_dict_serializes_paths() -> None:
    data = load_config_for_web(Path("config.example.yaml"))

    public = config_to_public_dict(data)

    assert isinstance(public["resume_dir"], str)
    assert isinstance(public["model"]["timeout_seconds"], int)
```

- [ ] **Step 2: Run tests and verify failure**

Run: `pytest tests/test_web_config_store.py -v`

Expected: FAIL with `ModuleNotFoundError: No module named 'resume_screening.web'`.

- [ ] **Step 3: Add dependencies and package data**

```toml
# pyproject.toml
dependencies = [
  "typer>=0.12",
  "pydantic>=2.7",
  "pyyaml>=6.0",
  "openpyxl>=3.1",
  "pypdf>=4.2",
  "python-docx>=1.1",
  "python-pptx>=0.6",
  "httpx>=0.27",
  "fastapi>=0.111",
  "uvicorn>=0.30",
]

[tool.setuptools.package-data]
"resume_screening.web" = ["static/**/*"]
```

- [ ] **Step 4: Create the web package marker**

```python
# src/resume_screening/web/__init__.py
"""Local web interface for resume screening."""
```

- [ ] **Step 5: Implement config store helpers**

```python
# src/resume_screening/web/config_store.py
from __future__ import annotations

from copy import deepcopy
from pathlib import Path
from typing import Any

import yaml

from resume_screening.config import AppConfig


DEFAULT_CONFIG: dict[str, Any] = {
    "resume_dir": "/Users/mac/Downloads",
    "job_book": "/Users/mac/Downloads/小A自动化岗位说明书.xlsx",
    "result_book": "/Users/mac/Downloads/小A科技（北京）组织招聘.xlsx",
    "default_source_channel": "",
    "default_interviewer": "",
    "index_path": "data/processed_index.json",
    "ocr_command": "tesseract",
    "model": {
        "provider": "openai-compatible",
        "base_url": "",
        "api_key": "",
        "model": "",
        "timeout_seconds": 60,
        "temperature": 0.1,
        "allow_without_model": True,
    },
    "screening": {
        "score_pass": 8,
        "score_excellent": 9,
        "categories": {
            "recommend": "推荐初试",
            "consider": "可考虑",
            "manual": "待人工二筛",
            "reject": "未通过",
        },
    },
}


def _deep_merge(base: dict[str, Any], overlay: dict[str, Any]) -> dict[str, Any]:
    merged = deepcopy(base)
    for key, value in overlay.items():
        if isinstance(value, dict) and isinstance(merged.get(key), dict):
            merged[key] = _deep_merge(merged[key], value)
        else:
            merged[key] = value
    return merged


def _read_yaml_mapping(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    if raw is None:
        return {}
    if not isinstance(raw, dict):
        raise ValueError("config file must contain a YAML mapping")
    return raw


def load_config_for_web(path: Path) -> dict[str, Any]:
    return _deep_merge(DEFAULT_CONFIG, _read_yaml_mapping(path))


def save_config_for_web(path: Path, data: dict[str, Any]) -> AppConfig:
    merged = _deep_merge(DEFAULT_CONFIG, data)
    validated = AppConfig.model_validate(merged)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(yaml.safe_dump(merged, allow_unicode=True, sort_keys=False), encoding="utf-8")
    return validated


def config_to_public_dict(data: dict[str, Any]) -> dict[str, Any]:
    public = deepcopy(data)
    for key in ("resume_dir", "job_book", "result_book", "index_path"):
        if key in public:
            public[key] = str(public[key])
    return public
```

- [ ] **Step 6: Run tests and verify pass**

Run: `pytest tests/test_web_config_store.py -v`

Expected: PASS.

- [ ] **Step 7: Commit**

```bash
git add pyproject.toml src/resume_screening/web/__init__.py src/resume_screening/web/config_store.py tests/test_web_config_store.py
git commit -m "feat: add web config store"
```

## Task 2: Add Lightweight Precheck Service

**Files:**
- Create: `src/resume_screening/web/precheck.py`
- Test: `tests/test_web_precheck.py`

- [ ] **Step 1: Write failing precheck tests**

```python
# tests/test_web_precheck.py
from pathlib import Path

from openpyxl import Workbook

from resume_screening.config import AppConfig
from resume_screening.web.precheck import run_precheck


def create_result_book(path: Path) -> None:
    workbook = Workbook()
    sheet = workbook.active
    sheet.title = "多维表格"
    sheet.append(["ID", "当前阶段", "候选人", "附件", "岗位方向", "来源渠道", "候选人摘要（妙记）", "量化打分", "可投入周期", "面试负责人", "下次动作日", "不推进原因", "推荐/触达人"])
    workbook.save(path)


def create_job_book(path: Path) -> None:
    workbook = Workbook()
    template = workbook.active
    template.title = "模板"
    job = workbook.create_sheet("财务总监")
    job.append(["岗位名称", "财务总监", "学历", "本科"])
    job.append(["工作经验", "8年以上", "具体描述", "负责公司财务管理"])
    job.append(["1. 核心职责", "预算、核算、风控"])
    workbook.save(path)


def make_config(tmp_path: Path) -> AppConfig:
    resume_dir = tmp_path / "resumes"
    resume_dir.mkdir()
    (resume_dir / "【财务总监_北京 18-28K】郭燕婷 10年以上.pdf").write_text("fake", encoding="utf-8")
    job_book = tmp_path / "jobs.xlsx"
    result_book = tmp_path / "result.xlsx"
    create_job_book(job_book)
    create_result_book(result_book)
    return AppConfig.model_validate(
        {
            "resume_dir": resume_dir,
            "job_book": job_book,
            "result_book": result_book,
            "index_path": tmp_path / "processed_index.json",
            "model": {"provider": "openai-compatible", "base_url": "", "api_key": "", "model": "", "allow_without_model": True},
        }
    )


def test_precheck_passes_for_valid_local_files(tmp_path: Path) -> None:
    result = run_precheck(make_config(tmp_path))

    assert result.status == "pass"
    assert result.resume_file_count == 1
    assert any(item.name == "岗位说明书" and item.status == "pass" for item in result.items)


def test_precheck_fails_when_result_book_is_missing(tmp_path: Path) -> None:
    config = make_config(tmp_path)
    config.result_book.unlink()

    result = run_precheck(config)

    assert result.status == "fail"
    assert any(item.name == "招聘结果表" and item.status == "fail" for item in result.items)
```

- [ ] **Step 2: Run tests and verify failure**

Run: `pytest tests/test_web_precheck.py -v`

Expected: FAIL because `resume_screening.web.precheck` does not exist.

- [ ] **Step 3: Implement precheck service**

```python
# src/resume_screening/web/precheck.py
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal

from openpyxl import load_workbook

from resume_screening.config import AppConfig
from resume_screening.extractors import SUPPORTED_EXTENSIONS
from resume_screening.job_requirements import load_job_requirements

CheckStatus = Literal["pass", "warning", "fail"]


@dataclass(frozen=True)
class PrecheckItem:
    name: str
    status: CheckStatus
    message: str


@dataclass(frozen=True)
class PrecheckResult:
    status: CheckStatus
    resume_file_count: int
    usable_job_sheet_count: int
    items: list[PrecheckItem] = field(default_factory=list)


def _supported_resume_count(resume_dir: Path, job_book: Path, result_book: Path) -> int:
    if not resume_dir.exists() or not resume_dir.is_dir():
        return 0
    skip = {job_book.resolve(), result_book.resolve()}
    count = 0
    for path in resume_dir.iterdir():
        if not path.is_file():
            continue
        if path.resolve() in skip:
            continue
        if path.suffix.lower() in SUPPORTED_EXTENSIONS:
            count += 1
    return count


def _is_writable_file(path: Path) -> bool:
    if not path.exists() or not path.is_file():
        return False
    try:
        with path.open("ab"):
            return True
    except OSError:
        return False


def _overall_status(items: list[PrecheckItem]) -> CheckStatus:
    statuses = [item.status for item in items]
    if "fail" in statuses:
        return "fail"
    if "warning" in statuses:
        return "warning"
    return "pass"


def run_precheck(config: AppConfig) -> PrecheckResult:
    items: list[PrecheckItem] = []

    resume_count = _supported_resume_count(config.resume_dir, config.job_book, config.result_book)
    if not config.resume_dir.exists() or not config.resume_dir.is_dir():
        items.append(PrecheckItem("简历文件夹", "fail", f"文件夹不存在：{config.resume_dir}"))
    elif resume_count == 0:
        items.append(PrecheckItem("简历文件夹", "warning", "没有找到支持格式的简历文件"))
    else:
        items.append(PrecheckItem("简历文件夹", "pass", f"找到 {resume_count} 个支持格式文件"))

    usable_jobs = 0
    if not config.job_book.exists():
        items.append(PrecheckItem("岗位说明书", "fail", f"文件不存在：{config.job_book}"))
    else:
        try:
            jobs = load_job_requirements(config.job_book)
            usable_jobs = sum(1 for job in jobs.values() if job.is_complete)
            if usable_jobs == 0:
                items.append(PrecheckItem("岗位说明书", "warning", "未找到完整岗位说明书 sheet"))
            else:
                items.append(PrecheckItem("岗位说明书", "pass", f"找到 {usable_jobs} 个完整岗位 sheet"))
        except Exception as exc:
            items.append(PrecheckItem("岗位说明书", "fail", f"读取失败：{exc}"))

    if not config.result_book.exists():
        items.append(PrecheckItem("招聘结果表", "fail", f"文件不存在：{config.result_book}"))
    else:
        try:
            workbook = load_workbook(config.result_book)
            workbook.close()
            if _is_writable_file(config.result_book):
                items.append(PrecheckItem("招聘结果表", "pass", "结果表存在且可写"))
            else:
                items.append(PrecheckItem("招聘结果表", "fail", "结果表不可写，可能已被 Excel 锁定"))
        except Exception as exc:
            items.append(PrecheckItem("招聘结果表", "fail", f"打开失败：{exc}"))

    model = config.model
    missing_model = [name for name in ("base_url", "api_key", "model") if not getattr(model, name)]
    if model.allow_without_model:
        items.append(PrecheckItem("模型配置", "warning", "当前允许无模型运行，简历会进入待人工二筛"))
    elif missing_model:
        items.append(PrecheckItem("模型配置", "fail", f"缺少模型配置：{', '.join(missing_model)}"))
    else:
        items.append(PrecheckItem("模型配置", "pass", f"模型已配置：{model.model}"))

    return PrecheckResult(
        status=_overall_status(items),
        resume_file_count=resume_count,
        usable_job_sheet_count=usable_jobs,
        items=items,
    )
```

- [ ] **Step 4: Run tests and verify pass**

Run: `pytest tests/test_web_precheck.py -v`

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/resume_screening/web/precheck.py tests/test_web_precheck.py
git commit -m "feat: add web precheck service"
```

## Task 3: Emit Pipeline Progress Events

**Files:**
- Modify: `src/resume_screening/models.py`
- Modify: `src/resume_screening/pipeline.py`
- Test: `tests/test_pipeline_events.py`

- [ ] **Step 1: Write failing pipeline event test**

```python
# tests/test_pipeline_events.py
from pathlib import Path

from docx import Document
from openpyxl import Workbook

from resume_screening.config import AppConfig
from resume_screening.models import PipelineEvent
from resume_screening.pipeline import ScreeningPipeline


def create_result_book(path: Path) -> None:
    workbook = Workbook()
    sheet = workbook.active
    sheet.title = "多维表格"
    sheet.append(["ID", "当前阶段", "候选人", "附件", "岗位方向", "来源渠道", "候选人摘要（妙记）", "量化打分", "可投入周期", "面试负责人", "下次动作日", "不推进原因", "推荐/触达人"])
    workbook.save(path)


def create_incomplete_job_book(path: Path) -> None:
    workbook = Workbook()
    template = workbook.active
    template.title = "模板"
    job = workbook.create_sheet("财务总监")
    job.append(["岗位说明书"])
    job.append(["一、基本信息"])
    workbook.save(path)


def test_pipeline_emits_run_and_file_events(tmp_path: Path) -> None:
    resume_dir = tmp_path / "resumes"
    resume_dir.mkdir()
    resume = resume_dir / "【财务总监_北京 18-28K】郭燕婷 10年以上.docx"
    document = Document()
    document.add_paragraph("郭燕婷，10年以上财务经验。")
    document.save(resume)
    job_book = tmp_path / "jobs.xlsx"
    result_book = tmp_path / "result.xlsx"
    create_incomplete_job_book(job_book)
    create_result_book(result_book)
    events: list[PipelineEvent] = []
    config = AppConfig.model_validate(
        {
            "resume_dir": resume_dir,
            "job_book": job_book,
            "result_book": result_book,
            "index_path": tmp_path / "processed_index.json",
            "model": {"provider": "openai-compatible", "base_url": "", "api_key": "", "model": "", "allow_without_model": True},
        }
    )

    stats = ScreeningPipeline(config, event_handler=events.append).run()

    assert stats.processed == 1
    assert [event.type for event in events] == ["run_started", "file_started", "file_completed", "run_completed"]
    assert events[1].filename == resume.name
    assert events[-1].stats is stats
```

- [ ] **Step 2: Run test and verify failure**

Run: `pytest tests/test_pipeline_events.py -v`

Expected: FAIL because `PipelineEvent` and the `event_handler` argument do not exist.

- [ ] **Step 3: Add pipeline event model**

```python
# src/resume_screening/models.py
from typing import Any, Literal


@dataclass(frozen=True)
class PipelineEvent:
    type: Literal["run_started", "file_started", "file_completed", "run_completed", "warning"]
    message: str
    current: int = 0
    total: int = 0
    filename: str = ""
    category: str = ""
    stats: PipelineStats | None = None
```

- [ ] **Step 4: Emit events from the pipeline**

```python
# src/resume_screening/pipeline.py
from collections.abc import Callable

from resume_screening.models import PipelineEvent


class ScreeningPipeline:
    def __init__(self, config: AppConfig, event_handler: Callable[[PipelineEvent], None] | None = None) -> None:
        self.config = config
        self.event_handler = event_handler

    def _emit(self, event: PipelineEvent) -> None:
        if self.event_handler is not None:
            self.event_handler(event)

    def run(self) -> PipelineStats:
        jobs = load_job_requirements(self.config.job_book)
        writer = ResultWorkbookWriter(self.config.result_book)
        index = DuplicateIndex.load(self.config.index_path)
        client = None if self.config.model.allow_without_model else ModelClient(self.config.model)
        stats = PipelineStats()
        files = self._resume_files()
        self._emit(PipelineEvent("run_started", f"开始处理 {len(files)} 个文件", total=len(files)))

        for current, path in enumerate(files, start=1):
            self._emit(PipelineEvent("file_started", f"正在处理：{path.name}", current=current, total=len(files), filename=path.name))
            parsed = parse_resume_filename(path)
            extraction = extract_text(path, self.config.ocr_command)
            duplicate = index.find(extraction.text) if extraction.text else DuplicateMatch(False)
            result = self._screen(parsed, extraction, jobs, client)
            row_id = writer.append_result(
                parsed=parsed,
                result=result,
                duplicate=duplicate,
                extraction_errors=extraction.errors,
                default_source_channel=self.config.default_source_channel,
                default_interviewer=self.config.default_interviewer,
            )
            if extraction.text:
                index.add(extraction.text, path.name, row_id, parsed.candidate_name, parsed.job_name)
            stats.processed += 1
            stats.count_category(result.category)
            if duplicate.is_duplicate:
                stats.duplicate += 1
            if not parsed.is_standard:
                stats.non_standard_names += 1
            if extraction.errors:
                stats.extraction_failures += 1
            if any(item.startswith("模型评估失败") for item in result.missing_information):
                stats.model_failures += 1
            self._emit(PipelineEvent("file_completed", f"完成：{path.name} -> {result.category}", current=current, total=len(files), filename=path.name, category=result.category, stats=stats))

        writer.save()
        index.save()
        self._emit(PipelineEvent("run_completed", "处理完成", current=len(files), total=len(files), stats=stats))
        return stats
```

- [ ] **Step 5: Run focused tests**

Run: `pytest tests/test_pipeline_events.py tests/test_pipeline.py tests/test_cli.py -v`

Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add src/resume_screening/models.py src/resume_screening/pipeline.py tests/test_pipeline_events.py
git commit -m "feat: emit pipeline progress events"
```

## Task 4: Add Background Run Manager

**Files:**
- Create: `src/resume_screening/web/runs.py`
- Test: `tests/test_web_runs.py`

- [ ] **Step 1: Write failing run-manager tests**

```python
# tests/test_web_runs.py
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
    assert snapshot.logs[-1]["message"] == "处理完成"


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
```

- [ ] **Step 2: Run tests and verify failure**

Run: `pytest tests/test_web_runs.py -v`

Expected: FAIL because `resume_screening.web.runs` does not exist.

- [ ] **Step 3: Implement run manager**

```python
# src/resume_screening/web/runs.py
from __future__ import annotations

from collections.abc import Callable
from copy import deepcopy
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from threading import Lock, Thread
from typing import Literal
from uuid import uuid4

from resume_screening.config import AppConfig, load_config
from resume_screening.models import PipelineEvent, PipelineStats
from resume_screening.pipeline import ScreeningPipeline

RunState = Literal["queued", "running", "completed", "failed"]


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
        pipeline_factory: Callable[[AppConfig, Callable[[PipelineEvent], None]], object] | None = None,
    ) -> None:
        self.config_path = config_path
        self.pipeline_factory = pipeline_factory or (lambda config, handler: ScreeningPipeline(config, event_handler=handler))
        self._lock = Lock()
        self._runs: dict[str, RunSnapshot] = {}
        self._threads: dict[str, Thread] = {}
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
            thread = Thread(target=self._run_worker, args=(run_id,), daemon=True)
            self._threads[run_id] = thread
            thread.start()
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
            pipeline = self.pipeline_factory(config, lambda event: self._handle_event(run_id, event))
            stats = pipeline.run()
            with self._lock:
                self._runs[run_id].state = "completed"
                self._runs[run_id].stats = _stats_dict(stats)
                self._append_log(run_id, "info", "筛选任务已完成")
                self._active_run_id = None
        except Exception as exc:
            with self._lock:
                self._runs[run_id].state = "failed"
                self._runs[run_id].error = str(exc)
                self._append_log(run_id, "error", f"筛选任务失败：{exc}")
                self._active_run_id = None
```

- [ ] **Step 4: Run focused tests**

Run: `pytest tests/test_web_runs.py tests/test_pipeline_events.py -v`

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/resume_screening/web/runs.py tests/test_web_runs.py
git commit -m "feat: add web run manager"
```

## Task 5: Add FastAPI Backend

**Files:**
- Create: `src/resume_screening/web/app.py`
- Test: `tests/test_web_api.py`

- [ ] **Step 1: Write failing API tests**

```python
# tests/test_web_api.py
from pathlib import Path

from fastapi.testclient import TestClient
from openpyxl import Workbook

from resume_screening.web.app import create_app


def create_result_book(path: Path) -> None:
    workbook = Workbook()
    sheet = workbook.active
    sheet.title = "多维表格"
    sheet.append(["ID", "当前阶段", "候选人", "附件", "岗位方向", "来源渠道", "候选人摘要（妙记）", "量化打分", "可投入周期", "面试负责人", "下次动作日", "不推进原因", "推荐/触达人"])
    workbook.save(path)


def create_job_book(path: Path) -> None:
    workbook = Workbook()
    workbook.active.title = "模板"
    job = workbook.create_sheet("财务总监")
    job.append(["岗位名称", "财务总监", "学历", "本科"])
    job.append(["工作经验", "8年以上", "具体描述", "负责公司财务管理"])
    job.append(["1. 核心职责", "预算、核算、风控"])
    workbook.save(path)


def valid_payload(tmp_path: Path) -> dict:
    resume_dir = tmp_path / "resumes"
    resume_dir.mkdir()
    (resume_dir / "【财务总监_北京 18-28K】郭燕婷 10年以上.pdf").write_text("fake", encoding="utf-8")
    job_book = tmp_path / "jobs.xlsx"
    result_book = tmp_path / "result.xlsx"
    create_job_book(job_book)
    create_result_book(result_book)
    return {
        "resume_dir": str(resume_dir),
        "job_book": str(job_book),
        "result_book": str(result_book),
        "index_path": str(tmp_path / "processed_index.json"),
        "ocr_command": "tesseract",
        "model": {"provider": "openai-compatible", "base_url": "", "api_key": "", "model": "", "timeout_seconds": 60, "temperature": 0.1, "allow_without_model": True},
    }


def test_config_endpoints_round_trip(tmp_path: Path) -> None:
    config_path = tmp_path / "config.yaml"
    client = TestClient(create_app(config_path=config_path))

    response = client.post("/api/config", json=valid_payload(tmp_path))
    assert response.status_code == 200
    assert response.json()["config"]["resume_dir"].endswith("resumes")

    response = client.get("/api/config")
    assert response.status_code == 200
    assert response.json()["config"]["result_book"].endswith("result.xlsx")


def test_precheck_endpoint_returns_items(tmp_path: Path) -> None:
    config_path = tmp_path / "config.yaml"
    client = TestClient(create_app(config_path=config_path))
    client.post("/api/config", json=valid_payload(tmp_path))

    response = client.get("/api/precheck")

    assert response.status_code == 200
    body = response.json()
    assert body["status"] in {"pass", "warning"}
    assert body["resume_file_count"] == 1
    assert body["items"]
```

- [ ] **Step 2: Run tests and verify failure**

Run: `pytest tests/test_web_api.py -v`

Expected: FAIL because `resume_screening.web.app` does not exist.

- [ ] **Step 3: Implement FastAPI app factory**

```python
# src/resume_screening/web/app.py
from __future__ import annotations

from dataclasses import asdict, is_dataclass
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import ValidationError

from resume_screening.config import AppConfig
from resume_screening.web.config_store import config_to_public_dict, load_config_for_web, save_config_for_web
from resume_screening.web.precheck import run_precheck
from resume_screening.web.runs import RunAlreadyActive, RunManager


def _jsonable(value: Any) -> Any:
    if is_dataclass(value):
        return asdict(value)
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, list):
        return [_jsonable(item) for item in value]
    if isinstance(value, dict):
        return {key: _jsonable(item) for key, item in value.items()}
    return value


def create_app(config_path: Path = Path("config.yaml"), static_dir: Path | None = None) -> FastAPI:
    app = FastAPI(title="Resume Screening Web")
    manager = RunManager(config_path)
    static_root = static_dir or Path(__file__).parent / "static"

    @app.get("/api/config")
    def get_config() -> dict[str, Any]:
        data = load_config_for_web(config_path)
        return {"config": config_to_public_dict(data)}

    @app.post("/api/config")
    def post_config(payload: dict[str, Any]) -> dict[str, Any]:
        try:
            saved = save_config_for_web(config_path, payload)
        except (ValueError, ValidationError) as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        return {"config": saved.model_dump(mode="json")}

    @app.get("/api/precheck")
    def get_precheck() -> dict[str, Any]:
        try:
            config = AppConfig.model_validate(load_config_for_web(config_path))
        except (ValueError, ValidationError) as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        return _jsonable(run_precheck(config))

    @app.post("/api/runs")
    def start_run() -> dict[str, Any]:
        try:
            return {"run": _jsonable(manager.start())}
        except RunAlreadyActive as exc:
            raise HTTPException(status_code=409, detail={"message": "已有筛选任务运行中", "run_id": exc.run_id}) from exc

    @app.get("/api/runs/{run_id}")
    def get_run(run_id: str) -> dict[str, Any]:
        try:
            return {"run": _jsonable(manager.get(run_id))}
        except KeyError as exc:
            raise HTTPException(status_code=404, detail="run not found") from exc

    if static_root.exists():
        assets = static_root / "assets"
        if assets.exists():
            app.mount("/assets", StaticFiles(directory=assets), name="assets")

        @app.get("/{path:path}")
        def frontend(path: str) -> FileResponse:
            target = static_root / path
            if path and target.exists() and target.is_file():
                return FileResponse(target)
            return FileResponse(static_root / "index.html")

    return app
```

- [ ] **Step 4: Run API tests**

Run: `pytest tests/test_web_api.py tests/test_web_config_store.py tests/test_web_precheck.py -v`

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/resume_screening/web/app.py tests/test_web_api.py
git commit -m "feat: add local web api"
```

## Task 6: Add Web CLI Command and Double-Click Launcher

**Files:**
- Modify: `src/resume_screening/cli.py`
- Create: `启动简历筛选网页版.command`
- Modify: `tests/test_cli.py`

- [ ] **Step 1: Extend CLI tests**

```python
# tests/test_cli.py
def test_cli_module_help_includes_web_command() -> None:
    result = subprocess.run(
        [sys.executable, "-m", "resume_screening.cli", "--help"],
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0
    assert "web" in result.stdout
```

- [ ] **Step 2: Run CLI test and verify failure**

Run: `pytest tests/test_cli.py::test_cli_module_help_includes_web_command -v`

Expected: FAIL because the `web` command is not registered.

- [ ] **Step 3: Add the web command**

```python
# src/resume_screening/cli.py
@app.command()
def web(
    config: Path = typer.Option(Path("config.yaml"), "--config", "-c"),
    host: str = typer.Option("127.0.0.1", "--host"),
    port: int = typer.Option(8765, "--port"),
) -> None:
    """Start the local web interface."""
    import uvicorn

    from resume_screening.web.app import create_app

    typer.echo(f"启动本地网页：http://{host}:{port}")
    uvicorn.run(create_app(config_path=config), host=host, port=port)
```

- [ ] **Step 4: Create the double-click launcher**

```bash
# 启动简历筛选网页版.command
#!/bin/zsh
set -e

PROJECT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$PROJECT_DIR"

if [ ! -d ".venv" ]; then
  python3 -m venv .venv
fi

source ".venv/bin/activate"
python -m pip install -e .

if [ ! -f "config.yaml" ]; then
  cp "config.example.yaml" "config.yaml"
fi

if [ ! -f "src/resume_screening/web/static/index.html" ]; then
  if command -v npm >/dev/null 2>&1; then
    (cd web && npm install && npm run build)
  else
    echo "没有找到 npm，无法构建 React 页面。请先安装 Node.js，或联系 Codex 帮你构建一次。"
    exit 1
  fi
fi

open "http://127.0.0.1:8765"
resume-screening web --config config.yaml --host 127.0.0.1 --port 8765
```

- [ ] **Step 5: Mark launcher executable**

Run: `chmod +x 启动简历筛选网页版.command`

Expected: command exits with code 0.

- [ ] **Step 6: Run CLI tests**

Run: `pytest tests/test_cli.py -v`

Expected: PASS.

- [ ] **Step 7: Commit**

```bash
git add src/resume_screening/cli.py tests/test_cli.py 启动简历筛选网页版.command
git commit -m "feat: add web launcher command"
```

## Task 7: Build the React Wizard

**Files:**
- Create: `web/package.json`
- Create: `web/vite.config.js`
- Create: `web/index.html`
- Create: `web/src/main.jsx`
- Create: `web/src/App.jsx`
- Create: `web/src/styles.css`

- [ ] **Step 1: Create frontend package files**

```json
{
  "name": "resume-screening-web",
  "version": "0.1.0",
  "private": true,
  "type": "module",
  "scripts": {
    "dev": "vite",
    "build": "vite build",
    "preview": "vite preview"
  },
  "dependencies": {
    "@vitejs/plugin-react": "^4.2.1",
    "vite": "^5.4.0",
    "react": "^18.2.0",
    "react-dom": "^18.2.0",
    "lucide-react": "^0.468.0"
  },
  "devDependencies": {}
}
```

```javascript
// web/vite.config.js
import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

export default defineConfig({
  plugins: [react()],
  build: {
    outDir: "../src/resume_screening/web/static",
    emptyOutDir: true,
    rollupOptions: {
      output: {
        entryFileNames: "assets/app.js",
        chunkFileNames: "assets/[name].js",
        assetFileNames: "assets/[name][extname]"
      }
    }
  }
});
```

```html
<!-- web/index.html -->
<!doctype html>
<html lang="zh-CN">
  <head>
    <meta charset="UTF-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1.0" />
    <title>简历初筛工具</title>
  </head>
  <body>
    <div id="root"></div>
    <script type="module" src="/src/main.jsx"></script>
  </body>
</html>
```

- [ ] **Step 2: Create React entry point**

```javascript
// web/src/main.jsx
import React from "react";
import { createRoot } from "react-dom/client";
import { App } from "./App.jsx";
import "./styles.css";

createRoot(document.getElementById("root")).render(
  <React.StrictMode>
    <App />
  </React.StrictMode>
);
```

- [ ] **Step 3: Create the wizard component**

```javascript
// web/src/App.jsx
import { useEffect, useMemo, useState } from "react";
import { CheckCircle2, CircleAlert, FileSpreadsheet, KeyRound, Loader2, Play, Save } from "lucide-react";

const steps = ["文件路径", "模型配置", "运行前预检", "开始筛选"];

const emptyConfig = {
  resume_dir: "",
  job_book: "",
  result_book: "",
  default_source_channel: "",
  default_interviewer: "",
  index_path: "data/processed_index.json",
  ocr_command: "tesseract",
  model: {
    provider: "openai-compatible",
    base_url: "",
    api_key: "",
    model: "",
    timeout_seconds: 60,
    temperature: 0.1,
    allow_without_model: true
  }
};

async function requestJson(path, options = {}) {
  const response = await fetch(path, {
    headers: { "Content-Type": "application/json" },
    ...options
  });
  const body = await response.json();
  if (!response.ok) {
    throw new Error(typeof body.detail === "string" ? body.detail : body.detail?.message || "请求失败");
  }
  return body;
}

export function App() {
  const [step, setStep] = useState(0);
  const [config, setConfig] = useState(emptyConfig);
  const [notice, setNotice] = useState("");
  const [error, setError] = useState("");
  const [precheck, setPrecheck] = useState(null);
  const [run, setRun] = useState(null);
  const [runId, setRunId] = useState("");

  useEffect(() => {
    requestJson("/api/config")
      .then((body) => setConfig({ ...emptyConfig, ...body.config, model: { ...emptyConfig.model, ...body.config.model } }))
      .catch((exc) => setError(exc.message));
  }, []);

  useEffect(() => {
    if (!runId || run?.state === "completed" || run?.state === "failed") return;
    const timer = window.setInterval(() => {
      requestJson(`/api/runs/${runId}`)
        .then((body) => setRun(body.run))
        .catch((exc) => setError(exc.message));
    }, 1200);
    return () => window.clearInterval(timer);
  }, [runId, run?.state]);

  const progress = useMemo(() => {
    if (!run || !run.total) return 0;
    return Math.round((run.current / run.total) * 100);
  }, [run]);

  function updateField(name, value) {
    setConfig((current) => ({ ...current, [name]: value }));
  }

  function updateModel(name, value) {
    setConfig((current) => ({ ...current, model: { ...current.model, [name]: value } }));
  }

  async function saveConfig() {
    setError("");
    setNotice("");
    const body = await requestJson("/api/config", { method: "POST", body: JSON.stringify(config) });
    setConfig({ ...emptyConfig, ...body.config, model: { ...emptyConfig.model, ...body.config.model } });
    setNotice("配置已保存到本地 config.yaml");
  }

  async function runPrecheck() {
    setError("");
    const body = await requestJson("/api/precheck");
    setPrecheck(body);
    setStep(2);
  }

  async function startRun() {
    setError("");
    const body = await requestJson("/api/runs", { method: "POST", body: "{}" });
    setRun(body.run);
    setRunId(body.run.run_id);
    setStep(3);
  }

  return (
    <main className="app-shell">
      <section className="topbar">
        <div>
          <p className="eyebrow">本地运行</p>
          <h1>简历初筛工具</h1>
        </div>
        <div className="stepper">
          {steps.map((label, index) => (
            <button key={label} className={index === step ? "active" : ""} onClick={() => setStep(index)}>
              {index + 1}. {label}
            </button>
          ))}
        </div>
      </section>

      {notice && <div className="notice success"><CheckCircle2 size={18} />{notice}</div>}
      {error && <div className="notice danger"><CircleAlert size={18} />{error}</div>}

      {step === 0 && (
        <section className="panel">
          <h2><FileSpreadsheet size={22} />文件路径</h2>
          <label>简历文件夹<input value={config.resume_dir} onChange={(event) => updateField("resume_dir", event.target.value)} /></label>
          <label>岗位说明书<input value={config.job_book} onChange={(event) => updateField("job_book", event.target.value)} /></label>
          <label>招聘结果表<input value={config.result_book} onChange={(event) => updateField("result_book", event.target.value)} /></label>
          <div className="actions">
            <button onClick={saveConfig}><Save size={18} />保存配置</button>
            <button className="primary" onClick={() => setStep(1)}>下一步</button>
          </div>
        </section>
      )}

      {step === 1 && (
        <section className="panel">
          <h2><KeyRound size={22} />模型配置</h2>
          <label>API 地址<input value={config.model.base_url} onChange={(event) => updateModel("base_url", event.target.value)} /></label>
          <label>API Key<input type="password" value={config.model.api_key} onChange={(event) => updateModel("api_key", event.target.value)} /></label>
          <label>模型名<input value={config.model.model} onChange={(event) => updateModel("model", event.target.value)} /></label>
          <label>超时时间（秒）<input type="number" value={config.model.timeout_seconds} onChange={(event) => updateModel("timeout_seconds", Number(event.target.value))} /></label>
          <label className="checkbox"><input type="checkbox" checked={config.model.allow_without_model} onChange={(event) => updateModel("allow_without_model", event.target.checked)} />允许无模型运行并进入待人工二筛</label>
          <div className="actions">
            <button onClick={saveConfig}><Save size={18} />保存配置</button>
            <button className="primary" onClick={runPrecheck}>运行预检</button>
          </div>
        </section>
      )}

      {step === 2 && (
        <section className="panel">
          <h2>运行前预检</h2>
          {!precheck && <button className="primary" onClick={runPrecheck}>开始预检</button>}
          {precheck && (
            <div className="checks">
              <div className={`summary ${precheck.status}`}>支持格式简历：{precheck.resume_file_count} 个</div>
              {precheck.items.map((item) => <div className={`check ${item.status}`} key={item.name}><strong>{item.name}</strong><span>{item.message}</span></div>)}
              <button className="primary" onClick={startRun}><Play size={18} />开始筛选</button>
            </div>
          )}
        </section>
      )}

      {step === 3 && (
        <section className="panel">
          <h2>{run?.state === "running" ? <Loader2 className="spin" size={22} /> : <Play size={22} />}开始筛选</h2>
          {!run && <button className="primary" onClick={startRun}>开始筛选</button>}
          {run && (
            <>
              <div className="progress"><span style={{ width: `${progress}%` }} /></div>
              <p className="muted">{run.current_file || "等待任务更新"} {run.total ? `${run.current}/${run.total}` : ""}</p>
              <div className="stats">
                {Object.entries(run.stats || {}).map(([key, value]) => <div key={key}><strong>{value}</strong><span>{key}</span></div>)}
              </div>
              <div className="logs">
                {(run.logs || []).map((log, index) => <p key={`${log.timestamp}-${index}`} className={log.level}>{log.message}</p>)}
              </div>
              {run.error && <div className="notice danger">{run.error}</div>}
            </>
          )}
        </section>
      )}
    </main>
  );
}
```

- [ ] **Step 4: Add responsive styling**

```css
/* web/src/styles.css */
:root {
  color: #172033;
  background: #f5f7fb;
  font-family: Inter, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
}

* { box-sizing: border-box; }
body { margin: 0; }
button, input { font: inherit; }

.app-shell {
  max-width: 1120px;
  margin: 0 auto;
  padding: 28px;
}

.topbar {
  display: flex;
  justify-content: space-between;
  gap: 24px;
  align-items: flex-end;
  margin-bottom: 24px;
}

.eyebrow {
  margin: 0 0 6px;
  color: #526070;
  font-size: 14px;
}

h1, h2 { margin: 0; }
h1 { font-size: 34px; }
h2 {
  display: flex;
  align-items: center;
  gap: 10px;
  font-size: 22px;
  margin-bottom: 20px;
}

.stepper {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 8px;
}

.stepper button,
.actions button,
.checks button {
  border: 1px solid #ccd4df;
  border-radius: 8px;
  background: #fff;
  color: #172033;
  min-height: 40px;
  padding: 0 14px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: 8px;
  cursor: pointer;
}

.stepper .active,
.primary {
  background: #1f6feb !important;
  border-color: #1f6feb !important;
  color: #fff !important;
}

.panel {
  background: #fff;
  border: 1px solid #d9e0ea;
  border-radius: 8px;
  padding: 24px;
}

label {
  display: grid;
  gap: 8px;
  margin-bottom: 16px;
  color: #344054;
}

input {
  width: 100%;
  min-height: 42px;
  border: 1px solid #ccd4df;
  border-radius: 8px;
  padding: 0 12px;
}

.checkbox {
  grid-template-columns: 18px 1fr;
  align-items: center;
}

.checkbox input { min-height: auto; }

.actions {
  display: flex;
  gap: 10px;
  justify-content: flex-end;
  margin-top: 20px;
}

.notice {
  display: flex;
  align-items: center;
  gap: 8px;
  border-radius: 8px;
  padding: 12px 14px;
  margin-bottom: 14px;
}

.success { background: #e8f7ee; color: #176c3a; }
.danger { background: #fdecec; color: #b42318; }

.checks {
  display: grid;
  gap: 12px;
}

.summary,
.check {
  border-radius: 8px;
  padding: 14px;
  border: 1px solid #d9e0ea;
}

.check {
  display: flex;
  justify-content: space-between;
  gap: 16px;
}

.pass { border-color: #92d7aa; }
.warning { border-color: #f4c779; }
.fail { border-color: #ef9a9a; }

.progress {
  height: 10px;
  background: #e8edf5;
  border-radius: 999px;
  overflow: hidden;
}

.progress span {
  display: block;
  height: 100%;
  background: #1f6feb;
  transition: width 0.2s ease;
}

.muted { color: #526070; }

.stats {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(120px, 1fr));
  gap: 10px;
  margin: 18px 0;
}

.stats div {
  border: 1px solid #d9e0ea;
  border-radius: 8px;
  padding: 12px;
}

.stats strong {
  display: block;
  font-size: 24px;
}

.stats span {
  color: #526070;
  font-size: 13px;
}

.logs {
  height: 260px;
  overflow: auto;
  border: 1px solid #d9e0ea;
  border-radius: 8px;
  background: #0f172a;
  padding: 14px;
}

.logs p {
  margin: 0 0 8px;
  color: #dbeafe;
  font-family: ui-monospace, SFMono-Regular, Menlo, monospace;
  font-size: 13px;
}

.logs .error { color: #fecaca; }

.spin {
  animation: spin 1s linear infinite;
}

@keyframes spin {
  to { transform: rotate(360deg); }
}

@media (max-width: 760px) {
  .app-shell { padding: 16px; }
  .topbar { display: block; }
  .stepper { grid-template-columns: 1fr; margin-top: 18px; }
  .actions { flex-direction: column; }
  .check { display: grid; }
}
```

- [ ] **Step 5: Build frontend**

Run:

```bash
cd web
npm install
npm run build
```

Expected: build succeeds and creates `src/resume_screening/web/static/index.html` from the project root.

- [ ] **Step 6: Commit**

```bash
git add web src/resume_screening/web/static
git commit -m "feat: add react web wizard"
```

## Task 8: Document Web Usage and Verify End to End

**Files:**
- Modify: `README.md`
- Modify: `使用说明.md`

- [ ] **Step 1: Add concise web usage docs**

```markdown
## 网页版使用

双击项目目录里的 `启动简历筛选网页版.command`。

第一次启动时脚本会：

1. 创建或复用 `.venv`
2. 安装当前工具
3. 如果没有 `config.yaml`，从 `config.example.yaml` 复制一份
4. 如果 React 页面还没有构建，自动运行 `npm install && npm run build`
5. 打开 `http://127.0.0.1:8765`

页面分四步：

1. 文件路径：确认简历文件夹、岗位说明书、招聘结果表
2. 模型配置：填写 API 地址、API Key、模型名、超时时间
3. 运行前预检：检查文件数量、岗位 sheet、结果表可写、模型配置
4. 开始筛选：查看实时进度、日志和统计

如果模型超时或报错，工具会把对应简历写成 `待人工二筛`，并在日志里显示原因。
```

- [ ] **Step 2: Run Python tests**

Run: `pytest -v`

Expected: PASS.

- [ ] **Step 3: Run frontend build**

Run:

```bash
cd web
npm run build
```

Expected: PASS with Vite build output.

- [ ] **Step 4: Smoke-test the web server**

Run:

```bash
.venv/bin/resume-screening web --config config.example.yaml --host 127.0.0.1 --port 8765
```

Expected: server prints `启动本地网页：http://127.0.0.1:8765`.

Open `http://127.0.0.1:8765` in the in-app browser. Confirm the page loads and the four wizard steps are visible. Stop the server after verification.

- [ ] **Step 5: Commit**

```bash
git add README.md 使用说明.md
git commit -m "docs: explain web interface usage"
```

## Task 9: Final Verification

**Files:**
- No source files changed in this task.

- [ ] **Step 1: Check worktree status**

Run: `git status --short`

Expected: no output.

- [ ] **Step 2: Run full backend tests**

Run: `pytest -v`

Expected: PASS.

- [ ] **Step 3: Run frontend build from a clean shell**

Run:

```bash
cd web
npm run build
```

Expected: PASS.

- [ ] **Step 4: Verify command help**

Run: `.venv/bin/resume-screening --help`

Expected: output includes both `run` and `web`.

- [ ] **Step 5: Verify local page responds**

Run the server:

```bash
.venv/bin/resume-screening web --config config.example.yaml --host 127.0.0.1 --port 8765
```

Open `http://127.0.0.1:8765`. Expected: React wizard loads, `GET /api/config` succeeds, and the UI shows default local paths. Stop the server after verification.
