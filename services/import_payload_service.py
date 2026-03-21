from __future__ import annotations

from typing import Any

from .contracts import ImportedRecipePayload
from .session import validate_import_payload


class ImportPayloadService:
    def reconcile_rows(
        self,
        rows: list[dict[str, Any]],
        payload: ImportedRecipePayload | dict[str, Any],
        *,
        export_run_id: str,
        source_section_id: str,
        exported_at: str,
    ) -> list[dict[str, Any]]:
        normalized_payload = self._normalize_payload(payload)
        validate_import_payload(
            normalized_payload,
            expected_run_id=export_run_id,
            expected_section_id=source_section_id,
            expected_exported_at=exported_at,
        )

        known_page_ids = {
            str(row.get("source_page_id") or "").strip()
            for row in rows
            if str(row.get("source_page_id") or "").strip()
        }
        recipes_by_id: dict[str, dict[str, Any]] = {}
        for recipe in normalized_payload.recipes:
            source_page_id = str(recipe.get("source_page_id") or "").strip()
            if source_page_id not in known_page_ids:
                raise RuntimeError(f"unknown source_page_id in import payload: {source_page_id}")
            recipes_by_id[source_page_id] = dict(recipe)

        for row in rows:
            source_page_id = str(row.get("source_page_id") or "").strip()
            imported_recipe = recipes_by_id.get(source_page_id)
            if imported_recipe is None:
                row["import_state"] = "missing"
                continue

            row.update(imported_recipe)
            row["import_state"] = "present"

        return rows

    def _normalize_payload(self, payload: ImportedRecipePayload | dict[str, Any]) -> ImportedRecipePayload:
        if isinstance(payload, ImportedRecipePayload):
            return payload
        if not isinstance(payload, dict):
            raise RuntimeError("import payload must be a mapping")

        recipes = payload.get("recipes")
        normalized_recipes: list[dict[str, Any]] = []
        if recipes is not None:
            if not isinstance(recipes, list):
                raise RuntimeError("import payload recipes must be a list")
            for recipe in recipes:
                if not isinstance(recipe, dict):
                    raise RuntimeError("import payload recipes must contain objects")
                normalized_recipes.append(dict(recipe))

        return ImportedRecipePayload(
            export_run_id=str(payload.get("export_run_id") or "").strip(),
            source_section_id=str(payload.get("source_section_id") or "").strip(),
            exported_at=str(payload.get("exported_at") or "").strip(),
            recipes=normalized_recipes,
        )
