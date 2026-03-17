from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path
from typing import Iterable, List

from .base import OCRArtifact, OCRResult

SUPPORTED_MEDIA_TYPES = {"image", "pdf"}
SUPPORTED_SUFFIXES = {".png", ".jpg", ".jpeg", ".tif", ".tiff", ".bmp", ".pdf"}
DEFAULT_MAX_BYTES = 25 * 1024 * 1024
DEFAULT_TIMEOUT_SECONDS = 60


def ocr_is_enabled() -> bool:
    return os.environ.get("REZEPTE_ENABLE_OCR", "0").strip().lower() in {"1", "true", "yes", "on"}


def _get_tesseract_cmd() -> str:
    return os.environ.get("REZEPTE_TESSERACT_CMD", "tesseract").strip() or "tesseract"


def _get_ocrmypdf_cmd() -> str:
    return os.environ.get("REZEPTE_OCRMYPDF_CMD", "ocrmypdf").strip() or "ocrmypdf"


def _get_timeout_seconds() -> int:
    raw = os.environ.get("REZEPTE_OCR_TIMEOUT", str(DEFAULT_TIMEOUT_SECONDS)).strip()
    try:
        return max(1, int(raw))
    except ValueError:
        return DEFAULT_TIMEOUT_SECONDS


def _get_max_bytes() -> int:
    raw = os.environ.get("REZEPTE_OCR_MAX_BYTES", str(DEFAULT_MAX_BYTES)).strip()
    try:
        return max(1, int(raw))
    except ValueError:
        return DEFAULT_MAX_BYTES


def build_ocr_command(input_path: str, language: str = "deu") -> List[str]:
    suffix = Path(input_path).suffix.lower()
    if suffix not in SUPPORTED_SUFFIXES:
        raise ValueError(f"OCR nicht unterstützt für Dateityp: {suffix or 'unbekannt'}")
    if suffix == ".pdf":
        return [_get_ocrmypdf_cmd(), "--sidecar", "-", "--skip-text", "--language", language, input_path, "-"]
    return [_get_tesseract_cmd(), input_path, "stdout", "-l", language]


def validate_ocr_artifact(artifact: OCRArtifact, *, max_bytes: int | None = None) -> str | None:
    if artifact.media_type not in SUPPORTED_MEDIA_TYPES:
        return "unsupported_media_type"
    ref = Path(artifact.ref)
    if not ref.exists() or not ref.is_file():
        return "missing_file"
    if ref.suffix.lower() not in SUPPORTED_SUFFIXES:
        return "unsupported_suffix"
    effective_max = _get_max_bytes() if max_bytes is None else max_bytes
    if ref.stat().st_size > effective_max:
        return "file_too_large"
    return None


def run_local_ocr(artifact: OCRArtifact) -> OCRResult:
    if not ocr_is_enabled():
        return OCRResult(media_id=artifact.media_id, text="", confidence=0.0, engine="disabled", language=artifact.language, status="disabled")

    validation_error = validate_ocr_artifact(artifact)
    if validation_error is not None:
        return OCRResult(media_id=artifact.media_id, text="", confidence=0.0, engine="validator", language=artifact.language, status=validation_error)

    command = build_ocr_command(artifact.ref, language=artifact.language)
    executable = command[0]
    if shutil.which(executable) is None:
        return OCRResult(media_id=artifact.media_id, text="", confidence=0.0, engine=executable, language=artifact.language, status="missing_binary")

    try:
        completed = subprocess.run(command, capture_output=True, text=True, timeout=_get_timeout_seconds(), check=False)
    except subprocess.TimeoutExpired:
        return OCRResult(media_id=artifact.media_id, text="", confidence=0.0, engine=executable, language=artifact.language, status="timeout")

    if completed.returncode != 0:
        return OCRResult(media_id=artifact.media_id, text=(completed.stdout or "").strip(), confidence=0.0, engine=executable, language=artifact.language, status="failed")

    text = (completed.stdout or "").strip()
    return OCRResult(
        media_id=artifact.media_id,
        text=text,
        confidence=0.8 if text else 0.0,
        engine=executable,
        language=artifact.language,
        status="done" if text else "empty",
    )


def run_ocr_for_artifacts(artifacts: Iterable[OCRArtifact]) -> List[OCRResult]:
    return [run_local_ocr(artifact) for artifact in artifacts]
