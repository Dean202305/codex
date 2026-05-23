from __future__ import annotations

from copy import deepcopy
from pathlib import Path
from typing import Any

import yaml

from resume_screening.config import AppConfig


DEFAULT_CONFIG: dict[str, Any] = {
    "resume_dir": "/Users/mac/Downloads",
    "job_book": "/Users/mac/Downloads/小A自动化岗位说明书.xlsx",
    "result_book": "/Users/mac/Downloads/小A科技（北京）组织招聘.xlsx",
    "job_aliases": {},
    "default_source_channel": "",
    "default_interviewer": "",
    "index_path": "data/processed_index.json",
    "ocr_command": "tesseract",
    "model": {
        "provider": "openai-compatible",
        "base_url": "",
        "api_key": "",
        "model": "",
        "timeout_seconds": 60,
        "temperature": 0.1,
        "allow_without_model": True,
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


def _deep_merge(base: dict[str, Any], overlay: dict[str, Any]) -> dict[str, Any]:
    merged = deepcopy(base)
    for key, value in overlay.items():
        if isinstance(value, dict) and isinstance(merged.get(key), dict):
            merged[key] = _deep_merge(merged[key], value)
        else:
            merged[key] = value
    return merged


def _read_yaml_mapping(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    if raw is None:
        return {}
    if not isinstance(raw, dict):
        raise ValueError("config file must contain a YAML mapping")
    return raw


def load_config_for_web(path: Path) -> dict[str, Any]:
    return _deep_merge(DEFAULT_CONFIG, _read_yaml_mapping(path))


def save_config_for_web(path: Path, data: dict[str, Any]) -> AppConfig:
    merged = _deep_merge(DEFAULT_CONFIG, data)
    validated = AppConfig.model_validate(merged)
    merged = _serialize_validated_paths(merged, validated)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(yaml.safe_dump(merged, allow_unicode=True, sort_keys=False), encoding="utf-8")
    return validated


def _serialize_validated_paths(data: dict[str, Any], validated: AppConfig) -> dict[str, Any]:
    serialized = deepcopy(data)
    for key in ("resume_dir", "job_book", "result_book", "index_path"):
        serialized[key] = str(getattr(validated, key))
    return serialized


def config_to_public_dict(data: dict[str, Any]) -> dict[str, Any]:
    public = deepcopy(data)
    for key in ("resume_dir", "job_book", "result_book", "index_path"):
        if key in public:
            public[key] = str(public[key])
    return public
