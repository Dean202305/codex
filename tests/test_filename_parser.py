from pathlib import Path

from resume_screening.filename_parser import parse_resume_filename


def test_parse_standard_resume_filename() -> None:
    parsed = parse_resume_filename(Path("【财务总监_北京 18-28K】郭燕婷 10年以上.pdf"))

    assert parsed.is_standard is True
    assert parsed.job_name == "财务总监"
    assert parsed.expected_location == "北京"
    assert parsed.salary_range == "18-28K"
    assert parsed.candidate_name == "郭燕婷"
    assert parsed.work_experience == "10年以上"
    assert parsed.missing_fields == []


def test_parse_non_standard_filename_marks_missing_fields() -> None:
    parsed = parse_resume_filename(Path("郭燕婷-简历.pdf"))

    assert parsed.is_standard is False
    assert parsed.candidate_name == "郭燕婷"
    assert "文件名不规范" in parsed.missing_fields
    assert "岗位名称" in parsed.missing_fields


def test_parse_standard_filename_without_salary_marks_salary_missing() -> None:
    parsed = parse_resume_filename(Path("【算法工程师_北京】张三 3年.pdf"))

    assert parsed.is_standard is True
    assert parsed.job_name == "算法工程师"
    assert parsed.expected_location == "北京"
    assert parsed.salary_range == ""
    assert "岗位标注薪资" in parsed.missing_fields


def test_parse_underscore_filename_with_monthly_salary() -> None:
    parsed = parse_resume_filename(Path("后端开发工程师_北京_12-18K_张松_3年.pdf"))

    assert parsed.is_standard is True
    assert parsed.job_name == "后端开发工程师"
    assert parsed.expected_location == "北京"
    assert parsed.salary_range == "12-18K"
    assert parsed.candidate_name == "张松"
    assert parsed.work_experience == "3年"
    assert parsed.missing_fields == []


def test_parse_underscore_filename_with_daily_salary() -> None:
    parsed = parse_resume_filename(Path("后端开发实习岗_北京_500-1000元_天_kanosa_一年以内.pdf"))

    assert parsed.is_standard is True
    assert parsed.job_name == "后端开发实习岗"
    assert parsed.expected_location == "北京"
    assert parsed.salary_range == "500-1000元/天"
    assert parsed.candidate_name == "kanosa"
    assert parsed.work_experience == "一年以内"
    assert parsed.missing_fields == []
