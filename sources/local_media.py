from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List

from ocr import OCRArtifact, OCRResult, merge_ocr_text_into_block
from .ocr_merge import attach_ocr_results_to_source_item


def build_local_media_source_item(input_path: str, ocr_results: List[OCRResult]) -> tuple[str, Dict[str, Any]]:
    path = Path(input_path)
    suffix = path.suffix.lower()
    media_type = "pdf" if suffix == ".pdf" else "image"
    artifact = OCRArtifact(media_id="file-1", media_type=media_type, ref=input_path)
    source_item = attach_ocr_results_to_source_item(
        {
            "id": input_path,
            "title": path.stem,
            "text": "",
            "ocr_text": "",
            "ocr_confidence": 0.0,
            "ocr_status": "pending",
            "media": [
                {
                    "media_id": artifact.media_id,
                    "type": artifact.media_type,
                    "ref": artifact.ref,
                    "caption": "",
                    "ocr_text_ref": "",
                    "ocr_status": "pending",
                    "ocr_confidence": 0.0,
                }
            ],
            "source_type": "ocr_file",
        },
        ocr_results,
    )
    merged_text = merge_ocr_text_into_block(source_item.get("text", "") or path.stem, ocr_results)
    return merged_text, source_item
