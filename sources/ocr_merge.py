from __future__ import annotations

from typing import Any, Dict, List

from ocr.base import OCRResult, summarize_ocr_results


def attach_ocr_results_to_source_item(source_item: Dict[str, Any], ocr_results: List[OCRResult]) -> Dict[str, Any]:
    updated = dict(source_item)
    media_raw = updated.get("media", [])
    media_items = media_raw if isinstance(media_raw, list) else []
    media = [dict(item) for item in media_items if isinstance(item, dict)]
    result_map = {result.media_id: result for result in ocr_results}
    for media_item in media:
        media_id = str(media_item.get("media_id") or "")
        result = result_map.get(media_id)
        if result is None:
            continue
        media_item["ocr_text_ref"] = result.text
        media_item["ocr_status"] = result.status
        media_item["ocr_confidence"] = result.confidence

    summary = summarize_ocr_results(ocr_results)
    updated["media"] = media
    updated["ocr_text"] = summary["text"]
    updated["ocr_confidence"] = summary["confidence"]
    updated["ocr_status"] = summary["status"]
    return updated

