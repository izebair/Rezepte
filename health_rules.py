from __future__ import annotations

import re
from typing import Any, Dict, List, Literal

HealthLight = Literal["green", "yellow", "red", "unrated"]
HealthCondition = Literal["prostate_cancer", "breast_cancer"]
HealthCertainty = Literal["low", "medium", "high"]

PROCESSED_MEAT_KEYWORDS = ["bacon", "speck", "schinken", "salami", "wurst", "pancetta", "chorizo"]
RED_MEAT_KEYWORDS = ["rind", "steak", "hackfleisch", "beef", "kalb", "lamm"]
ALCOHOL_KEYWORDS = ["wein", "bier", "vodka", "rum", "likoer", "likör", "prosecco", "gin", "whisky", "sekt"]
PROTECTIVE_KEYWORDS = ["hafer", "beeren", "linsen", "bohnen", "brokkoli", "spinat", "tomaten", "gemuese", "gemüse"]
SUGAR_RE = re.compile(r"(\d{2,4})\s*g\s+zucker", re.IGNORECASE)

DISCLAIMER = "Gesundheitshinweise sind unterstuetzende Empfehlungen und keine medizinische Beratung."


def build_health_assessments(recipe: Dict[str, Any]) -> Dict[str, Any]:
    ingredients = [str(item).strip().lower() for item in recipe.get("zutaten", []) if str(item).strip()]
    quality_status = str(recipe.get("quality", {}).get("status") or "")
    uncertainty = str(recipe.get("uncertainty", {}).get("overall") or "low")

    if not ingredients or quality_status == "problematisch" or uncertainty == "high":
        return {
            "assessments": [_unrated("prostate_cancer"), _unrated("breast_cancer")],
            "disclaimer": DISCLAIMER,
        }

    risk_flags = _collect_risk_flags(ingredients)
    protective_hits = _collect_protective_hits(ingredients)

    assessments = [
        _build_condition_assessment("prostate_cancer", risk_flags, protective_hits),
        _build_condition_assessment("breast_cancer", risk_flags, protective_hits),
    ]
    return {"assessments": assessments, "disclaimer": DISCLAIMER}


def _collect_risk_flags(ingredients: List[str]) -> List[str]:
    flags: List[str] = []
    joined = "\n".join(ingredients)
    if any(keyword in item for item in ingredients for keyword in PROCESSED_MEAT_KEYWORDS):
        flags.append("processed_meat")
    if any(keyword in item for item in ingredients for keyword in RED_MEAT_KEYWORDS):
        flags.append("red_meat")
    if any(keyword in item for item in ingredients for keyword in ALCOHOL_KEYWORDS):
        flags.append("alcohol")
    sugar_match = SUGAR_RE.search(joined)
    if sugar_match and int(sugar_match.group(1)) >= 100:
        flags.append("high_sugar")
    return flags


def _collect_protective_hits(ingredients: List[str]) -> List[str]:
    hits: List[str] = []
    for keyword in PROTECTIVE_KEYWORDS:
        if any(keyword in item for item in ingredients):
            hits.append(keyword)
    return hits


def _build_condition_assessment(condition: HealthCondition, risk_flags: List[str], protective_hits: List[str]) -> Dict[str, Any]:
    reasons: List[str] = []
    substitutions: List[str] = []
    light: HealthLight = "unrated"
    certainty: HealthCertainty = "low"

    if "processed_meat" in risk_flags:
        light = "red"
        certainty = "medium"
        reasons.append("Verarbeitetes Fleisch erkannt.")
        substitutions.append("Verarbeitetes Fleisch moeglichst durch frische pflanzliche oder magere Alternativen ersetzen.")
    elif "alcohol" in risk_flags:
        light = "yellow"
        certainty = "medium"
        reasons.append("Alkohol als Zutat erkannt.")
        substitutions.append("Alkoholische Zutaten wenn moeglich reduzieren oder alkoholfrei ersetzen.")
    elif "red_meat" in risk_flags:
        light = "yellow"
        certainty = "medium"
        reasons.append("Rotes Fleisch erkannt.")
        substitutions.append("Rotes Fleisch moeglichst seltener einsetzen oder teilweise ersetzen.")
    elif "high_sugar" in risk_flags:
        light = "yellow"
        certainty = "medium"
        reasons.append("Hohe Zuckermenge erkannt.")
        substitutions.append("Zuckermenge pruefen und wenn moeglich reduzieren.")
    elif protective_hits:
        light = "green"
        certainty = "medium"
        reasons.append("Mehrere eher guenstige Zutaten wie Hafer, Beeren oder Gemuese erkannt.")
    else:
        reasons.append("Keine belastbare gesundheitliche Einschaetzung aus den Zutaten ableitbar.")

    return {
        "condition": condition,
        "light": light,
        "certainty": certainty,
        "reasons": reasons,
        "substitutions": substitutions,
        "requires_review": certainty == "low" or light in {"red", "yellow"},
    }


def _unrated(condition: HealthCondition) -> Dict[str, Any]:
    return {
        "condition": condition,
        "light": "unrated",
        "certainty": "low",
        "reasons": ["Gesundheitliche Bewertung derzeit nicht belastbar moeglich."],
        "substitutions": [],
        "requires_review": True,
    }
