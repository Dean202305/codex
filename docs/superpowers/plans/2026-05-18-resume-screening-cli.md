# Resume Screening CLI Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a Python command-line tool that scans resumes, rereads the current job requirements workbook, evaluates candidates through a configurable OpenAI-compatible model, and appends screening results to the fixed recruiting workbook without overwriting history.

**Architecture:** The CLI is a thin entry point over a `ScreeningPipeline`. Local modules own deterministic work: config loading, filename parsing, workbook parsing, document text extraction, duplicate detection, model response validation, and Excel writeback. The model adapter only receives normalized resume and job text and returns strict JSON used by the writer.

**Tech Stack:** Python 3.11+, `typer`, `pydantic`, `pyyaml`, `openpyxl`, `pypdf`, `python-docx`, `python-pptx`, `httpx`, `pytest`.

---

## File Structure

- Create `pyproject.toml`: package metadata, CLI entry point, dependencies, pytest config.
- Create `config.example.yaml`: example paths and model settings matching the approved spec.
- Create `src/resume_screening/__init__.py`: package marker and version.
- Create `src/resume_screening/models.py`: shared dataclasses/enums for parsed metadata, job requirements, extraction result, screening result, duplicate match, and pipeline stats.
- Create `src/resume_screening/config.py`: YAML loading and validation.
- Create `src/resume_screening/filename_parser.py`: parse the preferred Chinese filename format and return missing-field diagnostics for non-standard names.
- Create `src/resume_screening/job_requirements.py`: load the job workbook on every run, ignore `模板`, extract row-pair fields, validate completeness.
- Create `src/resume_screening/extractors.py`: extract text from PDF, image OCR, DOC/DOCX, and PPTX.
- Create `src/resume_screening/duplicates.py`: normalize text, compute SHA-256 fingerprints, persist `data/processed_index.json`, detect exact and near matches.
- Create `src/resume_screening/model_client.py`: OpenAI-compatible chat completions client plus strict response validation.
- Create `src/resume_screening/excel_writer.py`: append rows to `多维表格`, add the three approved columns, continue IDs, and mark duplicates red.
- Create `src/resume_screening/pipeline.py`: orchestrate scanning, extraction, matching, model evaluation, fallback manual-review rows, writeback, and summary stats.
- Create `src/resume_screening/cli.py`: `resume-screening run --config config.yaml`.
- Create tests under `tests/` mirroring the modules above.

## Task 1: Project Skeleton and Config

**Files:**
- Create: `pyproject.toml`
- Create: `config.example.yaml`
- Create: `src/resume_screening/__init__.py`
- Create: `src/resume_screening/config.py`
- Test: `tests/test_config.py`

- [ ] **Step 1: Write the failing config tests**

```python
# tests/test_config.py
from pathlib import Path

import pytest
import yaml
from pydantic import ValidationError

from resume_screening.config import AppConfig, load_config


def test_load_config_reads_paths_and_model_settings(tmp_path: Path) -> None:
    config_path = tmp_path / "config.yaml"
    config_path.write_text(
        yaml.safe_dump(
            {
                "resume_dir": "/Users/mac/Downloads",
                "job_book": "/Users/mac/Downloads/小A自动化岗位说明书.xlsx",
                "result_book": "/Users/mac/Downloads/小A科技（北京）组织招聘.xlsx",
                "default_source_channel": "",
                "default_interviewer": "",
                "model": {
                    "provider": "openai-compatible",
                    "base_url": "https://api.example.com/v1",
                    "api_key": "test-key",
                    "model": "screening-model",
                    "timeout_seconds": 60,
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
            allow_unicode=True,
        ),
        encoding="utf-8",
    )

    loaded = load_config(config_path)

    assert loaded.resume_dir == Path("/Users/mac/Downloads")
    assert loaded.model.base_url == "https://api.example.com/v1"
    assert loaded.screening.categories.manual == "待人工二筛"


def test_config_rejects_missing_model_when_manual_mode_disabled() -> None:
    with pytest.raises(ValidationError):
        AppConfig.model_validate(
            {
                "resume_dir": "/Users/mac/Downloads",
                "job_book": "/Users/mac/Downloads/小A自动化岗位说明书.xlsx",
                "result_book": "/Users/mac/Downloads/小A科技（北京）组织招聘.xlsx",
                "model": {
                    "provider": "openai-compatible",
                    "base_url": "",
                    "api_key": "",
                    "model": "",
                    "timeout_seconds": 60,
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
            }
        )
```

- [ ] **Step 2: Run the config tests and verify they fail**

Run: `pytest tests/test_config.py -v`

Expected: FAIL because `resume_screening.config` does not exist.

- [ ] **Step 3: Create package metadata and config implementation**

```toml
# pyproject.toml
[build-system]
requires = ["setuptools>=68", "wheel"]
build-backend = "setuptools.build_meta"

[project]
name = "resume-screening"
version = "0.1.0"
description = "Resume screening CLI for 小A招聘表"
requires-python = ">=3.11"
dependencies = [
  "typer>=0.12",
  "pydantic>=2.7",
  "pyyaml>=6.0",
  "openpyxl>=3.1",
  "pypdf>=4.2",
  "python-docx>=1.1",
  "python-pptx>=0.6",
  "httpx>=0.27",
]

[project.scripts]
resume-screening = "resume_screening.cli:app"

[tool.setuptools.packages.find]
where = ["src"]

[tool.pytest.ini_options]
pythonpath = ["src"]
testpaths = ["tests"]
```

```yaml
# config.example.yaml
resume_dir: "/Users/mac/Downloads"
job_book: "/Users/mac/Downloads/小A自动化岗位说明书.xlsx"
result_book: "/Users/mac/Downloads/小A科技（北京）组织招聘.xlsx"

default_source_channel: ""
default_interviewer: ""
index_path: "data/processed_index.json"
ocr_command: "tesseract"

model:
  provider: "openai-compatible"
  base_url: ""
  api_key: ""
  model: ""
  timeout_seconds: 60
  temperature: 0.1
  allow_without_model: false

screening:
  score_pass: 8
  score_excellent: 9
  categories:
    recommend: "推荐初试"
    consider: "可考虑"
    manual: "待人工二筛"
    reject: "未通过"
```

```python
# src/resume_screening/__init__.py
__version__ = "0.1.0"
```

```python
# src/resume_screening/config.py
from pathlib import Path
from typing import Literal

import yaml
from pydantic import BaseModel, Field, ValidationError, model_validator


class CategoryConfig(BaseModel):
    recommend: str = "推荐初试"
    consider: str = "可考虑"
    manual: str = "待人工二筛"
    reject: str = "未通过"


class ScreeningConfig(BaseModel):
    score_pass: float = 8
    score_excellent: float = 9
    categories: CategoryConfig = Field(default_factory=CategoryConfig)


class ModelConfig(BaseModel):
    provider: Literal["openai-compatible"] = "openai-compatible"
    base_url: str = ""
    api_key: str = ""
    model: str = ""
    timeout_seconds: int = 60
    temperature: float = 0.1
    allow_without_model: bool = False

    @model_validator(mode="after")
    def require_model_config_unless_manual_mode(self) -> "ModelConfig":
        if self.allow_without_model:
            return self
        missing = [name for name in ("base_url", "api_key", "model") if not getattr(self, name)]
        if missing:
            joined = ", ".join(missing)
            raise ValueError(f"model config missing required values: {joined}")
        return self


class AppConfig(BaseModel):
    resume_dir: Path
    job_book: Path
    result_book: Path
    default_source_channel: str = ""
    default_interviewer: str = ""
    index_path: Path = Path("data/processed_index.json")
    ocr_command: str = "tesseract"
    model: ModelConfig
    screening: ScreeningConfig = Field(default_factory=ScreeningConfig)


def load_config(path: Path) -> AppConfig:
    raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        raise ValidationError.from_exception_data("AppConfig", [])
    return AppConfig.model_validate(raw)
```

- [ ] **Step 4: Run the config tests and verify they pass**

Run: `pytest tests/test_config.py -v`

Expected: PASS.

- [ ] **Step 5: Commit project skeleton**

```bash
git add pyproject.toml config.example.yaml src/resume_screening/__init__.py src/resume_screening/config.py tests/test_config.py
git commit -m "feat: add CLI config foundation"
```

## Task 2: Shared Models and Filename Parser

**Files:**
- Create: `src/resume_screening/models.py`
- Create: `src/resume_screening/filename_parser.py`
- Test: `tests/test_filename_parser.py`

- [ ] **Step 1: Write the failing parser tests**

```python
# tests/test_filename_parser.py
from pathlib import Path

from resume_screening.filename_parser import parse_resume_filename


def test_parse_standard_resume_filename() -> None:
    parsed = parse_resume_filename(Path("【财务总监_北京 18-28K】郭燕婷 10年以上.pdf"))

    assert parsed.is_standard is True
    assert parsed.job_name == "财务总监"
    assert parsed.expected_location == "北京"
    assert parsed.salary_range == "18-28K"
    assert parsed.candidate_name == "郭燕婷"
    assert parsed.work_experience == "10年以上"
    assert parsed.missing_fields == []


def test_parse_non_standard_filename_marks_missing_fields() -> None:
    parsed = parse_resume_filename(Path("郭燕婷-简历.pdf"))

    assert parsed.is_standard is False
    assert parsed.candidate_name == "郭燕婷"
    assert "文件名不规范" in parsed.missing_fields
    assert "岗位名称" in parsed.missing_fields


def test_parse_standard_filename_without_salary_marks_salary_missing() -> None:
    parsed = parse_resume_filename(Path("【算法工程师_北京】张三 3年.pdf"))

    assert parsed.is_standard is True
    assert parsed.job_name == "算法工程师"
    assert parsed.expected_location == "北京"
    assert parsed.salary_range == ""
    assert "岗位标注薪资" in parsed.missing_fields
```

- [ ] **Step 2: Run parser tests and verify they fail**

Run: `pytest tests/test_filename_parser.py -v`

Expected: FAIL because the parser module does not exist.

- [ ] **Step 3: Implement shared models and parser**

```python
# src/resume_screening/models.py
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


CATEGORY_RECOMMEND = "推荐初试"
CATEGORY_CONSIDER = "可考虑"
CATEGORY_MANUAL = "待人工二筛"
CATEGORY_REJECT = "未通过"


@dataclass(frozen=True)
class ParsedFilename:
    path: Path
    is_standard: bool
    job_name: str = ""
    expected_location: str = ""
    salary_range: str = ""
    candidate_name: str = ""
    work_experience: str = ""
    missing_fields: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class JobRequirement:
    sheet_name: str
    fields: dict[str, str]
    raw_text: str
    is_complete: bool
    missing_fields: list[str]


@dataclass(frozen=True)
class ExtractionResult:
    text: str
    method: str
    errors: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class DuplicateMatch:
    is_duplicate: bool
    matched_filename: str = ""
    matched_row_id: int | None = None
    similarity: float = 0.0


@dataclass(frozen=True)
class ScreeningScores:
    ability: float
    ego: float
    desire: float
    learning_ability: float
    job_fit: float
    experience_fit: float
    skill_fit: float
    stability_risk: float


@dataclass(frozen=True)
class ScreeningResult:
    category: str
    overall_score: float
    summary: str
    screening_reason: str
    missing_information: list[str]
    reject_reason: str
    scores: ScreeningScores


@dataclass
class PipelineStats:
    processed: int = 0
    recommend: int = 0
    consider: int = 0
    manual: int = 0
    reject: int = 0
    duplicate: int = 0
    model_failures: int = 0
    extraction_failures: int = 0
    non_standard_names: int = 0

    def count_category(self, category: str) -> None:
        if category == CATEGORY_RECOMMEND:
            self.recommend += 1
        elif category == CATEGORY_CONSIDER:
            self.consider += 1
        elif category == CATEGORY_MANUAL:
            self.manual += 1
        elif category == CATEGORY_REJECT:
            self.reject += 1


JsonDict = dict[str, Any]
```

```python
# src/resume_screening/filename_parser.py
from __future__ import annotations

import re
from pathlib import Path

from resume_screening.models import ParsedFilename


STANDARD_PATTERN = re.compile(
    r"^【(?P<job>[^_】]+)_(?P<location_salary>[^】]+)】(?P<name>\S+)\s+(?P<experience>.+?)$"
)


def parse_resume_filename(path: Path) -> ParsedFilename:
    stem = path.stem.strip()
    match = STANDARD_PATTERN.match(stem)
    if not match:
        guessed_name = re.split(r"[-_\s]+", stem, maxsplit=1)[0].strip()
        return ParsedFilename(
            path=path,
            is_standard=False,
            candidate_name=guessed_name,
            missing_fields=["文件名不规范", "岗位名称", "期望工作地", "岗位标注薪资", "工龄"],
        )

    location_salary = match.group("location_salary").strip()
    parts = location_salary.split()
    expected_location = parts[0].strip() if parts else ""
    salary_range = " ".join(parts[1:]).strip() if len(parts) > 1 else ""
    missing_fields: list[str] = []
    if not salary_range:
        missing_fields.append("岗位标注薪资")

    return ParsedFilename(
        path=path,
        is_standard=True,
        job_name=match.group("job").strip(),
        expected_location=expected_location,
        salary_range=salary_range,
        candidate_name=match.group("name").strip(),
        work_experience=match.group("experience").strip(),
        missing_fields=missing_fields,
    )
```

- [ ] **Step 4: Run parser tests and verify they pass**

Run: `pytest tests/test_filename_parser.py -v`

Expected: PASS.

- [ ] **Step 5: Commit parser**

```bash
git add src/resume_screening/models.py src/resume_screening/filename_parser.py tests/test_filename_parser.py
git commit -m "feat: parse resume filenames"
```

## Task 3: Job Requirements Workbook Parser

**Files:**
- Create: `src/resume_screening/job_requirements.py`
- Test: `tests/test_job_requirements.py`

- [ ] **Step 1: Write failing workbook parser tests**

```python
# tests/test_job_requirements.py
from pathlib import Path

from openpyxl import Workbook

from resume_screening.job_requirements import load_job_requirements


def make_job_book(path: Path) -> None:
    workbook = Workbook()
    template = workbook.active
    template.title = "模板"
    template["A1"] = "岗位说明书"
    product = workbook.create_sheet("产品总监")
    product.append(["岗位说明书"])
    product.append([None, None, None, None, None, None, None, "HR(03)20260001"])
    product.append(["一、基本信息"])
    product.append(["岗位名称", "技术产品总监", "所属部门", "研发部", "直接上级", "郑廉", "岗位等级", None])
    product.append(["岗位编制", "1/1", "岗位性质", "全职", None, None, "职级", "总监"])
    product.append(["工作地点", "北京", "工作方式", "半线上", None, None, "工作经验", "8年以上"])
    product.append(["学历", "统招本科及以上", "专业", "计算机、信息工程", "证书持有", "", "技能/素质", "AI产品、Agent"])
    product.append(["语言要求", "普通话", None, None, "晋升路径", "", None, None])
    product.append(["二、岗位目的"])
    product.append(["具体描述", "负责AI产品规划和跨团队落地。"])
    product.append(["三、主要工作职责及核心考核指标"])
    product.append(["1. 核心职责", "负责产品路线图和核心指标。"])
    product.append(["2. 核心职责", "推动研发、算法、运营协同。"])
    product.append(["3. 核心职责", "建立产品数据反馈机制。"])
    product.append(["4. 补充职责", "有Agent经验优先。"])
    product.append(["四、其他说明"])
    product.append(["补充说明", "无"])
    empty = workbook.create_sheet("算法")
    empty.append(["岗位说明书"])
    empty.append(["一、基本信息"])
    workbook.save(path)


def test_load_job_requirements_ignores_template_and_detects_completeness(tmp_path: Path) -> None:
    path = tmp_path / "jobs.xlsx"
    make_job_book(path)

    jobs = load_job_requirements(path)

    assert "模板" not in jobs
    assert jobs["产品总监"].is_complete is True
    assert "负责AI产品规划" in jobs["产品总监"].raw_text
    assert jobs["算法"].is_complete is False
    assert "岗位名称" in jobs["算法"].missing_fields
```

- [ ] **Step 2: Run workbook parser tests and verify they fail**

Run: `pytest tests/test_job_requirements.py -v`

Expected: FAIL because `resume_screening.job_requirements` does not exist.

- [ ] **Step 3: Implement workbook parser**

```python
# src/resume_screening/job_requirements.py
from __future__ import annotations

from pathlib import Path

from openpyxl import load_workbook

from resume_screening.models import JobRequirement


PLACEHOLDER_MARKERS = ("XXXX", "具体描述", "无则填", "年       月")
REQUIRED_FIELDS = ("岗位名称", "学历", "工作经验", "具体描述", "1. 核心职责")


def _clean(value: object) -> str:
    return str(value).strip() if value is not None else ""


def _is_placeholder(value: str) -> bool:
    return not value or any(marker in value for marker in PLACEHOLDER_MARKERS)


def _extract_sheet_fields(rows: list[list[str]]) -> dict[str, str]:
    fields: dict[str, str] = {}
    for row in rows:
        for index in range(0, len(row), 2):
            key = row[index].strip() if index < len(row) else ""
            value = row[index + 1].strip() if index + 1 < len(row) else ""
            if key and value:
                fields[key] = value
    return fields


def _raw_text(rows: list[list[str]]) -> str:
    lines = []
    for row in rows:
        text = " ".join(cell for cell in row if cell)
        if text:
            lines.append(text)
    return "\n".join(lines)


def _missing_required(fields: dict[str, str]) -> list[str]:
    missing = []
    for field_name in REQUIRED_FIELDS:
        value = fields.get(field_name, "")
        if _is_placeholder(value):
            missing.append(field_name)
    return missing


def load_job_requirements(path: Path) -> dict[str, JobRequirement]:
    workbook = load_workbook(path, data_only=True)
    jobs: dict[str, JobRequirement] = {}
    for sheet_name in workbook.sheetnames:
        if sheet_name == "模板":
            continue
        sheet = workbook[sheet_name]
        rows = [[_clean(cell) for cell in row] for row in sheet.iter_rows(values_only=True)]
        fields = _extract_sheet_fields(rows)
        missing = _missing_required(fields)
        raw_text = _raw_text(rows)
        jobs[sheet_name] = JobRequirement(
            sheet_name=sheet_name,
            fields=fields,
            raw_text=raw_text,
            is_complete=len(missing) == 0,
            missing_fields=missing,
        )
    return jobs
```

- [ ] **Step 4: Run workbook parser tests and verify they pass**

Run: `pytest tests/test_job_requirements.py -v`

Expected: PASS.

- [ ] **Step 5: Commit workbook parser**

```bash
git add src/resume_screening/job_requirements.py tests/test_job_requirements.py
git commit -m "feat: read job requirements workbook"
```

## Task 4: Document Text Extraction

**Files:**
- Create: `src/resume_screening/extractors.py`
- Test: `tests/test_extractors.py`

- [ ] **Step 1: Write failing extraction tests**

```python
# tests/test_extractors.py
from pathlib import Path

from resume_screening.extractors import extract_text


def test_extract_unsupported_file_returns_error(tmp_path: Path) -> None:
    path = tmp_path / "resume.txt"
    path.write_text("hello", encoding="utf-8")

    result = extract_text(path, ocr_command="tesseract")

    assert result.text == ""
    assert result.method == "unsupported"
    assert "不支持的文件格式" in result.errors


def test_extract_docx_reads_paragraphs(tmp_path: Path) -> None:
    from docx import Document

    path = tmp_path / "resume.docx"
    document = Document()
    document.add_paragraph("郭燕婷")
    document.add_paragraph("财务总监候选人，10年以上经验")
    document.save(path)

    result = extract_text(path, ocr_command="tesseract")

    assert "郭燕婷" in result.text
    assert "10年以上经验" in result.text
    assert result.method == "docx"
```

- [ ] **Step 2: Run extraction tests and verify they fail**

Run: `pytest tests/test_extractors.py -v`

Expected: FAIL because the extractor module does not exist.

- [ ] **Step 3: Implement text extraction**

```python
# src/resume_screening/extractors.py
from __future__ import annotations

import subprocess
from pathlib import Path

from docx import Document
from pptx import Presentation
from pypdf import PdfReader

from resume_screening.models import ExtractionResult


SUPPORTED_EXTENSIONS = {".pdf", ".jpg", ".jpeg", ".png", ".doc", ".docx", ".pptx"}


def extract_text(path: Path, ocr_command: str) -> ExtractionResult:
    suffix = path.suffix.lower()
    if suffix not in SUPPORTED_EXTENSIONS:
        return ExtractionResult(text="", method="unsupported", errors=["不支持的文件格式"])
    try:
        if suffix == ".pdf":
            return _extract_pdf(path)
        if suffix in {".jpg", ".jpeg", ".png"}:
            return _extract_image_ocr(path, ocr_command)
        if suffix == ".docx":
            return _extract_docx(path)
        if suffix == ".doc":
            return _extract_doc(path)
        if suffix == ".pptx":
            return _extract_pptx(path)
    except Exception as exc:
        return ExtractionResult(text="", method=suffix.lstrip("."), errors=[f"正文提取失败：{exc}"])
    return ExtractionResult(text="", method="unsupported", errors=["不支持的文件格式"])


def _extract_pdf(path: Path) -> ExtractionResult:
    reader = PdfReader(str(path))
    text = "\n".join(page.extract_text() or "" for page in reader.pages).strip()
    if len(text) < 80:
        return ExtractionResult(text=text, method="pdf", errors=["PDF文本过短，可能需要OCR人工复核"])
    return ExtractionResult(text=text, method="pdf")


def _extract_image_ocr(path: Path, ocr_command: str) -> ExtractionResult:
    completed = subprocess.run(
        [ocr_command, str(path), "stdout", "-l", "chi_sim+eng"],
        capture_output=True,
        text=True,
        check=False,
        timeout=120,
    )
    if completed.returncode != 0:
        return ExtractionResult(text="", method="ocr", errors=[f"OCR失败：{completed.stderr.strip()}"])
    return ExtractionResult(text=completed.stdout.strip(), method="ocr")


def _extract_docx(path: Path) -> ExtractionResult:
    document = Document(str(path))
    text = "\n".join(paragraph.text for paragraph in document.paragraphs if paragraph.text.strip())
    return ExtractionResult(text=text.strip(), method="docx")


def _extract_doc(path: Path) -> ExtractionResult:
    completed = subprocess.run(
        ["textutil", "-convert", "txt", "-stdout", str(path)],
        capture_output=True,
        text=True,
        check=False,
        timeout=120,
    )
    if completed.returncode != 0:
        return ExtractionResult(text="", method="doc", errors=[f"DOC转换失败：{completed.stderr.strip()}"])
    return ExtractionResult(text=completed.stdout.strip(), method="doc")


def _extract_pptx(path: Path) -> ExtractionResult:
    presentation = Presentation(str(path))
    parts: list[str] = []
    for slide in presentation.slides:
        for shape in slide.shapes:
            if hasattr(shape, "text") and shape.text.strip():
                parts.append(shape.text.strip())
    return ExtractionResult(text="\n".join(parts), method="pptx")
```

- [ ] **Step 4: Run extraction tests and verify they pass**

Run: `pytest tests/test_extractors.py -v`

Expected: PASS.

- [ ] **Step 5: Commit extraction module**

```bash
git add src/resume_screening/extractors.py tests/test_extractors.py
git commit -m "feat: extract resume text"
```

## Task 5: Duplicate Detection Index

**Files:**
- Create: `src/resume_screening/duplicates.py`
- Test: `tests/test_duplicates.py`

- [ ] **Step 1: Write failing duplicate tests**

```python
# tests/test_duplicates.py
from pathlib import Path

from resume_screening.duplicates import DuplicateIndex, normalize_text


def test_normalize_text_removes_spacing_noise() -> None:
    assert normalize_text("郭  燕婷\n\n10年以上经验") == "郭燕婷10年以上经验"


def test_duplicate_index_detects_exact_content(tmp_path: Path) -> None:
    path = tmp_path / "processed_index.json"
    index = DuplicateIndex.load(path)
    index.add(text="郭燕婷10年以上财务经验", filename="a.pdf", row_id=7, candidate_name="郭燕婷", job_name="财务总监")
    index.save()

    reloaded = DuplicateIndex.load(path)
    match = reloaded.find("郭燕婷 10年以上 财务经验")

    assert match.is_duplicate is True
    assert match.matched_filename == "a.pdf"
    assert match.matched_row_id == 7
```

- [ ] **Step 2: Run duplicate tests and verify they fail**

Run: `pytest tests/test_duplicates.py -v`

Expected: FAIL because `resume_screening.duplicates` does not exist.

- [ ] **Step 3: Implement duplicate index**

```python
# src/resume_screening/duplicates.py
from __future__ import annotations

import hashlib
import json
import re
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from difflib import SequenceMatcher
from pathlib import Path

from resume_screening.models import DuplicateMatch


def normalize_text(text: str) -> str:
    return re.sub(r"\s+", "", text).strip()


def fingerprint(text: str) -> str:
    normalized = normalize_text(text)
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()


@dataclass(frozen=True)
class IndexEntry:
    fingerprint: str
    normalized_text: str
    filename: str
    row_id: int
    candidate_name: str
    job_name: str
    processed_at: str


class DuplicateIndex:
    def __init__(self, path: Path, entries: list[IndexEntry]) -> None:
        self.path = path
        self.entries = entries

    @classmethod
    def load(cls, path: Path) -> "DuplicateIndex":
        if not path.exists():
            return cls(path=path, entries=[])
        raw = json.loads(path.read_text(encoding="utf-8"))
        entries = [IndexEntry(**item) for item in raw.get("entries", [])]
        return cls(path=path, entries=entries)

    def save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        payload = {"entries": [asdict(entry) for entry in self.entries]}
        self.path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    def find(self, text: str, threshold: float = 0.92) -> DuplicateMatch:
        normalized = normalize_text(text)
        current_hash = fingerprint(normalized)
        for entry in self.entries:
            if entry.fingerprint == current_hash:
                return DuplicateMatch(True, entry.filename, entry.row_id, 1.0)
        best_entry: IndexEntry | None = None
        best_ratio = 0.0
        for entry in self.entries:
            ratio = SequenceMatcher(None, normalized, entry.normalized_text).ratio()
            if ratio > best_ratio:
                best_ratio = ratio
                best_entry = entry
        if best_entry and best_ratio >= threshold:
            return DuplicateMatch(True, best_entry.filename, best_entry.row_id, best_ratio)
        return DuplicateMatch(False)

    def add(self, text: str, filename: str, row_id: int, candidate_name: str, job_name: str) -> None:
        normalized = normalize_text(text)
        self.entries.append(
            IndexEntry(
                fingerprint=fingerprint(normalized),
                normalized_text=normalized,
                filename=filename,
                row_id=row_id,
                candidate_name=candidate_name,
                job_name=job_name,
                processed_at=datetime.now(timezone.utc).isoformat(),
            )
        )
```

- [ ] **Step 4: Run duplicate tests and verify they pass**

Run: `pytest tests/test_duplicates.py -v`

Expected: PASS.

- [ ] **Step 5: Commit duplicate index**

```bash
git add src/resume_screening/duplicates.py tests/test_duplicates.py
git commit -m "feat: detect duplicate resume content"
```

## Task 6: Model Client and JSON Validation

**Files:**
- Create: `src/resume_screening/model_client.py`
- Test: `tests/test_model_client.py`

- [ ] **Step 1: Write failing model validation tests**

```python
# tests/test_model_client.py
import pytest

from resume_screening.model_client import parse_model_response


def test_parse_model_response_accepts_valid_json() -> None:
    result = parse_model_response(
        {
            "category": "推荐初试",
            "overall_score": 8.5,
            "summary": "候选人具备财务管理经验。",
            "screening_reason": "经验和岗位要求匹配。",
            "missing_information": [],
            "reject_reason": "",
            "scores": {
                "ability": 8,
                "ego": 6,
                "desire": 8,
                "learning_ability": 8,
                "job_fit": 9,
                "experience_fit": 9,
                "skill_fit": 8,
                "stability_risk": 7,
            },
        }
    )

    assert result.category == "推荐初试"
    assert result.scores.job_fit == 9


def test_parse_model_response_rejects_unknown_category() -> None:
    with pytest.raises(ValueError, match="category"):
        parse_model_response(
            {
                "category": "强烈推荐",
                "overall_score": 8.5,
                "summary": "摘要",
                "screening_reason": "理由",
                "missing_information": [],
                "reject_reason": "",
                "scores": {
                    "ability": 8,
                    "ego": 6,
                    "desire": 8,
                    "learning_ability": 8,
                    "job_fit": 9,
                    "experience_fit": 9,
                    "skill_fit": 8,
                    "stability_risk": 7,
                },
            }
        )
```

- [ ] **Step 2: Run model tests and verify they fail**

Run: `pytest tests/test_model_client.py -v`

Expected: FAIL because the module does not exist.

- [ ] **Step 3: Implement model client and parser**

```python
# src/resume_screening/model_client.py
from __future__ import annotations

import json

import httpx
from pydantic import BaseModel, Field, ValidationError, field_validator

from resume_screening.config import ModelConfig
from resume_screening.models import (
    CATEGORY_CONSIDER,
    CATEGORY_MANUAL,
    CATEGORY_RECOMMEND,
    CATEGORY_REJECT,
    JobRequirement,
    ScreeningResult,
    ScreeningScores,
)


VALID_CATEGORIES = {CATEGORY_RECOMMEND, CATEGORY_CONSIDER, CATEGORY_MANUAL, CATEGORY_REJECT}


class ModelScoresPayload(BaseModel):
    ability: float = Field(ge=0, le=10)
    ego: float = Field(ge=0, le=10)
    desire: float = Field(ge=0, le=10)
    learning_ability: float = Field(ge=0, le=10)
    job_fit: float = Field(ge=0, le=10)
    experience_fit: float = Field(ge=0, le=10)
    skill_fit: float = Field(ge=0, le=10)
    stability_risk: float = Field(ge=0, le=10)


class ModelPayload(BaseModel):
    category: str
    overall_score: float = Field(ge=0, le=10)
    summary: str
    screening_reason: str
    missing_information: list[str]
    reject_reason: str = ""
    scores: ModelScoresPayload

    @field_validator("category")
    @classmethod
    def validate_category(cls, value: str) -> str:
        if value not in VALID_CATEGORIES:
            raise ValueError("category must be one of 推荐初试, 可考虑, 待人工二筛, 未通过")
        return value


def parse_model_response(payload: dict) -> ScreeningResult:
    try:
        parsed = ModelPayload.model_validate(payload)
    except ValidationError as exc:
        raise ValueError(f"模型返回格式不符合JSON结构：{exc}") from exc
    return ScreeningResult(
        category=parsed.category,
        overall_score=parsed.overall_score,
        summary=parsed.summary,
        screening_reason=parsed.screening_reason,
        missing_information=parsed.missing_information,
        reject_reason=parsed.reject_reason,
        scores=ScreeningScores(**parsed.scores.model_dump()),
    )


class ModelClient:
    def __init__(self, config: ModelConfig) -> None:
        self.config = config

    def evaluate(self, resume_text: str, job: JobRequirement, filename_metadata: dict[str, str]) -> ScreeningResult:
        prompt = self._build_prompt(resume_text, job, filename_metadata)
        response = httpx.post(
            f"{self.config.base_url.rstrip('/')}/chat/completions",
            headers={"Authorization": f"Bearer {self.config.api_key}", "Content-Type": "application/json"},
            json={
                "model": self.config.model,
                "temperature": self.config.temperature,
                "response_format": {"type": "json_object"},
                "messages": [
                    {"role": "system", "content": "你是招聘初筛助手，只返回严格JSON。"},
                    {"role": "user", "content": prompt},
                ],
            },
            timeout=self.config.timeout_seconds,
        )
        response.raise_for_status()
        content = response.json()["choices"][0]["message"]["content"]
        return parse_model_response(json.loads(content))

    def _build_prompt(self, resume_text: str, job: JobRequirement, filename_metadata: dict[str, str]) -> str:
        return json.dumps(
            {
                "instruction": "根据岗位要求和简历内容进行初筛。评分均为0到10分，8分通过，9分优秀。稳定性/风险高分表示低风险。只返回指定JSON字段。",
                "required_json_fields": [
                    "category",
                    "overall_score",
                    "summary",
                    "screening_reason",
                    "missing_information",
                    "reject_reason",
                    "scores",
                ],
                "allowed_categories": sorted(VALID_CATEGORIES),
                "filename_metadata": filename_metadata,
                "job_requirement": {"sheet_name": job.sheet_name, "fields": job.fields, "raw_text": job.raw_text},
                "resume_text": resume_text[:12000],
            },
            ensure_ascii=False,
        )
```

- [ ] **Step 4: Run model tests and verify they pass**

Run: `pytest tests/test_model_client.py -v`

Expected: PASS.

- [ ] **Step 5: Commit model client**

```bash
git add src/resume_screening/model_client.py tests/test_model_client.py
git commit -m "feat: validate model screening responses"
```

## Task 7: Excel Writer

**Files:**
- Create: `src/resume_screening/excel_writer.py`
- Test: `tests/test_excel_writer.py`

- [ ] **Step 1: Write failing Excel writer tests**

```python
# tests/test_excel_writer.py
from pathlib import Path

from openpyxl import Workbook, load_workbook

from resume_screening.excel_writer import ResultWorkbookWriter
from resume_screening.models import DuplicateMatch, ParsedFilename, ScreeningResult, ScreeningScores


def create_result_book(path: Path) -> None:
    workbook = Workbook()
    sheet = workbook.active
    sheet.title = "多维表格"
    sheet.append(["ID", "当前阶段", "候选人", "附件", "岗位方向", "来源渠道", "候选人摘要（妙记）", "量化打分", "可投入周期", "面试负责人", "下次动作日", "不推进原因", "推荐/触达人"])
    sheet.append([1, "未通过", "历史候选人", "old.pdf", "财务", "BOSS", "", "", "", "", "", "不匹配", ""])
    workbook.save(path)


def make_result() -> ScreeningResult:
    return ScreeningResult(
        category="推荐初试",
        overall_score=8.5,
        summary="候选人具备财务管理经验。",
        screening_reason="经验匹配。",
        missing_information=[],
        reject_reason="",
        scores=ScreeningScores(8, 6, 8, 8, 9, 9, 8, 7),
    )


def test_writer_appends_columns_and_duplicate_red_fill(tmp_path: Path) -> None:
    path = tmp_path / "result.xlsx"
    create_result_book(path)
    writer = ResultWorkbookWriter(path)
    parsed = ParsedFilename(
        path=Path("【财务总监_北京 18-28K】郭燕婷 10年以上.pdf"),
        is_standard=True,
        job_name="财务总监",
        expected_location="北京",
        salary_range="18-28K",
        candidate_name="郭燕婷",
        work_experience="10年以上",
    )

    row_id = writer.append_result(
        parsed=parsed,
        result=make_result(),
        duplicate=DuplicateMatch(True, "old.pdf", 1, 1.0),
        extraction_errors=[],
        default_source_channel="",
        default_interviewer="",
    )
    writer.save()

    workbook = load_workbook(path)
    sheet = workbook["多维表格"]
    headers = [cell.value for cell in sheet[1]]
    assert headers[-3:] == ["初筛分类", "初筛理由", "缺失信息"]
    assert row_id == 2
    assert sheet["A3"].value == 2
    assert sheet["C3"].value == "郭燕婷"
    assert sheet["N3"].value == "推荐初试"
    assert "疑似重复简历" in sheet["P3"].value
    assert sheet["A3"].fill.fgColor.rgb == "FFFFC7CE"
```

- [ ] **Step 2: Run Excel writer tests and verify they fail**

Run: `pytest tests/test_excel_writer.py -v`

Expected: FAIL because the writer module does not exist.

- [ ] **Step 3: Implement Excel writer**

```python
# src/resume_screening/excel_writer.py
from __future__ import annotations

from pathlib import Path

from openpyxl import load_workbook
from openpyxl.styles import PatternFill

from resume_screening.models import CATEGORY_REJECT, DuplicateMatch, ParsedFilename, ScreeningResult


BASE_HEADERS = ["ID", "当前阶段", "候选人", "附件", "岗位方向", "来源渠道", "候选人摘要（妙记）", "量化打分", "可投入周期", "面试负责人", "下次动作日", "不推进原因", "推荐/触达人"]
EXTRA_HEADERS = ["初筛分类", "初筛理由", "缺失信息"]
DUPLICATE_FILL = PatternFill(fill_type="solid", fgColor="FFFFC7CE")


class ResultWorkbookWriter:
    def __init__(self, path: Path, sheet_name: str = "多维表格") -> None:
        self.path = path
        self.workbook = load_workbook(path)
        self.sheet = self.workbook[sheet_name]
        self._ensure_headers()

    def _ensure_headers(self) -> None:
        headers = [cell.value for cell in self.sheet[1]]
        for header in EXTRA_HEADERS:
            if header not in headers:
                self.sheet.cell(row=1, column=len(headers) + 1).value = header
                headers.append(header)

    def next_id(self) -> int:
        ids: list[int] = []
        for row in self.sheet.iter_rows(min_row=2, min_col=1, max_col=1, values_only=True):
            value = row[0]
            if isinstance(value, int):
                ids.append(value)
        return (max(ids) if ids else 0) + 1

    def append_result(
        self,
        parsed: ParsedFilename,
        result: ScreeningResult,
        duplicate: DuplicateMatch,
        extraction_errors: list[str],
        default_source_channel: str,
        default_interviewer: str,
    ) -> int:
        row_id = self.next_id()
        missing = list(result.missing_information) + list(parsed.missing_fields) + list(extraction_errors)
        if duplicate.is_duplicate:
            missing.append(f"疑似重复简历：与历史附件 {duplicate.matched_filename} 内容一致")
        row = [
            row_id,
            result.category,
            parsed.candidate_name,
            parsed.path.name,
            parsed.job_name,
            default_source_channel,
            result.summary,
            format_score_block(result),
            "",
            default_interviewer,
            "",
            result.reject_reason if result.category == CATEGORY_REJECT else "",
            "",
            result.category,
            result.screening_reason,
            "；".join(item for item in missing if item),
        ]
        self.sheet.append(row)
        row_number = self.sheet.max_row
        if duplicate.is_duplicate:
            for cell in self.sheet[row_number]:
                cell.fill = DUPLICATE_FILL
        return row_id

    def save(self) -> None:
        self.workbook.save(self.path)


def format_score_block(result: ScreeningResult) -> str:
    conclusion = "优秀" if result.overall_score >= 9 else "通过" if result.overall_score >= 8 else "未通过"
    scores = result.scores
    return "\n".join(
        [
            f"综合评分：{result.overall_score:g}/10",
            f"结论：{conclusion}",
            "",
            f"能力：{scores.ability:g}",
            f"ego大小：{scores.ego:g}",
            f"野心desire：{scores.desire:g}",
            f"学习能力与聪明程度：{scores.learning_ability:g}",
            "",
            f"岗位匹配度：{scores.job_fit:g}",
            f"经验匹配：{scores.experience_fit:g}",
            f"技能匹配：{scores.skill_fit:g}",
            f"稳定性/风险：{scores.stability_risk:g}",
            "",
            f"评价：{result.screening_reason}",
        ]
    )
```

- [ ] **Step 4: Run Excel writer tests and verify they pass**

Run: `pytest tests/test_excel_writer.py -v`

Expected: PASS.

- [ ] **Step 5: Commit Excel writer**

```bash
git add src/resume_screening/excel_writer.py tests/test_excel_writer.py
git commit -m "feat: append screening results to workbook"
```

## Task 8: Pipeline and CLI

**Files:**
- Create: `src/resume_screening/pipeline.py`
- Create: `src/resume_screening/cli.py`
- Test: `tests/test_pipeline.py`
- Test: `tests/test_cli.py`

- [ ] **Step 1: Write failing pipeline test for manual fallback**

```python
# tests/test_pipeline.py
from pathlib import Path

from openpyxl import Workbook, load_workbook

from resume_screening.config import AppConfig
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
    template.append(["岗位说明书"])
    job = workbook.create_sheet("财务总监")
    job.append(["岗位说明书"])
    job.append(["一、基本信息"])
    workbook.save(path)


def test_pipeline_writes_manual_review_for_incomplete_job(tmp_path: Path) -> None:
    resume_dir = tmp_path / "resumes"
    resume_dir.mkdir()
    resume = resume_dir / "【财务总监_北京 18-28K】郭燕婷 10年以上.docx"
    from docx import Document
    document = Document()
    document.add_paragraph("郭燕婷，10年以上财务经验。")
    document.save(resume)
    job_book = tmp_path / "jobs.xlsx"
    result_book = tmp_path / "result.xlsx"
    create_incomplete_job_book(job_book)
    create_result_book(result_book)
    config = AppConfig.model_validate(
        {
            "resume_dir": resume_dir,
            "job_book": job_book,
            "result_book": result_book,
            "index_path": tmp_path / "processed_index.json",
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
    )

    stats = ScreeningPipeline(config).run()

    assert stats.processed == 1
    assert stats.manual == 1
    workbook = load_workbook(result_book)
    sheet = workbook["多维表格"]
    assert sheet["B2"].value == "待人工二筛"
    assert "岗位要求不完整" in sheet["P2"].value
```

- [ ] **Step 2: Write failing CLI smoke test**

```python
# tests/test_cli.py
from typer.testing import CliRunner

from resume_screening.cli import app


def test_cli_requires_config_argument() -> None:
    runner = CliRunner()
    result = runner.invoke(app, ["run"])

    assert result.exit_code != 0
    assert "Missing option" in result.output or "Error" in result.output
```

- [ ] **Step 3: Run pipeline and CLI tests and verify they fail**

Run: `pytest tests/test_pipeline.py tests/test_cli.py -v`

Expected: FAIL because `pipeline.py` and `cli.py` do not exist.

- [ ] **Step 4: Implement pipeline and CLI**

```python
# src/resume_screening/pipeline.py
from __future__ import annotations

from pathlib import Path

import httpx

from resume_screening.config import AppConfig
from resume_screening.duplicates import DuplicateIndex
from resume_screening.excel_writer import ResultWorkbookWriter
from resume_screening.extractors import SUPPORTED_EXTENSIONS, extract_text
from resume_screening.filename_parser import parse_resume_filename
from resume_screening.job_requirements import load_job_requirements
from resume_screening.model_client import ModelClient
from resume_screening.models import (
    CATEGORY_MANUAL,
    ExtractionResult,
    JobRequirement,
    ParsedFilename,
    PipelineStats,
    ScreeningResult,
    ScreeningScores,
)


class ScreeningPipeline:
    def __init__(self, config: AppConfig) -> None:
        self.config = config

    def run(self) -> PipelineStats:
        jobs = load_job_requirements(self.config.job_book)
        writer = ResultWorkbookWriter(self.config.result_book)
        index = DuplicateIndex.load(self.config.index_path)
        client = None if self.config.model.allow_without_model else ModelClient(self.config.model)
        stats = PipelineStats()
        for path in self._resume_files():
            parsed = parse_resume_filename(path)
            extraction = extract_text(path, self.config.ocr_command)
            duplicate = index.find(extraction.text) if extraction.text else index.find(path.name)
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
        writer.save()
        index.save()
        return stats

    def _resume_files(self) -> list[Path]:
        skip = {self.config.job_book.resolve(), self.config.result_book.resolve()}
        files: list[Path] = []
        for path in self.config.resume_dir.iterdir():
            if not path.is_file():
                continue
            if path.resolve() in skip:
                continue
            if path.suffix.lower() in SUPPORTED_EXTENSIONS:
                files.append(path)
        return sorted(files)

    def _screen(
        self,
        parsed: ParsedFilename,
        extraction: ExtractionResult,
        jobs: dict[str, JobRequirement],
        client: ModelClient | None,
    ) -> ScreeningResult:
        missing = list(parsed.missing_fields)
        if not parsed.is_standard:
            missing.append("文件名不规范/字段无法从文件名确认")
        if not extraction.text:
            missing.extend(extraction.errors or ["无法提取简历正文"])
            return manual_result("无法提取简历正文，需人工确认", missing)
        job = jobs.get(parsed.job_name)
        if not job:
            missing.append("岗位名称未匹配到岗位说明书sheet")
            return manual_result("岗位名称未匹配到岗位说明书sheet，需人工确认", missing)
        if not job.is_complete:
            missing.append("岗位要求不完整，需人工确认")
            missing.extend(job.missing_fields)
            return manual_result("岗位要求不完整，需人工确认", missing)
        if client is None:
            missing.append("模型配置缺失，已按人工二筛处理")
            return manual_result("模型配置缺失，需人工确认", missing)
        try:
            return client.evaluate(
                resume_text=extraction.text,
                job=job,
                filename_metadata={
                    "job_name": parsed.job_name,
                    "expected_location": parsed.expected_location,
                    "salary_range": parsed.salary_range,
                    "candidate_name": parsed.candidate_name,
                    "work_experience": parsed.work_experience,
                },
            )
        except httpx.TimeoutException:
            print(f"模型评估失败：请求超时 - {parsed.path.name}")
            return manual_result("模型评估失败，需人工确认", missing + ["模型评估失败：请求超时"])
        except httpx.HTTPStatusError as exc:
            print(f"模型评估失败：HTTP {exc.response.status_code} - {parsed.path.name}")
            return manual_result("模型评估失败，需人工确认", missing + [f"模型评估失败：HTTP {exc.response.status_code}"])
        except Exception as exc:
            print(f"模型评估失败：{exc} - {parsed.path.name}")
            return manual_result("模型评估失败，需人工确认", missing + [f"模型评估失败：{exc}"])


def manual_result(reason: str, missing: list[str]) -> ScreeningResult:
    return ScreeningResult(
        category=CATEGORY_MANUAL,
        overall_score=0,
        summary=reason,
        screening_reason=reason,
        missing_information=missing,
        reject_reason="",
        scores=ScreeningScores(0, 0, 0, 0, 0, 0, 0, 0),
    )
```

```python
# src/resume_screening/cli.py
from __future__ import annotations

from pathlib import Path

import typer

from resume_screening.config import load_config
from resume_screening.pipeline import ScreeningPipeline


app = typer.Typer(no_args_is_help=True)


@app.command()
def run(config: Path = typer.Option(..., "--config", "-c", exists=True, readable=True)) -> None:
    app_config = load_config(config)
    stats = ScreeningPipeline(app_config).run()
    typer.echo("处理完成")
    typer.echo(f"处理数量：{stats.processed}")
    typer.echo(f"推荐初试：{stats.recommend}")
    typer.echo(f"可考虑：{stats.consider}")
    typer.echo(f"待人工二筛：{stats.manual}")
    typer.echo(f"未通过：{stats.reject}")
    typer.echo(f"疑似重复：{stats.duplicate}")
    typer.echo(f"模型失败：{stats.model_failures}")
    typer.echo(f"提取失败/警告：{stats.extraction_failures}")
    typer.echo(f"文件名不规范：{stats.non_standard_names}")
```

- [ ] **Step 5: Run pipeline and CLI tests and verify they pass**

Run: `pytest tests/test_pipeline.py tests/test_cli.py -v`

Expected: PASS.

- [ ] **Step 6: Commit pipeline and CLI**

```bash
git add src/resume_screening/pipeline.py src/resume_screening/cli.py tests/test_pipeline.py tests/test_cli.py
git commit -m "feat: orchestrate resume screening pipeline"
```

## Task 9: End-to-End Verification and Documentation

**Files:**
- Create: `README.md`
- Modify: `config.example.yaml`
- Test: all tests

- [ ] **Step 1: Write README usage**

Create `README.md` with this content:

`# Resume Screening CLI`

`## Setup`

Run `python -m venv .venv`, then `source .venv/bin/activate`, then `pip install -e ".[test]"`, then `cp config.example.yaml config.yaml`.

Edit `config.yaml` and set `model.base_url`, `model.api_key`, and `model.model`.

`## Run`

Run `resume-screening run --config config.yaml`.

The tool appends rows to `/Users/mac/Downloads/小A科技（北京）组织招聘.xlsx`.
It rereads `/Users/mac/Downloads/小A自动化岗位说明书.xlsx` on every run.
Historical rows are preserved.
Duplicate resume content is still appended and marked red.

`## Manual-Review Mode`

Set `model.allow_without_model: true` to process files without model calls.
Rows that require model judgment are classified as `待人工二筛`.

- [ ] **Step 2: Add pytest dependency group**

```toml
# pyproject.toml addition
[project.optional-dependencies]
test = ["pytest>=8.0"]
```

- [ ] **Step 3: Run the full test suite**

Run: `pytest -v`

Expected: PASS for all tests.

- [ ] **Step 4: Run CLI help**

Run: `python -m resume_screening.cli --help`

Expected: command help renders without import errors.

- [ ] **Step 5: Run a manual-mode smoke test using temporary workbooks**

Run: `pytest tests/test_pipeline.py::test_pipeline_writes_manual_review_for_incomplete_job -v`

Expected: PASS and no changes to files under `/Users/mac/Downloads`.

- [ ] **Step 6: Inspect git status**

Run: `git status --short`

Expected: README, pyproject, config example, source files, and tests are modified or added only by this implementation.

- [ ] **Step 7: Commit docs and final verification**

```bash
git add README.md pyproject.toml config.example.yaml
git commit -m "docs: add resume screening usage"
```

## Self-Review Checklist

- Spec coverage:
  - PDF and secondary file types: Task 4.
  - Filename metadata: Task 2.
  - Job workbook reread and `模板` ignore: Task 3 and Task 8.
  - Incomplete job requirements to manual review: Task 3 and Task 8.
  - OpenAI-compatible configurable model: Task 1 and Task 6.
  - Four screening categories and 10-point scoring: Task 2, Task 6, Task 7, Task 8.
  - Append-only result workbook with three new columns: Task 7.
  - Duplicate content red rows: Task 5 and Task 7.
  - Model timeout/API error visible in CLI and Excel: Task 8.
  - CLI summary counts: Task 8.
- Placeholder scan:
  - The plan does not contain unresolved placeholder markers or vague implementation handoffs.
- Type consistency:
  - Shared objects are defined in `models.py` before use by parser, model client, writer, and pipeline.
  - Category strings are centralized in `models.py`.
  - `ParsedFilename`, `ScreeningResult`, and `DuplicateMatch` signatures match writer and pipeline usage.
