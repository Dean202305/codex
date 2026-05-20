from __future__ import annotations

from dataclasses import dataclass

from resume_screening.models import JobRequirement, ParsedFilename


@dataclass(frozen=True)
class JobMatch:
    job: JobRequirement | None
    note: str = ""


def resolve_job(
    parsed: ParsedFilename,
    jobs: dict[str, JobRequirement],
    aliases: dict[str, str] | None = None,
) -> JobMatch:
    if not parsed.job_name:
        return JobMatch(None)

    if parsed.job_name in jobs:
        return JobMatch(jobs[parsed.job_name])

    alias_target = (aliases or {}).get(parsed.job_name, "")
    if alias_target:
        job = jobs.get(alias_target)
        if job is not None:
            return JobMatch(job, f"岗位别名映射：{parsed.job_name} -> {alias_target}")
        return JobMatch(None, f"岗位别名无效：{parsed.job_name} -> {alias_target}")

    normalized_name = _normalize_job_name(parsed.job_name)
    for job in jobs.values():
        field_name = job.fields.get("岗位名称", "")
        if field_name and _normalize_job_name(field_name) == normalized_name:
            note = ""
            if job.sheet_name != parsed.job_name:
                note = f"岗位名称匹配：{parsed.job_name} -> {job.sheet_name}"
            return JobMatch(job, note)

    return JobMatch(None)


def _normalize_job_name(value: str) -> str:
    return "".join(value.split())
