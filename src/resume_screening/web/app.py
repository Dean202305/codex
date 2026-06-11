from __future__ import annotations

from dataclasses import asdict, is_dataclass
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import ValidationError

from resume_screening.config import AppConfig
from resume_screening.web.config_store import config_to_public_dict, load_config_for_web, save_config_for_web
from resume_screening.web.job_profiles import JobProfilesPayload, load_job_profiles_for_web, save_job_profiles_for_web
from resume_screening.web.local_model_api import register_local_model_routes
from resume_screening.web.model_check import check_model_for_web
from resume_screening.web.precheck import run_precheck
from resume_screening.web.runs import RunAlreadyActive, RunManager


def _jsonable(value: Any) -> Any:
    if is_dataclass(value):
        return asdict(value)
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, list):
        return [_jsonable(item) for item in value]
    if isinstance(value, dict):
        return {key: _jsonable(item) for key, item in value.items()}
    return value


def create_app(config_path: Path = Path("config.yaml"), static_dir: Path | None = None, run_manager: RunManager | None = None) -> FastAPI:
    app = FastAPI(title="Resume Screening Web")
    manager = run_manager or RunManager(config_path)
    static_root = static_dir or Path(__file__).parent / "static"

    @app.get("/api/config")
    def get_config() -> dict[str, Any]:
        data = load_config_for_web(config_path)
        return {"config": config_to_public_dict(data)}

    @app.post("/api/config")
    def post_config(payload: dict[str, Any]) -> dict[str, Any]:
        try:
            saved = save_config_for_web(config_path, payload)
        except (ValueError, ValidationError) as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        return {"config": saved.model_dump(mode="json")}

    @app.get("/api/precheck")
    def get_precheck() -> dict[str, Any]:
        try:
            config = AppConfig.model_validate(load_config_for_web(config_path))
        except (ValueError, ValidationError) as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        return _jsonable(run_precheck(config))

    @app.post("/api/model/check")
    def post_model_check() -> dict[str, Any]:
        try:
            return _jsonable(check_model_for_web(config_path))
        except (ValueError, ValidationError) as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.get("/api/job-profiles")
    def get_job_profiles() -> dict[str, Any]:
        try:
            config = AppConfig.model_validate(load_config_for_web(config_path))
            return {"profiles": _jsonable(load_job_profiles_for_web(config))}
        except Exception as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.post("/api/job-profiles")
    def post_job_profiles(payload: dict[str, Any]) -> dict[str, Any]:
        try:
            parsed = JobProfilesPayload.model_validate(payload)
            return _jsonable(save_job_profiles_for_web(config_path, parsed))
        except Exception as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.post("/api/runs")
    def start_run() -> dict[str, Any]:
        try:
            return {"run": _jsonable(manager.start())}
        except RunAlreadyActive as exc:
            raise HTTPException(status_code=409, detail={"message": "已有筛选任务运行中", "run_id": exc.run_id}) from exc

    @app.get("/api/runs/{run_id}")
    def get_run(run_id: str) -> dict[str, Any]:
        try:
            return {"run": _jsonable(manager.get(run_id))}
        except KeyError as exc:
            raise HTTPException(status_code=404, detail="run not found") from exc

    @app.post("/api/runs/{run_id}/cancel")
    def cancel_run(run_id: str) -> dict[str, Any]:
        try:
            return {"run": _jsonable(manager.cancel(run_id))}
        except KeyError as exc:
            raise HTTPException(status_code=404, detail="run not found") from exc

    register_local_model_routes(app, config_path)

    if static_root.exists():
        assets = static_root / "assets"
        if assets.exists():
            app.mount("/assets", StaticFiles(directory=assets), name="assets")

        @app.get("/{path:path}")
        def frontend(path: str) -> FileResponse:
            target = static_root / path
            if path and target.exists() and target.is_file():
                return FileResponse(target)
            return FileResponse(static_root / "index.html")

    return app
