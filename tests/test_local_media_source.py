from ocr.base import OCRResult
from sources.local_media import build_local_media_source_item


def test_build_local_media_source_item_merges_ocr_results():
    block, source_item = build_local_media_source_item(
        "recipe_scan.png",
        [OCRResult(media_id="file-1", text="2 Eier", confidence=0.75, engine="tesseract", status="done")],
    )

    assert "OCR-Notizen" in block
    assert "2 Eier" in block
    assert source_item["source_type"] == "ocr_file"
    assert source_item["ocr_status"] == "done"
    assert source_item["ocr_engine"] == "tesseract"
    assert source_item["ocr_confidence"] == 0.75
    assert source_item["media"][0]["ocr_status"] == "done"
    assert source_item["media"][0]["ocr_engine"] == "tesseract"
