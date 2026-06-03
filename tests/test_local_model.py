from pathlib import Path

from resume_screening.config import ModelConfig
from resume_screening.local_model import LocalModelManager, platform_runtime_key


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
