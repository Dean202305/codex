from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal

from openpyxl import load_workbook

from resume_screening.config import AppConfig
from resume_screening.file_scanner import iter_candidate_files
from resume_screening.filename_parser import parse_resume_filename
from resume_screening.job_matcher import resolve_job
from resume_screening.job_requirements import load_job_requirements
from resume_screening.models import JobRequirement

CheckStatus = Literal["pass", "warning", "fail"]


@dataclass(frozen=True)
class PrecheckItem:
    name: str
    status: CheckStatus
    message: str


@dataclass(frozen=True)
class PrecheckResult:
    status: CheckStatus
    resume_file_count: int
    usable_job_sheet_count: int
    items: list[PrecheckItem] = field(default_factory=list)


def _is_writable_file(path: Path) -> bool:
    if not path.exists() or not path.is_file():
        return False
    try:
        with path.open("ab"):
            return True
    except OSError:
        return False


def _overall_status(items: list[PrecheckItem]) -> CheckStatus:
    statuses = [item.status for item in items]
    if "fail" in statuses:
        return "fail"
    if "warning" in statuses:
        return "warning"
    return "pass"


def run_precheck(config: AppConfig) -> PrecheckResult:
    items: list[PrecheckItem] = []

    resume_files = iter_candidate_files(config.resume_dir, config.job_book, config.result_book)
    resume_count = len(resume_files)
    if not config.resume_dir.exists() or not config.resume_dir.is_dir():
        items.append(PrecheckItem("简历文件夹", "fail", f"文件夹不存在：{config.resume_dir}"))
    elif resume_count == 0:
        items.append(PrecheckItem("简历文件夹", "warning", "没有找到待处理文件"))
    else:
        items.append(PrecheckItem("简历文件夹", "pass", f"找到 {resume_count} 个待处理文件"))

    jobs = {}
    usable_jobs = 0
    if not config.job_book.exists():
        items.append(PrecheckItem("岗位说明书", "fail", f"文件不存在：{config.job_book}"))
    else:
        try:
            jobs = load_job_requirements(config.job_book)
            usable_jobs = sum(1 for job in jobs.values() if job.is_complete)
            if usable_jobs == 0:
                items.append(PrecheckItem("岗位说明书", "warning", "未找到完整岗位说明书 sheet"))
            else:
                items.append(PrecheckItem("岗位说明书", "pass", f"找到 {usable_jobs} 个完整岗位 sheet"))
        except Exception as exc:
            items.append(PrecheckItem("岗位说明书", "fail", f"读取失败：{exc}"))

    if jobs and resume_files:
        unmatched_jobs = _unmatched_resume_jobs(resume_files, jobs, config.job_aliases)
        if unmatched_jobs:
            preview = "、".join(f"{name}({count})" for name, count in unmatched_jobs[:6])
            items.append(
                PrecheckItem(
                    "岗位匹配",
                    "warning",
                    f"{sum(count for _, count in unmatched_jobs)} 个文件岗位未匹配岗位说明书：{preview}。可补充对应sheet，或在 config.yaml 的 job_aliases 中配置映射。",
                )
            )
        else:
            items.append(PrecheckItem("岗位匹配", "pass", "文件名岗位均已匹配到岗位说明书"))

    if not config.result_book.exists():
        items.append(PrecheckItem("招聘结果表", "fail", f"文件不存在：{config.result_book}"))
    else:
        try:
            workbook = load_workbook(config.result_book)
            workbook.close()
            if _is_writable_file(config.result_book):
                items.append(PrecheckItem("招聘结果表", "pass", "结果表存在且可写"))
            else:
                items.append(PrecheckItem("招聘结果表", "fail", "结果表不可写，可能已被 Excel 锁定"))
        except Exception as exc:
            items.append(PrecheckItem("招聘结果表", "fail", f"打开失败：{exc}"))

    model = config.model
    missing_model = [name for name in ("base_url", "api_key", "model") if not getattr(model, name)]
    if model.allow_without_model:
        if missing_model:
            items.append(PrecheckItem("模型配置", "pass", "当前允许无模型运行，简历会进入待人工二筛"))
        else:
            items.append(PrecheckItem("模型配置", "pass", f"模型已配置：{model.model}"))
    elif missing_model:
        items.append(PrecheckItem("模型配置", "fail", f"缺少模型配置：{', '.join(missing_model)}"))
    else:
        items.append(PrecheckItem("模型配置", "pass", f"模型已配置：{model.model}"))

    return PrecheckResult(
        status=_overall_status(items),
        resume_file_count=resume_count,
        usable_job_sheet_count=usable_jobs,
        items=items,
    )


def _unmatched_resume_jobs(
    resume_files: list[Path],
    jobs: dict[str, JobRequirement],
    aliases: dict[str, str],
) -> list[tuple[str, int]]:
    counts: dict[str, int] = {}
    for path in resume_files:
        parsed = parse_resume_filename(path)
        if not parsed.job_name:
            continue
        if resolve_job(parsed, jobs, aliases).job is None:
            counts[parsed.job_name] = counts.get(parsed.job_name, 0) + 1
    return sorted(counts.items(), key=lambda item: (-item[1], item[0]))
