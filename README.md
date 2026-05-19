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

## Manual-Review Mode

Set `model.allow_without_model: true` to process files without model calls.
Rows that require model judgment are classified as `待人工二筛`.
