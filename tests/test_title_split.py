import pytest
from onenote_import import rezepte_aufteilen, rezept_parsen

SAMPLE = """
Titel: Chili con Carne

Kategorie:
Mexikanisch

Zutaten:
- 500g Hackfleisch
- 1 Dose Bohnen

Zubereitung:
1. Anbraten
2. Kochen

Titel: Kaiserschmarrn

Zutaten:
- 2 Eier
- 150g Mehl

Zubereitung:
- Verrühren
- Ausbacken
"""

def test_title_based_splitting():
    parts = rezepte_aufteilen(SAMPLE)
    assert len(parts) == 2
    r1 = rezept_parsen(parts[0])
    r2 = rezept_parsen(parts[1])
    assert r1["titel"].lower().startswith("chili con carne")
    assert r2["titel"].lower().startswith("kaiserschmarrn")
