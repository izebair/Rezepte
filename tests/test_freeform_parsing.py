from onenote_import import rezept_parsen


FREEFORM_SAMPLE = """
Tomatensuppe

2 Tomaten
500 ml Wasser
1 Prise Salz

Tomaten schneiden.
Alles im Topf 20 Minuten kochen.
Danach servieren.
"""


def test_parse_freeform_recipe_extracts_title_ingredients_and_steps():
    recipe = rezept_parsen(FREEFORM_SAMPLE)

    assert recipe["titel"] == "Tomatensuppe"
    assert recipe["zutaten"][0] == "2 Tomaten"
    assert "500 ml Wasser" in recipe["zutaten"]
    assert any("kochen" in step.lower() for step in recipe["schritte"])
    assert recipe["hauptkategorie"] == ""
    assert recipe["review"]["status"] == "needs_review"
