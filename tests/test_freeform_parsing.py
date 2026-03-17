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


FREEFORM_METADATA_SAMPLE = """
Ofengemuese

Fuer 4 Personen
35 Min
leicht

Zutaten
    assert recipe["parser_type"] == "freeform"
- 800 g Kartoffeln
- 2 Zwiebeln
- 1 EL Olivenoel

Anleitung
Ofen auf 180 C vorheizen.
20 Min backen.
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


def test_parse_freeform_recipe_extracts_metadata_without_colons_and_alias_headers():
    recipe = rezept_parsen(FREEFORM_METADATA_SAMPLE)

    assert recipe["titel"] == "Ofengemuese"
    assert recipe["portionen"] == "Fuer 4 Personen"
    assert recipe["zeit"] == "35 Min"
    assert recipe["schwierigkeit"] == "Leicht"
    assert "800 g Kartoffeln" in recipe["zutaten"]
    assert any("vorheizen" in step.lower() for step in recipe["schritte"])
    assert any("backen" in step.lower() for step in recipe["schritte"])
