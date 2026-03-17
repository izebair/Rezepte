from ocr.base import OCRResult, build_ocr_artifacts, merge_ocr_text_into_block


def test_build_ocr_artifacts_filters_invalid_media_items():
    media = [
        {"media_id": "image-1", "type": "image", "ref": "https://example.com/a.jpg"},
        {"media_id": "pdf-1", "type": "pdf", "ref": "https://example.com/a.pdf"},
        {"media_id": "", "type": "image", "ref": "missing"},
    ]
    artifacts = build_ocr_artifacts(media)
    assert len(artifacts) == 2
    assert artifacts[0].media_id == "image-1"
    assert artifacts[1].media_type == "pdf"


def test_merge_ocr_text_into_block_appends_ocr_notes():
    block = "Tomatensuppe\n\n2 Tomaten\n500 ml Wasser"
    merged = merge_ocr_text_into_block(
        block,
        [OCRResult(media_id="pdf-1", text="Zusatz aus PDF", confidence=0.7, engine="test", status="done")],
    )
    assert "Tomatensuppe" in merged
    assert "OCR-Notizen:" in merged
    assert "Zusatz aus PDF" in merged
