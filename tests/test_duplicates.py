from pathlib import Path

from resume_screening.duplicates import DuplicateIndex, normalize_text


def test_normalize_text_removes_spacing_noise() -> None:
    assert normalize_text("郭  燕婷\n\n10年以上经验") == "郭燕婷10年以上经验"


def test_duplicate_index_detects_exact_content(tmp_path: Path) -> None:
    path = tmp_path / "processed_index.json"
    index = DuplicateIndex.load(path)
    index.add(text="郭燕婷10年以上财务经验", filename="a.pdf", row_id=7, candidate_name="郭燕婷", job_name="财务总监")
    index.save()

    reloaded = DuplicateIndex.load(path)
    match = reloaded.find("郭燕婷 10年以上 财务经验")

    assert match.is_duplicate is True
    assert match.matched_filename == "a.pdf"
    assert match.matched_row_id == 7
