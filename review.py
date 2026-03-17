from __future__ import annotations

from typing import Any, Dict, List


def derive_review_status(recipe: Dict[str, Any], validation_errors: List[str], findings: List[Dict[str, Any]]) -> str:
    if validation_errors:
        return "rejected"
    if recipe.get("ocr_text"):
        return "needs_review"
    if any(finding.get("severity") == "error" for finding in findings):
        return "needs_review"
    if any(bool(finding.get("requires_review")) for finding in findings):
        return "needs_review"
    assessments = recipe.get("health", {}).get("assessments", [])
    if any(bool(item.get("requires_review")) for item in assessments if isinstance(item, dict)):
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

    ocr_text = str(recipe.get("ocr_text") or "").strip()
    if ocr_text:
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
            "ocr": 0.5 if ocr_text else 1.0,
        },
    }
