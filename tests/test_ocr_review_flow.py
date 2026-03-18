from quality_rules import build_quality_findings
from review import derive_review_status, derive_uncertainty


def test_quality_findings_mark_ocr_pending_when_media_exists_without_ocr_text():
    recipe = {
        "titel": "Tomatensuppe",
        "hauptkategorie": "Vorspeise",
        "kategorie": "Suppe",
        "zutaten": ["500 ml Wasser"],
        "schritte": ["Kochen"],
        "zeit": "20 min",
        "media": [{"media_id": "pdf-1", "type": "pdf", "ref": "x", "ocr_status": "pending"}],
        "ocr_text": "",
    }
    findings = build_quality_findings(recipe)
    assert any(f["id"] == "OCR_PENDING" for f in findings)


def test_quality_findings_mark_ocr_failed_when_media_processing_failed():
    recipe = {
        "titel": "Tomatensuppe",
        "hauptkategorie": "Vorspeise",
        "kategorie": "Suppe",
        "zutaten": ["500 ml Wasser"],
        "schritte": ["Kochen"],
        "zeit": "20 min",
        "media": [{"media_id": "pdf-1", "type": "pdf", "ref": "x", "ocr_status": "failed"}],
        "ocr_text": "",
    }
    findings = build_quality_findings(recipe)
    assert any(f["id"] == "OCR_FAILED" for f in findings)


def test_quality_findings_mark_ocr_empty_and_disabled_states():
    empty_recipe = {
        "titel": "Tomatensuppe",
        "hauptkategorie": "Vorspeise",
        "kategorie": "Suppe",
        "zutaten": ["500 ml Wasser"],
        "schritte": ["Kochen"],
        "zeit": "20 min",
        "media": [{"media_id": "pdf-1", "type": "pdf", "ref": "x", "ocr_status": "empty"}],
        "ocr_text": "",
    }
    disabled_recipe = {
        "titel": "Tomatensuppe",
        "hauptkategorie": "Vorspeise",
        "kategorie": "Suppe",
        "zutaten": ["500 ml Wasser"],
        "schritte": ["Kochen"],
        "zeit": "20 min",
        "media": [{"media_id": "pdf-1", "type": "pdf", "ref": "x", "ocr_status": "disabled"}],
        "ocr_text": "",
    }
    empty_findings = build_quality_findings(empty_recipe)
    disabled_findings = build_quality_findings(disabled_recipe)
    assert any(f["id"] == "OCR_EMPTY" for f in empty_findings)
    assert any(f["id"] == "OCR_DISABLED" for f in disabled_findings)


def test_review_status_needs_review_when_ocr_text_exists():
    recipe = {"ocr_text": "Zusatz aus OCR", "uncertainty": {"overall": "medium"}}
    status = derive_review_status(recipe, [], [])
    assert status == "needs_review"


def test_uncertainty_is_raised_for_ocr_text():
    uncertainty = derive_uncertainty({"ocr_text": "OCR Inhalt"}, [], [])
    assert uncertainty["overall"] in {"medium", "high"}
    assert any("OCR" in reason for reason in uncertainty["reasons"])


def test_health_assessment_with_low_certainty_requires_review():
    recipe = {
        "health": {
            "assessments": [
                {"condition": "prostate_cancer", "light": "unrated", "certainty": "low", "requires_review": True}
            ]
        },
        "uncertainty": {"overall": "medium"},
    }
    status = derive_review_status(recipe, [], [])
    uncertainty = derive_uncertainty(recipe, [], [])
    assert status == "needs_review"
    assert uncertainty["overall"] in {"medium", "high"}
    assert any("Gesundheit" in reason for reason in uncertainty["reasons"])

