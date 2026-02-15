"""Analyse-Modul für Rezeptqualität, Ähnlichkeiten und Import-Entscheidung.

Hinweis: Die Heuristiken sind regelbasiert und liefern nur Hinweise, keine medizinische Beratung.
"""

from __future__ import annotations

import re
from typing import Any, Dict, List, Set

_MEASURE_RE = re.compile(r"\b\d+[\d.,]*\s*(g|kg|ml|l|tl|el|stk|stück|prise|tasse|cup)\b", re.IGNORECASE)
_WORD_RE = re.compile(r"[a-zA-ZäöüÄÖÜß]+")

_RISKY_INGREDIENTS = {
    "processed_meat": ["pancetta", "speck", "salami", "wurst", "schinken", "bacon"],
    "red_meat": ["rind", "schwein", "hackfleisch"],
    "high_sugar": ["zucker", "sirup"],
}

_PROTECTIVE_INGREDIENTS = [
    "brokkoli", "beeren", "hafer", "linsen", "hülsenfrüchte", "spinat", "kurkuma", "nüsse", "leinsamen",
]

_TOKEN_SYNONYMS = {
    "spaghetti": "nudeln",
    "pasta": "nudeln",
    "napoli": "tomatensosse",
    "tomatensoße": "tomatensosse",
    "tomatensauce": "tomatensosse",
    "hafermilch": "pflanzenmilch",
    "mandelmilch": "pflanzenmilch",
    "milch": "milchbasis",
    "butter": "fett",
    "ghee": "fett",
    "knoblauch": "aroma",
    "kraeuter": "aroma",
    "kräuter": "aroma",
}

_STOPWORDS = {"mit", "und", "der", "die", "das", "ein", "eine", "zu", "für", "im", "in"}


def _contains_any(text: str, needles: List[str]) -> bool:
    text_l = text.lower()
    return any(n in text_l for n in needles)


def _normalize_word(token: str) -> str:
    t = token.lower().strip()
    if t in _STOPWORDS:
        return ""
    return _TOKEN_SYNONYMS.get(t, t)


def _tokenize(text: str) -> Set[str]:
    tokens: Set[str] = set()
    for word in _WORD_RE.findall(text.lower()):
        normalized = _normalize_word(word)
        if normalized:
            tokens.add(normalized)
    return tokens


def _recipe_similarity(recipe_a: Dict[str, Any], recipe_b: Dict[str, Any]) -> float:
    text_a = f"{recipe_a.get('titel','')} {' '.join(recipe_a.get('zutaten', []) or [])}"
    text_b = f"{recipe_b.get('titel','')} {' '.join(recipe_b.get('zutaten', []) or [])}"
    set_a = _tokenize(text_a)
    set_b = _tokenize(text_b)
    if not set_a or not set_b:
        return 0.0
    return len(set_a & set_b) / len(set_a | set_b)


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


def analyze_recipes(recipes: List[Dict[str, Any]], similarity_threshold: float = 0.45) -> Dict[str, Any]:
    items = [analyze_recipe(r) for r in recipes]
    avg_score = round(sum(i["quality_score"] for i in items) / len(items), 1) if items else 0.0
    total_issues = sum(len(i["issues"]) for i in items)
    total_warnings = sum(len(i["warnings"]) for i in items)

    similar_candidates: List[Dict[str, Any]] = []
    for i in range(len(recipes)):
        for j in range(i + 1, len(recipes)):
            sim = _recipe_similarity(recipes[i], recipes[j])
            if sim >= similarity_threshold:
                similar_candidates.append(
                    {
                        "index_a": i,
                        "titel_a": items[i]["titel"],
                        "index_b": j,
                        "titel_b": items[j]["titel"],
                        "similarity": round(sim, 3),
                    }
                )

    return {
        "summary": {
            "count": len(items),
            "average_quality_score": avg_score,
            "total_issues": total_issues,
            "total_warnings": total_warnings,
            "similar_candidates": len(similar_candidates),
        },
        "similarity_threshold": similarity_threshold,
        "similar_candidates": similar_candidates,
        "items": items,
    }
