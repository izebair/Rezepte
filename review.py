from __future__ import annotations

from typing import Any, Dict, List


def derive_review_triggers(recipe: Dict[str, Any], validation_errors: List[str], findings: List[Dict[str, Any]]) -> List[str]:
    triggers: List[str] = []

    title = str(recipe.get("titel") or "").strip()
    ingredients = recipe.get("zutaten", []) or []
    steps = recipe.get("schritte", []) or []
    main_category = str(recipe.get("hauptkategorie") or "").strip()
    media = recipe.get("media", []) or []
    ocr_text = str(recipe.get("ocr_text") or "").strip()
    ocr_status = str(recipe.get("ocr_status") or "").strip()
    ocr_confidence = float(recipe.get("ocr_confidence") or 0.0)

    if validation_errors:
        triggers.append("validation_error")
    if "titel" in recipe and not title:
        triggers.append("missing_title")
    if "zutaten" in recipe and not ingredients:
        triggers.append("missing_ingredients")
    if "schritte" in recipe and not steps:
        triggers.append("missing_steps")
    if "hauptkategorie" in recipe and not main_category:
        triggers.append("category_unknown")
    if ocr_text:
        triggers.append("ocr_present")
    if media and not ocr_text:
        triggers.append("ocr_empty")
    if media and ocr_status == "failed":
        triggers.append("ocr_failed")
    if media and ocr_confidence and ocr_confidence < 0.6:
        triggers.append("low_confidence")
    if media and not ocr_status:
        triggers.append("media_missing")
    if any(bool(finding.get("requires_review")) for finding in findings):
        triggers.append("quality_review")

    assessments = recipe.get("health", {}).get("assessments", [])
    if any(str(item.get("certainty") or "") == "low" for item in assessments if isinstance(item, dict)):
        triggers.append("health_low_certainty")
    if any(str(item.get("light") or "") == "red" for item in assessments if isinstance(item, dict)):
        triggers.append("health_red")

    deduped: List[str] = []
    for trigger in triggers:
        if trigger not in deduped:
            deduped.append(trigger)
    return deduped


def derive_blocking_issues(recipe: Dict[str, Any], validation_errors: List[str], findings: List[Dict[str, Any]]) -> List[str]:
    triggers = derive_review_triggers(recipe, validation_errors, findings)
    blocking = {
        "validation_error",
        "missing_title",
        "missing_ingredients",
        "missing_steps",
        "category_unknown",
        "ocr_failed",
        "health_red",
    }
    return [trigger for trigger in triggers if trigger in blocking]


def derive_review_status(recipe: Dict[str, Any], validation_errors: List[str], findings: List[Dict[str, Any]]) -> str:
    if validation_errors:
        return "rejected"
    if derive_review_triggers(recipe, validation_errors, findings):
        return "needs_review"
    if recipe.get("uncertainty", {}).get("overall") == "high":
        return "needs_review"
    return "approved"


def derive_uncertainty(recipe: Dict[str, Any], validation_errors: List[str], findings: List[Dict[str, Any]]) -> Dict[str, Any]:
    reasons: List[str] = []
    overall = "low"

    if validation_errors:
        overall = "high"
        reasons.extend(validation_errors)
    elif any(finding.get("severity") == "error" for finding in findings):
        overall = "high"
        reasons.append("Kritische Findings vorhanden")
    elif any(finding.get("severity") == "warning" for finding in findings):
        overall = "medium"
        reasons.append("Warnungen vorhanden")

    if str(recipe.get("ocr_text") or "").strip():
        if overall == "low":
            overall = "medium"
        reasons.append("OCR-Text erfordert fachliches Review")

    assessments = recipe.get("health", {}).get("assessments", [])
    if any(str(item.get("certainty") or "") == "low" for item in assessments if isinstance(item, dict)):
        if overall == "low":
            overall = "medium"
        reasons.append("Gesundheitshinweise sind noch unsicher")

    return {
        "overall": overall,
        "reasons": reasons,
        "confidence_by_stage": {
            "parsing": 0.9 if not validation_errors else 0.4,
            "taxonomy": 0.8,
            "health": 0.3,
            "ocr": 0.5 if str(recipe.get("ocr_text") or "").strip() else 1.0,
        },
    }

