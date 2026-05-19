from __future__ import annotations

from pathlib import Path

import httpx

from resume_screening.config import AppConfig
from resume_screening.duplicates import DuplicateIndex
from resume_screening.excel_writer import ResultWorkbookWriter
from resume_screening.extractors import SUPPORTED_EXTENSIONS, extract_text
from resume_screening.filename_parser import parse_resume_filename
from resume_screening.job_requirements import load_job_requirements
from resume_screening.model_client import ModelClient
from resume_screening.models import (
    CATEGORY_MANUAL,
    DuplicateMatch,
    ExtractionResult,
    JobRequirement,
    ParsedFilename,
    PipelineStats,
    ScreeningResult,
    ScreeningScores,
)


class ScreeningPipeline:
    def __init__(self, config: AppConfig) -> None:
        self.config = config

    def run(self) -> PipelineStats:
        jobs = load_job_requirements(self.config.job_book)
        writer = ResultWorkbookWriter(self.config.result_book)
        index = DuplicateIndex.load(self.config.index_path)
        client = None if self.config.model.allow_without_model else ModelClient(self.config.model)
        stats = PipelineStats()

        for path in self._resume_files():
            parsed = parse_resume_filename(path)
            extraction = extract_text(path, self.config.ocr_command)
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

        writer.save()
        index.save()
        return stats

    def _resume_files(self) -> list[Path]:
        skip = {self.config.job_book.resolve(), self.config.result_book.resolve()}
        files: list[Path] = []
        for path in self.config.resume_dir.iterdir():
            if not path.is_file():
                continue
            if path.resolve() in skip:
                continue
            if path.suffix.lower() in SUPPORTED_EXTENSIONS:
                files.append(path)
        return sorted(files)

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

        job = jobs.get(parsed.job_name)
        if not job:
            missing.append("岗位名称未匹配到岗位说明书sheet")
            return manual_result("岗位名称未匹配到岗位说明书sheet，需人工确认", missing)
        if not job.is_complete:
            missing.append("岗位要求不完整，需人工确认")
            missing.extend(job.missing_fields)
            return manual_result("岗位要求不完整，需人工确认", missing)
        if client is None:
            missing.append("模型配置缺失，已按人工二筛处理")
            return manual_result("模型配置缺失，需人工确认", missing)

        try:
            return client.evaluate(
                resume_text=extraction.text,
                job=job,
                filename_metadata={
                    "job_name": parsed.job_name,
                    "expected_location": parsed.expected_location,
                    "salary_range": parsed.salary_range,
                    "candidate_name": parsed.candidate_name,
                    "work_experience": parsed.work_experience,
                },
            )
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
