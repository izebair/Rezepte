import json
import shutil
from pathlib import Path
from uuid import uuid4

import onenote_import
from ocr.base import OCRResult


VALID_OCR_BLOCK = """Titel: OCR Kuchen
Gruppe: Backen
Kategorie: Kuchen

Zutaten:
- 1 Ei

Zubereitung:
1. Ruehren
"""


def _local_test_dir(prefix: str) -> Path:
    root = Path(".tmp_test_runs")
    root.mkdir(exist_ok=True)
    path = root / f"{prefix}-{uuid4()}"
    path.mkdir()
    return path


def test_main_dry_run_processes_local_media_with_mocked_ocr(monkeypatch):
    tmp_path = _local_test_dir("local-ocr-flow")
    input_file = tmp_path / "scan.png"
    report_file = tmp_path / "report.json"
    input_file.write_bytes(b"fake-image")

    captured = {}

    def fake_run_ocr_for_artifacts(artifacts):
        captured["artifacts"] = artifacts
        return [OCRResult(media_id="file-1", text="Titel: OCR Kuchen", confidence=0.81, engine="tesseract", status="done")]

    def fake_build_local_media_source_item(input_path, ocr_results):
        return (
            VALID_OCR_BLOCK,
            {
                "id": input_path,
                "title": "scan",
                "text": "",
                "ocr_text": "Titel: OCR Kuchen",
                "ocr_confidence": 0.81,
                "ocr_status": "done",
                "ocr_engine": "tesseract",
                "media": [
                    {
                        "media_id": "file-1",
                        "type": "image",
                        "ref": input_path,
                        "ocr_text_ref": "Titel: OCR Kuchen",
                        "ocr_status": "done",
                        "ocr_confidence": 0.81,
                        "ocr_engine": "tesseract",
                    }
                ],
                "source_type": "ocr_file",
            },
        )

    monkeypatch.setattr(onenote_import, "run_ocr_for_artifacts", fake_run_ocr_for_artifacts)
    monkeypatch.setattr(onenote_import, "build_local_media_source_item", fake_build_local_media_source_item)

    try:
        result = onenote_import.main([
            "--dry-run",
            "--ocr",
            "--input-file",
            str(input_file),
            "--report-file",
            str(report_file),
        ])

        assert result == 0
        assert captured["artifacts"][0].ref == str(input_file)

        report = json.loads(report_file.read_text(encoding="utf-8"))
        assert report["summary"]["valid"] == 1
        assert report["summary"]["invalid"] == 0
        assert report["items"][0]["source_type"] == "ocr_file"
        assert report["items"][0]["source_label"] == "OCR-Extrakt"
        assert report["items"][0]["ocr_status"] == "done"
        assert report["items"][0]["ocr_engine"] == "tesseract"
        assert report["queue_summary"]["source_type_counts"]["ocr_file"] == 1
        assert report["queue_summary"]["ocr_engine_counts"]["tesseract"] == 1
    finally:
        shutil.rmtree(tmp_path, ignore_errors=True)


def test_main_rejects_local_media_without_ocr_flag():
    tmp_path = _local_test_dir("local-ocr-no-flag")
    input_file = tmp_path / "scan.png"
    input_file.write_bytes(b"fake-image")

    try:
        result = onenote_import.main([
            "--dry-run",
            "--input-file",
            str(input_file),
        ])

        assert result == 2
    finally:
        shutil.rmtree(tmp_path, ignore_errors=True)


def test_main_dry_run_marks_empty_local_ocr_for_review(monkeypatch):
    tmp_path = _local_test_dir("local-ocr-empty")
    input_file = tmp_path / "scan.png"
    report_file = tmp_path / "report.json"
    input_file.write_bytes(b"fake-image")

    def fake_run_ocr_for_artifacts(artifacts):
        return [OCRResult(media_id="file-1", text="", confidence=0.0, engine="tesseract", status="empty")]

    def fake_build_local_media_source_item(input_path, ocr_results):
        return (
            "Titel: Leer Scan\nGruppe: Backen\nKategorie: Kuchen\n\nZutaten:\n- 1 Ei\n\nZubereitung:\n1. Ruehren\n",
            {
                "id": input_path,
                "title": "scan",
                "text": "",
                "ocr_text": "",
                "ocr_confidence": 0.0,
                "ocr_status": "empty",
                "ocr_engine": "tesseract",
                "media": [
                    {
                        "media_id": "file-1",
                        "type": "image",
                        "ref": input_path,
                        "ocr_text_ref": "",
                        "ocr_status": "empty",
                        "ocr_confidence": 0.0,
                        "ocr_engine": "tesseract",
                    }
                ],
                "source_type": "ocr_file",
            },
        )

    monkeypatch.setattr(onenote_import, "run_ocr_for_artifacts", fake_run_ocr_for_artifacts)
    monkeypatch.setattr(onenote_import, "build_local_media_source_item", fake_build_local_media_source_item)

    try:
        result = onenote_import.main([
            "--dry-run",
            "--ocr",
            "--input-file",
            str(input_file),
            "--report-file",
            str(report_file),
        ])

        assert result == 0

        report = json.loads(report_file.read_text(encoding="utf-8"))
        item = report["items"][0]
        assert item["ocr_status"] == "empty"
        assert "ocr_empty" in item["review_triggers"]
        assert "ocr_empty_result" in item["review_triggers"]
        assert item["review_status"] == "needs_review"
        assert report["queue_summary"]["ocr_empty_count"] == 1
    finally:
        shutil.rmtree(tmp_path, ignore_errors=True)
