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
        guessed_name = re.split(r"[-_\s]+", stem, maxsplit=1)[0].strip()
        return ParsedFilename(
            path=path,
            is_standard=False,
            candidate_name=guessed_name,
            missing_fields=["文件名不规范", "岗位名称", "期望工作地", "岗位标注薪资", "工龄"],
        )

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
