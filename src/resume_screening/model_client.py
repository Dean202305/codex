from __future__ import annotations

import json

import httpx
from pydantic import BaseModel, Field, ValidationError, field_validator

from resume_screening.config import ModelConfig
from resume_screening.local_model import LocalModelManager
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
SCORE_ALIASES = {
    "ability": ("能力", "能力评分", "综合能力", "四项人格/潜力-能力", "project_depth"),
    "ego": ("自我认知", "自驱/自我认知", "自我", "ego"),
    "desire": ("意愿", "欲望", "求职意愿", "动机", "desire"),
    "learning_ability": ("学习能力", "学习潜力", "学习力", "project_depth"),
    "job_fit": ("岗位匹配", "岗位匹配度", "岗位匹配评分", "匹配度"),
    "experience_fit": ("经验匹配", "经验匹配度", "经历匹配", "工作经验匹配", "experience_match"),
    "skill_fit": ("技能匹配", "技能匹配度", "技术匹配", "能力技能匹配", "skill_match"),
    "stability_risk": ("稳定性/风险", "稳定性风险", "稳定性", "风险稳定性", "稳定风险"),
}
SCORE_LABELS = {
    "ability": "能力",
    "ego": "自我认知",
    "desire": "意愿",
    "learning_ability": "学习能力",
    "job_fit": "岗位匹配度",
    "experience_fit": "经验匹配度",
    "skill_fit": "技能匹配度",
    "stability_risk": "稳定性/风险",
}


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
        parsed = ModelPayload.model_validate(_normalize_model_payload(sanitize_jsonable(payload)))
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


def _normalize_model_payload(payload: object) -> object:
    if not isinstance(payload, dict):
        return payload
    normalized = dict(payload)
    for key in ("summary", "screening_reason", "reject_reason"):
        if key in normalized:
            normalized[key] = _stringify_model_value(normalized[key])
    if "missing_information" in normalized:
        normalized["missing_information"] = _listify_model_value(normalized["missing_information"])
    else:
        normalized["missing_information"] = []
    if isinstance(normalized.get("scores"), dict):
        scores, notes = _normalize_scores(normalized["scores"], normalized.get("overall_score", 0))
        normalized["scores"] = scores
        normalized["missing_information"].extend(notes)
    return normalized


def _stringify_model_value(value: object) -> str:
    if value is None:
        return ""
    if isinstance(value, list):
        return "；".join(_stringify_model_value(item) for item in value if _stringify_model_value(item))
    if isinstance(value, dict):
        return json.dumps(value, ensure_ascii=False)
    return str(value)


def _listify_model_value(value: object) -> list[str]:
    if value is None or value == "":
        return []
    if isinstance(value, list):
        return [_stringify_model_value(item) for item in value if _stringify_model_value(item)]
    return [_stringify_model_value(value)]


def _normalize_scores(scores: dict, overall_score: object) -> tuple[dict, list[str]]:
    normalized = dict(scores)
    for target, aliases in SCORE_ALIASES.items():
        if target in normalized:
            continue
        for alias in aliases:
            if alias in scores:
                normalized[target] = scores[alias]
                break
    notes: list[str] = []
    for target in SCORE_LABELS:
        if target in normalized:
            continue
        normalized[target] = _fallback_score(target, normalized, overall_score)
        notes.append(f"模型未返回{SCORE_LABELS[target]}评分，已用综合/相关评分暂填")
    if "job_fit" not in scores and "岗位匹配" not in scores and "岗位匹配度" not in scores:
        job_fit = _average_scores(normalized, ("experience_fit", "skill_fit", "location_match"))
        if job_fit is not None:
            normalized["job_fit"] = job_fit
    return normalized, notes


def _fallback_score(target: str, scores: dict, overall_score: object) -> float:
    if target in {"ego", "desire"}:
        return _coerce_score(overall_score) or 0.0
    if target == "job_fit":
        averaged = _average_scores(scores, ("experience_fit", "skill_fit", "location_match"))
        if averaged is not None:
            return averaged
    for key in ("ability", "learning_ability", "experience_fit", "skill_fit", "job_fit"):
        value = _coerce_score(scores.get(key))
        if value is not None:
            return value
    return _coerce_score(overall_score) or 0.0


def _average_scores(scores: dict, keys: tuple[str, ...]) -> float | None:
    values = [_coerce_score(scores.get(key)) for key in keys]
    present = [value for value in values if value is not None]
    if not present:
        return None
    return round(sum(present) / len(present), 2)


def _coerce_score(value: object) -> float | None:
    if value is None or value == "":
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


class ModelClient:
    def __init__(self, config: ModelConfig) -> None:
        self.config = config

    def evaluate(self, resume_text: str, job: JobRequirement, filename_metadata: dict[str, str]) -> ScreeningResult:
        prompt = self._build_prompt(resume_text, job, filename_metadata)
        response = httpx.post(
            f"{self._base_url().rstrip('/')}/chat/completions",
            headers={"Authorization": f"Bearer {self._api_key()}", "Content-Type": "application/json"},
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

    def _base_url(self) -> str:
        if self.config.provider == "local-qwen":
            return LocalModelManager(self.config).service_base_url
        return self.config.base_url

    def _api_key(self) -> str:
        if self.config.provider == "local-qwen" and not self.config.api_key:
            return "local-qwen"
        return self.config.api_key

    def _build_prompt(self, resume_text: str, job: JobRequirement, filename_metadata: dict[str, str]) -> str:
        payload = {
            "instruction": "根据岗位要求和简历内容进行初筛。优先给出推荐初试、可考虑或未通过；只有正文严重不足、候选人关键信息缺失到无法判断、或证据明显矛盾时才使用待人工二筛。岗位要求不完整时，基于现有岗位信息尽力评估，并把缺失项写入missing_information。评分均为0到10分，8分通过，9分优秀。稳定性/风险高分表示低风险。只返回指定JSON字段。",
            "classification_rules": {
                "推荐初试": "overall_score >= 8，核心经验、能力或技能与岗位要求明显匹配。",
                "可考虑": "overall_score 在 6 到 8 之间，存在匹配点但仍需面试确认。",
                "未通过": "overall_score < 6，核心经验、技能或条件明显不匹配。",
                "待人工二筛": "仅用于信息不足或模型无法可靠判断，不作为默认分类。",
            },
            "scores_schema": {
                "ability": "能力评分，0到10",
                "ego": "自我认知/ego评分，0到10",
                "desire": "意愿/desire评分，0到10",
                "learning_ability": "学习能力与聪明程度评分，0到10",
                "job_fit": "岗位匹配度评分，0到10",
                "experience_fit": "经验匹配评分，0到10",
                "skill_fit": "技能匹配评分，0到10",
                "stability_risk": "稳定性/风险评分，0到10，高分表示低风险",
            },
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
