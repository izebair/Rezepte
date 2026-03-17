from ocr.adapter import build_ocr_command, run_local_ocr, validate_ocr_artifact
from ocr.base import OCRArtifact


def test_build_ocr_command_for_image_uses_tesseract():
    cmd = build_ocr_command("recipe.png")
    assert cmd[0].endswith("tesseract") or cmd[0] == "tesseract"


def test_validate_ocr_artifact_rejects_missing_file():
    artifact = OCRArtifact(media_id="image-1", media_type="image", ref="missing.png")
    assert validate_ocr_artifact(artifact) == "missing_file"


def test_run_local_ocr_is_disabled_by_default(tmp_path, monkeypatch):
    file_path = tmp_path / "recipe.png"
    file_path.write_bytes(b"fake")
    monkeypatch.delenv("REZEPTE_ENABLE_OCR", raising=False)
    result = run_local_ocr(OCRArtifact(media_id="image-1", media_type="image", ref=str(file_path)))
    assert result.status == "disabled"


def test_validate_ocr_artifact_rejects_large_file(tmp_path):
    file_path = tmp_path / "recipe.png"
    file_path.write_bytes(b"123456")
    artifact = OCRArtifact(media_id="image-1", media_type="image", ref=str(file_path))
    assert validate_ocr_artifact(artifact, max_bytes=2) == "file_too_large"


def test_build_ocr_command_for_pdf_uses_ocrmypdf():
    cmd = build_ocr_command("recipe.pdf")
    assert cmd[0].endswith("ocrmypdf") or cmd[0] == "ocrmypdf"
