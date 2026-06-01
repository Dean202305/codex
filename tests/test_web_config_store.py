from pathlib import Path

import yaml

from resume_screening.web.config_store import config_to_public_dict, load_config_for_web, save_config_for_web


def test_load_config_for_web_uses_example_defaults_when_missing(tmp_path: Path) -> None:
    config_path = tmp_path / "config.yaml"

    data = load_config_for_web(config_path)

    assert data["resume_dir"] == "/Users/mac/Downloads"
    assert data["job_book"].endswith("小A自动化岗位说明书_副本.xlsx")
    assert data["result_book"].endswith("小A科技（北京）组织招聘.xlsx")
    assert data["model"]["allow_without_model"] is True


def test_save_config_for_web_round_trips_paths_and_model(tmp_path: Path) -> None:
    config_path = tmp_path / "config.yaml"
    saved = save_config_for_web(
        config_path,
        {
            "resume_dir": str(tmp_path / "resumes"),
            "job_book": str(tmp_path / "jobs.xlsx"),
            "result_book": str(tmp_path / "result.xlsx"),
            "default_source_channel": "Boss直聘",
            "default_interviewer": "小A",
            "index_path": str(tmp_path / "processed_index.json"),
            "ocr_command": "tesseract",
            "model": {
                "provider": "openai-compatible",
                "base_url": "https://api.example.com/v1",
                "api_key": "sk-test",
                "model": "gpt-test",
                "timeout_seconds": 30,
                "temperature": 0.1,
                "allow_without_model": False,
            },
            "screening": {
                "score_pass": 8,
                "score_excellent": 9,
                "categories": {
                    "recommend": "推荐初试",
                    "consider": "可考虑",
                    "manual": "待人工二筛",
                    "reject": "未通过",
                },
            },
        },
    )

    raw = yaml.safe_load(config_path.read_text(encoding="utf-8"))

    assert saved.resume_dir == tmp_path / "resumes"
    assert raw["model"]["api_key"] == "sk-test"
    assert raw["default_source_channel"] == "Boss直聘"


def test_save_config_for_web_persists_normalized_paths(tmp_path: Path) -> None:
    config_path = tmp_path / "config.yaml"
    resume_dir = tmp_path / "Resume Folder"
    resume_dir.mkdir()
    job_book = tmp_path / "jobs.xlsx"
    result_book = tmp_path / "result.xlsx"
    job_book.write_text("fake", encoding="utf-8")
    result_book.write_text("fake", encoding="utf-8")

    save_config_for_web(
        config_path,
        {
            "resume_dir": f" {resume_dir}",
            "job_book": f"'{job_book}'",
            "result_book": f'"{result_book}"',
            "model": {"provider": "openai-compatible", "base_url": "", "api_key": "", "model": "", "allow_without_model": True},
        },
    )

    raw = yaml.safe_load(config_path.read_text(encoding="utf-8"))
    assert raw["resume_dir"] == str(resume_dir)
    assert raw["job_book"] == str(job_book)
    assert raw["result_book"] == str(result_book)


def test_config_to_public_dict_serializes_paths() -> None:
    data = {
        "resume_dir": Path("/tmp/resumes"),
        "job_book": Path("/tmp/jobs.xlsx"),
        "result_book": Path("/tmp/result.xlsx"),
        "index_path": Path("data/processed_index.json"),
        "model": {"timeout_seconds": 60},
    }

    public = config_to_public_dict(data)

    assert isinstance(public["resume_dir"], str)
    assert isinstance(public["job_book"], str)
    assert isinstance(public["result_book"], str)
    assert isinstance(public["index_path"], str)
    assert isinstance(public["model"]["timeout_seconds"], int)
