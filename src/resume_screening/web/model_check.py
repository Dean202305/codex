from __future__ import annotations

from copy import deepcopy
from pathlib import Path
from typing import Any

import httpx
from resume_screening.config import AppConfig, ModelConfig
from resume_screening.local_model import LocalModelManager
from resume_screening.web.config_store import config_to_public_dict, load_config_for_web, save_config_for_web

LOCAL_PROVIDER = "local-qwen"
CUSTOM_PROVIDER = "openai-compatible"
DEFAULT_LOCAL_MODEL = "qwen3.5-local"


def check_model_for_web(config_path: Path) -> dict[str, Any]:
    data = load_config_for_web(config_path)
    config = AppConfig.model_validate(data)
    if config.model.provider == CUSTOM_PROVIDER:
        available, message = check_custom_model(config.model)
        if available:
            return {
                "available": True,
                "switched": False,
                "provider": CUSTOM_PROVIDER,
                "message": message,
                "config": config_to_public_dict(data),
            }
        if not config.model.fallback_to_local_when_unavailable:
            return {
                "available": False,
                "switched": False,
                "provider": CUSTOM_PROVIDER,
                "message": f"自定义模型不可用：{message}",
                "config": config_to_public_dict(data),
            }
        switched_data = _switch_to_local_model(data)
        saved = save_config_for_web(config_path, switched_data)
        return {
            "available": False,
            "switched": True,
            "provider": LOCAL_PROVIDER,
            "message": f"自定义模型不可用，已切换到本地模型：{message}",
            "config": saved.model_dump(mode="json"),
        }

    available, message = check_local_model(config.model)
    return {
        "available": available,
        "switched": False,
        "provider": LOCAL_PROVIDER,
        "message": message,
        "config": config_to_public_dict(data),
    }


def check_custom_model(model: ModelConfig) -> tuple[bool, str]:
    missing = [name for name in ("base_url", "api_key", "model") if not getattr(model, name)]
    if missing:
        return False, f"缺少自定义模型配置：{', '.join(missing)}"

    headers = {"Authorization": f"Bearer {model.api_key}"}
    url = f"{model.base_url.rstrip('/')}/models"
    try:
        response = httpx.get(url, headers=headers, timeout=min(max(model.timeout_seconds, 5), 20))
        response.raise_for_status()
    except httpx.HTTPStatusError as exc:
        if exc.response.status_code in {404, 405}:
            return _check_custom_chat_completion(model)
        return False, str(exc)
    except Exception as exc:
        return False, str(exc)
    return True, f"自定义模型可用：{model.model}"


def _check_custom_chat_completion(model: ModelConfig) -> tuple[bool, str]:
    try:
        response = httpx.post(
            f"{model.base_url.rstrip('/')}/chat/completions",
            headers={"Authorization": f"Bearer {model.api_key}", "Content-Type": "application/json"},
            json={
                "model": model.model,
                "temperature": 0,
                "max_tokens": 1,
                "messages": [{"role": "user", "content": "ping"}],
            },
            timeout=min(max(model.timeout_seconds, 5), 20),
        )
        response.raise_for_status()
    except Exception as exc:
        return False, str(exc)
    return True, f"自定义模型可用：{model.model}"


def check_local_model(model: ModelConfig) -> tuple[bool, str]:
    manager = LocalModelManager(model)
    status = manager.status()
    if status.state != "ready":
        return False, status.message
    try:
        available, message = manager.ensure_service(wait_seconds=min(max(model.timeout_seconds, 30), 120))
    except Exception as exc:
        return False, str(exc)
    return available, message


def _switch_to_local_model(data: dict[str, Any]) -> dict[str, Any]:
    switched = deepcopy(data)
    model = switched.setdefault("model", {})
    if not isinstance(model, dict):
        raise ValueError("model config must be a mapping")
    model["provider"] = LOCAL_PROVIDER
    model["model"] = DEFAULT_LOCAL_MODEL
    model["timeout_seconds"] = max(int(model.get("timeout_seconds") or 0), 120)
    model["allow_without_model"] = False
    model.setdefault("local", {})
    return switched
