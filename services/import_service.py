from __future__ import annotations

from uuid import uuid4
from typing import Any, Dict

from services.contracts import MigrationSessionResult
from services.report_service import ReportService


class ImportService:
    def __init__(self, onenote_service: Any, report_service: ReportService | None = None) -> None:
        self._onenote_service = onenote_service
        self._report_service = report_service or ReportService()

    def run_dry_run(self, source_scope: Dict[str, Any], target_scope: Dict[str, Any]) -> MigrationSessionResult:
        from onenote_import import parse_source_items

        section_id = str(source_scope.get("section_id") or source_scope.get("id") or "").strip()
        if not section_id:
            raise RuntimeError("section_id fehlt fuer den Dry-Run")

        pages = self._onenote_service.list_pages(section_id)
        source_items = [self._onenote_service.get_page_source_item(page) for page in pages]
        valid_recipes, invalid_entries = parse_source_items(source_items)
        target_fingerprints = self._onenote_service.load_target_fingerprints(target_scope)
        dry_run_items, dry_run_summary = self._report_service.build_dry_run_results(
            valid_recipes,
            invalid_entries,
            target_fingerprints,
        )

        return MigrationSessionResult(
            session_id=f"dry-run-{uuid4()}",
            source_scope=dict(source_scope),
            target_scope=dict(target_scope),
            dry_run_items=dry_run_items,
            dry_run_summary=dry_run_summary,
            execute_result=None,
        )
