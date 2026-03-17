from ocr.base import OCRResult
from sources.ocr_merge import attach_ocr_results_to_source_item


def test_attach_ocr_results_updates_media_and_summary():
    source_item = {
        "id": "page-1",
        "title": "Tomatensuppe",
        "text": "Tomatensuppe",
        "ocr_text": "",
        "ocr_confidence": 0.0,
        "media": [{"media_id": "image-1", "type": "image", "ref": "a.png", "ocr_text_ref": "", "ocr_status": "pending", "ocr_confidence": 0.0}],
    }
    updated = attach_ocr_results_to_source_item(
        source_item,
        [OCRResult(media_id="image-1", text="2 Tomaten", confidence=0.7, engine="test", status="done")],
    )
    assert updated["ocr_text"] == "2 Tomaten"
    assert updated["ocr_status"] == "done"
    assert updated["media"][0]["ocr_status"] == "done"
    assert updated["media"][0]["ocr_text_ref"] == "2 Tomaten"
