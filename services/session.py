from __future__ import annotations

from typing import Any

from .contracts import ImportedRecipePayload, MigrationSessionResult


def is_session_valid(
    session: MigrationSessionResult,
    source_scope: dict[str, Any],
    target_scope: dict[str, Any],
    auth_state: str,
) -> bool:
    if auth_state != "connected":
        return False
    if session.source_scope != source_scope:
        return False
    if session.target_scope != target_scope:
        return False
    return True


def validate_import_payload(
    payload: ImportedRecipePayload,
    *,
    expected_run_id: str,
    expected_section_id: str,
) -> ImportedRecipePayload:
    if payload.export_run_id != expected_run_id:
        raise RuntimeError(
            f"import payload export_run_id mismatch: expected {expected_run_id}, got {payload.export_run_id}"
        )
    if payload.source_section_id != expected_section_id:
        raise RuntimeError(
            f"import payload source_section_id mismatch: expected {expected_section_id}, got {payload.source_section_id}"
        )
    if not str(payload.exported_at or "").strip():
        raise RuntimeError("import payload exported_at missing")

    seen_page_ids: set[str] = set()
    for recipe in payload.recipes:
        source_page_id = str(recipe.get("source_page_id") or "").strip()
        if not source_page_id:
            raise RuntimeError("import payload source_page_id missing")
        if source_page_id in seen_page_ids:
            raise RuntimeError(f"duplicate source_page_id in import payload: {source_page_id}")
        seen_page_ids.add(source_page_id)

    return payload
