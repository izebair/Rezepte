import pytest
from onenote_import import rezepte_aufteilen, rezept_parsen

SAMPLE = """
Schokoladenkuchen

Zutaten:
- 200g Mehl
- 100g Zucker
- 2 Eier

Zubereitung:
1. Zutaten mischen.
2. 30 Minuten backen.


Pfannkuchen

Zutaten:
* 250ml Milch
* 2 Eier
* 150g Mehl

Zubereitung:
- Mischen
- In der Pfanne braten
"""

def test_split_recipes():
    parts = rezepte_aufteilen(SAMPLE)
    assert len(parts) == 2

def test_parse_first_recipe():
    parts = rezepte_aufteilen(SAMPLE)
    r = rezept_parsen(parts[0])
    assert r["titel"].lower().startswith("schokoladenkuchen")
    assert "200g Mehl" in r["zutaten"]
    assert any("backen" in s.lower() for s in r["schritte"])

def test_parse_second_recipe():
    parts = rezepte_aufteilen(SAMPLE)
    r = rezept_parsen(parts[1])
    assert r["titel"].lower().startswith("pfannkuchen")
    assert any("250ml Milch" in it for it in r["zutaten"])
    assert any("braten" in s.lower() or "mischen" in s.lower() for s in r["schritte"])