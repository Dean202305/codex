# Resume Screening CLI

## Setup

```bash
python3 -m venv .venv
source .venv/bin/activate
python3 -m pip install ".[test]"
cp config.example.yaml config.yaml
```

Edit `config.yaml` and set `model.base_url`, `model.api_key`, and `model.model`.

If the resume filename job name differs from the job workbook sheet name, add aliases:

```yaml
job_aliases:
  后端开发工程师: "全栈"
  后端开发实习岗: "全栈"
```

## Run

```bash
resume-screening run --config config.yaml
```

The tool appends rows to `/Users/mac/Downloads/小A科技（北京）组织招聘.xlsx`.
It rereads `/Users/mac/Downloads/小A自动化岗位说明书_副本.xlsx` on every run.
Historical rows are preserved.
Duplicate resume content is still appended and marked red.
The resume folder is scanned recursively. All visible regular files are processed; unsupported formats are appended as `待人工二筛` with an extraction note.
Supported filename formats include `【岗位_地点 薪资】姓名 工龄.pdf` and `岗位_地点_薪资_姓名_工龄.pdf`.
The job workbook can use the original one-sheet-per-job layout or a tabular layout where each row contains a `岗位名称`.

## Web Interface

Double-click `启动简历筛选网页版.command` from this project folder.

On first launch, the script creates or reuses `.venv`, installs the tool, creates `config.yaml` from `config.example.yaml` if needed, builds the React page if needed, and opens `http://127.0.0.1:8765`.

The web page has four steps:

1. Confirm resume folder, job requirements workbook, result workbook paths, and optional job aliases.
2. Save model API settings.
3. Run a lightweight precheck.
4. Start screening and watch live progress, logs, and final statistics.

## Local Desktop App

Build a portable macOS app bundle:

```bash
source .venv/bin/activate
bash scripts/build_macos_app.sh
```

The outputs are `dist/小A简历筛选.app` and `dist/小A简历筛选-mac.zip`.

The app stores its config at `~/Library/Application Support/小A简历筛选/config.yaml`.
When copied to a new Mac, copy `小A简历筛选-mac.zip`, unzip it, launch the app, and reselect the local resume folder, job workbook, result workbook, and model API settings.
The app bundles the Python runtime and project dependencies. OCR still depends on a local `tesseract` installation if image or scanned-PDF recognition is needed.
The app is built for the architecture of the Mac that runs the build script. The current generated package is for Apple Silicon; build again on Intel Mac if an Intel-only Mac needs to run it.

## Manual-Review Mode

Set `model.allow_without_model: true` to process files without model calls.
Rows that require model judgment are classified as `待人工二筛`.
When `base_url`, `api_key`, and `model` are all set, the tool uses the model first even if fallback mode is enabled.
