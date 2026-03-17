from onenote_import import _build_report_item
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
