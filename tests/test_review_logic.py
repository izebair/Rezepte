from review import derive_review_status, derive_review_triggers, derive_uncertainty



def test_review_status_rejected_on_validation_errors():
    recipe = {"uncertainty": {"overall": "low"}}
    status = derive_review_status(recipe, ["Pflichtfeld fehlt: Titel"], [])
    assert status == "rejected"



def test_review_status_needs_review_on_warning_findings():
    recipe = {"uncertainty": {"overall": "medium"}}
    findings = [{"severity": "warning", "requires_review": True}]
    status = derive_review_status(recipe, [], findings)
    assert status == "needs_review"



def test_review_status_approved_when_clean():
    recipe = {"uncertainty": {"overall": "low"}}
    status = derive_review_status(recipe, [], [])
    assert status == "approved"



def test_uncertainty_high_when_errors_exist():
    uncertainty = derive_uncertainty({}, ["Fehler"], [])
    assert uncertainty["overall"] == "high"
    assert uncertainty["reasons"]



def test_review_triggers_include_category_unmapped_for_taxonomy_notes():
    recipe = {
        "titel": "Test",
        "hauptkategorie": "Hauptgericht",
        "zutaten": ["1 Tomate"],
        "schritte": ["Schneiden"],
        "uncertainty": {"overall": "medium", "reasons": ["Unterkategorie nicht in kontrollierter Liste"]},
    }
    triggers = derive_review_triggers(recipe, [], [])
    assert "category_unmapped" in triggers



def test_review_triggers_ignore_unrelated_uncertainty_reasons():
    recipe = {
        "titel": "Test",
        "hauptkategorie": "Hauptgericht",
        "zutaten": ["1 Tomate"],
        "schritte": ["Schneiden"],
        "uncertainty": {"overall": "medium", "reasons": ["Warnungen vorhanden"]},
    }
    triggers = derive_review_triggers(recipe, [], [])
    assert "category_unmapped" not in triggers



def test_review_triggers_include_ocr_required_for_pending_ocr_items():
    recipe = {
        "titel": "Scan",
        "hauptkategorie": "Dessert",
        "zutaten": ["1 Ei"],
        "schritte": ["Ruehren"],
        "source_type": "ocr_file",
        "media": [{"type": "image"}],
        "ocr_required_status": "pending",
        "ocr_status": "pending",
    }
    triggers = derive_review_triggers(recipe, [], [])
    assert "ocr_required" in triggers
    assert "ocr_empty" in triggers



def test_review_triggers_include_source_has_media_for_onenote_pages():
    recipe = {
        "titel": "OneNote",
        "hauptkategorie": "Dessert",
        "zutaten": ["1 Ei"],
        "schritte": ["Ruehren"],
        "source_type": "onenote_page",
        "media": [{"type": "image"}],
        "ocr_required_status": "done",
        "ocr_status": "done",
        "ocr_text": "1 Ei",
    }
    triggers = derive_review_triggers(recipe, [], [])
    assert "source_has_media" in triggers
    assert "ocr_required" not in triggers
