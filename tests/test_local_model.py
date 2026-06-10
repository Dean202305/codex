from pathlib import Path
import sys

from resume_screening.config import ModelConfig
from resume_screening.local_model import (
    LocalModelManager,
    default_runtime_root,
    local_model_startup_wait_seconds,
    platform_runtime_key,
)


def local_config(tmp_path: Path, **overrides: object) -> ModelConfig:
    local = {
        "model_path": str(tmp_path / "models" / "qwen.gguf"),
        "manifest_path": str(tmp_path / "models" / "manifest.json"),
        "host": "127.0.0.1",
        "port": 18080,
        "context_size": 8192,
    }
    local.update(overrides.pop("local", {}))
    data = {
        "provider": "local-qwen",
        "base_url": "",
        "api_key": "",
        "model": "qwen3.5-local",
        "timeout_seconds": 120,
        "temperature": 0.1,
        "allow_without_model": False,
        "local": local,
    }
    data.update(overrides)
    return ModelConfig.model_validate(data)


def test_platform_runtime_key_maps_common_desktop_targets() -> None:
    assert platform_runtime_key("Darwin", "arm64") == "macos-arm64"
    assert platform_runtime_key("Darwin", "x86_64") == "macos-x64"
    assert platform_runtime_key("Windows", "AMD64") == "windows-x64"
    assert platform_runtime_key("Windows", "x86_64") == "windows-x64"


def test_default_runtime_root_finds_packaged_onedir_runtime(tmp_path: Path, monkeypatch) -> None:
    app_dir = tmp_path / "App"
    runtime_root = app_dir / "_internal" / "packaging" / "runtime"
    runtime_root.mkdir(parents=True)
    monkeypatch.delenv("RESUME_SCREENING_RUNTIME_DIR", raising=False)
    monkeypatch.setattr(sys, "_MEIPASS", str(tmp_path / "missing-meipass"), raising=False)
    monkeypatch.setattr(sys, "executable", str(app_dir / "小A简历筛选.exe"))

    assert default_runtime_root() == runtime_root


def test_default_runtime_root_falls_back_to_working_directory_runtime(tmp_path: Path, monkeypatch) -> None:
    runtime_root = tmp_path / "packaging" / "runtime"
    runtime_root.mkdir(parents=True)
    monkeypatch.delenv("RESUME_SCREENING_RUNTIME_DIR", raising=False)
    monkeypatch.setattr(sys, "_MEIPASS", str(tmp_path / "missing-meipass"), raising=False)
    monkeypatch.setattr(sys, "executable", str(tmp_path / "venv" / "bin" / "python"))
    monkeypatch.chdir(tmp_path)

    assert default_runtime_root() == runtime_root


def test_status_reports_missing_runtime_before_model(tmp_path: Path) -> None:
    manager = LocalModelManager(local_config(tmp_path), app_data_dir=tmp_path / "app", runtime_root=tmp_path / "runtime")

    status = manager.status(system="Darwin", machine="arm64")

    assert status.state == "runtime_missing"
    assert status.runtime_available is False
    assert status.model_installed is False
    assert status.service_base_url == "http://127.0.0.1:18080/v1"


def test_status_reports_missing_model_when_runtime_exists(tmp_path: Path) -> None:
    runtime = tmp_path / "runtime" / "macos-arm64" / "llama-server"
    runtime.parent.mkdir(parents=True)
    runtime.write_text("#!/bin/sh\n", encoding="utf-8")
    manager = LocalModelManager(local_config(tmp_path), app_data_dir=tmp_path / "app", runtime_root=tmp_path / "runtime")

    status = manager.status(system="Darwin", machine="arm64")

    assert status.state == "model_missing"
    assert status.runtime_available is True
    assert status.model_installed is False


def test_environment_check_lists_runtime_model_and_data_directory(tmp_path: Path) -> None:
    runtime = tmp_path / "runtime" / "windows-x64" / "llama-server.exe"
    runtime.parent.mkdir(parents=True)
    runtime.write_text("@echo off\n", encoding="utf-8")
    manager = LocalModelManager(local_config(tmp_path), app_data_dir=tmp_path / "app", runtime_root=tmp_path / "runtime")

    report = manager.environment_check(system="Windows", machine="AMD64").to_dict()

    assert report["ready"] is False
    assert [item["id"] for item in report["items"]] == ["runtime", "model", "data_dir"]
    assert report["items"][0]["state"] == "ready"
    assert report["items"][1]["state"] == "missing"
    assert report["items"][1]["action"] == "download_model"
    assert report["items"][1]["requires_confirmation"] is True
    assert report["items"][2]["state"] == "ready"
    assert report["status"]["state"] == "model_missing"


def test_environment_check_is_ready_when_runtime_model_and_directory_exist(tmp_path: Path) -> None:
    runtime = tmp_path / "runtime" / "windows-x64" / "llama-server.exe"
    runtime.parent.mkdir(parents=True)
    runtime.write_text("@echo off\n", encoding="utf-8")
    model = tmp_path / "models" / "qwen.gguf"
    model.parent.mkdir()
    model.write_bytes(b"model")
    manager = LocalModelManager(local_config(tmp_path), app_data_dir=tmp_path / "app", runtime_root=tmp_path / "runtime")

    report = manager.environment_check(system="Windows", machine="AMD64").to_dict()

    assert report["ready"] is True
    assert {item["state"] for item in report["items"]} == {"ready"}


def test_status_reads_installed_manifest(tmp_path: Path) -> None:
    runtime = tmp_path / "runtime" / "macos-arm64" / "llama-server"
    runtime.parent.mkdir(parents=True)
    runtime.write_text("#!/bin/sh\n", encoding="utf-8")
    model = tmp_path / "models" / "qwen.gguf"
    model.parent.mkdir()
    model.write_bytes(b"model")
    config = local_config(tmp_path)
    manager = LocalModelManager(config, app_data_dir=tmp_path / "app", runtime_root=tmp_path / "runtime")
    manager.write_manifest(model, size_bytes=5, sha256="abc123", source_url="https://example.com/model.gguf")

    status = manager.status(system="Darwin", machine="arm64")

    assert status.state == "ready"
    assert status.model_installed is True
    assert status.model_path == str(model)
    assert status.manifest["sha256"] == "abc123"


def test_default_download_plan_uses_configured_target_path(tmp_path: Path) -> None:
    manager = LocalModelManager(local_config(tmp_path), app_data_dir=tmp_path / "app", runtime_root=tmp_path / "runtime")

    plan = manager.download_plan()

    assert plan.display_name.startswith("Qwen3.5")
    assert plan.target_path == str(tmp_path / "models" / "qwen.gguf")
    assert plan.size_bytes > 1_000_000_000
    assert plan.url.startswith("https://")


def test_build_server_command_uses_runtime_model_and_openai_port(tmp_path: Path) -> None:
    runtime = tmp_path / "runtime" / "macos-arm64" / "llama-server"
    runtime.parent.mkdir(parents=True)
    runtime.write_text("#!/bin/sh\n", encoding="utf-8")
    model = tmp_path / "models" / "qwen.gguf"
    model.parent.mkdir()
    model.write_bytes(b"model")
    manager = LocalModelManager(local_config(tmp_path), app_data_dir=tmp_path / "app", runtime_root=tmp_path / "runtime")

    command = manager.build_server_command(model, system="Darwin", machine="arm64")

    assert command[:3] == [str(runtime), "-m", str(model)]
    assert "--host" in command
    assert "127.0.0.1" in command
    assert "--port" in command
    assert "18080" in command
    assert "--alias" in command
    assert "qwen3.5-local" in command
    assert "--parallel" in command
    assert "1" in command
    assert "--no-ui" in command
    assert "--no-warmup" in command
    assert command[command.index("-ngl") + 1] == "auto"


def test_local_model_startup_wait_seconds_has_long_floor_and_cap() -> None:
    assert local_model_startup_wait_seconds(120) == 600
    assert local_model_startup_wait_seconds(900) == 900
    assert local_model_startup_wait_seconds(3600) == 1200


def test_check_service_reports_loading_model_503(tmp_path: Path, monkeypatch) -> None:
    import httpx
    import resume_screening.local_model as local_model

    manager = LocalModelManager(local_config(tmp_path), app_data_dir=tmp_path / "app", runtime_root=tmp_path / "runtime")

    def fake_get(url: str, timeout: float) -> httpx.Response:
        request = httpx.Request("GET", url)
        return httpx.Response(503, json={"error": {"message": "Loading model"}}, request=request)

    monkeypatch.setattr(local_model.httpx, "get", fake_get)

    available, message = manager.check_service()

    assert available is False
    assert message == "本地模型正在加载"


def test_windows_server_environment_adds_runtime_and_bundle_paths(tmp_path: Path, monkeypatch) -> None:
    import resume_screening.local_model as local_model

    runtime_root = tmp_path / "App" / "_internal" / "packaging" / "runtime"
    runtime = runtime_root / "windows-x64" / "llama-server.exe"
    runtime.parent.mkdir(parents=True)
    manager = LocalModelManager(local_config(tmp_path), app_data_dir=tmp_path / "app", runtime_root=runtime_root)
    monkeypatch.setattr(local_model.os, "name", "nt")
    monkeypatch.setenv("PATH", "C:\\Windows")

    env = manager._server_environment(runtime)

    assert str(runtime.parent) in env["PATH"]
    assert str(tmp_path / "App" / "_internal") in env["PATH"]


def test_macos_server_environment_adds_runtime_library_path(tmp_path: Path, monkeypatch) -> None:
    import resume_screening.local_model as local_model

    runtime_root = tmp_path / "App.app" / "Contents" / "Resources" / "packaging" / "runtime"
    runtime = runtime_root / "macos-arm64" / "llama-server"
    runtime.parent.mkdir(parents=True)
    manager = LocalModelManager(local_config(tmp_path), app_data_dir=tmp_path / "app", runtime_root=runtime_root)
    monkeypatch.setattr(local_model.sys, "platform", "darwin")
    monkeypatch.setenv("DYLD_LIBRARY_PATH", "/usr/local/lib")

    env = manager._server_environment(runtime)

    assert env["DYLD_LIBRARY_PATH"].split(local_model.os.pathsep)[0] == str(runtime.parent)
    assert "/usr/local/lib" in env["DYLD_LIBRARY_PATH"]
