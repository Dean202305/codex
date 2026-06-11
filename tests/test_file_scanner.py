from pathlib import Path

from resume_screening.file_scanner import iter_candidate_files


def test_iter_candidate_files_recurses_and_includes_all_visible_file_types(tmp_path: Path) -> None:
    resume_dir = tmp_path / "resumes"
    nested = resume_dir / "nested"
    hidden = resume_dir / ".hidden"
    nested.mkdir(parents=True)
    hidden.mkdir()
    pdf = resume_dir / "a.pdf"
    txt = nested / "b.txt"
    hidden_file = hidden / "c.pdf"
    job_book = resume_dir / "jobs.xlsx"
    result_book = nested / "result.xlsx"
    for path in (pdf, txt, hidden_file, job_book, result_book):
        path.write_text("x", encoding="utf-8")

    files = iter_candidate_files(resume_dir, job_book, result_book)

    assert files == [pdf, txt]
