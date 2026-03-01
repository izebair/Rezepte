from pathlib import Path

from onenote_import import rezept_parsen, rezepte_aufteilen


ROOT = Path(__file__).resolve().parent.parent
SAMPLE = (ROOT / "rezepte_mvp_beispiel.txt").read_text(encoding="utf-8")


def test_delimiter_based_splitting():
    parts = rezepte_aufteilen(SAMPLE)
    assert len(parts) == 2
    r1 = rezept_parsen(parts[0])
    r2 = rezept_parsen(parts[1])
    assert r1["titel"] == "Schokoladenkuchen"
    assert r2["titel"] == "Pfannkuchen"
