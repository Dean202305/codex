from pathlib import Path

from fastapi.testclient import TestClient
from openpyxl import Workbook

from resume_screening.web.app import create_app


def create_result_book(path: Path) -> None:
    workbook = Workbook()
    sheet = workbook.active
    sheet.title = "多维表格"
    sheet.append(["ID", "当前阶段", "候选人", "附件", "岗位方向", "来源渠道", "候选人摘要（妙记）", "量化打分", "可投入周期", "面试负责人", "下次动作日", "不推进原因", "推荐/触达人"])
    workbook.save(path)


def create_job_book(path: Path) -> None:
    workbook = Workbook()
    workbook.active.title = "模板"
    job = workbook.create_sheet("财务总监")
    job.append(["岗位名称", "财务总监", "学历", "本科"])
    job.append(["工作经验", "8年以上", "具体描述", "负责公司财务管理"])
    job.append(["1. 核心职责", "预算、核算、风控"])
    workbook.save(path)


def valid_payload(tmp_path: Path) -> dict:
    resume_dir = tmp_path / "resumes"
    resume_dir.mkdir()
    (resume_dir / "【财务总监_北京 18-28K】郭燕婷 10年以上.pdf").write_text("fake", encoding="utf-8")
    job_book = tmp_path / "jobs.xlsx"
    result_book = tmp_path / "result.xlsx"
    create_job_book(job_book)
    create_result_book(result_book)
    return {
        "resume_dir": str(resume_dir),
        "job_book": str(job_book),
        "result_book": str(result_book),
        "index_path": str(tmp_path / "processed_index.json"),
        "ocr_command": "tesseract",
        "model": {"provider": "openai-compatible", "base_url": "", "api_key": "", "model": "", "timeout_seconds": 60, "temperature": 0.1, "allow_without_model": True},
    }


def test_config_endpoints_round_trip(tmp_path: Path) -> None:
    config_path = tmp_path / "config.yaml"
    client = TestClient(create_app(config_path=config_path))

    response = client.post("/api/config", json=valid_payload(tmp_path))
    assert response.status_code == 200
    assert response.json()["config"]["resume_dir"].endswith("resumes")

    response = client.get("/api/config")
    assert response.status_code == 200
    assert response.json()["config"]["result_book"].endswith("result.xlsx")


def test_precheck_endpoint_returns_items(tmp_path: Path) -> None:
    config_path = tmp_path / "config.yaml"
    client = TestClient(create_app(config_path=config_path))
    client.post("/api/config", json=valid_payload(tmp_path))

    response = client.get("/api/precheck")

    assert response.status_code == 200
    body = response.json()
    assert body["status"] in {"pass", "warning"}
    assert body["resume_file_count"] == 1
    assert body["items"]
