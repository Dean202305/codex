# Local Qwen Model Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a local Qwen model mode that can detect missing model files, ask the user to confirm a download, download/install the model, verify availability, and preserve the existing custom API mode.

**Architecture:** Keep model inference OpenAI-compatible. Add a focused local model manager that owns runtime/model paths, status, download tasks, and service checks; config/precheck/model client consume that manager through small interfaces. The frontend adds a provider switch and local model status/download controls without changing the screening result flow.

**Tech Stack:** Python 3.11+, Pydantic, FastAPI, httpx, pytest, React/Vite, PyInstaller, llama.cpp `llama-server`.

---

### Task 1: Config Model Shape

**Files:**
- Modify: `src/resume_screening/config.py`
- Modify: `src/resume_screening/web/config_store.py`
- Test: `tests/test_config.py`
- Test: `tests/test_web_config_store.py`

- [ ] **Step 1: Write failing config tests**

Add tests that validate `provider: local-qwen`, nested local settings, and legacy custom API config.

- [ ] **Step 2: Run config tests and verify failure**

Run: `.venv/bin/python -m pytest tests/test_config.py tests/test_web_config_store.py -v`
Expected: FAIL because `local-qwen` and `model.local` do not exist yet.

- [ ] **Step 3: Implement config models**

Add `LocalModelConfig`, extend `ModelConfig.provider`, make `api_key` optional for local mode, and keep custom API validation strict unless `allow_without_model` is enabled.

- [ ] **Step 4: Run tests and commit**

Run: `.venv/bin/python -m pytest tests/test_config.py tests/test_web_config_store.py -v`
Expected: PASS.

### Task 2: Local Model Manager

**Files:**
- Create: `src/resume_screening/local_model.py`
- Test: `tests/test_local_model.py`

- [ ] **Step 1: Write failing manager tests**

Cover app data directory resolution, runtime path selection, missing model status, installed model manifest status, download plan shape, and service base URL.

- [ ] **Step 2: Run local manager tests and verify failure**

Run: `.venv/bin/python -m pytest tests/test_local_model.py -v`
Expected: FAIL because `resume_screening.local_model` does not exist.

- [ ] **Step 3: Implement local manager**

Implement dataclasses for status/download plan, model manifest read/write, runtime path detection, model path resolution, and non-network status checks. Add service command construction but keep actual subprocess start behind methods that tests can avoid.

- [ ] **Step 4: Run tests and commit**

Run: `.venv/bin/python -m pytest tests/test_local_model.py -v`
Expected: PASS.

### Task 3: Web API For Status, Download, And Check

**Files:**
- Modify: `src/resume_screening/web/app.py`
- Create: `src/resume_screening/web/local_model_api.py`
- Test: `tests/test_web_local_model_api.py`

- [ ] **Step 1: Write failing API tests**

Use FastAPI TestClient to assert `/api/local-model/status`, `/api/local-model/download-plan`, `/api/local-model/download`, `/api/local-model/download/{task_id}`, cancel, and check endpoints return stable JSON.

- [ ] **Step 2: Run API tests and verify failure**

Run: `.venv/bin/python -m pytest tests/test_web_local_model_api.py -v`
Expected: FAIL because endpoints do not exist.

- [ ] **Step 3: Implement API**

Add a lightweight in-memory download task manager. Support deterministic tests with a fake download mode for small local files; production code streams remote URLs to `.part`, verifies size/SHA256 when present, installs manifest, and returns progress.

- [ ] **Step 4: Run tests and commit**

Run: `.venv/bin/python -m pytest tests/test_web_local_model_api.py -v`
Expected: PASS.

### Task 4: Precheck And Model Client Integration

**Files:**
- Modify: `src/resume_screening/web/precheck.py`
- Modify: `src/resume_screening/model_client.py`
- Modify: `src/resume_screening/pipeline.py`
- Test: `tests/test_web_precheck.py`
- Test: `tests/test_model_client.py`
- Test: `tests/test_pipeline.py`

- [ ] **Step 1: Write failing integration tests**

Add tests for local mode precheck when model is missing, local mode when installed, custom mode still requiring API fields, and model client deriving local base URL.

- [ ] **Step 2: Run tests and verify failure**

Run: `.venv/bin/python -m pytest tests/test_web_precheck.py tests/test_model_client.py tests/test_pipeline.py -v`
Expected: FAIL because provider-specific checks and local base URL are not wired.

- [ ] **Step 3: Implement integration**

Use local manager for local provider. If the model is missing, precheck returns a warning with a download action message; screening cannot silently fall back unless `allow_without_model` is explicitly true. If installed, client talks to `http://127.0.0.1:<port>/v1/chat/completions`.

- [ ] **Step 4: Run tests and commit**

Run: `.venv/bin/python -m pytest tests/test_web_precheck.py tests/test_model_client.py tests/test_pipeline.py -v`
Expected: PASS.

### Task 5: React Local Model UI

**Files:**
- Modify: `web/src/App.jsx`
- Modify: `web/src/styles.css`

- [ ] **Step 1: Add frontend behavior**

Add provider segmented control, local status card, download confirmation dialog, download progress, availability check button, and custom API mode preserving existing fields.

- [ ] **Step 2: Build frontend**

Run: `npm --prefix web run build`
Expected: PASS and updated `web/dist` assets.

- [ ] **Step 3: Verify in browser**

Run the local app server and open the current local URL. Confirm the model mode switch, missing model prompt, and download progress UI render cleanly.

- [ ] **Step 4: Commit**

Commit frontend changes with the backend API they depend on.

### Task 6: Packaging For macOS And Windows

**Files:**
- Modify: `scripts/build_macos_app.sh`
- Create: `scripts/build_windows_app.ps1`
- Create: `packaging/windows/resume_screening_windows.spec`
- Create: `packaging/runtime/README.md`
- Test: `tests/test_packaging_scripts.py`

- [ ] **Step 1: Write failing packaging tests**

Assert macOS script checks runtime paths, Windows script exists, Windows spec includes app entry and static assets, and runtime README documents required binary paths.

- [ ] **Step 2: Run packaging tests and verify failure**

Run: `.venv/bin/python -m pytest tests/test_packaging_scripts.py -v`
Expected: FAIL because Windows packaging files do not exist yet.

- [ ] **Step 3: Implement packaging updates**

Add runtime directory convention, script checks, and Windows PyInstaller spec. Do not bundle model weights in either package.

- [ ] **Step 4: Run tests and commit**

Run: `.venv/bin/python -m pytest tests/test_packaging_scripts.py -v`
Expected: PASS.

### Task 7: Full Verification

**Files:**
- No new files expected.

- [ ] **Step 1: Run backend test suite**

Run: `.venv/bin/python -m pytest -v`
Expected: PASS.

- [ ] **Step 2: Run frontend build**

Run: `npm --prefix web run build`
Expected: PASS.

- [ ] **Step 3: Build macOS package if runtime is available**

Run: `scripts/build_macos_app.sh`
Expected: PASS only if `packaging/runtime/<current-arch>/llama-server` exists; otherwise document the missing runtime binary.

- [ ] **Step 4: Summarize Windows boundary**

Confirm Windows script/spec are present. State that the Windows artifact still needs to be built on Windows or CI.
