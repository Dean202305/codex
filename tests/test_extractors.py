from pathlib import Path

from resume_screening.extractors import extract_text


def test_extract_unsupported_file_returns_error(tmp_path: Path) -> None:
    path = tmp_path / "resume.txt"
    path.write_text("hello", encoding="utf-8")

    result = extract_text(path, ocr_command="tesseract")

    assert result.text == ""
    assert result.method == "unsupported"
    assert "不支持的文件格式" in result.errors


def test_extract_docx_reads_paragraphs(tmp_path: Path) -> None:
    from docx import Document

    path = tmp_path / "resume.docx"
    document = Document()
    document.add_paragraph("郭燕婷")
    document.add_paragraph("财务总监候选人，10年以上经验")
    document.save(path)

    result = extract_text(path, ocr_command="tesseract")

    assert "郭燕婷" in result.text
    assert "10年以上经验" in result.text
    assert result.method == "docx"
