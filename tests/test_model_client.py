import json

import pytest

from resume_screening.config import ModelConfig
from resume_screening.model_client import ModelClient
from resume_screening.models import JobRequirement
from resume_screening.model_client import parse_job_profile_response, parse_model_response


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


def test_parse_job_profile_response_normalizes_alias_fields() -> None:
    profile = parse_job_profile_response(
        {
            "岗位核心画像": "负责AI产品从0到1落地，关注海外ToC用户体验和商业闭环。",
            "硬性条件关键词": ["本科", "AI产品经验"],
            "核心职责关键词": ["产品规划", "交互设计"],
            "能力/技能关键词": ["模型部署理解", "需求文档"],
            "匹配规则": "围绕核心画像综合判断，不要求逐条覆盖岗位职责。",
        }
    )

    profile_lines = [line for line in profile.splitlines() if line.strip()]
    assert 3 <= len(profile_lines) <= 10
    assert any(line.startswith("学历:") and "本科" in line for line in profile_lines)
    assert any(line.startswith("工作内容:") and "AI产品" in line for line in profile_lines)
    assert any(line.startswith("匹配程度:") for line in profile_lines)
    assert "AI产品经验" in profile
    assert "模型部署理解" in profile


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


def test_build_prompt_uses_keyword_profile_and_70_point_pass_threshold() -> None:
    client = ModelClient(
        ModelConfig(
            provider="openai-compatible",
            base_url="https://api.example.com/v1",
            api_key="test",
            model="screening-model",
            allow_without_model=False,
        ),
        score_pass=7,
        score_excellent=9,
    )
    job = JobRequirement(
        "AI产品运营",
        {"岗位核心画像": "岗位关键词画像\n核心职责关键词：用户增长、数据分析\n匹配规则：不要求候选人逐条覆盖所有岗位职责"},
        "【岗位核心画像】\n核心职责关键词：用户增长、数据分析",
        True,
        [],
    )

    prompt = client._build_prompt("候选人有用户增长和数据分析经验。", job, {"candidate_name": "张三"})
    payload = json.loads(prompt)

    assert "7分通过" in payload["instruction"]
    assert "8分通过" not in payload["instruction"]
    assert "不要求逐条匹配岗位职责" in payload["instruction"]
    assert payload["classification_rules"]["推荐初试"].startswith("overall_score >= 7")
    assert "岗位关键词画像" in payload["evaluation_flow"][0]


def test_model_client_calibrates_manual_result_above_pass_score_to_recommend(monkeypatch) -> None:
    class FakeResponse:
        def raise_for_status(self) -> None:
            return None

        def json(self) -> dict:
            return {
                "choices": [
                    {
                        "message": {
                            "content": json.dumps(
                                {
                                    "category": "待人工二筛",
                                    "overall_score": 7.2,
                                    "summary": "候选人具备用户增长和数据分析经验。",
                                    "screening_reason": "核心画像匹配度达到通过线。",
                                    "missing_information": ["薪资期望需面试确认"],
                                    "reject_reason": "",
                                    "scores": {
                                        "ability": 7,
                                        "ego": 6,
                                        "desire": 7,
                                        "learning_ability": 7,
                                        "job_fit": 7.2,
                                        "experience_fit": 7.2,
                                        "skill_fit": 7,
                                        "stability_risk": 7,
                                    },
                                },
                                ensure_ascii=False,
                            )
                        }
                    }
                ]
            }

    monkeypatch.setattr("resume_screening.model_client.httpx.post", lambda *args, **kwargs: FakeResponse())
    client = ModelClient(
        ModelConfig(
            provider="openai-compatible",
            base_url="https://api.example.com/v1",
            api_key="test",
            model="screening-model",
            allow_without_model=False,
        ),
        score_pass=7,
    )

    result = client.evaluate(
        "候选人有用户增长、数据分析经验。",
        JobRequirement("AI产品运营", {"岗位核心画像": "用户增长、数据分析"}, "岗位要求", True, []),
        {},
    )

    assert result.category == "推荐初试"
    assert "已按评分规则校准为推荐初试" in result.screening_reason


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
