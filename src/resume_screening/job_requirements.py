from __future__ import annotations

from pathlib import Path

from openpyxl import load_workbook

from resume_screening.models import JobRequirement


PLACEHOLDER_MARKERS = ("XXXX", "具体描述", "无则填", "年       月")
REQUIRED_FIELDS = ("岗位名称", "学历", "工作经验", "具体描述", "1. 核心职责")
TABULAR_REQUIRED_FIELDS = ("岗位名称",)
TABULAR_DETAIL_FIELDS = ("岗位jd", "核心职责1", "核心职责2", "核心职责3", "工作经验要求", "学历要求")


def _clean(value: object) -> str:
    return str(value).strip() if value is not None else ""


def _is_placeholder(value: str) -> bool:
    return not value or any(marker in value for marker in PLACEHOLDER_MARKERS)


def _extract_sheet_fields(rows: list[list[str]]) -> dict[str, str]:
    fields: dict[str, str] = {}
    for row in rows:
        for index in range(0, len(row), 2):
            key = row[index].strip() if index < len(row) else ""
            value = row[index + 1].strip() if index + 1 < len(row) else ""
            if key and value:
                fields[key] = value
    return fields


def _raw_text(rows: list[list[str]]) -> str:
    lines = []
    for row in rows:
        text = " ".join(cell for cell in row if cell)
        if text:
            lines.append(text)
    return "\n".join(lines)


def _missing_required(fields: dict[str, str]) -> list[str]:
    missing = []
    for field_name in REQUIRED_FIELDS:
        value = fields.get(field_name, "")
        if _is_placeholder(value):
            missing.append(field_name)
    return missing


def _is_tabular_sheet(rows: list[list[str]]) -> bool:
    if not rows:
        return False
    header = rows[0]
    return "岗位名称" in header and any(name in header for name in ("岗位别名", "岗位jd", "核心职责1", "学历要求"))


def _tabular_missing_required(fields: dict[str, str]) -> list[str]:
    missing = [field_name for field_name in TABULAR_REQUIRED_FIELDS if _is_placeholder(fields.get(field_name, ""))]
    if not any(not _is_placeholder(fields.get(field_name, "")) for field_name in TABULAR_DETAIL_FIELDS):
        missing.append("岗位要求")
    return missing


def _row_raw_text(fields: dict[str, str]) -> str:
    return "\n".join(f"{key}: {value}" for key, value in fields.items() if value)


def _load_tabular_jobs(sheet_name: str, rows: list[list[str]]) -> dict[str, JobRequirement]:
    header = rows[0]
    jobs: dict[str, JobRequirement] = {}
    for row in rows[1:]:
        fields = {
            header[index]: row[index]
            for index in range(min(len(header), len(row)))
            if header[index] and row[index]
        }
        job_name = fields.get("岗位名称", "").strip()
        if not job_name:
            continue
        missing = _tabular_missing_required(fields)
        jobs[job_name] = JobRequirement(
            sheet_name=sheet_name,
            fields=fields,
            raw_text=_row_raw_text(fields),
            is_complete=len(missing) == 0,
            missing_fields=missing,
        )
    return jobs


def load_job_requirements(path: Path) -> dict[str, JobRequirement]:
    workbook = load_workbook(path, data_only=True)
    jobs: dict[str, JobRequirement] = {}
    for sheet_name in workbook.sheetnames:
        if sheet_name == "模板":
            continue
        sheet = workbook[sheet_name]
        rows = [[_clean(cell) for cell in row] for row in sheet.iter_rows(values_only=True)]
        if _is_tabular_sheet(rows):
            jobs.update(_load_tabular_jobs(sheet_name, rows))
            continue
        fields = _extract_sheet_fields(rows)
        missing = _missing_required(fields)
        raw_text = _raw_text(rows)
        jobs[sheet_name] = JobRequirement(
            sheet_name=sheet_name,
            fields=fields,
            raw_text=raw_text,
            is_complete=len(missing) == 0,
            missing_fields=missing,
        )
    return jobs
