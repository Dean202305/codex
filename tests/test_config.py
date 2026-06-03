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
                "job_book": "/Users/mac/Downloads/小A自动化岗位说明书_副本.xlsx",
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


def test_config_normalizes_common_copied_path_formats(tmp_path: Path) -> None:
    resume_dir = tmp_path / "Resume Folder"
    resume_dir.mkdir()

    config = AppConfig.model_validate(
        {
            "resume_dir": f" '{resume_dir}' ",
            "job_book": f'"{tmp_path / "jobs.xlsx"}"',
            "result_book": str(tmp_path / "result.xlsx"),
            "index_path": str(tmp_path / "Data Folder" / "index.json").replace(" ", "\\ "),
            "model": {
                "provider": "openai-compatible",
                "base_url": "",
                "api_key": "",
                "model": "",
                "timeout_seconds": 60,
                "temperature": 0.1,
                "allow_without_model": True,
            },
        }
    )

    assert config.resume_dir == resume_dir
    assert config.job_book == tmp_path / "jobs.xlsx"
    assert config.index_path == tmp_path / "Data Folder" / "index.json"


def test_config_rejects_missing_model_when_manual_mode_disabled() -> None:
    with pytest.raises(ValidationError):
        AppConfig.model_validate(
            {
                "resume_dir": "/Users/mac/Downloads",
                "job_book": "/Users/mac/Downloads/小A自动化岗位说明书_副本.xlsx",
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


def test_config_accepts_local_qwen_without_api_credentials(tmp_path: Path) -> None:
    config = AppConfig.model_validate(
        {
            "resume_dir": tmp_path / "resumes",
            "job_book": tmp_path / "jobs.xlsx",
            "result_book": tmp_path / "result.xlsx",
            "model": {
                "provider": "local-qwen",
                "base_url": "",
                "api_key": "",
                "model": "qwen3.5-local",
                "timeout_seconds": 120,
                "temperature": 0.1,
                "allow_without_model": False,
                "local": {
                    "runtime": "llama.cpp",
                    "model_family": "qwen3.5",
                    "model_display_name": "Qwen3.5 本地模型",
                    "model_path": str(tmp_path / "models" / "qwen.gguf"),
                    "manifest_path": str(tmp_path / "models" / "manifest.json"),
                    "host": "127.0.0.1",
                    "port": 18080,
                    "context_size": 8192,
                    "threads": 0,
                    "gpu_layers": "auto",
                    "auto_start": True,
                    "auto_download": False,
                },
            },
        }
    )

    assert config.model.provider == "local-qwen"
    assert config.model.is_complete() is True
    assert config.model.local.port == 18080
    assert config.model.local.model_path == tmp_path / "models" / "qwen.gguf"


def test_config_rejects_local_qwen_without_model_name(tmp_path: Path) -> None:
    with pytest.raises(ValidationError, match="model config missing required values: model"):
        AppConfig.model_validate(
            {
                "resume_dir": tmp_path / "resumes",
                "job_book": tmp_path / "jobs.xlsx",
                "result_book": tmp_path / "result.xlsx",
                "model": {
                    "provider": "local-qwen",
                    "base_url": "",
                    "api_key": "",
                    "model": "",
                    "allow_without_model": False,
                },
            }
        )


def test_cli_app_imports_cleanly() -> None:
    from resume_screening.cli import app

    assert app is not None


def test_example_config_loads() -> None:
    loaded = load_config(Path("config.example.yaml"))

    assert loaded.model.allow_without_model is True


def test_load_config_rejects_non_mapping_yaml(tmp_path: Path) -> None:
    config_path = tmp_path / "config.yaml"
    config_path.write_text("- not\n- a\n- mapping\n", encoding="utf-8")

    with pytest.raises(ValueError, match="config file must contain a YAML mapping"):
        load_config(config_path)
