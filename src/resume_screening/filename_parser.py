from __future__ import annotations

import re
from pathlib import Path

from resume_screening.models import ParsedFilename


STANDARD_PATTERN = re.compile(
    r"^【(?P<job>[^_】]+)_(?P<location_salary>[^】]+)】(?P<name>\S+)\s+(?P<experience>.+?)$"
)


def parse_resume_filename(path: Path) -> ParsedFilename:
    stem = path.stem.strip()
    match = STANDARD_PATTERN.match(stem)
    if not match:
        underscore_parsed = _parse_underscore_filename(path, stem)
        if underscore_parsed is not None:
            return underscore_parsed
        return _non_standard_filename(path, stem)

    location_salary = match.group("location_salary").strip()
    parts = location_salary.split()
    expected_location = parts[0].strip() if parts else ""
    salary_range = " ".join(parts[1:]).strip() if len(parts) > 1 else ""
    missing_fields: list[str] = []
    if not salary_range:
        missing_fields.append("岗位标注薪资")

    return ParsedFilename(
        path=path,
        is_standard=True,
        job_name=match.group("job").strip(),
        expected_location=expected_location,
        salary_range=salary_range,
        candidate_name=match.group("name").strip(),
        work_experience=match.group("experience").strip(),
        missing_fields=missing_fields,
    )


def _parse_underscore_filename(path: Path, stem: str) -> ParsedFilename | None:
    parts = [part.strip() for part in stem.split("_") if part.strip()]
    if len(parts) < 5:
        return None

    job_name = parts[0]
    expected_location = parts[1]
    salary_parts = parts[2:-2]
    candidate_name = parts[-2]
    work_experience = parts[-1]
    salary_range = _join_salary_parts(salary_parts)

    missing_fields = []
    if not job_name:
        missing_fields.append("岗位名称")
    if not expected_location:
        missing_fields.append("期望工作地")
    if not salary_range:
        missing_fields.append("岗位标注薪资")
    if not candidate_name:
        missing_fields.append("候选人姓名")
    if not work_experience:
        missing_fields.append("工龄")

    return ParsedFilename(
        path=path,
        is_standard=True,
        job_name=job_name,
        expected_location=expected_location,
        salary_range=salary_range,
        candidate_name=candidate_name,
        work_experience=work_experience,
        missing_fields=missing_fields,
    )


def _join_salary_parts(parts: list[str]) -> str:
    if not parts:
        return ""
    if len(parts) == 2 and parts[1] in {"天", "日", "月", "年"}:
        return f"{parts[0]}/{parts[1]}"
    return "_".join(parts)


def _non_standard_filename(path: Path, stem: str) -> ParsedFilename:
    guessed_name = re.split(r"[-_\s]+", stem, maxsplit=1)[0].strip()
    return ParsedFilename(
        path=path,
        is_standard=False,
        candidate_name=guessed_name,
        missing_fields=["文件名不规范", "岗位名称", "期望工作地", "岗位标注薪资", "工龄"],
    )
