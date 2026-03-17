from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, Dict, List, Literal

MainCategory = Literal["Dessert", "Getraenke", "Hauptgericht", "Snack", "Vorspeise"]
Severity = Literal["info", "warning", "error"]
Certainty = Literal["low", "medium", "high"]
ReviewStatus = Literal["extracted", "needs_review", "approved", "rejected"]
HealthLight = Literal["green", "yellow", "red", "unrated"]


@dataclass
class Ingredient:
    name_raw: str
    name_norm: str = ""
    quantity_raw: str = ""
    quantity_norm: str = ""
    unit_raw: str = ""
    unit_norm: str = ""
    preparation: str = ""
    is_optional: bool = False
    notes: str = ""


@dataclass
class Step:
    order: int
    text_raw: str
    text_norm: str = ""
    duration_minutes: int | None = None
    temperature_c: int | None = None
    equipment: str = ""
    notes: str = ""


@dataclass
class MediaAsset:
    media_id: str
    type: str
    ref: str
    caption: str = ""
    checksum: str = ""
    ocr_text_ref: str = ""
    ocr_status: str = "pending"
    ocr_confidence: float = 0.0


@dataclass
class QualityFinding:
    id: str
    area: str
    severity: Severity
    certainty: Certainty
    message: str
    evidence: str = ""
    suggestions: List[str] = field(default_factory=list)
    requires_review: bool = False


@dataclass
class HealthAssessment:
    condition: Literal["prostate_cancer", "breast_cancer"]
    light: HealthLight = "unrated"
    certainty: Certainty = "low"
    reasons: List[str] = field(default_factory=list)
    substitutions: List[str] = field(default_factory=list)
    requires_review: bool = True


@dataclass
class ReviewInfo:
    status: ReviewStatus = "extracted"
    owner: str = ""
    last_reviewed_at: str = ""
    changelog: List[Dict[str, Any]] = field(default_factory=list)


@dataclass
class UncertaintyInfo:
    overall: Certainty = "low"
    reasons: List[str] = field(default_factory=list)
    confidence_by_stage: Dict[str, float] = field(default_factory=dict)


@dataclass
class Recipe:
    recipe_id: str
    title: str
    category_main: MainCategory | str = ""
    category_sub: str = ""
    group: str = ""
    description: str = ""
    servings: str = ""
    prep_minutes: int | None = None
    cook_minutes: int | None = None
    total_minutes: int | None = None
    time_text: str = ""
    difficulty: str = ""
    ingredients: List[Ingredient] = field(default_factory=list)
    steps: List[Step] = field(default_factory=list)
    media: List[MediaAsset] = field(default_factory=list)
    ocr_text: str = ""
    temperatures: List[int] = field(default_factory=list)
    notes: str = ""
    tags: List[str] = field(default_factory=list)
    raw: str = ""
    source_type: str = ""
    quality_status: Literal["ok", "unsicher", "problematisch"] = "unsicher"
    quality_findings: List[QualityFinding] = field(default_factory=list)
    quality_suggestions: List[str] = field(default_factory=list)
    health_assessments: List[HealthAssessment] = field(default_factory=list)
    health_disclaimer: str = "Gesundheitshinweise sind unterstuetzende Empfehlungen und keine medizinische Beratung."
    review: ReviewInfo = field(default_factory=ReviewInfo)
    uncertainty: UncertaintyInfo = field(default_factory=UncertaintyInfo)

    def to_legacy_dict(self) -> Dict[str, Any]:
        return {
            "recipe_id": self.recipe_id,
            "titel": self.title,
            "gruppe": self.group,
            "kategorie": self.category_sub,
            "hauptkategorie": self.category_main,
            "portionen": self.servings,
            "zeit": self.time_text,
            "schwierigkeit": self.difficulty,
            "zutaten": [ingredient.name_raw for ingredient in self.ingredients],
            "schritte": [step.text_raw for step in self.steps],
            "media": [asdict(media) for media in self.media],
            "ocr_text": self.ocr_text,
            "source_type": self.source_type,
            "raw": self.raw,
            "quality": {
                "status": self.quality_status,
                "findings": [asdict(finding) for finding in self.quality_findings],
                "suggestions": list(self.quality_suggestions),
            },
            "health": {
                "assessments": [asdict(assessment) for assessment in self.health_assessments],
                "disclaimer": self.health_disclaimer,
            },
            "review": asdict(self.review),
            "uncertainty": asdict(self.uncertainty),
        }


def recipe_to_dict(recipe: Recipe) -> Dict[str, Any]:
    return recipe.to_legacy_dict()
