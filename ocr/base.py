from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Dict, List


@dataclass
class OCRArtifact:
    media_id: str
    media_type: str
    ref: str
    language: str = "de"


@dataclass
class OCRResult:
    media_id: str
    text: str
    confidence: float = 0.0
    engine: str = "pending"
    language: str = "de"
    status: str = "pending"

    def to_dict(self) -> Dict[str, object]:
        return asdict(self)


def build_ocr_artifacts(media: List[Dict[str, object]]) -> List[OCRArtifact]:
    artifacts: List[OCRArtifact] = []
    for item in media:
        media_id = str(item.get("media_id") or "").strip()
        media_type = str(item.get("type") or "").strip()
        ref = str(item.get("ref") or "").strip()
        if not media_id or not media_type or not ref:
            continue
        artifacts.append(OCRArtifact(media_id=media_id, media_type=media_type, ref=ref))
    return artifacts


def merge_ocr_text_into_block(base_block: str, ocr_results: List[OCRResult]) -> str:
    texts = [result.text.strip() for result in ocr_results if result.text.strip()]
    if not texts:
        return base_block.strip()

    block = base_block.strip()
    ocr_section = "\n\nOCR-Notizen:\n" + "\n\n".join(texts)
    if not block:
        return ocr_section.strip()
    return (block + ocr_section).strip()


def summarize_ocr_results(ocr_results: List[OCRResult]) -> Dict[str, object]:
    texts = [result.text.strip() for result in ocr_results if result.text.strip()]
    confidences = [result.confidence for result in ocr_results if result.status != "failed"]
    engines = sorted({result.engine for result in ocr_results if result.engine and result.engine not in {"pending", "disabled"}})
    if len(engines) == 1:
        engine = engines[0]
    elif len(engines) > 1:
        engine = "mixed"
    else:
        engine = "pending"
    return {
        "text": "\n\n".join(texts).strip(),
        "confidence": (sum(confidences) / len(confidences)) if confidences else 0.0,
        "status": "done" if texts else ("failed" if ocr_results else "pending"),
        "engine": engine,
    }
