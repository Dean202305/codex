from __future__ import annotations

from dataclasses import replace
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


class ModelJobProfilePayload(BaseModel):
    education: str = ""
    age: str = ""
    gender: str = ""
    work_content: str = ""
    match_degree: str = ""
    keywords: list[str] = Field(default_factory=list)
    core_profile: str = ""
    must_have_keywords: list[str] = Field(default_factory=list)
    responsibility_keywords: list[str] = Field(default_factory=list)
    capability_keywords: list[str] = Field(default_factory=list)
    bonus_keywords: list[str] = Field(default_factory=list)
    matching_guidance: str = ""


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
    def __init__(self, config: ModelConfig, *, score_pass: float = 7, score_excellent: float = 9) -> None:
        self.config = config
        self.score_pass = score_pass
        self.score_excellent = score_excellent

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
        return self._calibrate_result(parse_model_response(json.loads(content)))

    def generate_job_profile(self, job: JobRequirement) -> str:
        prompt = self._build_job_profile_prompt(job)
        response = httpx.post(
            f"{self._base_url().rstrip('/')}/chat/completions",
            headers={"Authorization": f"Bearer {self._api_key()}", "Content-Type": "application/json"},
            json={
                "model": self.config.model,
                "temperature": min(self.config.temperature, 0.2),
                "response_format": {"type": "json_object"},
                "messages": [
                    {"role": "system", "content": "你是招聘岗位画像分析助手，只返回严格JSON。"},
                    {"role": "user", "content": prompt},
                ],
            },
            timeout=self.config.timeout_seconds,
        )
        response.raise_for_status()
        content = response.json()["choices"][0]["message"]["content"]
        return parse_job_profile_response(json.loads(content))

    def _base_url(self) -> str:
        if self.config.provider == "local-qwen":
            return LocalModelManager(self.config).service_base_url
        return self.config.base_url

    def _api_key(self) -> str:
        if self.config.provider == "local-qwen" and not self.config.api_key:
            return "local-qwen"
        return self.config.api_key

    def _build_prompt(self, resume_text: str, job: JobRequirement, filename_metadata: dict[str, str]) -> str:
        pass_score = _format_score(self.score_pass)
        excellent_score = _format_score(self.score_excellent)
        payload = {
            "instruction": (
                "根据岗位要求和简历内容进行初筛。先从岗位说明书中提炼岗位关键词画像，"
                "再根据画像综合匹配候选人，不要求逐条匹配岗位职责，也不要因为某一条职责未出现就直接人工二筛。"
                "优先给出推荐初试、可考虑或未通过；只有正文严重不足、候选人关键信息缺失到无法判断、"
                "或证据明显矛盾时才使用待人工二筛。岗位要求不完整时，基于现有岗位信息尽力评估，"
                "并把缺失项写入missing_information。评分均为0到10分，"
                f"{pass_score}分通过（约{int(round(self.score_pass * 10))}分），"
                f"{excellent_score}分优秀。稳定性/风险高分表示低风险。只返回指定JSON字段。"
            ),
            "evaluation_flow": [
                "优先读取 job_requirement.fields.岗位核心画像 或 raw_text 中的【岗位核心画像】；没有画像时，先自行从岗位职责、任职要求、硬性条件中提炼岗位关键词画像。",
                "将岗位职责理解为工作重心和能力信号，不作为逐条必须命中的清单。",
                "按核心经验、能力技能、项目/行业场景、学历年限、地点薪资和稳定性综合评分。",
                "只有无法提取正文、候选人关键身份/经历信息严重缺失、岗位完全无法匹配或证据冲突时，才分类为待人工二筛。",
            ],
            "classification_rules": {
                "推荐初试": f"overall_score >= {pass_score}，核心经验、能力或技能与岗位关键词画像明显匹配，可进入初试。",
                "可考虑": f"overall_score 在 6 到 {pass_score} 之间，存在匹配点但仍需面试确认。",
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
            "job_requirement": {
                "sheet_name": job.sheet_name,
                "core_profile": job.fields.get("岗位核心画像", ""),
                "fields": job.fields,
                "raw_text": job.raw_text,
            },
            "resume_text": sanitize_text(resume_text)[:12000],
        }
        return json.dumps(
            sanitize_jsonable(payload),
            ensure_ascii=False,
        )

    def _build_job_profile_prompt(self, job: JobRequirement) -> str:
        payload = {
            "instruction": (
                "请先分析岗位说明书中的岗位职责、任职要求、硬性条件和加分项，"
                "生成用于简历初筛的岗位关键词画像。画像必须精简为3到10条短标签，"
                "优先包含学历、年龄、性别、工作内容和匹配程度。不要把每条岗位职责都当作必须命中项，"
                "要提炼核心能力、关键经验、技术/业务关键词、行业场景和可迁移经验。"
                "只返回JSON，不要返回Markdown。"
            ),
            "output_schema": {
                "education": "学历要求，未写明则填未写明",
                "age": "年龄要求，未写明则填未写明",
                "gender": "性别要求，未写明则填未写明",
                "work_content": "工作内容关键词，最多3个，用顿号分隔",
                "match_degree": "匹配程度短标签，例如核心工作内容匹配优先",
                "keywords": ["其余关键短标签，总数与上面字段合计不超过10条"],
            },
            "job_requirement": {
                "sheet_name": job.sheet_name,
                "fields": job.fields,
                "raw_text": sanitize_text(job.raw_text)[:12000],
            },
        }
        return json.dumps(sanitize_jsonable(payload), ensure_ascii=False)

    def _calibrate_result(self, result: ScreeningResult) -> ScreeningResult:
        if result.category != CATEGORY_MANUAL or result.overall_score < self.score_pass:
            return result
        if _has_blocking_manual_signal(result):
            return result
        note = (
            f"模型原分类为待人工二筛，但综合评分 {result.overall_score:g}/10 达到通过线 "
            f"{self.score_pass:g}/10，且未发现严重阻断信息，已按评分规则校准为推荐初试。"
        )
        return replace(
            result,
            category=CATEGORY_RECOMMEND,
            screening_reason="；".join(item for item in (result.screening_reason, note) if item),
            missing_information=list(dict.fromkeys([*result.missing_information, "模型分类校准：原分类为待人工二筛，已按评分规则校准为推荐初试"])),
        )


def _has_blocking_manual_signal(result: ScreeningResult) -> bool:
    text = "；".join([result.summary, result.screening_reason, *result.missing_information])
    blocking_keywords = (
        "正文严重不足",
        "无法提取",
        "无法判断",
        "无法可靠判断",
        "证据明显矛盾",
        "证据冲突",
        "岗位无法匹配",
        "岗位名称未匹配",
        "文件名不规范",
        "候选人关键信息缺失",
        "模型评估失败",
    )
    return any(keyword in text for keyword in blocking_keywords)


def _format_score(value: float) -> str:
    return f"{value:g}"


def parse_job_profile_response(payload: dict) -> str:
    try:
        parsed = ModelJobProfilePayload.model_validate(_normalize_job_profile_payload(sanitize_jsonable(payload)))
    except ValidationError as exc:
        raise ValueError(f"模型岗位画像返回格式不符合JSON结构：{exc}") from exc

    sections = _compact_job_profile_lines(parsed)
    if not sections:
        raise ValueError("模型未返回可用的岗位画像")
    return "\n".join(sections[:10])


def _normalize_job_profile_payload(payload: object) -> object:
    if not isinstance(payload, dict):
        return payload
    normalized = dict(payload)
    for target, aliases in {
        "education": ("学历", "学历要求", "education_requirement"),
        "age": ("年龄", "年龄要求", "age_requirement"),
        "gender": ("性别", "性别要求", "gender_requirement"),
        "work_content": ("工作内容", "岗位职责摘要", "core_work", "work"),
        "match_degree": ("匹配程度", "工作内容匹配程度", "match", "match_rule"),
        "keywords": ("关键词", "短标签", "tags"),
        "core_profile": ("岗位核心画像", "岗位画像", "profile", "summary"),
        "must_have_keywords": ("硬性条件关键词", "must_have", "hard_requirements"),
        "responsibility_keywords": ("核心职责关键词", "responsibilities", "duty_keywords"),
        "capability_keywords": ("能力/技能关键词", "skills", "skill_keywords"),
        "bonus_keywords": ("加分项关键词", "bonus", "nice_to_have"),
        "matching_guidance": ("匹配规则", "筛选规则", "guidance"),
    }.items():
        if target in normalized:
            continue
        for alias in aliases:
            if alias in normalized:
                normalized[target] = normalized[alias]
                break
    for key in ("keywords", "must_have_keywords", "responsibility_keywords", "capability_keywords", "bonus_keywords"):
        normalized[key] = _listify_model_value(normalized.get(key))
    for key in ("education", "age", "gender", "work_content", "match_degree", "core_profile", "matching_guidance"):
        normalized[key] = _stringify_model_value(normalized.get(key))
    return normalized


def _compact_job_profile_lines(parsed: ModelJobProfilePayload) -> list[str]:
    keyword_pool = _dedupe_non_empty(
        _stringify_model_value(item)
        for item in (
            *parsed.keywords,
            *parsed.must_have_keywords,
            *parsed.responsibility_keywords,
            *parsed.capability_keywords,
            *parsed.bonus_keywords,
        )
    )
    education = parsed.education or _first_matching_keyword(keyword_pool, ("本科", "硕士", "博士", "大专", "专科", "学历"))
    age = parsed.age or _first_matching_keyword(keyword_pool, ("岁", "年龄", "届"))
    gender = parsed.gender or _first_matching_keyword(keyword_pool, ("男性", "女性", "男", "女", "不限"))
    work_content = parsed.work_content or parsed.core_profile
    if not work_content:
        work_content = "、".join(keyword_pool[:3])
    match_degree = parsed.match_degree or parsed.matching_guidance or "核心工作内容匹配优先"

    lines: list[str] = []
    _add_compact_line(lines, "学历", education or "未写明")
    _add_compact_line(lines, "年龄", age or "未写明")
    _add_compact_line(lines, "性别", gender or "未写明")
    _add_compact_line(lines, "工作内容", work_content, max_chars=64)
    _add_compact_line(lines, "匹配程度", match_degree, max_chars=40)

    used_values = {_line_value(line) for line in lines}
    for keyword in keyword_pool:
        cleaned = _short_profile_value(keyword, max_chars=32)
        if not cleaned or cleaned in used_values:
            continue
        _add_compact_line(lines, "关键词", cleaned, max_chars=32)
        used_values.add(cleaned)
        if len(lines) >= 10:
            break
    return list(dict.fromkeys(lines))


def _first_matching_keyword(values: list[str], needles: tuple[str, ...]) -> str:
    for value in values:
        if any(needle in value for needle in needles):
            return value
    return ""


def _add_compact_line(lines: list[str], label: str, value: str, *, max_chars: int = 40) -> None:
    cleaned = _short_profile_value(value, max_chars=max_chars)
    if cleaned:
        lines.append(f"{label}: {cleaned}")


def _line_value(line: str) -> str:
    return line.split(":", 1)[1].strip() if ":" in line else line.strip()


def _short_profile_value(value: str, *, max_chars: int) -> str:
    cleaned = _stringify_model_value(value).replace("\n", " ").strip(" ：:，,。；;、")
    if not cleaned:
        return ""
    if len(cleaned) <= max_chars:
        return cleaned
    return cleaned[:max_chars].rstrip(" ：:，,。；;、") + "..."


def _dedupe_non_empty(values) -> list[str]:
    deduped: list[str] = []
    for value in values:
        cleaned = value.strip()
        if cleaned and cleaned not in deduped:
            deduped.append(cleaned)
    return deduped
