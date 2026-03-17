from pathlib import Path

from onenote_import import rezept_parsen, rezepte_aufteilen, _parse_and_validate_blocks


ROOT = Path(__file__).resolve().parent.parent
SAMPLE = (ROOT / "rezepte_mvp_beispiel.txt").read_text(encoding="utf-8")


def test_split_recipes_by_delimiter():
    parts = rezepte_aufteilen(SAMPLE)
    assert len(parts) == 2


def test_parse_recipe_fields_and_lists():
    parts = rezepte_aufteilen(SAMPLE)
    recipe = rezept_parsen(parts[0])

    assert recipe["titel"] == "Schokoladenkuchen"
    assert recipe["gruppe"] == "Backen"
    assert recipe["kategorie"] == "Kuchen"
    assert recipe["portionen"] == "8"
    assert recipe["zeit"] == "45 min"
    assert recipe["schwierigkeit"] == "Einfach"
    assert recipe["parser_type"] == "structured"
    assert "200 g Mehl" in recipe["zutaten"]
    assert any("backen" in step.lower() for step in recipe["schritte"])


def test_file_text_source_type_is_applied_for_plain_blocks():
    parts = rezepte_aufteilen(SAMPLE)
    valid, invalid = _parse_and_validate_blocks(parts)
    assert not invalid
    assert valid[0]["source_type"] == "file_text"


def test_mvp_example_file_exists():
    assert (ROOT / "rezepte_mvp_beispiel.txt").is_file()
