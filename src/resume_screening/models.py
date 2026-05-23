from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Literal


CATEGORY_RECOMMEND = "推荐初试"
CATEGORY_CONSIDER = "可考虑"
CATEGORY_MANUAL = "待人工二筛"
CATEGORY_REJECT = "未通过"


@dataclass(frozen=True)
class ParsedFilename:
    path: Path
    is_standard: bool
    job_name: str = ""
    expected_location: str = ""
    salary_range: str = ""
    candidate_name: str = ""
    work_experience: str = ""
    missing_fields: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class JobRequirement:
    sheet_name: str
    fields: dict[str, str]
    raw_text: str
    is_complete: bool
    missing_fields: list[str]


@dataclass(frozen=True)
class ExtractionResult:
    text: str
    method: str
    errors: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class DuplicateMatch:
    is_duplicate: bool
    matched_filename: str = ""
    matched_row_id: int | None = None
    similarity: float = 0.0


@dataclass(frozen=True)
class ScreeningScores:
    ability: float
    ego: float
    desire: float
    learning_ability: float
    job_fit: float
    experience_fit: float
    skill_fit: float
    stability_risk: float


@dataclass(frozen=True)
class ScreeningResult:
    category: str
    overall_score: float
    summary: str
    screening_reason: str
    missing_information: list[str]
    reject_reason: str
    scores: ScreeningScores


@dataclass
class PipelineStats:
    processed: int = 0
    recommend: int = 0
    consider: int = 0
    manual: int = 0
    reject: int = 0
    duplicate: int = 0
    model_failures: int = 0
    extraction_failures: int = 0
    non_standard_names: int = 0

    def count_category(self, category: str) -> None:
        if category == CATEGORY_RECOMMEND:
            self.recommend += 1
        elif category == CATEGORY_CONSIDER:
            self.consider += 1
        elif category == CATEGORY_MANUAL:
            self.manual += 1
        elif category == CATEGORY_REJECT:
            self.reject += 1


@dataclass(frozen=True)
class PipelineEvent:
    type: Literal["run_started", "file_started", "file_completed", "run_completed", "run_cancelled", "warning"]
    message: str
    current: int = 0
    total: int = 0
    filename: str = ""
    category: str = ""
    stats: PipelineStats | None = None


JsonDict = dict[str, Any]
