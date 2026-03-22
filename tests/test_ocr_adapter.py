from ocr.adapter import build_ocr_command, run_local_ocr, validate_ocr_artifact
from ocr.base import OCRArtifact
from pathlib import Path
import shutil
from uuid import uuid4


def _local_test_dir(prefix: str) -> Path:
    root = Path(".tmp_test_runs")
    root.mkdir(exist_ok=True)
    path = root / f"{prefix}-{uuid4()}"
    path.mkdir()
    return path


def test_build_ocr_command_for_image_uses_tesseract(monkeypatch):
    monkeypatch.delenv("REZEPTE_OCR_PROVIDER", raising=False)
    cmd = build_ocr_command("recipe.png")
    assert cmd[0].endswith("tesseract") or cmd[0] == "tesseract"


def test_build_ocr_command_for_pdf_uses_ocrmypdf(monkeypatch):
    monkeypatch.delenv("REZEPTE_OCR_PROVIDER", raising=False)
    cmd = build_ocr_command("recipe.pdf")
    assert cmd[0].endswith("ocrmypdf") or cmd[0] == "ocrmypdf"


def test_build_ocr_command_rejects_incompatible_forced_provider(monkeypatch):
    monkeypatch.setenv("REZEPTE_OCR_PROVIDER", "tesseract")
    try:
        build_ocr_command("recipe.pdf")
        assert False, "expected ValueError"
    except ValueError as exc:
        assert "Tesseract" in str(exc)


def test_validate_ocr_artifact_rejects_missing_file():
    artifact = OCRArtifact(media_id="image-1", media_type="image", ref="missing.png")
    assert validate_ocr_artifact(artifact) == "missing_file"


def test_validate_ocr_artifact_rejects_remote_ref():
    artifact = OCRArtifact(media_id="image-1", media_type="image", ref="https://example.com/recipe.png")
    assert validate_ocr_artifact(artifact) == "non_local_ref"


def test_validate_ocr_artifact_rejects_outside_allowed_root(monkeypatch):
    tmp_path = _local_test_dir("ocr-allowed-root")
    try:
        allowed_root = tmp_path / "allowed"
        allowed_root.mkdir()
        file_path = tmp_path / "recipe.png"
        file_path.write_bytes(b"fake")
        monkeypatch.setenv("REZEPTE_OCR_ROOT", str(allowed_root))
        artifact = OCRArtifact(media_id="image-1", media_type="image", ref=str(file_path))
        assert validate_ocr_artifact(artifact) == "outside_allowed_root"
    finally:
        shutil.rmtree(tmp_path, ignore_errors=True)


def test_run_local_ocr_is_disabled_by_default(monkeypatch):
    tmp_path = _local_test_dir("ocr-disabled")
    try:
        file_path = tmp_path / "recipe.png"
        file_path.write_bytes(b"fake")
        monkeypatch.delenv("REZEPTE_ENABLE_OCR", raising=False)
        result = run_local_ocr(OCRArtifact(media_id="image-1", media_type="image", ref=str(file_path)))
        assert result.status == "disabled"
    finally:
        shutil.rmtree(tmp_path, ignore_errors=True)


def test_run_local_ocr_rejects_invalid_provider(monkeypatch):
    tmp_path = _local_test_dir("ocr-invalid-provider")
    try:
        file_path = tmp_path / "recipe.png"
        file_path.write_bytes(b"fake")
        monkeypatch.setenv("REZEPTE_ENABLE_OCR", "1")
        monkeypatch.setenv("REZEPTE_OCR_PROVIDER", "broken")
        result = run_local_ocr(OCRArtifact(media_id="image-1", media_type="image", ref=str(file_path)))
        assert result.status == "invalid_provider"
    finally:
        shutil.rmtree(tmp_path, ignore_errors=True)


def test_validate_ocr_artifact_rejects_large_file():
    tmp_path = _local_test_dir("ocr-large-file")
    try:
        file_path = tmp_path / "recipe.png"
        file_path.write_bytes(b"123456")
        artifact = OCRArtifact(media_id="image-1", media_type="image", ref=str(file_path))
        assert validate_ocr_artifact(artifact, max_bytes=2) == "file_too_large"
    finally:
        shutil.rmtree(tmp_path, ignore_errors=True)
