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
