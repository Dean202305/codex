from __future__ import annotations

from collections.abc import Callable
from dataclasses import replace
from pathlib import Path

import httpx

from resume_screening.config import AppConfig
from resume_screening.duplicates import DuplicateIndex
from resume_screening.excel_writer import ResultWorkbookWriter
from resume_screening.extractors import extract_text
from resume_screening.file_scanner import iter_candidate_files
from resume_screening.filename_parser import parse_resume_filename
from resume_screening.job_matcher import resolve_job
from resume_screening.job_requirements import apply_job_profile_overrides, load_job_requirements
from resume_screening.model_client import ModelClient
from resume_screening.models import (
    CATEGORY_MANUAL,
    DuplicateMatch,
    ExtractionResult,
    JobRequirement,
    ParsedFilename,
    PipelineEvent,
    PipelineStats,
    ScreeningResult,
    ScreeningScores,
)
from resume_screening.text_utils import sanitize_text


class ScreeningPipeline:
    def __init__(
        self,
        config: AppConfig,
        event_handler: Callable[[PipelineEvent], None] | None = None,
        should_stop: Callable[[], bool] | None = None,
    ) -> None:
        self.config = config
        self.event_handler = event_handler
        self.should_stop = should_stop or (lambda: False)
        self.model_unavailable_message = ""

    def _emit(self, event: PipelineEvent) -> None:
        if self.event_handler is not None:
            self.event_handler(event)

    def run(self) -> PipelineStats:
        jobs = apply_job_profile_overrides(
            load_job_requirements(self.config.job_book, ocr_command=self.config.ocr_command),
            self.config.job_profile_overrides,
        )
        writer = ResultWorkbookWriter(
            self.config.result_book,
            score_pass=self.config.screening.score_pass,
            score_excellent=self.config.screening.score_excellent,
        )
        index = DuplicateIndex.load(self.config.index_path)
        if self.config.model.provider == "local-qwen":
            available, message = self._ensure_local_model_service()
            if not available:
                self.model_unavailable_message = message
                self._emit(PipelineEvent("warning", message))
        client = (
            ModelClient(
                self.config.model,
                score_pass=self.config.screening.score_pass,
                score_excellent=self.config.screening.score_excellent,
            )
            if self.config.model.is_complete() and not self.model_unavailable_message
            else None
        )
        stats = PipelineStats()
        files = self._resume_files()
        self._emit(PipelineEvent("run_started", f"开始处理 {len(files)} 个文件", total=len(files)))

        stopped = False
        for current, path in enumerate(files, start=1):
            if self.should_stop():
                stopped = True
                break
            self._emit(PipelineEvent("file_started", f"正在处理：{path.name}", current=current, total=len(files), filename=path.name))
            parsed = parse_resume_filename(path)
            extraction = extract_text(path, self.config.ocr_command)
            extraction = ExtractionResult(
                text=sanitize_text(extraction.text),
                method=extraction.method,
                errors=[sanitize_text(error) for error in extraction.errors],
            )
            duplicate = index.find(extraction.text) if extraction.text else DuplicateMatch(False)
            result = self._screen(parsed, extraction, jobs, client)
            row_id = writer.append_result(
                parsed=parsed,
                result=result,
                duplicate=duplicate,
                extraction_errors=extraction.errors,
                default_source_channel=self.config.default_source_channel,
                default_interviewer=self.config.default_interviewer,
            )
            if extraction.text:
                index.add(extraction.text, path.name, row_id, parsed.candidate_name, parsed.job_name)
            stats.processed += 1
            stats.count_category(result.category)
            if duplicate.is_duplicate:
                stats.duplicate += 1
            if not parsed.is_standard:
                stats.non_standard_names += 1
            if extraction.errors:
                stats.extraction_failures += 1
            if any(item.startswith("模型评估失败") for item in result.missing_information):
                stats.model_failures += 1
            self._emit(
                PipelineEvent(
                    "file_completed",
                    f"完成：{path.name} -> {result.category}",
                    current=current,
                    total=len(files),
                    filename=path.name,
                    category=result.category,
                    stats=stats,
                )
            )

        stopped = stopped or self.should_stop()
        writer.save()
        index.save()
        if stopped:
            self._emit(PipelineEvent("run_cancelled", "筛选任务已停止，已保存已完成结果", current=stats.processed, total=len(files), stats=stats))
        else:
            self._emit(PipelineEvent("run_completed", "处理完成", current=len(files), total=len(files), stats=stats))
        return stats

    def _resume_files(self) -> list[Path]:
        return iter_candidate_files(self.config.resume_dir, self.config.job_book, self.config.result_book)

    def _ensure_local_model_service(self) -> tuple[bool, str]:
        from resume_screening.local_model import LocalModelManager, local_model_startup_wait_seconds

        manager = LocalModelManager(self.config.model)
        wait_seconds = local_model_startup_wait_seconds(self.config.model.timeout_seconds)
        return manager.ensure_service(wait_seconds=wait_seconds)

    def _screen(
        self,
        parsed: ParsedFilename,
        extraction: ExtractionResult,
        jobs: dict[str, JobRequirement],
        client: ModelClient | None,
    ) -> ScreeningResult:
        missing = list(parsed.missing_fields)
        if not parsed.is_standard:
            missing.append("文件名不规范/字段无法从文件名确认")
            if not extraction.text:
                missing.extend(extraction.errors or ["无法提取简历正文"])
            return manual_result("文件名不规范，需人工确认", missing)
        if not extraction.text:
            missing.extend(extraction.errors or ["无法提取简历正文"])
            return manual_result("无法提取简历正文，需人工确认", missing)

        job_match = resolve_job(parsed, jobs, self.config.job_aliases)
        if job_match.note:
            missing.append(job_match.note)
        if not job_match.job:
            missing.append("岗位名称未匹配到岗位说明书sheet")
            if jobs:
                missing.append(f"可用岗位sheet：{'、'.join(jobs)}")
            return manual_result("岗位名称未匹配到岗位说明书sheet，需人工确认", missing)
        job = job_match.job
        if not job.is_complete:
            missing.append("岗位要求不完整")
            missing.extend(job.missing_fields)
        if client is None:
            message = self.model_unavailable_message or "模型配置缺失，已按人工二筛处理"
            missing.append(message)
            return manual_result("模型不可用，需人工确认", missing)

        try:
            result = client.evaluate(
                resume_text=extraction.text,
                job=job,
                filename_metadata={
                    "job_name": parsed.job_name,
                    "expected_location": parsed.expected_location,
                    "salary_range": parsed.salary_range,
                    "candidate_name": parsed.candidate_name,
                    "work_experience": parsed.work_experience,
                    "matched_job_sheet": job.sheet_name,
                },
            )
            return _append_missing_information(result, missing)
        except httpx.TimeoutException:
            print(f"模型评估失败：请求超时 - {parsed.path.name}")
            return manual_result("模型评估失败，需人工确认", missing + ["模型评估失败：请求超时"])
        except httpx.HTTPStatusError as exc:
            print(f"模型评估失败：HTTP {exc.response.status_code} - {parsed.path.name}")
            return manual_result("模型评估失败，需人工确认", missing + [f"模型评估失败：HTTP {exc.response.status_code}"])
        except Exception as exc:
            print(f"模型评估失败：{exc} - {parsed.path.name}")
            return manual_result("模型评估失败，需人工确认", missing + [f"模型评估失败：{exc}"])


def manual_result(reason: str, missing: list[str]) -> ScreeningResult:
    return ScreeningResult(
        category=CATEGORY_MANUAL,
        overall_score=0,
        summary=reason,
        screening_reason=reason,
        missing_information=missing,
        reject_reason="",
        scores=ScreeningScores(0, 0, 0, 0, 0, 0, 0, 0),
    )


def _append_missing_information(result: ScreeningResult, missing: list[str]) -> ScreeningResult:
    merged = [item for item in [*missing, *result.missing_information] if item]
    deduped = list(dict.fromkeys(merged))
    return replace(result, missing_information=deduped)
