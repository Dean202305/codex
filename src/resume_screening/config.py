from pathlib import Path
from typing import Literal

import yaml
from pydantic import BaseModel, Field, model_validator


class CategoryConfig(BaseModel):
    recommend: str = "推荐初试"
    consider: str = "可考虑"
    manual: str = "待人工二筛"
    reject: str = "未通过"


class ScreeningConfig(BaseModel):
    score_pass: float = 8
    score_excellent: float = 9
    categories: CategoryConfig = Field(default_factory=CategoryConfig)


class ModelConfig(BaseModel):
    provider: Literal["openai-compatible"] = "openai-compatible"
    base_url: str = ""
    api_key: str = ""
    model: str = ""
    timeout_seconds: int = 60
    temperature: float = 0.1
    allow_without_model: bool = False

    @model_validator(mode="after")
    def require_model_config_unless_manual_mode(self) -> "ModelConfig":
        if self.allow_without_model:
            return self
        missing = [name for name in ("base_url", "api_key", "model") if not getattr(self, name)]
        if missing:
            joined = ", ".join(missing)
            raise ValueError(f"model config missing required values: {joined}")
        return self


class AppConfig(BaseModel):
    resume_dir: Path
    job_book: Path
    result_book: Path
    default_source_channel: str = ""
    default_interviewer: str = ""
    index_path: Path = Path("data/processed_index.json")
    ocr_command: str = "tesseract"
    model: ModelConfig
    screening: ScreeningConfig = Field(default_factory=ScreeningConfig)


def load_config(path: Path) -> AppConfig:
    raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        raise ValueError("config file must contain a YAML mapping")
    return AppConfig.model_validate(raw)
