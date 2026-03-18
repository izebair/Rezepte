from onenote_import import _build_confidence_summary, _build_media_summary, _build_queue_summary, _build_report_item, _sanitize_report_error, _sanitize_report_path, _derive_source_label, _derive_ocr_required_status, _derive_work_bucket
from review import derive_blocking_issues, derive_review_triggers


def test_build_report_item_includes_review_ocr_and_health_fields():
    recipe = {
        "titel": "Testrezept",
        "gruppe": "Backen",
        "hauptkategorie": "Dessert",
        "kategorie": "Kuchen",
        "ziel_gruppe": "Dessert",
        "ziel_kategorie": "Kuchen & Gebaeck",
        "source_type": "ocr_file",
        "ocr_status": "done",
        "ocr_engine": "tesseract",
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
    assert item["source_label"] == "OCR-Extrakt"
    assert item["ocr_required_status"] == "done"
    assert item["parser_type"] == "unknown"
    assert item["target_group"] == "Dessert"
    assert item["target_category"] == "Kuchen & Gebaeck"
    assert item["ocr_status"] == "done"
    assert item["ocr_engine"] == "tesseract"
    assert item["ocr_confidence"] == 0.8
    assert item["review_status"] == "needs_review"
    assert item["quality_status"] == "unsicher"
    assert item["work_bucket"] == "review_general"
    assert item["health_prostate"] == "yellow"
    assert item["health_breast"] == "green"
    assert "quality_review" in item["review_triggers"]
    assert "health_low_certainty" in item["review_triggers"]
    assert item["media_summary"]["images"] == 1
    assert item["media_summary"]["pdfs"] == 1
    assert item["confidence_summary"]["overall"] == "medium"
    assert item["uncertainty_reasons"] == []
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
        {"status": "invalid", "parser_type": "freeform", "source_type": "file_text", "review_status": "needs_review", "work_bucket": "review_general", "quality_status": "unsicher", "review_triggers": ["quality_review", "category_unmapped"], "blocking_issues": [], "health_prostate": "yellow", "health_breast": "unrated", "ocr_engine": "pending", "ocr_status": "", "media_summary": {"images": 0, "pdfs": 0}, "confidence_summary": {"overall": "medium"}},
        {"status": "imported", "parser_type": "structured", "source_type": "ocr_file", "review_status": "approved", "work_bucket": "ocr_repair", "quality_status": "ok", "review_triggers": ["health_red", "source_has_media"], "blocking_issues": ["health_red"], "health_prostate": "red", "health_breast": "green", "ocr_engine": "tesseract", "ocr_required_status": "failed", "ocr_status": "failed", "media_summary": {"images": 1, "pdfs": 0}, "confidence_summary": {"overall": "high"}},
        {"status": "dry_run_ok", "parser_type": "structured", "source_type": "ocr_file", "review_status": "needs_review", "work_bucket": "ocr_first", "quality_status": "unsicher", "review_triggers": ["source_has_media", "ocr_required", "ocr_empty_result"], "blocking_issues": [], "health_prostate": "green", "health_breast": "green", "ocr_engine": "pending", "ocr_required_status": "pending", "ocr_status": "empty", "media_summary": {"images": 1, "pdfs": 0}, "confidence_summary": {"overall": "low"}},
        {"status": "dry_run_ok", "parser_type": "freeform", "source_type": "onenote_page", "review_status": "needs_review", "work_bucket": "review_after_ocr", "quality_status": "unsicher", "review_triggers": ["source_has_media"], "blocking_issues": [], "health_prostate": "green", "health_breast": "green", "ocr_engine": "ocrmypdf", "ocr_required_status": "done", "ocr_status": "done", "media_summary": {"images": 0, "pdfs": 1}, "confidence_summary": {"overall": "low"}},
    ]

    summary = _build_queue_summary(items)

    assert summary["total_items"] == 4
    assert summary["status_counts"]["invalid"] == 1
    assert summary["review_status_counts"]["needs_review"] == 3
    assert summary["parser_type_counts"]["freeform"] == 2
    assert summary["parser_type_counts"]["structured"] == 2
    assert summary["needs_review_by_parser_type"]["freeform"] == 2
    assert summary["needs_review_by_parser_type"]["structured"] == 1
    assert summary["needs_review_by_source_type"]["file_text"] == 1
    assert summary["needs_review_by_source_type"]["ocr_file"] == 1
    assert summary["needs_review_by_source_type"]["onenote_page"] == 1
    assert summary["needs_review_by_ocr_engine"]["pending"] == 2
    assert summary["needs_review_by_ocr_engine"]["ocrmypdf"] == 1
    assert summary["source_type_counts"]["ocr_file"] == 2
    assert summary["ocr_engine_counts"]["pending"] == 2
    assert summary["work_bucket_counts"]["review_general"] == 1
    assert summary["work_bucket_counts"]["ocr_repair"] == 1
    assert summary["work_bucket_counts"]["ocr_first"] == 1
    assert summary["work_bucket_counts"]["review_after_ocr"] == 1
    assert summary["ocr_engine_counts"]["tesseract"] == 1
    assert summary["ocr_engine_counts"]["ocrmypdf"] == 1
    assert summary["trigger_counts"]["quality_review"] == 1
    assert summary["blocker_count"] == 1
    assert summary["review_triggered_item_count"] == 4
    assert summary["uncertain_item_count"] == 2
    assert summary["taxonomy_fallback_count"] == 1
    assert summary["high_review_load_count"] == 2
    assert summary["needs_review_count"] == 3
    assert summary["ocr_required_item_count"] == 2
    assert summary["ocr_queue_count"] == 2
    assert summary["ocr_fix_count"] == 1
    assert summary["post_ocr_review_count"] == 1
    assert summary["media_review_count"] == 3
    assert summary["media_present_count"] == 3
    assert summary["onenote_media_count"] == 1
    assert summary["health_red_count"] == 1
    assert summary["ocr_pending_count"] == 0
    assert summary["ocr_empty_count"] == 1
    assert summary["ocr_disabled_count"] == 0
    assert summary["ocr_failed_count"] == 1


def test_report_sanitizers_reduce_path_and_error_exposure():
    assert _sanitize_report_path(r"C:\Users\Heiko\OneDrive\Dokumente\Dev\Python\Rezepte\rezepte.txt") == "rezepte.txt"
    sanitized = _sanitize_report_error("401 https://graph.microsoft.com/v1.0/me Authorization=Bearer secret-token")
    assert "graph.microsoft.com" not in sanitized
    assert "secret-token" not in sanitized
    assert "[url]" in sanitized
    assert "[redacted]" in sanitized


def test_source_helpers_derive_human_label_and_ocr_requirement():
    recipe = {"source_type": "onenote_page", "media": [{"type": "image"}], "ocr_status": "pending"}
    assert _derive_source_label(recipe) == "OneNote-Notiz mit Medien"
    assert _derive_ocr_required_status(recipe) == "pending"





def test_work_bucket_helper_maps_ocr_and_review_states():
    assert _derive_work_bucket({"ocr_required_status": "pending", "review_status": "needs_review", "review_triggers": ["ocr_required"]}) == "ocr_first"
    assert _derive_work_bucket({"ocr_required_status": "failed", "review_status": "needs_review", "review_triggers": ["ocr_failed"]}) == "ocr_repair"
    assert _derive_work_bucket({"ocr_required_status": "done", "review_status": "needs_review", "review_triggers": ["source_has_media"]}) == "review_after_ocr"
    assert _derive_work_bucket({"ocr_required_status": "not_needed", "review_status": "needs_review", "review_triggers": ["quality_review"]}) == "review_general"

