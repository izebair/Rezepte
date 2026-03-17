from quality_rules import build_quality_findings, build_quality_suggestions, summarize_quality


def test_quality_findings_detect_missing_unit_and_category_issue():
    recipe = {
        "titel": "Suppe",
        "hauptkategorie": "",
        "kategorie": "Suppe",
        "zutaten": ["2 Karotten", "500 ml Wasser"],
        "schritte": ["Alles in den Topf geben"],
        "zeit": "ca. 25 min",
    }

    findings = build_quality_findings(recipe)
    ids = {finding["id"] for finding in findings}

    assert "CATEGORY_MAIN_INVALID" in ids
    assert "UNIT_MISSING" in ids
    assert summarize_quality(findings) == "unsicher"


def test_quality_suggestions_include_missing_time_and_optional_herbs_hint():
    recipe = {
        "titel": "Pasta",
        "hauptkategorie": "Hauptgericht",
        "kategorie": "Pasta",
        "zutaten": ["200 g Nudeln", "2 Tomaten"],
        "schritte": ["Nudeln kochen", "Tomaten schneiden"],
        "zeit": "",
    }

    findings = build_quality_findings(recipe)
    suggestions = build_quality_suggestions(recipe, findings)

    assert any("Zeitangabe" in suggestion for suggestion in suggestions)
    assert any("Kraeuter" in suggestion for suggestion in suggestions)
