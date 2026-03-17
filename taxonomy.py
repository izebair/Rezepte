from __future__ import annotations

from typing import Dict, List, Tuple

MAIN_CATEGORIES: List[str] = [
    "Dessert",
    "Getraenke",
    "Hauptgericht",
    "Snack",
    "Vorspeise",
]

SUBCATEGORY_MAP: Dict[str, List[str]] = {
    "Dessert": ["Allgemein", "Kuchen & Gebaeck", "Cremes & Pudding", "Eis", "Frucht"],
    "Getraenke": ["Allgemein", "Kaffee & Tee", "Cocktails & Mocktails", "Smoothies & Saefte"],
    "Hauptgericht": ["Allgemein", "Pasta", "Fleisch", "Fisch", "Vegetarisch", "Auflaeufe & Eintoepfe", "International"],
    "Snack": ["Allgemein", "Herzhaft", "Suess", "Dips & Kleinigkeiten"],
    "Vorspeise": ["Allgemein", "Salat", "Suppe", "Antipasti & Kleinigkeiten"],
}

DEFAULT_SUBCATEGORY_BY_MAIN: Dict[str, str] = {
    main_category: "Allgemein" for main_category in MAIN_CATEGORIES
}

_GROUP_TO_MAIN = {
    "backen": "Dessert",
    "dessert": "Dessert",
    "getraenke": "Getraenke",
    "hauptgerichte": "Hauptgericht",
    "hauptgericht": "Hauptgericht",
    "snack": "Snack",
    "snacks": "Snack",
    "vorspeise": "Vorspeise",
    "vorspeisen": "Vorspeise",
}

_SUBCATEGORY_ALIASES = {
    "kuchen": ("Dessert", "Kuchen & Gebaeck"),
    "kaffee": ("Getraenke", "Kaffee & Tee"),
    "tee": ("Getraenke", "Kaffee & Tee"),
    "cocktails": ("Getraenke", "Cocktails & Mocktails"),
    "mocktails": ("Getraenke", "Cocktails & Mocktails"),
    "pasta": ("Hauptgericht", "Pasta"),
    "fleisch": ("Hauptgericht", "Fleisch"),
    "fisch": ("Hauptgericht", "Fisch"),
    "vegetarisch": ("Hauptgericht", "Vegetarisch"),
    "auflauf": ("Hauptgericht", "Auflaeufe & Eintoepfe"),
    "auflaeufe": ("Hauptgericht", "Auflaeufe & Eintoepfe"),
    "eintoepfe": ("Hauptgericht", "Auflaeufe & Eintoepfe"),
    "dip": ("Snack", "Dips & Kleinigkeiten"),
    "dips": ("Snack", "Dips & Kleinigkeiten"),
    "salat": ("Vorspeise", "Salat"),
    "suppe": ("Vorspeise", "Suppe"),
}


def _normalize(value: str | None) -> str:
    return (value or "").strip().lower()


def resolve_categories(group: str | None, category: str | None) -> tuple[str, str, list[str]]:
    notes: list[str] = []
    normalized_group = _normalize(group)
    normalized_category = _normalize(category)

    mapped_main = _GROUP_TO_MAIN.get(normalized_group, "")
    mapped_sub = ""

    if normalized_category in _SUBCATEGORY_ALIASES:
        alias_main, alias_sub = _SUBCATEGORY_ALIASES[normalized_category]
        mapped_sub = alias_sub
        if mapped_main and mapped_main != alias_main:
            notes.append("Kategorie passt nicht eindeutig zur Hauptkategorie")
        mapped_main = mapped_main or alias_main
    elif category:
        for candidate_main, subcategories in SUBCATEGORY_MAP.items():
            for subcategory in subcategories:
                if _normalize(subcategory) == normalized_category:
                    mapped_main = mapped_main or candidate_main
                    mapped_sub = subcategory
                    break
            if mapped_sub:
                break

    if not mapped_sub and category:
        notes.append("Unterkategorie nicht in kontrollierter Liste")

    if mapped_main and not mapped_sub:
        mapped_sub = DEFAULT_SUBCATEGORY_BY_MAIN.get(mapped_main, "Allgemein")

    if mapped_main and mapped_sub and mapped_sub not in SUBCATEGORY_MAP.get(mapped_main, []):
        notes.append("Unterkategorie gehoert nicht zur Hauptkategorie")

    return mapped_main, mapped_sub, notes


def resolve_destination_categories(group: str | None, category: str | None) -> Tuple[str, str, List[str]]:
    main_category, subcategory, notes = resolve_categories(group, category)
    if main_category and not subcategory:
        subcategory = DEFAULT_SUBCATEGORY_BY_MAIN.get(main_category, "Allgemein")
    return main_category, subcategory, notes


def is_valid_main_category(value: str | None) -> bool:
    return value in MAIN_CATEGORIES


def is_valid_subcategory(main_category: str | None, subcategory: str | None) -> bool:
    if not main_category or not subcategory:
        return False
    return subcategory in SUBCATEGORY_MAP.get(main_category, [])
