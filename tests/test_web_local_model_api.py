from __future__ import annotations

import hashlib
from pathlib import Path
import time

from fastapi.testclient import TestClient
import yaml

from resume_screening.local_model import platform_runtime_key
from resume_screening.web.app import create_app
from resume_screening.web.local_model_api import _download_error_message, _file_url_to_path


def write_local_config(config_path: Path, tmp_path: Path, *, port: int = 18080) -> Path:
    model_path = tmp_path / "models" / "qwen.gguf"
    config_path.write_text(
        yaml.safe_dump(
            {
                "resume_dir": str(tmp_path / "resumes"),
                "job_book": str(tmp_path / "jobs.xlsx"),
                "result_book": str(tmp_path / "result.xlsx"),
                "model": {
                    "provider": "local-qwen",
                    "base_url": "",
                    "api_key": "",
                    "model": "qwen3.5-local",
                    "timeout_seconds": 120,
                    "temperature": 0.1,
                    "allow_without_model": False,
                    "local": {
                        "model_path": str(model_path),
                        "manifest_path": str(tmp_path / "models" / "manifest.json"),
                        "host": "127.0.0.1",
                        "port": port,
                    },
                },
            },
            allow_unicode=True,
        ),
        encoding="utf-8",
    )
    return model_path


def create_runtime(runtime_root: Path) -> None:
    key = platform_runtime_key()
    executable = "llama-server.exe" if key.startswith("windows") else "llama-server"
    runtime = runtime_root / key / executable
    runtime.parent.mkdir(parents=True)
    runtime.write_text("@echo off\n" if executable.endswith(".exe") else "#!/bin/sh\n", encoding="utf-8")


def test_file_url_to_path_roundtrip(tmp_path: Path) -> None:
    source = tmp_path / "model source.gguf"
    source.write_bytes(b"model")

    assert _file_url_to_path(source.as_uri()) == source


def test_download_error_message_normalizes_windows_connection_refused() -> None:
    import httpx

    message = _download_error_message(
        httpx.ConnectError("[WinError 10061] 由于目标计算机积极拒绝，无法连接")
    )

    assert "模型下载连接失败" in message
    assert "VPN/代理" in message
    assert "WinError 10061" not in message


def test_local_model_status_and_plan_endpoints(tmp_path: Path, monkeypatch) -> None:
    config_path = tmp_path / "config.yaml"
    model_path = write_local_config(config_path, tmp_path)
    runtime_root = tmp_path / "runtime"
    create_runtime(runtime_root)
    monkeypatch.setenv("RESUME_SCREENING_RUNTIME_DIR", str(runtime_root))
    client = TestClient(create_app(config_path=config_path))

    response = client.get("/api/local-model/status")
    plan_response = client.get("/api/local-model/download-plan")

    assert response.status_code == 200
    assert response.json()["status"]["state"] == "model_missing"
    assert response.json()["status"]["runtime_available"] is True
    assert plan_response.status_code == 200
    assert plan_response.json()["plan"]["target_path"] == str(model_path)
    assert plan_response.json()["plan"]["display_name"].startswith("Qwen3.5")


def test_local_model_environment_endpoint_marks_model_download_as_confirmed_action(tmp_path: Path, monkeypatch) -> None:
    config_path = tmp_path / "config.yaml"
    write_local_config(config_path, tmp_path)
    runtime_root = tmp_path / "runtime"
    create_runtime(runtime_root)
    monkeypatch.setenv("RESUME_SCREENING_RUNTIME_DIR", str(runtime_root))
    client = TestClient(create_app(config_path=config_path))

    response = client.get("/api/local-model/environment")

    assert response.status_code == 200
    environment = response.json()["environment"]
    assert environment["ready"] is False
    assert [item["id"] for item in environment["items"]] == ["runtime", "model", "data_dir"]
    model_item = next(item for item in environment["items"] if item["id"] == "model")
    assert model_item["state"] == "missing"
    assert model_item["action"] == "download_model"
    assert model_item["requires_confirmation"] is True


def test_local_model_download_installs_file_and_manifest(tmp_path: Path, monkeypatch) -> None:
    config_path = tmp_path / "config.yaml"
    model_path = write_local_config(config_path, tmp_path)
    runtime_root = tmp_path / "runtime"
    create_runtime(runtime_root)
    monkeypatch.setenv("RESUME_SCREENING_RUNTIME_DIR", str(runtime_root))
    source = tmp_path / "source.gguf"
    source.write_bytes(b"small-model")
    sha256 = hashlib.sha256(b"small-model").hexdigest()
    client = TestClient(create_app(config_path=config_path))

    response = client.post(
        "/api/local-model/download",
        json={"url": source.as_uri(), "size_bytes": source.stat().st_size, "sha256": sha256},
    )
    assert response.status_code == 200
    task_id = response.json()["task"]["task_id"]

    task = None
    for _ in range(20):
        task = client.get(f"/api/local-model/download/{task_id}").json()["task"]
        if task["state"] == "completed":
            break
        time.sleep(0.05)

    assert task is not None
    assert task["state"] == "completed"
    assert model_path.read_bytes() == b"small-model"
    status = client.get("/api/local-model/status").json()["status"]
    assert status["state"] == "ready"
    assert status["manifest"]["sha256"] == sha256


def test_local_model_download_cancel_unknown_task_returns_404(tmp_path: Path) -> None:
    config_path = tmp_path / "config.yaml"
    write_local_config(config_path, tmp_path)
    client = TestClient(create_app(config_path=config_path))

    response = client.post("/api/local-model/download/missing/cancel")

    assert response.status_code == 404


def test_local_model_check_reports_unavailable_service_without_crashing(
    tmp_path: Path,
    monkeypatch,
    free_tcp_port: int,
) -> None:
    config_path = tmp_path / "config.yaml"
    model_path = write_local_config(config_path, tmp_path, port=free_tcp_port)
    model_path.parent.mkdir(parents=True)
    model_path.write_bytes(b"small-model")
    runtime_root = tmp_path / "runtime"
    create_runtime(runtime_root)
    monkeypatch.setenv("RESUME_SCREENING_RUNTIME_DIR", str(runtime_root))
    client = TestClient(create_app(config_path=config_path))

    response = client.post("/api/local-model/check")

    assert response.status_code == 200
    assert response.json()["available"] is False
    assert response.json()["status"]["state"] == "ready"
    assert "启动失败" in response.json()["message"] or "Permission" in response.json()["message"]


def test_local_model_check_auto_starts_ready_service(tmp_path: Path, monkeypatch) -> None:
    import resume_screening.web.local_model_api as local_model_api

    config_path = tmp_path / "config.yaml"
    model_path = write_local_config(config_path, tmp_path)
    model_path.parent.mkdir(parents=True)
    model_path.write_bytes(b"small-model")
    runtime_root = tmp_path / "runtime"
    create_runtime(runtime_root)
    monkeypatch.setenv("RESUME_SCREENING_RUNTIME_DIR", str(runtime_root))
    checks = {"count": 0}
    started: list[float] = []

    def fake_check_service(self, timeout_seconds: float = 5) -> tuple[bool, str]:
        checks["count"] += 1
        if checks["count"] == 1:
            return False, "[Errno 61] Connection refused"
        return True, "本地模型服务可用"

    def fake_start_service(self, wait_seconds: float = 30) -> object:
        started.append(wait_seconds)
        return object()

    monkeypatch.setattr(local_model_api.LocalModelManager, "check_service", fake_check_service)
    monkeypatch.setattr(local_model_api.LocalModelManager, "start_service", fake_start_service)
    client = TestClient(create_app(config_path=config_path))

    response = client.post("/api/local-model/check")

    assert response.status_code == 200
    assert response.json()["available"] is True
    assert response.json()["message"] == "本地模型服务已启动并可用"
    assert started == [600]
