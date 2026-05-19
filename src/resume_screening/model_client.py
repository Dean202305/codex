from __future__ import annotations

import json

import httpx
from pydantic import BaseModel, Field, ValidationError, field_validator

from resume_screening.config import ModelConfig
from resume_screening.models import (
    CATEGORY_CONSIDER,
    CATEGORY_MANUAL,
    CATEGORY_RECOMMEND,
    CATEGORY_REJECT,
    JobRequirement,
    ScreeningResult,
    ScreeningScores,
)
from resume_screening.text_utils import sanitize_jsonable, sanitize_text


VALID_CATEGORIES = {CATEGORY_RECOMMEND, CATEGORY_CONSIDER, CATEGORY_MANUAL, CATEGORY_REJECT}


class ModelScoresPayload(BaseModel):
    ability: float = Field(ge=0, le=10)
    ego: float = Field(ge=0, le=10)
    desire: float = Field(ge=0, le=10)
    learning_ability: float = Field(ge=0, le=10)
    job_fit: float = Field(ge=0, le=10)
    experience_fit: float = Field(ge=0, le=10)
    skill_fit: float = Field(ge=0, le=10)
    stability_risk: float = Field(ge=0, le=10)


class ModelPayload(BaseModel):
    category: str
    overall_score: float = Field(ge=0, le=10)
    summary: str
    screening_reason: str
    missing_information: list[str]
    reject_reason: str = ""
    scores: ModelScoresPayload

    @field_validator("category")
    @classmethod
    def validate_category(cls, value: str) -> str:
        if value not in VALID_CATEGORIES:
            raise ValueError("category must be one of 推荐初试, 可考虑, 待人工二筛, 未通过")
        return value


def parse_model_response(payload: dict) -> ScreeningResult:
    try:
        parsed = ModelPayload.model_validate(sanitize_jsonable(payload))
    except ValidationError as exc:
        raise ValueError(f"模型返回格式不符合JSON结构：{exc}") from exc
    return ScreeningResult(
        category=parsed.category,
        overall_score=parsed.overall_score,
        summary=parsed.summary,
        screening_reason=parsed.screening_reason,
        missing_information=parsed.missing_information,
        reject_reason=parsed.reject_reason,
        scores=ScreeningScores(**parsed.scores.model_dump()),
    )


class ModelClient:
    def __init__(self, config: ModelConfig) -> None:
        self.config = config

    def evaluate(self, resume_text: str, job: JobRequirement, filename_metadata: dict[str, str]) -> ScreeningResult:
        prompt = self._build_prompt(resume_text, job, filename_metadata)
        response = httpx.post(
            f"{self.config.base_url.rstrip('/')}/chat/completions",
            headers={"Authorization": f"Bearer {self.config.api_key}", "Content-Type": "application/json"},
            json={
                "model": self.config.model,
                "temperature": self.config.temperature,
                "response_format": {"type": "json_object"},
                "messages": [
                    {"role": "system", "content": "你是招聘初筛助手，只返回严格JSON。"},
                    {"role": "user", "content": prompt},
                ],
            },
            timeout=self.config.timeout_seconds,
        )
        response.raise_for_status()
        content = response.json()["choices"][0]["message"]["content"]
        return parse_model_response(json.loads(content))

    def _build_prompt(self, resume_text: str, job: JobRequirement, filename_metadata: dict[str, str]) -> str:
        payload = {
            "instruction": "根据岗位要求和简历内容进行初筛。评分均为0到10分，8分通过，9分优秀。稳定性/风险高分表示低风险。只返回指定JSON字段。",
            "required_json_fields": [
                "category",
                "overall_score",
                "summary",
                "screening_reason",
                "missing_information",
                "reject_reason",
                "scores",
            ],
            "allowed_categories": sorted(VALID_CATEGORIES),
            "filename_metadata": filename_metadata,
            "job_requirement": {"sheet_name": job.sheet_name, "fields": job.fields, "raw_text": job.raw_text},
            "resume_text": sanitize_text(resume_text)[:12000],
        }
        return json.dumps(
            sanitize_jsonable(payload),
            ensure_ascii=False,
        )
