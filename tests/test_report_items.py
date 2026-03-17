from onenote_import import _build_confidence_summary, _build_media_summary, _build_queue_summary, _build_report_item
from review import derive_blocking_issues, derive_review_triggers


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
        "quality": {"status": "unsicher", "findings": [{"requires_review": True}]},
        "health": {
            "assessments": [
                {"condition": "prostate_cancer", "light": "yellow", "certainty": "low", "requires_review": True},
                {"condition": "breast_cancer", "light": "green", "certainty": "medium", "requires_review": False},
            ]
        },
        "zutaten": ["1 Ei"],
        "schritte": ["Ruehren"],
        "media": [{"type": "image", "ocr_status": "done"}, {"type": "pdf", "ocr_status": "pending"}],
        "uncertainty": {"overall": "medium", "confidence_by_stage": {"parsing": 0.9, "taxonomy": 0.8, "health": 0.3, "ocr": 0.8}},
    }

    item = _build_report_item(recipe, status="dry_run_ok", fingerprint="abc")

    assert item["source_type"] == "ocr_file"
    assert item["ocr_status"] == "done"
    assert item["ocr_confidence"] == 0.8
    assert item["review_status"] == "needs_review"
    assert item["quality_status"] == "unsicher"
    assert item["health_prostate"] == "yellow"
    assert item["health_breast"] == "green"
    assert "quality_review" in item["review_triggers"]
    assert "health_low_certainty" in item["review_triggers"]
    assert item["media_summary"]["images"] == 1
    assert item["media_summary"]["pdfs"] == 1
    assert item["confidence_summary"]["overall"] == "medium"
    assert item["confidence_summary"]["ocr"] == 0.8
    assert item["fingerprint"] == "abc"


def test_blocking_issues_include_missing_fields_and_red_health():
    recipe = {
        "titel": "",
        "gruppe": "Backen",
        "hauptkategorie": "",
        "kategorie": "Kuchen",
        "zutaten": [],
        "schritte": [],
        "health": {"assessments": [{"condition": "prostate_cancer", "light": "red", "certainty": "medium", "requires_review": True}]},
    }
    triggers = derive_review_triggers(recipe, ["Pflichtfeld fehlt"], [])
    blocking = derive_blocking_issues(recipe, ["Pflichtfeld fehlt"], [])
    assert "missing_title" in triggers
    assert "missing_ingredients" in blocking
    assert "health_red" in blocking


def test_build_media_summary_counts_assets_and_statuses():
    summary = _build_media_summary({"media": [{"type": "image", "ocr_status": "done"}, {"type": "image", "ocr_status": "failed"}, {"type": "pdf", "ocr_status": "pending"}]})
    assert summary == {"images": 2, "pdfs": 1, "ocr_done": 1, "ocr_pending": 1, "ocr_failed": 1}


def test_build_confidence_summary_uses_uncertainty_and_ocr_confidence():
    summary = _build_confidence_summary({"ocr_confidence": 0.7, "uncertainty": {"overall": "medium", "confidence_by_stage": {"parsing": 0.9, "taxonomy": 0.8, "health": 0.3, "ocr": 0.5}}})
    assert summary == {"overall": "medium", "ocr": 0.7, "parsing": 0.9, "taxonomy": 0.8, "health": 0.3}


def test_build_queue_summary_aggregates_items_consistently():
    items = [
        {"status": "invalid", "review_status": "needs_review", "quality_status": "unsicher", "source_type": "file", "review_triggers": ["quality_review"], "blocking_issues": [], "health_prostate": "yellow", "health_breast": "unrated", "ocr_status": "", "media_summary": {"images": 0, "pdfs": 0}},
        {"status": "imported", "review_status": "approved", "quality_status": "ok", "source_type": "ocr_file", "review_triggers": ["health_red"], "blocking_issues": ["health_red"], "health_prostate": "red", "health_breast": "green", "ocr_status": "failed", "media_summary": {"images": 1, "pdfs": 0}},
    ]
    summary = _build_queue_summary(items)
    assert summary["total_items"] == 2
    assert summary["status_counts"]["invalid"] == 1
    assert summary["review_status_counts"]["needs_review"] == 1
    assert summary["source_type_counts"]["ocr_file"] == 1
    assert summary["trigger_counts"]["quality_review"] == 1
    assert summary["blocker_count"] == 1
    assert summary["needs_review_count"] == 1
    assert summary["media_present_count"] == 1
    assert summary["health_red_count"] == 1
    assert summary["ocr_failed_count"] == 1


