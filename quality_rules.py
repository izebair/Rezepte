from __future__ import annotations

import re
from typing import Any, Dict, List, Literal

from taxonomy import is_valid_main_category, is_valid_subcategory

UNIT_RE = re.compile(r"\b(g|kg|ml|l|el|tl|prise|stueck|min)\b", re.IGNORECASE)
NUMBER_RE = re.compile(r"\d")
TIME_RE = re.compile(r"\b(\d{1,3})\s*(min|stunden|std)\b", re.IGNORECASE)
TEMP_RE = re.compile(r"\b(\d{2,3})\s*[° ]?c\b", re.IGNORECASE)


def build_quality_findings(recipe: Dict[str, Any]) -> List[Dict[str, Any]]:
    findings: List[Dict[str, Any]] = []

    title = str(recipe.get("titel") or "").strip()
    main_category = str(recipe.get("hauptkategorie") or "").strip()
    sub_category = str(recipe.get("kategorie") or "").strip()
    ingredients = [str(item).strip() for item in recipe.get("zutaten", []) if str(item).strip()]
    steps = [str(item).strip() for item in recipe.get("schritte", []) if str(item).strip()]
    time_text = str(recipe.get("zeit") or "").strip()
    media = recipe.get("media", []) or []
    ocr_text = str(recipe.get("ocr_text") or "").strip()

    if not is_valid_main_category(main_category):
        findings.append(_finding("CATEGORY_MAIN_INVALID", "taxonomy", "warning", "medium", "Hauptkategorie ist nicht gesetzt oder nicht erlaubt.", requires_review=True))
    if sub_category and main_category and not is_valid_subcategory(main_category, sub_category):
        findings.append(_finding("CATEGORY_SUB_INVALID", "taxonomy", "warning", "medium", "Unterkategorie passt nicht zur Hauptkategorie.", requires_review=True))
    if not title:
        findings.append(_finding("TITLE_MISSING", "ingredients", "error", "high", "Titel fehlt.", requires_review=True))
    if not ingredients:
        findings.append(_finding("INGREDIENTS_MISSING", "ingredients", "error", "high", "Zutaten fehlen.", requires_review=True))
    if not steps:
        findings.append(_finding("STEPS_MISSING", "steps", "error", "high", "Zubereitungsschritte fehlen.", requires_review=True))

    for ingredient in ingredients:
        if NUMBER_RE.search(ingredient) and not UNIT_RE.search(ingredient):
            findings.append(_finding("UNIT_MISSING", "ingredients", "warning", "medium", f"Einheit fehlt oder ist uneinheitlich: {ingredient}", evidence=ingredient, requires_review=True))
            break

    if not any(_looks_like_action(step) for step in steps):
        findings.append(_finding("STEP_ACTION_WEAK", "steps", "warning", "medium", "Schritte wirken wenig handlungsorientiert.", requires_review=True))

    if time_text and not TIME_RE.search(time_text):
        findings.append(_finding("TIME_FORMAT_UNCLEAR", "times_temps", "warning", "medium", "Zeitangabe ist nicht klar normalisierbar.", evidence=time_text, requires_review=True))

    detected_temps = sum(1 for step in steps if TEMP_RE.search(step))
    if detected_temps and not any("ofen" in step.lower() or "back" in step.lower() for step in steps):
        findings.append(_finding("TEMP_WITHOUT_BAKING_CONTEXT", "times_temps", "warning", "low", "Temperatur gefunden, aber kein klarer Back-/Ofen-Kontext.", requires_review=True))

    if media and not ocr_text:
        findings.append(_finding("OCR_PENDING", "media", "warning", "medium", "Medien vorhanden, aber noch kein OCR-Text verfuegbar.", requires_review=True))

    if media and any(str(item.get("ocr_status") or "") == "failed" for item in media if isinstance(item, dict)):
        findings.append(_finding("OCR_FAILED", "media", "warning", "high", "Mindestens ein Medium konnte nicht per OCR verarbeitet werden.", requires_review=True))

    return findings


QualityStatus = Literal['ok', 'unsicher', 'problematisch']

def summarize_quality(findings: List[Dict[str, Any]]) -> QualityStatus:
    severities = {finding["severity"] for finding in findings}
    if "error" in severities:
        return "problematisch"
    if "warning" in severities:
        return "unsicher"
    return "ok"


def build_quality_suggestions(recipe: Dict[str, Any], findings: List[Dict[str, Any]]) -> List[str]:
    suggestions: List[str] = []
    if any(f["id"] == "UNIT_MISSING" for f in findings):
        suggestions.append("Mengenangaben in deutsches Format mit klaren Einheiten ueberfuehren.")
    if not recipe.get("zeit"):
        suggestions.append("Zeitangabe ergaenzen, damit das Rezept besser einschaetzbar ist.")
    if recipe.get("zutaten") and not any("kraeuter" in str(item).lower() for item in recipe.get("zutaten", [])):
        suggestions.append("Optional pruefen, ob frische Kraeuter das Rezept geschmacklich verbessern.")
    if any(f["id"] == "OCR_PENDING" for f in findings):
        suggestions.append("OCR fuer vorhandene Bilder/PDFs ausfuehren oder manuell pruefen.")
    return suggestions


def _looks_like_action(step: str) -> bool:
    lowered = step.lower()
    return any(word in lowered for word in ["misch", "koch", "back", "brate", "schneid", "ruehr", "gib", "heiz", "servier"])


def _finding(identifier: str, area: str, severity: str, certainty: str, message: str, evidence: str = "", requires_review: bool = False) -> Dict[str, Any]:
    return {
        "id": identifier,
        "area": area,
        "severity": severity,
        "certainty": certainty,
        "message": message,
        "evidence": evidence,
        "suggestions": [],
        "requires_review": requires_review,
    }


