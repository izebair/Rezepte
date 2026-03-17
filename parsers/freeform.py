from __future__ import annotations

import re
from typing import Any, Dict, List

LIST_PREFIX_RE = re.compile(r"^\s*(?:[-*]|\d+[.)])\s+")
INGREDIENT_HINT_RE = re.compile(
    r"\b(g|kg|ml|l|el|tl|prise|prisen|eier|ei|mehl|zucker|milch|butter|salz|pfeffer|tomaten|zwiebel)\b",
    re.IGNORECASE,
)
STEP_HINT_RE = re.compile(
    r"\b(mischen|mixen|ruehren|rühren|backen|braten|kochen|geben|hinzufuegen|hinzufügen|servieren|heizen|erhitzen|schneiden)\b",
    re.IGNORECASE,
)


def _clean_list_item(line: str) -> str:
    return LIST_PREFIX_RE.sub("", line).strip()


def _looks_like_step(line: str) -> bool:
    cleaned = _clean_list_item(line)
    return bool(STEP_HINT_RE.search(cleaned))


def _looks_like_ingredient(line: str) -> bool:
    cleaned = _clean_list_item(line)
    if cleaned.endswith(".") and _looks_like_step(cleaned):
        return False
    return bool(re.search(r"\d", cleaned) or INGREDIENT_HINT_RE.search(cleaned))


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

        if lower.startswith("zeit:"):
            recipe["zeit"] = cleaned.split(":", 1)[1].strip()
            continue
        if lower.startswith("portionen:"):
            recipe["portionen"] = cleaned.split(":", 1)[1].strip()
            continue
        if lower.startswith("schwierigkeit:"):
            recipe["schwierigkeit"] = cleaned.split(":", 1)[1].strip()
            continue

        if lower in {"zutaten", "zutaten:"}:
            current_section = "ingredients"
            continue
        if lower in {"zubereitung", "zubereitung:"}:
            current_section = "steps"
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
