from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4
from typing import Any, Dict

from services.contracts import ExecuteResult, MigrationSessionResult
from services.export_package_service import ExportPackageService
from services.import_payload_service import ImportPayloadService
from services.report_service import ReportService


class ImportService:
    def __init__(
        self,
        onenote_service: Any,
        report_service: ReportService | None = None,
        import_payload_service: ImportPayloadService | None = None,
        export_package_service: ExportPackageService | None = None,
    ) -> None:
        self._onenote_service = onenote_service
        self._report_service = report_service or ReportService()
        self._import_payload_service = import_payload_service or ImportPayloadService()
        self._export_package_service = export_package_service or ExportPackageService(onenote_service)

    def load_section_rows(self, source_scope: Dict[str, Any]) -> list[dict[str, Any]]:
        section_id = str(source_scope.get("section_id") or source_scope.get("id") or "").strip()
        if not section_id:
            raise RuntimeError("section_id fehlt fuer das Laden der Quellseiten")
        source_items = self._onenote_service.get_section_source_items(section_id)
        rows: list[dict[str, Any]] = []
        for item in source_items:
            source_page_id = str(item.get("id") or "").strip()
            if not source_page_id:
                continue
            rows.append(
                {
                    "source_page_id": source_page_id,
                    "source_page_title": str(item.get("title") or "").strip(),
                }
            )
        return rows

    def export_section(self, source_scope: Dict[str, Any], *, output_root: str | Path) -> Any:
        section_id = str(source_scope.get("section_id") or source_scope.get("id") or "").strip()
        section_name = str(source_scope.get("section_name") or source_scope.get("name") or "").strip()
        notebook_id = str(source_scope.get("notebook_id") or "").strip()
        if not section_id:
            raise RuntimeError("section_id fehlt fuer den Export")
        if not notebook_id:
            raise RuntimeError("notebook_id fehlt fuer den Export")
        return self._export_package_service.export_section(
            source_notebook_id=notebook_id,
            source_section_id=section_id,
            source_section_name=section_name or section_id,
            output_root=output_root,
        )

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

    def run_execute(self, session: MigrationSessionResult) -> MigrationSessionResult:
        from onenote_import import parse_source_items, rezept_fingerprint, rezept_zu_html

        started_at = datetime.now(timezone.utc).isoformat()
        summary = {"migrated": 0, "duplicate_skipped": 0, "write_error": 0, "excluded": 0}
        execute_items: list[dict[str, Any]] = []
        target_fingerprints = {
            str(fingerprint).strip().lower()
            for fingerprint in self._onenote_service.load_target_fingerprints(session.target_scope)
            if str(fingerprint).strip()
        }
        section_cache: dict[tuple[str, str], str] = {}

        for item in session.dry_run_items:
            if item.status == "duplicate":
                execute_items.append(
                    self._build_execute_item(
                        item,
                        status="duplicate_skipped",
                        message="duplicate",
                    )
                )
                summary["duplicate_skipped"] += 1
                continue

            if item.status == "error":
                execute_items.append(
                    self._build_execute_item(
                        item,
                        status="write_error",
                        message="dry-run error: " + "; ".join(item.messages) if item.messages else "dry-run error",
                    )
                )
                summary["write_error"] += 1
                continue

            if not item.selected:
                execute_items.append(
                    self._build_execute_item(
                        item,
                        status="excluded",
                        message="excluded",
                    )
                )
                summary["excluded"] += 1
                continue

            try:
                source_item = self._onenote_service.get_page_source_item_by_id(item.source_page_id)
                valid_recipes, invalid_entries = parse_source_items([source_item])
                if invalid_entries or not valid_recipes:
                    raise RuntimeError("Quelle wurde seit dem Dry-Run geaendert oder ist nicht mehr gueltig")

                recipe = valid_recipes[0]
                current_fingerprint = rezept_fingerprint(recipe)
                if current_fingerprint != item.fingerprint:
                    raise RuntimeError("Quelle wurde seit dem Dry-Run geaendert")

                if current_fingerprint in target_fingerprints:
                    execute_items.append(
                        self._build_execute_item(
                            item,
                            status="duplicate_skipped",
                            message="duplicate",
                        )
                    )
                    summary["duplicate_skipped"] += 1
                    continue

                section_id = self._resolve_target_section_id(
                    session.target_scope,
                    item.target_main_category,
                    item.target_subcategory,
                    section_cache,
                )
                html_inhalt = rezept_zu_html(recipe, fingerprint=current_fingerprint)
                response = self._onenote_service.create_recipe_page(
                    section_id,
                    html_inhalt,
                    page_title=str(recipe.get("titel") or item.recognized_title or item.source_page_title),
                )
                target_fingerprints.add(current_fingerprint)
                execute_items.append(
                    self._build_execute_item(
                        item,
                        status="migrated",
                        message="migrated",
                        written_target_page_id=str(response.get("id") or ""),
                        written_target_url=self._extract_written_target_url(response),
                    )
                )
                summary["migrated"] += 1
            except Exception as exc:
                execute_items.append(
                    self._build_execute_item(
                        item,
                        status="write_error",
                        message=str(exc),
                    )
                )
                summary["write_error"] += 1

        session.execute_result = ExecuteResult(
            started_at=started_at,
            finished_at=datetime.now(timezone.utc).isoformat(),
            items=execute_items,
            summary=summary,
        )
        return session

    def apply_import_payload(
        self,
        rows: list[dict[str, Any]],
        payload: dict[str, Any],
        *,
        export_run_id: str,
        source_section_id: str,
        exported_at: str,
        target_scope: Dict[str, Any],
    ) -> list[dict[str, Any]]:
        reconciled_rows = self._import_payload_service.reconcile_rows(
            rows,
            payload,
            export_run_id=export_run_id,
            source_section_id=source_section_id,
            exported_at=exported_at,
        )
        target_fingerprints = {
            str(fingerprint).strip().lower()
            for fingerprint in self._onenote_service.load_target_fingerprints(target_scope)
            if str(fingerprint).strip()
        }

        for row in reconciled_rows:
            self._apply_pre_migration_status(row, target_fingerprints)

        return reconciled_rows

    def execute_import_rows(self, rows: list[dict[str, Any]], *, target_scope: Dict[str, Any]) -> list[dict[str, Any]]:
        from onenote_import import rezept_fingerprint, rezept_zu_html

        target_fingerprints = {
            str(fingerprint).strip().lower()
            for fingerprint in self._onenote_service.load_target_fingerprints(target_scope)
            if str(fingerprint).strip()
        }
        section_cache: dict[tuple[str, str], str] = {}

        for row in rows:
            if not bool(row.get("selected")) or str(row.get("status") or "") != "Bereit":
                continue

            fingerprint = str(row.get("fingerprint") or "").strip().lower()
            if fingerprint and fingerprint in target_fingerprints:
                row["status"] = "Duplikat"
                row["selected"] = False
                row["selectable"] = False
                row["action_label"] = "Schon vorhanden"
                continue

            try:
                recipe = self._row_to_recipe(row)
                current_fingerprint = rezept_fingerprint(recipe)
                if current_fingerprint in target_fingerprints:
                    row["status"] = "Duplikat"
                    row["selected"] = False
                    row["selectable"] = False
                    row["action_label"] = "Schon vorhanden"
                    continue

                section_id = self._resolve_target_section_id(
                    target_scope,
                    str(row.get("target_main_category") or ""),
                    str(row.get("target_subcategory") or ""),
                    section_cache,
                )
                html_inhalt = rezept_zu_html(recipe, fingerprint=current_fingerprint)
                response = self._onenote_service.create_recipe_page(
                    section_id,
                    html_inhalt,
                    page_title=str(recipe.get("titel") or row.get("source_page_title") or ""),
                )
                target_fingerprints.add(current_fingerprint)
                row["status"] = "Migriert"
                row["selected"] = False
                row["selectable"] = False
                row["action_label"] = "Migriert"
                row["written_target_page_id"] = str(response.get("id") or "")
                row["written_target_url"] = self._extract_written_target_url(response)
            except Exception as exc:
                row["status"] = "Migrationsfehler"
                row["selected"] = False
                row["selectable"] = False
                row["action_label"] = str(exc)

        return rows

    def _resolve_target_section_id(
        self,
        target_scope: Dict[str, Any],
        main_category: str,
        subcategory: str,
        section_cache: dict[tuple[str, str], str],
    ) -> str:
        notebook_id = str(target_scope.get("notebook_id") or target_scope.get("id") or "").strip()
        if not notebook_id:
            raise RuntimeError("Notebook-ID fehlt fuer den Execute-Lauf")

        section_key = (str(main_category), str(subcategory))
        if section_key in section_cache:
            return section_cache[section_key]

        root_group_id = self._onenote_service.ensure_target_root(notebook_id, "Migrated Recipes")
        category_group_id = self._onenote_service.ensure_category_group(root_group_id, str(main_category))
        section_id = self._onenote_service.ensure_subcategory_section(category_group_id, str(subcategory))
        section_cache[section_key] = section_id
        return section_id

    def _apply_pre_migration_status(
        self,
        row: dict[str, Any],
        target_fingerprints: set[str],
    ) -> dict[str, Any]:
        fingerprint = str(row.get("fingerprint") or "").strip().lower()
        duplicate = bool(fingerprint) and fingerprint in target_fingerprints
        has_title = bool(str(row.get("title") or "").strip())
        has_main_category = bool(str(row.get("target_main_category") or "").strip())
        has_subcategory = bool(str(row.get("target_subcategory") or "").strip())

        row["duplicate"] = duplicate
        if duplicate:
            row["status"] = "Duplikat"
            row["selected"] = False
        elif row.get("import_state") == "missing" or not (has_title and has_main_category and has_subcategory):
            row["status"] = "Fehlt noch"
            row["selected"] = False
        else:
            row["status"] = "Bereit"
            row["selected"] = True
        row["selectable"] = row["status"] == "Bereit"
        row["action_label"] = row["status"]
        return row

    def _row_to_recipe(self, row: dict[str, Any]) -> dict[str, Any]:
        title = str(row.get("title") or row.get("source_page_title") or "").strip()
        main_category = str(row.get("target_main_category") or row.get("group") or "").strip()
        subcategory = str(row.get("target_subcategory") or row.get("category") or "").strip()
        ingredients = row.get("zutaten") or row.get("ingredients") or []
        steps = row.get("schritte") or row.get("steps") or []
        if not title or not main_category or not subcategory or not ingredients or not steps:
            raise RuntimeError("Pflichtdaten fuer die Migration fehlen noch")
        return {
            "titel": title,
            "gruppe": main_category,
            "kategorie": subcategory,
            "hauptkategorie": main_category,
            "unterkategorie": subcategory,
            "ziel_gruppe": main_category,
            "ziel_kategorie": subcategory,
            "zutaten": [str(item).strip() for item in ingredients if str(item).strip()],
            "schritte": [str(item).strip() for item in steps if str(item).strip()],
            "source_type": "onenote_page",
        }

    def _build_execute_item(
        self,
        item: Any,
        *,
        status: str,
        message: str,
        written_target_page_id: str = "",
        written_target_url: str = "",
    ) -> dict[str, Any]:
        return {
            "source_page_id": item.source_page_id,
            "source_page_title": item.source_page_title,
            "status": status,
            "message": message,
            "written_target_page_id": written_target_page_id,
            "written_target_url": written_target_url,
            "planned_target_path": item.planned_target_path,
        }

    def _extract_written_target_url(self, response: Dict[str, Any]) -> str:
        direct_url = response.get("url")
        if isinstance(direct_url, str):
            return direct_url

        links = response.get("links")
        if not isinstance(links, dict):
            return ""
        web_url = links.get("oneNoteWebUrl")
        if not isinstance(web_url, dict):
            return ""
        href = web_url.get("href")
        return href if isinstance(href, str) else ""
