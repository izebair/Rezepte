"""Analyse-Modul für Rezeptqualität und Gesundheits-Hinweise.

Hinweis: Die Heuristiken sind regelbasiert und liefern nur Hinweise, keine medizinische Beratung.
"""

from __future__ import annotations

import re
from typing import Any, Dict, List


_MEASURE_RE = re.compile(r"\b\d+[\d.,]*\s*(g|kg|ml|l|tl|el|stk|stück|prise|tasse|cup)\b", re.IGNORECASE)

_RISKY_INGREDIENTS = {
    "processed_meat": ["pancetta", "speck", "salami", "wurst", "schinken", "bacon"],
    "red_meat": ["rind", "schwein", "hackfleisch"],
    "high_sugar": ["zucker", "sirup"],
}

_PROTECTIVE_INGREDIENTS = [
    "brokkoli", "beeren", "hafer", "linsen", "hülsenfrüchte", "spinat", "kurkuma", "nüsse", "leinsamen",
]


def _contains_any(text: str, needles: List[str]) -> bool:
    text_l = text.lower()
    return any(n in text_l for n in needles)


def analyze_recipe(recipe: Dict[str, Any]) -> Dict[str, Any]:
    title = str(recipe.get("titel") or "").strip()
    category = str(recipe.get("kategorie") or "").strip()
    ingredients = [str(x).strip() for x in recipe.get("zutaten") or [] if str(x).strip()]
    steps = [str(x).strip() for x in recipe.get("schritte") or [] if str(x).strip()]

    issues: List[str] = []
    warnings: List[str] = []
    suggestions: List[str] = []

    if not title or title.lower() == "unbekannt":
        issues.append("Titel fehlt oder ist unklar")
    if not category:
        warnings.append("Kategorie fehlt")
    if not ingredients:
        issues.append("Zutaten fehlen")
    if not steps:
        issues.append("Zubereitungsschritte fehlen")

    # Mengenangaben prüfen
    ingredients_without_measure = [i for i in ingredients if not _MEASURE_RE.search(i)]
    if ingredients and len(ingredients_without_measure) > max(2, len(ingredients) // 2):
        warnings.append("Viele Zutaten ohne klare Mengenangaben")

    joined_ingredients = " | ".join(ingredients).lower()

    risk_flags: List[str] = []
    for label, needle_words in _RISKY_INGREDIENTS.items():
        if _contains_any(joined_ingredients, needle_words):
            risk_flags.append(label)

    protective_count = sum(1 for w in _PROTECTIVE_INGREDIENTS if w in joined_ingredients)
    if protective_count >= 2:
        suggestions.append("Rezept enthält mehrere nährstoffreiche Komponenten")
    else:
        suggestions.append("Optional mehr ballaststoffreiche Zutaten/Kräuter ergänzen")

    if "processed_meat" in risk_flags:
        warnings.append("Verarbeitetes Fleisch erkannt – ggf. durch pflanzliche Alternative ersetzen")
    if "high_sugar" in risk_flags:
        warnings.append("Zuckeranteil prüfen und ggf. reduzieren")

    prostata = "geeignet"
    brust = "geeignet"
    if "processed_meat" in risk_flags or "red_meat" in risk_flags:
        prostata = "bedingt"
        brust = "bedingt"

    score = 100
    score -= 20 * len(issues)
    score -= 7 * len(warnings)
    if protective_count >= 2:
        score += 5
    score = max(0, min(100, score))

    return {
        "titel": title or "Unbekannt",
        "quality_score": score,
        "issues": issues,
        "warnings": warnings,
        "suggestions": suggestions,
        "health": {
            "prostata_krebs": prostata,
            "brustkrebs": brust,
            "risk_flags": risk_flags,
            "protective_hits": protective_count,
        },
        "medical_disclaimer": "Automatisch erzeugte Hinweise ersetzen keine medizinische Beratung.",
    }


def analyze_recipes(recipes: List[Dict[str, Any]]) -> Dict[str, Any]:
    items = [analyze_recipe(r) for r in recipes]
    avg_score = round(sum(i["quality_score"] for i in items) / len(items), 1) if items else 0.0
    total_issues = sum(len(i["issues"]) for i in items)
    total_warnings = sum(len(i["warnings"]) for i in items)

    return {
        "summary": {
            "count": len(items),
            "average_quality_score": avg_score,
            "total_issues": total_issues,
            "total_warnings": total_warnings,
        },
        "items": items,
    }
