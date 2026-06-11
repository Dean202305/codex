from __future__ import annotations

from pathlib import Path
from typing import Any

from pydantic import BaseModel

from resume_screening.config import AppConfig
from resume_screening.job_requirements import apply_job_profile_overrides, compact_job_profile_text, load_job_requirements
from resume_screening.model_client import ModelClient
from resume_screening.web.config_store import config_to_public_dict, load_config_for_web, save_config_for_web


class JobProfilePayload(BaseModel):
    job_name: str
    profile: str


class JobProfilesPayload(BaseModel):
    profiles: list[JobProfilePayload]


def load_job_profiles_for_web(config: AppConfig) -> list[dict[str, Any]]:
    loaded_jobs = load_job_requirements(config.job_book, ocr_command=config.ocr_command)
    jobs = apply_job_profile_overrides(
        loaded_jobs,
        config.job_profile_overrides,
    )
    model_client = _profile_model_client(config)
    profiles: list[dict[str, Any]] = []
    for job_name, job in jobs.items():
        profile_error = ""
        if job_name in config.job_profile_overrides:
            profile = job.fields.get("岗位核心画像") or config.job_profile_overrides[job_name]
            source = "custom"
        else:
            profile, source, profile_error = _generate_profile(model_client, job)
        profiles.append(
            {
                "job_name": job_name,
                "sheet_name": job.sheet_name,
                "profile": profile,
                "source": source,
                "profile_error": profile_error,
                "is_custom_only": job_name not in loaded_jobs,
                "is_complete": job.is_complete,
                "missing_fields": job.missing_fields,
            }
        )
    return profiles


def save_job_profiles_for_web(config_path: Path, payload: JobProfilesPayload) -> dict[str, Any]:
    data = load_config_for_web(config_path)
    overrides = {}
    for profile in payload.profiles:
        job_name = profile.job_name.strip()
        cleaned = profile.profile.strip()
        if not job_name:
            continue
        if cleaned:
            overrides[job_name] = compact_job_profile_text(cleaned, job_name=job_name)
        else:
            overrides.pop(job_name, None)
    data["job_profile_overrides"] = overrides
    saved = save_config_for_web(config_path, data)
    return {
        "profiles": load_job_profiles_for_web(saved),
        "config": config_to_public_dict(load_config_for_web(config_path)),
    }


def _profile_model_client(config: AppConfig) -> ModelClient | None:
    if config.model.provider == "local-qwen":
        return None
    if config.model.allow_without_model or not config.model.is_complete():
        return None
    return ModelClient(
        config.model,
        score_pass=config.screening.score_pass,
        score_excellent=config.screening.score_excellent,
    )


def _generate_profile(model_client: ModelClient | None, job) -> tuple[str, str, str]:
    fallback = job.fields.get("岗位核心画像") or job.raw_text
    if model_client is None:
        return fallback, "generated", ""
    try:
        generated = model_client.generate_job_profile(job).strip()
    except Exception as exc:
        return fallback, "generated", f"模型画像生成失败，已使用规则画像：{exc}"
    if not generated:
        return fallback, "generated", "模型画像为空，已使用规则画像"
    return generated, "model", ""
