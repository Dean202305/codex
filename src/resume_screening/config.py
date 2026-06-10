from pathlib import Path
import shlex
import os
from typing import Literal

import yaml
from pydantic import BaseModel, Field, field_validator, model_validator


class CategoryConfig(BaseModel):
    recommend: str = "推荐初试"
    consider: str = "可考虑"
    manual: str = "待人工二筛"
    reject: str = "未通过"


class ScreeningConfig(BaseModel):
    score_pass: float = 7
    score_excellent: float = 9
    categories: CategoryConfig = Field(default_factory=CategoryConfig)


class LocalModelConfig(BaseModel):
    runtime: str = "llama.cpp"
    model_family: str = "qwen3.5"
    model_display_name: str = "Qwen3.5 本地模型"
    model_path: Path | None = None
    manifest_path: Path = Path("models/qwen/manifest.json")
    host: str = "127.0.0.1"
    port: int = 18080
    context_size: int = 8192
    threads: int = 0
    gpu_layers: str = "auto"
    auto_start: bool = True
    auto_download: bool = False

    @field_validator("model_path", "manifest_path", mode="before")
    @classmethod
    def normalize_optional_path_fields(cls, value: object) -> object:
        if value == "":
            return None
        return normalize_path_value(value)


class ModelConfig(BaseModel):
    provider: Literal["openai-compatible", "local-qwen"] = "openai-compatible"
    base_url: str = ""
    api_key: str = ""
    model: str = ""
    timeout_seconds: int = 60
    temperature: float = 0.1
    allow_without_model: bool = False
    fallback_to_local_when_unavailable: bool = True
    local: LocalModelConfig = Field(default_factory=LocalModelConfig)

    @model_validator(mode="after")
    def require_model_config_unless_manual_mode(self) -> "ModelConfig":
        if self.allow_without_model:
            return self
        if self.provider == "openai-compatible" and self.fallback_to_local_when_unavailable:
            return self
        required = ("model",) if self.provider == "local-qwen" else ("base_url", "api_key", "model")
        missing = [name for name in required if not getattr(self, name)]
        if missing:
            joined = ", ".join(missing)
            raise ValueError(f"model config missing required values: {joined}")
        return self

    def is_complete(self) -> bool:
        if self.provider == "local-qwen":
            return bool(self.model)
        return all(getattr(self, name) for name in ("base_url", "api_key", "model"))


class AppConfig(BaseModel):
    resume_dir: Path
    job_book: Path
    result_book: Path
    job_aliases: dict[str, str] = Field(default_factory=dict)
    job_profile_overrides: dict[str, str] = Field(default_factory=dict)
    default_source_channel: str = ""
    default_interviewer: str = ""
    index_path: Path = Path("data/processed_index.json")
    ocr_command: str = "tesseract"
    model: ModelConfig
    screening: ScreeningConfig = Field(default_factory=ScreeningConfig)

    @field_validator("resume_dir", "job_book", "result_book", "index_path", mode="before")
    @classmethod
    def normalize_path_fields(cls, value: object) -> object:
        return normalize_path_value(value)


def normalize_path_value(value: object) -> object:
    if isinstance(value, Path) or not isinstance(value, str):
        return value
    cleaned = value.strip()
    if len(cleaned) >= 2 and cleaned[0] == cleaned[-1] and cleaned[0] in {"'", '"'}:
        cleaned = cleaned[1:-1].strip()
    try:
        parts = shlex.split(cleaned, posix=os.name != "nt")
    except ValueError:
        parts = []
    if len(parts) == 1:
        cleaned = parts[0]
    else:
        cleaned = cleaned.replace("\\ ", " ")
    return Path(cleaned).expanduser()


def load_config(path: Path) -> AppConfig:
    raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        raise ValueError("config file must contain a YAML mapping")
    return AppConfig.model_validate(raw)
