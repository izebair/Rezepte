from __future__ import annotations

from typing import Any

from .contracts import ExportRunContext, ImportedRecipePayload, ImportedRecipeRow, MigrationSessionResult


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


def validate_expected_export_run_id(actual_export_run_id: str, expected_export_run_id: str) -> str:
    if actual_export_run_id != expected_export_run_id:
        raise RuntimeError(
            f"import payload export_run_id mismatch: expected {expected_export_run_id}, got {actual_export_run_id}"
        )
    return actual_export_run_id


def validate_expected_source_section_id(
    actual_source_section_id: str,
    expected_source_section_id: str,
) -> str:
    if actual_source_section_id != expected_source_section_id:
        raise RuntimeError(
            f"import payload source_section_id mismatch: expected {expected_source_section_id}, got {actual_source_section_id}"
        )
    return actual_source_section_id


def _source_page_id_from_recipe(recipe: ImportedRecipeRow | dict[str, Any]) -> str:
    if isinstance(recipe, ImportedRecipeRow):
        source_page_id = recipe.source_page_id
    else:
        source_page_id = str(recipe.get("source_page_id") or "").strip()
    if not source_page_id:
        raise RuntimeError("import payload source_page_id missing")
    return source_page_id


def validate_unique_source_page_ids(recipes: list[ImportedRecipeRow | dict[str, Any]]) -> list[str]:
    seen_page_ids: set[str] = set()
    ordered_page_ids: list[str] = []
    for recipe in recipes:
        source_page_id = _source_page_id_from_recipe(recipe)
        if source_page_id in seen_page_ids:
            raise RuntimeError(f"duplicate source_page_id in import payload: {source_page_id}")
        seen_page_ids.add(source_page_id)
        ordered_page_ids.append(source_page_id)
    return ordered_page_ids


def validate_exported_at(exported_at: str, expected_exported_at: str | None = None) -> str:
    normalized_exported_at = str(exported_at or "").strip()
    if not normalized_exported_at:
        raise RuntimeError("import payload exported_at missing")
    if expected_exported_at is not None and normalized_exported_at != expected_exported_at:
        raise RuntimeError(
            f"import payload exported_at mismatch: expected {expected_exported_at}, got {normalized_exported_at}"
        )
    return normalized_exported_at


def validate_import_payload(
    payload: ImportedRecipePayload,
    context: ExportRunContext | None = None,
    *,
    expected_run_id: str | None = None,
    expected_section_id: str | None = None,
    expected_exported_at: str | None = None,
) -> ImportedRecipePayload:
    if context is not None:
        expected_run_id = context.export_run_id
        expected_section_id = context.source_section_id
        expected_exported_at = context.exported_at
    if expected_run_id is None:
        raise RuntimeError("expected export_run_id is required")
    if expected_section_id is None:
        raise RuntimeError("expected source_section_id is required")

    validate_expected_export_run_id(payload.export_run_id, expected_run_id)
    validate_expected_source_section_id(payload.source_section_id, expected_section_id)
    validate_unique_source_page_ids(payload.recipes)
    validate_exported_at(payload.exported_at, expected_exported_at)
    return payload
