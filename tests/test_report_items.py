from onenote_import import _build_report_item


def test_build_report_item_includes_review_ocr_and_health_fields():
    recipe = {
        "titel": "Testrezept",
        "gruppe": "Backen",
        "hauptkategorie": "Dessert",
        "kategorie": "Kuchen",
        "source_type": "ocr_file",
        "ocr_status": "done",
        "ocr_confidence": 0.8,
        "review": {"status": "needs_review"},
        "quality": {"status": "unsicher"},
        "health": {
            "assessments": [
                {"condition": "prostate_cancer", "light": "yellow"},
                {"condition": "breast_cancer", "light": "green"},
            ]
        },
    }

    item = _build_report_item(recipe, status="dry_run_ok", fingerprint="abc")

    assert item["source_type"] == "ocr_file"
    assert item["ocr_status"] == "done"
    assert item["ocr_confidence"] == 0.8
    assert item["review_status"] == "needs_review"
    assert item["quality_status"] == "unsicher"
    assert item["health_prostate"] == "yellow"
    assert item["health_breast"] == "green"
    assert item["fingerprint"] == "abc"
