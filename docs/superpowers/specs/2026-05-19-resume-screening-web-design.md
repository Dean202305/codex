# Resume Screening Web Design

## Overview

Build a local web interface for the existing resume screening automation.

The web version should make the current CLI easier to use without changing the core screening behavior. It runs entirely on the user's Mac: a local Python backend reads and writes local files, while a React frontend provides a step-by-step browser interface.

The first web version prioritizes reliable local operation, clear progress visibility, and safe Excel writeback. It is not a cloud product and does not introduce user accounts, remote storage, or online file upload.

## Confirmed Decisions

- UI style: step-by-step wizard.
- Frontend/backend approach: React frontend plus Python backend.
- Startup method: double-click a local `.command` file as the primary user entry.
- Configuration storage: save editable settings to local `config.yaml`.
- Default paths: prefill the current known local paths, and allow editing in the page.
- Precheck depth: simple precheck only.
- Run feedback: show real-time progress and logs.
- File writeback: continue writing to the original recruiting workbook and append rows without overwriting history.

## Local Architecture

The system has three local pieces:

1. A double-click startup script.
2. A FastAPI backend service.
3. A React frontend served locally.

The startup script launches the backend and opens the browser to the local web page. The React page calls local API endpoints exposed by the backend. The browser never reads or writes arbitrary local files directly; local file access is handled by the Python process.

The backend reuses the existing screening modules for:

- Configuration loading.
- Resume directory scanning.
- Filename parsing.
- Document text extraction.
- Job requirements workbook reading.
- Model evaluation.
- Duplicate content detection.
- Excel row append and duplicate row red marking.

This keeps CLI and web behavior aligned and avoids creating a second screening implementation.

## User Flow

The first web version has four wizard steps.

### Step 1: File Paths

Show editable path fields for:

- Resume directory, defaulting to `/Users/mac/Downloads`.
- Job requirements workbook, defaulting to `/Users/mac/Downloads/小A自动化岗位说明书.xlsx`.
- Recruiting result workbook, defaulting to `/Users/mac/Downloads/小A科技（北京）组织招聘.xlsx`.

The page should make it clear when a path is missing or unreadable, but it should not scan every file in detail on this step.

### Step 2: Model Configuration

Show editable fields for:

- API base URL.
- API key.
- Model name.
- Timeout seconds.
- Allow-without-model fallback option if it already exists in the CLI configuration.

Saving this step writes to local `config.yaml`. The API key remains local and is not written to the recruiting Excel workbook.

### Step 3: Precheck

Run a lightweight precheck and show:

- Number of supported resume files found.
- Whether the job requirements workbook exists and can be read.
- Whether usable job sheets are present.
- Whether the recruiting workbook exists and appears writable.
- Whether required model settings are present, unless offline/manual fallback is enabled.

The precheck does not show the full resume file list and does not perform full model evaluation.

### Step 4: Run Screening

Show a start button, progress indicator, current file name, running logs, and final statistics.

Final statistics include:

- Processed file count.
- Appended row count.
- Duplicate-content row count.
- Category counts for `推荐初试`, `可考虑`, `待人工二筛`, and `未通过`.
- Model timeout or model failure count.

The page may show the result workbook path after completion, but it should not automatically open Excel while the backend is writing the workbook.

## Backend API

The backend exposes local JSON endpoints for the React frontend.

### `GET /api/config`

Return the current effective configuration, including defaults from the project when `config.yaml` is incomplete.

Sensitive values such as API keys may be returned masked unless the implementation needs plain values for editing. The first version can return the raw local value because the page is local-only, but the design should keep masking as an easy later improvement.

### `POST /api/config`

Validate and save editable path and model settings to `config.yaml`.

Validation should catch obvious malformed values, such as empty required paths or non-numeric timeout values. It should not require every external file to exist before saving, because users may edit paths before creating files.

### `GET /api/precheck`

Run the lightweight precheck using the current saved configuration.

The endpoint returns a structured result with:

- Overall status: pass, warning, or fail.
- Individual check items.
- Human-readable messages for the page.

Warnings should allow the user to continue when the existing CLI would still be able to route affected resumes to `待人工二筛`.

### `POST /api/runs`

Start one screening run.

Only one run may execute at a time. If a run is already active, return the existing run status or a clear conflict response so the page can show that another task is running.

### `GET /api/runs/{run_id}`

Return the latest run status:

- Run state: queued, running, completed, failed, or cancelled if cancellation is later added.
- Current file index and total file count.
- Current file name.
- Recent logs.
- Accumulated warnings and errors.
- Current statistics.

The first implementation can use polling from the React page. Server-sent events or WebSockets can be added later if needed, but they are not required for the first version.

## Run State and Concurrency

The backend keeps an in-memory run registry for the current process. This is enough for the first local-only version.

The run worker executes in the background so the API remains responsive while screening is in progress. A process-level lock prevents two runs from writing to the same workbook at the same time.

If the backend process is closed during a run, the run is considered interrupted. The existing Excel append behavior and local processed index should remain the source of truth for what was already written.

## Error Handling

The web version follows the CLI's conservative screening behavior.

- If a resume has a non-standard filename, still extract text and route to `待人工二筛`.
- If the matching job sheet is missing or incomplete, route affected resumes to `待人工二筛`.
- If document text extraction fails, write a manual-review result when possible and log the extraction issue.
- If the model API times out or returns invalid output, do not stop the batch. Mark that resume as `待人工二筛` and log the model problem.
- If the recruiting workbook is locked by Excel or not writable, stop before modifying it and show a clear error.
- If a duplicate content fingerprint is detected, write the row and apply the existing red row marking behavior.

The page should distinguish blocking errors from warnings. Blocking errors stop the run before unsafe writeback; warnings are visible but allow the run to continue.

## Files and Build Shape

The implementation should keep the web layer separate from the screening core.

Expected project additions:

- A web backend module under `src/resume_screening/web/`.
- React frontend source under a dedicated web directory, such as `web/`.
- A command entry for launching the local web server.
- A double-click `.command` startup file for everyday use.
- Tests for configuration endpoints, precheck behavior, and run-state locking.

The backend should import the existing core modules rather than shelling out to the CLI whenever practical. If a small orchestration adapter is needed, it should sit between the web worker and the existing pipeline.

## Testing and Verification

Automated tests should cover:

- Loading current configuration through the API.
- Saving edited configuration to a temporary config file.
- Precheck results for valid and invalid test paths.
- Rejecting or reusing a run request while another run is active.
- Model failure fallback remaining visible in run logs and statistics.

Manual verification should cover:

- Double-click startup opens the local page.
- The React wizard can save paths and API settings.
- Precheck displays simple status without listing every resume.
- A test run shows progress and logs.
- The result workbook append behavior remains consistent with the CLI.

The implementation is complete only after the local web page can be opened in a browser and the primary wizard flow has been exercised.

## Out of Scope for First Web Version

- Cloud deployment.
- Multi-user accounts or authentication.
- Uploading resumes through a remote webpage.
- Editing the recruiting workbook directly in the web UI.
- A historical run database.
- Parallel screening runs.
- Complex desktop app packaging.
