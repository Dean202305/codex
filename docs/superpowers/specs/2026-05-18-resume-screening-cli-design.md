# Resume Screening CLI Design

## Overview

Build a command-line automation tool for initial resume screening and structured recruiting records.

The tool scans resume files, reads the latest job requirements from a workbook, extracts resume text, evaluates each candidate with a configurable OpenAI-compatible model API, and appends results to a fixed recruiting Excel workbook. It never overwrites historical rows.

The first version prioritizes reliability over UI polish. It will be a stable CLI that can later be wrapped by a local web or desktop interface.

## Confirmed Inputs

### Resume Directory

- Default directory: `/Users/mac/Downloads`
- Supported formats:
  - Primary: `.pdf`
  - Secondary: `.jpg`, `.jpeg`, `.png`, `.doc`, `.docx`, `.pptx`
- The tool skips the job requirements workbook and result workbook themselves.

### Job Requirements Workbook

- Path: `/Users/mac/Downloads/小A自动化岗位说明书.xlsx`
- Each job is represented by one sheet.
- The sheet named `模板` is ignored.
- The workbook must be reread on every run because requirements may change.
- The tool must not cache parsed job requirements as authoritative screening rules.

Known current job sheets include:

- `产品总监`
- `全栈`
- `算法`
- `产品实习生`
- `财务`
- `人事`

Some current job sheets are partially empty or template-like. The tool must detect incomplete job requirements and route affected resumes to manual review instead of rejecting them.

### Result Workbook

- Path: `/Users/mac/Downloads/小A科技（北京）组织招聘.xlsx`
- Target sheet: `多维表格`
- Existing columns:
  - `ID`
  - `当前阶段`
  - `候选人`
  - `附件`
  - `岗位方向`
  - `来源渠道`
  - `候选人摘要（妙记）`
  - `量化打分`
  - `可投入周期`
  - `面试负责人`
  - `下次动作日`
  - `不推进原因`
  - `推荐/触达人`
- Add only these necessary columns after the existing table:
  - `初筛分类`
  - `初筛理由`
  - `缺失信息`

The tool appends rows below existing data and continues from the current maximum `ID`.

## Resume Filename Parsing

The preferred filename pattern is:

```text
【岗位名称_期望工作地 薪资】候选人姓名 工龄
```

Example:

```text
【财务总监_北京 18-28K】郭燕婷 10年以上
```

When the pattern matches, the parser extracts:

- Job name
- Expected work location
- Stated salary range
- Candidate name
- Work experience

The job name is used to match a sheet in the job requirements workbook.

If the filename does not match the pattern:

- The tool still attempts to extract resume text.
- The row is classified as `待人工二筛`.
- `缺失信息` records that the filename is non-standard and key fields could not be confirmed from the filename.

## Architecture

Use the recommended hybrid approach:

- Local code handles deterministic work:
  - File scanning
  - Filename parsing
  - Document text extraction
  - Job workbook parsing
  - Duplicate content detection
  - Excel append/writeback
  - Logging and error handling
- The model API handles semantic judgment:
  - Resume and job requirement matching
  - Candidate summary
  - Scoring
  - Category selection
  - Screening rationale
  - Missing information analysis

This gives better accuracy than pure rules and better traceability than sending everything blindly to the model.

## Data Flow

1. Load configuration.
2. Read the latest job requirements workbook.
3. Validate each non-template job sheet for usable requirements.
4. Open the result workbook and inspect existing rows.
5. Build a historical content fingerprint index from stored local records.
6. Scan the resume directory for supported files.
7. For each resume:
   - Parse metadata from filename.
   - Extract document text.
   - Normalize extracted text.
   - Compute content fingerprint.
   - Detect exact or highly similar historical content.
   - Match filename job name to a job sheet.
   - If extraction or job requirements are incomplete, prepare a manual-review result.
   - Otherwise call the configured model API for evaluation.
   - Validate the model response against the expected JSON schema.
   - Append a row to the result workbook.
   - Mark duplicate-content rows in red.
8. Save the result workbook in place.
9. Update the local processed index.
10. Print a run summary.

## Screening Categories

Use these four categories:

- `推荐初试`
- `可考虑`
- `待人工二筛`
- `未通过`

Rules:

- `推荐初试`: overall score is at least 8, job requirements are basically satisfied, and key information is complete.
- `可考虑`: overall score is 7 to 7.9, or score is at least 8 but there is minor uncertainty.
- `待人工二筛`: filename is non-standard, job sheet cannot be matched, key information is missing, job requirements are incomplete, resume text extraction is weak, the model is uncertain, or the model/API fails.
- `未通过`: overall score is below 7, or the resume clearly misses hard requirements.

Score interpretation:

- 10-point scale.
- 8 means pass.
- 9 means excellent.

## Model Evaluation Output

The model must return structured JSON so the CLI can validate and write deterministic fields.

Required fields:

- `category`: one of `推荐初试`, `可考虑`, `待人工二筛`, `未通过`
- `overall_score`: number from 0 to 10
- `summary`: concise candidate summary for `候选人摘要（妙记）`
- `screening_reason`: concise rationale for `初筛理由`
- `missing_information`: array of missing or uncertain information
- `reject_reason`: string, required when category is `未通过`
- `scores`:
  - `ability`: 0 to 10
  - `ego`: 0 to 10
  - `desire`: 0 to 10
  - `learning_ability`: 0 to 10
  - `job_fit`: 0 to 10
  - `experience_fit`: 0 to 10
  - `skill_fit`: 0 to 10
  - `stability_risk`: 0 to 10, where higher means lower risk

The `量化打分` cell should include both the original potential/personality-style dimensions and the job matching dimensions:

```text
综合评分：8.3/10
结论：通过

能力：8
ego大小：6
野心desire：8
学习能力与聪明程度：8

岗位匹配度：8
经验匹配：9
技能匹配：8
稳定性/风险：7

评价：...
```

## Excel Write Rules

Append one row per processed resume.

Column mapping:

- `ID`: next numeric ID after the current maximum.
- `当前阶段`: screening category.
- `候选人`: filename candidate name first; if missing, model-extracted name; if still missing, blank.
- `附件`: original filename.
- `岗位方向`: parsed job name or matched job sheet name.
- `来源渠道`: configurable default, initially blank.
- `候选人摘要（妙记）`: model summary or extraction failure note.
- `量化打分`: formatted scoring block.
- `可投入周期`: blank in v1.
- `面试负责人`: configurable default, initially blank.
- `下次动作日`: blank in v1.
- `不推进原因`: filled only for `未通过`.
- `推荐/触达人`: blank in v1.
- `初筛分类`: screening category.
- `初筛理由`: model or fallback rationale.
- `缺失信息`: semicolon-separated missing fields, parse issues, duplicate warnings, or model/API errors.

If duplicate content is detected, append the row normally and mark the entire row red.

## Duplicate Detection

Duplicate detection is based on resume content, not filenames.

The tool normalizes extracted text by removing excess whitespace, common page noise, and irrelevant symbol differences while preserving meaningful text.

It then computes a text fingerprint and stores metadata in a local index such as:

```text
data/processed_index.json
```

The index records:

- Fingerprint
- Original filename
- Candidate name when known
- Job name when known
- Processed timestamp
- Result workbook row ID

When a new resume matches prior content exactly or with high similarity:

- The tool still appends a new row.
- The entire row is marked red.
- `缺失信息` or `初筛理由` includes:

```text
疑似重复简历：与历史附件 xxx 内容一致
```

## Document Extraction

Extraction strategy by file type:

- PDF: extract text first; if text is too short or likely scanned, use OCR fallback.
- JPG/PNG/JPEG: use OCR.
- DOC/DOCX: extract document body text, using a best-effort converter for legacy `.doc`.
- PPTX: extract text from slides and text boxes.

If text cannot be extracted:

- Append a row.
- Classify as `待人工二筛`.
- Record `无法提取简历正文` in `缺失信息`.

## Job Requirement Validation

Each job sheet is considered incomplete if it is empty, only contains template placeholders, or lacks usable details for core fields such as:

- Job name
- Education
- Major or skills
- Work experience
- Job purpose
- Core responsibilities
- Supplemental notes, if present

If the matched job sheet is incomplete:

- Do not reject the candidate based on absent requirements.
- Classify as `待人工二筛`.
- Record `岗位要求不完整，需人工确认`.

## Model Configuration

The model interface must be OpenAI-compatible and configurable.

Example config:

```yaml
resume_dir: "/Users/mac/Downloads"
job_book: "/Users/mac/Downloads/小A自动化岗位说明书.xlsx"
result_book: "/Users/mac/Downloads/小A科技（北京）组织招聘.xlsx"

default_source_channel: ""
default_interviewer: ""

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

The CLI validates model config at startup. If model config is missing, it prints a clear warning and runs in manual-review mode only when `allow_without_model: true` is set. Otherwise it exits before modifying the result workbook.

## Model and API Errors

Model timeout, authentication errors, provider errors, invalid JSON, and schema validation failures must be visible in two places:

- Real-time command-line output during the run.
- The Excel row's `缺失信息`.

Examples:

- `模型评估失败：请求超时`
- `模型评估失败：API认证错误`
- `模型评估失败：返回格式不符合JSON结构`

The batch should continue after a per-resume model failure.

The affected resume should be classified as `待人工二筛`.

## CLI

Primary command:

```bash
resume-screening run --config config.yaml
```

Expected end-of-run summary:

- Processed file count
- `推荐初试` count
- `可考虑` count
- `待人工二筛` count
- `未通过` count
- Duplicate-content count
- Model/API failure count
- Files that could not be extracted
- Files with non-standard names

## Testing Strategy

Cover the risky behavior with focused tests:

- Filename parser:
  - Standard filename.
  - Candidate names with multiple Chinese characters.
  - Missing salary.
  - Non-standard filename.
- Job workbook parser:
  - Ignores `模板`.
  - Detects incomplete job sheets.
  - Matches job names to sheet names.
- Resume extraction:
  - Text PDF.
  - Image/OCR path when OCR is available.
  - Unsupported or unreadable file.
- Duplicate detection:
  - Same content and same filename.
  - Same content and different filename.
  - Different content and same candidate name.
- Model adapter:
  - Valid JSON response.
  - Timeout.
  - Invalid JSON.
  - Missing API config.
- Excel writer:
  - Appends after existing rows.
  - Preserves existing history.
  - Adds only the three required new columns.
  - Continues ID sequence.
  - Marks duplicate rows red.

## Non-Goals for Version 1

- No web UI.
- No desktop app.
- No automatic email or recruitment platform integration.
- No automatic editing of job requirement sheets.
- No destructive rewrite or deduplication of existing result rows.
- No automatic scheduling.

## Version 1 Implementation Choices

Use these implementation choices for the first build:

- Runtime: Python CLI.
- Config format: YAML.
- Excel append/writeback: `openpyxl`, preserving existing workbook sheets and styles where possible.
- PDF text extraction: `pypdf`.
- DOCX extraction: `python-docx`.
- Legacy `.doc` extraction: best-effort conversion through macOS `textutil`; if unavailable or failed, classify as `待人工二筛`.
- PPTX extraction: `python-pptx`.
- Image OCR: configurable local OCR command; default to `tesseract` when available. If OCR is unavailable or fails, classify as `待人工二筛`.
- Duplicate exact match: SHA-256 of normalized resume text.
- Duplicate near match: normalized text similarity at or above 0.92.
- Model adapter: OpenAI-compatible chat completions API, configured by `base_url`, `api_key`, `model`, timeout, and temperature.
