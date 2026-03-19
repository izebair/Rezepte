from __future__ import annotations

from typing import Any, Dict, Iterable, List, Sequence, Tuple

from services.contracts import MigrationPageCandidate


class ReportService:
    def build_dry_run_results(
        self,
        valid_recipes: Sequence[Dict[str, Any]],
        invalid_entries: Sequence[Tuple[int, Dict[str, Any], List[str]]],
        target_fingerprints: Iterable[str],
    ) -> tuple[list[MigrationPageCandidate], dict[str, Any]]:
        from onenote_import import (
            TARGET_ROOT_NAME,
            build_queue_summary_for_session,
            build_report_item_for_session,
            rezept_fingerprint,
        )

        known_fingerprints = {str(fingerprint).strip().lower() for fingerprint in target_fingerprints if str(fingerprint).strip()}
        report_items: list[dict[str, Any]] = []
        candidates: list[MigrationPageCandidate] = []
        summary = {"ready": 0, "duplicate": 0, "error": 0, "excluded": 0}

        for recipe in valid_recipes:
            fingerprint = rezept_fingerprint(recipe)
            status = "duplicate" if fingerprint in known_fingerprints else "ready"
            report_item = build_report_item_for_session(recipe, status=status, fingerprint=fingerprint)
            report_items.append(report_item)
            candidates.append(
                self._to_candidate(
                    recipe,
                    report_item,
                    status=status,
                    duplicate=(status == "duplicate"),
                    selected=(status == "ready"),
                    target_root_name=TARGET_ROOT_NAME,
                )
            )
            summary[status] += 1
            known_fingerprints.add(fingerprint)

        for _, recipe, reasons in invalid_entries:
            report_item = build_report_item_for_session(
                recipe,
                status="invalid",
                title=str(recipe.get("source_page_title") or recipe.get("titel") or ""),
                reasons=reasons,
            )
            report_items.append(report_item)
            candidates.append(
                self._to_candidate(
                    recipe,
                    report_item,
                    status="error",
                    duplicate=False,
                    selected=False,
                    target_root_name=TARGET_ROOT_NAME,
                )
            )
            summary["error"] += 1

        summary["total_items"] = len(candidates)
        summary["queue_summary"] = build_queue_summary_for_session(report_items)
        return candidates, summary

    def _to_candidate(
        self,
        recipe: Dict[str, Any],
        report_item: Dict[str, Any],
        *,
        status: str,
        duplicate: bool,
        selected: bool,
        target_root_name: str,
    ) -> MigrationPageCandidate:
        target_main_category = str(
            report_item.get("target_group")
            or recipe.get("ziel_gruppe")
            or recipe.get("hauptkategorie")
            or recipe.get("gruppe")
            or ""
        ).strip()
        target_subcategory = str(
            report_item.get("target_category")
            or recipe.get("ziel_kategorie")
            or recipe.get("unterkategorie")
            or recipe.get("kategorie")
            or ""
        ).strip()

        return MigrationPageCandidate(
            source_page_id=str(recipe.get("source_page_id") or ""),
            source_page_title=str(recipe.get("source_page_title") or report_item.get("title") or ""),
            selected=selected,
            status=status,
            recognized_title=str(report_item.get("title") or recipe.get("titel") or ""),
            target_main_category=target_main_category,
            target_subcategory=target_subcategory,
            duplicate=duplicate,
            messages=self._build_messages(report_item),
            fingerprint=str(report_item.get("fingerprint") or ""),
            planned_target_path=self._build_target_path(target_root_name, target_main_category, target_subcategory),
            planned_target_section_id="",
            planned_target_section_name=target_subcategory,
        )

    def _build_messages(self, report_item: Dict[str, Any]) -> list[str]:
        messages: list[str] = []
        for key in ("reasons", "blocking_issues", "review_triggers"):
            value = report_item.get(key)
            if not isinstance(value, list):
                continue
            for item in value:
                text = str(item).strip()
                if text and text not in messages:
                    messages.append(text)
        error = str(report_item.get("error") or "").strip()
        if error and error not in messages:
            messages.append(error)
        return messages

    def _build_target_path(self, target_root_name: str, target_main_category: str, target_subcategory: str) -> str:
        segments = [target_root_name]
        if target_main_category:
            segments.append(target_main_category)
        if target_subcategory:
            segments.append(target_subcategory)
        return "/".join(segments)
