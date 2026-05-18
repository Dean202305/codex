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
                "job_book": "/Users/mac/Downloads/小A自动化岗位说明书.xlsx",
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


def test_config_rejects_missing_model_when_manual_mode_disabled() -> None:
    with pytest.raises(ValidationError):
        AppConfig.model_validate(
            {
                "resume_dir": "/Users/mac/Downloads",
                "job_book": "/Users/mac/Downloads/小A自动化岗位说明书.xlsx",
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
