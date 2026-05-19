from __future__ import annotations

from pathlib import Path


def iter_candidate_files(resume_dir: Path, job_book: Path, result_book: Path) -> list[Path]:
    if not resume_dir.exists() or not resume_dir.is_dir():
        return []

    skip = {job_book.resolve(), result_book.resolve()}
    files: list[Path] = []
    for path in resume_dir.rglob("*"):
        if not path.is_file():
            continue
        if _has_hidden_part(path, resume_dir):
            continue
        if path.resolve() in skip:
            continue
        files.append(path)
    return sorted(files)


def _has_hidden_part(path: Path, root: Path) -> bool:
    try:
        relative = path.relative_to(root)
    except ValueError:
        relative = path
    return any(part.startswith(".") for part in relative.parts)
