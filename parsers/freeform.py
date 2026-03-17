from __future__ import annotations

import re
from typing import Any, Dict, List

LIST_PREFIX_RE = re.compile(r"^\s*(?:[-*]|\d+[.)])\s+")
INGREDIENT_HINT_RE = re.compile(
    r"\b(g|kg|mg|ml|l|el|tl|prise|prisen|eier|ei|mehl|zucker|milch|butter|salz|pfeffer|tomaten|zwiebel|zwiebeln|knoblauch|zehe|zehen|kartoffeln?|nudeln?|reis|wasser|oel|öl|olivenoel|olivenöl|sahne|quark|kaese|käse)\b",
    re.IGNORECASE,
)
STEP_HINT_RE = re.compile(
    r"\b(mischen|mixen|ruehren|rühren|backen|braten|kochen|geben|hinzufuegen|hinzufügen|servieren|heizen|erhitzen|schneiden|vorheizen|anbraten|kocheln|verruehren|verrühren|vermengen)\b",
    re.IGNORECASE,
)
TIME_HINT_RE = re.compile(r"\b(?:ca\.?\s*)?\d{1,3}\s*(?:min(?:uten)?|std\.?|stunden?)\b", re.IGNORECASE)
SERVINGS_HINT_RE = re.compile(r"\b(?:fuer|für)?\s*\d{1,2}\s*(?:personen|portionen|port\.)\b", re.IGNORECASE)
DIFFICULTY_HINT_RE = re.compile(r"\b(einfach|leicht|mittel|schwer)\b", re.IGNORECASE)
INGREDIENT_AMOUNT_RE = re.compile(r"^(?:ca\.?\s*)?(?:\d+[\./-]?\d*|\d+\s*/\s*\d+)\s*(?:g|kg|mg|ml|l|el|tl|prise|prisen|stk\.?|stueck|stück|dose|dosen|bund|zehe|zehen)?\b", re.IGNORECASE)
HEADER_ALIASES = {
    "zutaten": "ingredients",
    "zutaten:": "ingredients",
    "zubereitung": "steps",
    "zubereitung:": "steps",
    "anleitung": "steps",
    "anleitung:": "steps",
    "zubereiten": "steps",
    "zubereiten:": "steps",
}


def _clean_list_item(line: str) -> str:
    return LIST_PREFIX_RE.sub("", line).strip()


def _looks_like_step(line: str) -> bool:
    cleaned = _clean_list_item(line)
    return bool(STEP_HINT_RE.search(cleaned))


def _looks_like_ingredient(line: str) -> bool:
    cleaned = _clean_list_item(line)
    if cleaned.endswith(".") and _looks_like_step(cleaned):
        return False
    return bool(INGREDIENT_AMOUNT_RE.search(cleaned) or INGREDIENT_HINT_RE.search(cleaned))


def _extract_metadata(recipe: Dict[str, Any], cleaned: str) -> bool:
    lower = cleaned.lower()

    key_value_patterns = {
        "zeit": ("zeit:", "dauer:", "backzeit:", "kochzeit:"),
        "portionen": ("portionen:", "portionen ", "serviert "),
        "schwierigkeit": ("schwierigkeit:", "schwierig:", "level:"),
    }
    for field, prefixes in key_value_patterns.items():
        for prefix in prefixes:
            if lower.startswith(prefix):
                value = cleaned.split(":", 1)[1].strip() if ":" in cleaned else cleaned[len(prefix):].strip()
                recipe[field] = value
                return True

    if not recipe.get("portionen") and SERVINGS_HINT_RE.fullmatch(lower):
        recipe["portionen"] = cleaned
        return True

    if not recipe.get("zeit") and TIME_HINT_RE.fullmatch(lower):
        recipe["zeit"] = cleaned
        return True

    if not recipe.get("schwierigkeit") and DIFFICULTY_HINT_RE.fullmatch(lower):
        recipe["schwierigkeit"] = cleaned.capitalize()
        return True

    return False


def parse_freeform_recipe(block: str) -> Dict[str, Any]:
    lines = [line.strip() for line in block.splitlines() if line.strip()]
    recipe: Dict[str, Any] = {
        "titel": lines[0] if lines else "",
        "gruppe": "",
        "kategorie": "",
        "portionen": "",
        "zeit": "",
        "schwierigkeit": "",
        "zutaten": [],
        "schritte": [],
        "raw": block,
    }

    if not lines:
        return recipe

    ingredients: List[str] = []
    steps: List[str] = []
    current_section = "ingredients"

    for line in lines[1:]:
        cleaned = _clean_list_item(line)
        lower = cleaned.lower()

        if _extract_metadata(recipe, cleaned):
            continue

        section = HEADER_ALIASES.get(lower)
        if section:
            current_section = section
            continue

        if current_section == "ingredients" and _looks_like_step(cleaned) and not _looks_like_ingredient(cleaned):
            current_section = "steps"

        if current_section == "ingredients":
            if _looks_like_ingredient(cleaned) or not ingredients:
                ingredients.append(cleaned)
                continue
            current_section = "steps"

        steps.append(cleaned)

    recipe["zutaten"] = ingredients
    recipe["schritte"] = steps
    return recipe
