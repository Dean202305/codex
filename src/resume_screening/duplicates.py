from __future__ import annotations

import hashlib
import json
import re
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from difflib import SequenceMatcher
from pathlib import Path

from resume_screening.models import DuplicateMatch


def normalize_text(text: str) -> str:
    return re.sub(r"\s+", "", text).strip()


def fingerprint(text: str) -> str:
    normalized = normalize_text(text)
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()


@dataclass(frozen=True)
class IndexEntry:
    fingerprint: str
    normalized_text: str
    filename: str
    row_id: int
    candidate_name: str
    job_name: str
    processed_at: str


class DuplicateIndex:
    def __init__(self, path: Path, entries: list[IndexEntry]) -> None:
        self.path = path
        self.entries = entries

    @classmethod
    def load(cls, path: Path) -> "DuplicateIndex":
        if not path.exists():
            return cls(path=path, entries=[])
        raw = json.loads(path.read_text(encoding="utf-8"))
        entries = [IndexEntry(**item) for item in raw.get("entries", [])]
        return cls(path=path, entries=entries)

    def save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        payload = {"entries": [asdict(entry) for entry in self.entries]}
        self.path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    def find(self, text: str, threshold: float = 0.92) -> DuplicateMatch:
        normalized = normalize_text(text)
        current_hash = fingerprint(normalized)
        for entry in self.entries:
            if entry.fingerprint == current_hash:
                return DuplicateMatch(True, entry.filename, entry.row_id, 1.0)
        best_entry: IndexEntry | None = None
        best_ratio = 0.0
        for entry in self.entries:
            ratio = SequenceMatcher(None, normalized, entry.normalized_text).ratio()
            if ratio > best_ratio:
                best_ratio = ratio
                best_entry = entry
        if best_entry and best_ratio >= threshold:
            return DuplicateMatch(True, best_entry.filename, best_entry.row_id, best_ratio)
        return DuplicateMatch(False)

    def add(self, text: str, filename: str, row_id: int, candidate_name: str, job_name: str) -> None:
        normalized = normalize_text(text)
        self.entries.append(
            IndexEntry(
                fingerprint=fingerprint(normalized),
                normalized_text=normalized,
                filename=filename,
                row_id=row_id,
                candidate_name=candidate_name,
                job_name=job_name,
                processed_at=datetime.now(timezone.utc).isoformat(),
            )
        )
