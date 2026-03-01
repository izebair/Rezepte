from onenote_import import rezept_validieren


def test_validation_accepts_required_fields():
    recipe = {
        "titel": "Rotes Curry",
        "gruppe": "Hauptgerichte",
        "kategorie": "Pasta",
        "zutaten": ["200 g Nudeln"],
        "schritte": ["Kochen"],
    }
    assert rezept_validieren(recipe) == []


def test_validation_rejects_missing_required_fields():
    recipe = {
        "titel": "Ohne Bereich",
        "gruppe": "",
        "kategorie": "",
        "zutaten": [],
        "schritte": [],
    }
    errors = rezept_validieren(recipe)
    assert "Pflichtfeld fehlt: Gruppe" in errors
    assert "Pflichtfeld fehlt: Kategorie" in errors
    assert "Pflichtfeld fehlt: Zutaten" in errors
    assert "Pflichtfeld fehlt: Zubereitung" in errors
