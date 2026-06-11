from pathlib import Path

from resume_screening.filename_parser import parse_resume_filename
from resume_screening.job_matcher import resolve_job
from resume_screening.models import JobRequirement


def test_resolve_job_matches_filename_job_by_contained_job_name() -> None:
    parsed = parse_resume_filename(Path("后端开发工程师_北京_12-18K_张松_3年.pdf"))
    jobs = {
        "后端开发": JobRequirement(
            sheet_name="后端开发",
            fields={"岗位名称": "后端开发", "岗位别名": "Java开发"},
            raw_text="后端开发 Java开发",
            is_complete=True,
            missing_fields=[],
        )
    }

    match = resolve_job(parsed, jobs)

    assert match.job is jobs["后端开发"]
    assert match.note == "岗位名称匹配：后端开发工程师 -> 后端开发"
