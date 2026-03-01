from onenote_import import FINGERPRINT_PREFIX, rezept_fingerprint, rezept_zu_html


def test_fingerprint_is_stable_for_same_recipe():
    recipe = {
        "titel": "Tomatensuppe",
        "gruppe": "Suppen",
        "kategorie": "Klassiker",
        "zutaten": ["1 kg Tomaten", "1 Zwiebel"],
        "schritte": ["Kochen", "Puerieren"],
    }
    fp1 = rezept_fingerprint(recipe)
    fp2 = rezept_fingerprint(recipe)
    assert fp1 == fp2
    assert len(fp1) == 64


def test_html_contains_hidden_fingerprint_marker():
    recipe = {
        "titel": "Tomatensuppe",
        "gruppe": "Suppen",
        "kategorie": "Klassiker",
        "zutaten": ["1 kg Tomaten"],
        "schritte": ["Kochen"],
    }
    fp = rezept_fingerprint(recipe)
    html = rezept_zu_html(recipe, fingerprint=fp)
    assert f"{FINGERPRINT_PREFIX}:{fp}" in html
    assert "display:none" in html
