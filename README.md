# Resume Screening CLI

## Setup

```bash
python3 -m venv .venv
source .venv/bin/activate
python3 -m pip install ".[test]"
cp config.example.yaml config.yaml
```

Edit `config.yaml` and set `model.base_url`, `model.api_key`, and `model.model`.

## Run

```bash
resume-screening run --config config.yaml
```

The tool appends rows to `/Users/mac/Downloads/小A科技（北京）组织招聘.xlsx`.
It rereads `/Users/mac/Downloads/小A自动化岗位说明书.xlsx` on every run.
Historical rows are preserved.
Duplicate resume content is still appended and marked red.
The resume folder is scanned recursively. All visible regular files are processed; unsupported formats are appended as `待人工二筛` with an extraction note.

## Web Interface

Double-click `启动简历筛选网页版.command` from this project folder.

On first launch, the script creates or reuses `.venv`, installs the tool, creates `config.yaml` from `config.example.yaml` if needed, builds the React page if needed, and opens `http://127.0.0.1:8765`.

The web page has four steps:

1. Confirm resume folder, job requirements workbook, and result workbook paths.
2. Save model API settings.
3. Run a lightweight precheck.
4. Start screening and watch live progress, logs, and final statistics.

## Manual-Review Mode

Set `model.allow_without_model: true` to process files without model calls.
Rows that require model judgment are classified as `待人工二筛`.
