import pytest

from resume_screening.config import ModelConfig
from resume_screening.model_client import ModelClient
from resume_screening.models import JobRequirement
from resume_screening.model_client import parse_model_response


def test_parse_model_response_accepts_valid_json() -> None:
    result = parse_model_response(
        {
            "category": "推荐初试",
            "overall_score": 8.5,
            "summary": "候选人具备财务管理经验。",
            "screening_reason": "经验和岗位要求匹配。",
            "missing_information": [],
            "reject_reason": "",
            "scores": {
                "ability": 8,
                "ego": 6,
                "desire": 8,
                "learning_ability": 8,
                "job_fit": 9,
                "experience_fit": 9,
                "skill_fit": 8,
                "stability_risk": 7,
            },
        }
    )

    assert result.category == "推荐初试"
    assert result.scores.job_fit == 9


def test_parse_model_response_rejects_unknown_category() -> None:
    with pytest.raises(ValueError, match="category"):
        parse_model_response(
            {
                "category": "强烈推荐",
                "overall_score": 8.5,
                "summary": "摘要",
                "screening_reason": "理由",
                "missing_information": [],
                "reject_reason": "",
                "scores": {
                    "ability": 8,
                    "ego": 6,
                    "desire": 8,
                    "learning_ability": 8,
                    "job_fit": 9,
                    "experience_fit": 9,
                    "skill_fit": 8,
                    "stability_risk": 7,
                },
            }
        )


def test_parse_model_response_accepts_common_chinese_score_keys_and_reason_list() -> None:
    result = parse_model_response(
        {
            "category": "推荐初试",
            "overall_score": 8.1,
            "summary": "候选人具备后端开发经验。",
            "screening_reason": ["硬性条件匹配", "项目经验相关"],
            "missing_information": "",
            "reject_reason": "",
            "scores": {
                "能力": 8,
                "自我认知": 6,
                "意愿": 7,
                "学习能力": 8,
                "岗位匹配度": 8.5,
                "经验匹配": 8.5,
                "技能匹配": 8,
                "稳定性/风险": 7.8,
            },
        }
    )

    assert result.screening_reason == "硬性条件匹配；项目经验相关"
    assert result.missing_information == []
    assert result.scores.job_fit == 8.5
    assert result.scores.stability_risk == 7.8


def test_parse_model_response_accepts_observed_alternate_score_keys() -> None:
    result = parse_model_response(
        {
            "category": "推荐初试",
            "overall_score": 8.5,
            "summary": "候选人3年Java后端经验。",
            "screening_reason": ["工作年限匹配", "后端核心技术匹配"],
            "missing_information": ["薪资期望需确认"],
            "reject_reason": "",
            "scores": {
                "experience_match": 8.5,
                "skill_match": 9.0,
                "project_depth": 8.8,
                "education_match": 8.0,
                "communication_language": 7.5,
                "stability_risk": 8.2,
                "location_match": 8.5,
                "job_info_completeness": 5.5,
            },
        }
    )

    assert result.category == "推荐初试"
    assert result.scores.ability == 8.8
    assert result.scores.learning_ability == 8.8
    assert result.scores.experience_fit == 8.5
    assert result.scores.skill_fit == 9.0
    assert result.scores.stability_risk == 8.2
    assert result.scores.ego == 8.5
    assert result.scores.desire == 8.5
    assert result.scores.job_fit == 8.67
    assert any("自我认知" in item for item in result.missing_information)


def test_build_prompt_replaces_invalid_unicode_surrogates() -> None:
    client = ModelClient(
        ModelConfig(
            provider="openai-compatible",
            base_url="https://api.example.com/v1",
            api_key="test",
            model="screening-model",
            allow_without_model=False,
        )
    )
    job = JobRequirement("财务总监", {}, "岗位要求", True, [])

    prompt = client._build_prompt("候选人\ud835简历", job, {"candidate_name": "郭燕婷"})

    prompt.encode("utf-8")
    assert "\ud835" not in prompt


def test_local_qwen_client_uses_local_openai_compatible_base_url(monkeypatch, tmp_path) -> None:
    captured = {}

    class FakeResponse:
        def raise_for_status(self) -> None:
            return None

        def json(self) -> dict:
            return {
                "choices": [
                    {
                        "message": {
                            "content": """
                            {
                              "category": "可考虑",
                              "overall_score": 7.5,
                              "summary": "候选人经验可考虑。",
                              "screening_reason": "岗位匹配度中等。",
                              "missing_information": [],
                              "reject_reason": "",
                              "scores": {
                                "ability": 7,
                                "ego": 7,
                                "desire": 7,
                                "learning_ability": 7,
                                "job_fit": 7.5,
                                "experience_fit": 7.5,
                                "skill_fit": 7,
                                "stability_risk": 7
                              }
                            }
                            """
                        }
                    }
                ]
            }

    def fake_post(url, headers, json, timeout):
        captured["url"] = url
        captured["headers"] = headers
        captured["payload"] = json
        captured["timeout"] = timeout
        return FakeResponse()

    monkeypatch.setattr("resume_screening.model_client.httpx.post", fake_post)
    client = ModelClient(
        ModelConfig(
            provider="local-qwen",
            base_url="",
            api_key="",
            model="qwen3.5-local",
            timeout_seconds=120,
            allow_without_model=False,
            local={"model_path": str(tmp_path / "qwen.gguf"), "port": 19090},
        )
    )

    result = client.evaluate("候选人简历", JobRequirement("财务总监", {}, "岗位要求", True, []), {})

    assert result.category == "可考虑"
    assert captured["url"] == "http://127.0.0.1:19090/v1/chat/completions"
    assert captured["headers"]["Authorization"] == "Bearer local-qwen"
    assert captured["payload"]["model"] == "qwen3.5-local"
