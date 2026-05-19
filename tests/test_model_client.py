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
