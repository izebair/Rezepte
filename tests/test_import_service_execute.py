from services.contracts import MigrationPageCandidate, MigrationSessionResult
from services.import_service import ImportService


class FakeOneNoteService:
    def __init__(self, pages=None, *, target_fingerprints=None, missing_pages=None) -> None:
        self._pages = dict(pages or {})
        self._target_fingerprints = set(target_fingerprints or set())
        self._missing_pages = set(missing_pages or set())
        self.created_pages = []
        self.calls = []

    def load_target_fingerprints(self, target_scope):
        self.calls.append(("load_target_fingerprints", target_scope))
        return set(self._target_fingerprints)

    def get_page_source_item_by_id(self, page_id):
        self.calls.append(("get_page_source_item_by_id", page_id))
        if page_id in self._missing_pages:
            raise RuntimeError(f"Seite nicht gefunden: {page_id}")
        return dict(self._pages[page_id])

    def ensure_target_root(self, notebook_id, root_name="Migrated Recipes"):
        self.calls.append(("ensure_target_root", notebook_id, root_name))
        return "root-1"

    def ensure_category_group(self, root_group_id, group_name):
        self.calls.append(("ensure_category_group", root_group_id, group_name))
        return "group-1"

    def ensure_subcategory_section(self, category_group_id, section_name):
        self.calls.append(("ensure_subcategory_section", category_group_id, section_name))
        return "section-1"

    def create_recipe_page(self, section_id, html_inhalt, *, page_title):
        self.calls.append(("create_recipe_page", section_id, page_title))
        self.created_pages.append((section_id, page_title, html_inhalt))
        return {"id": f"new-{len(self.created_pages)}", "url": f"https://example/{page_title}"}


def _session_with_items(*items: MigrationPageCandidate) -> MigrationSessionResult:
    return MigrationSessionResult(
        session_id="session-1",
        source_scope={"section_id": "src-1"},
        target_scope={"notebook_id": "dst-1"},
        dry_run_items=list(items),
        dry_run_summary={},
        execute_result=None,
    )


def _page_source_item(page_id: str, title: str, group: str = "Vorspeise", category: str = "Suppe") -> dict:
    return {
        "id": page_id,
        "title": title,
        "text": (
            f"Titel: {title}\n"
            f"Gruppe: {group}\n"
            f"Kategorie: {category}\n\n"
            "Zutaten:\n"
            "- 500 ml Wasser\n\n"
            "Zubereitung:\n"
            "1. Kochen"
        ),
        "source_type": "onenote_page",
        "media": [],
    }


def test_execute_migrates_ready_items_and_skips_excluded_and_duplicates():
    from onenote_import import parse_source_items, rezept_fingerprint

    ready_source = _page_source_item("page-ready", "Tomatensuppe")
    duplicate_source = _page_source_item("page-duplicate", "Tomatensuppe Kopie")
    ready_recipe, _ = parse_source_items([ready_source])
    duplicate_recipe, _ = parse_source_items([duplicate_source])
    ready_fp = rezept_fingerprint(ready_recipe[0])
    duplicate_fp = rezept_fingerprint(duplicate_recipe[0])
    session = _session_with_items(
        MigrationPageCandidate(
            "page-ready",
            "Tomatensuppe",
            True,
            "ready",
            "Tomatensuppe",
            "Vorspeise",
            "Suppe",
            False,
            [],
            ready_fp,
            "Migrated Recipes/Vorspeise/Suppe",
            "",
            "Suppe",
        ),
        MigrationPageCandidate(
            "page-excluded",
            "Ausgelassen",
            False,
            "excluded",
            "Ausgelassen",
            "Vorspeise",
            "Suppe",
            False,
            [],
            "excluded-fp",
            "Migrated Recipes/Vorspeise/Suppe",
            "",
            "Suppe",
        ),
        MigrationPageCandidate(
            "page-duplicate",
            "Tomatensuppe Kopie",
            False,
            "duplicate",
            "Tomatensuppe Kopie",
            "Vorspeise",
            "Suppe",
            True,
            [],
            duplicate_fp,
            "Migrated Recipes/Vorspeise/Suppe",
            "",
            "Suppe",
        ),
    )
    service = ImportService(
        onenote_service=FakeOneNoteService(
            pages={
                "page-ready": ready_source,
                "page-duplicate": duplicate_source,
            },
            target_fingerprints={duplicate_fp},
        )
    )

    updated = service.run_execute(session)

    assert updated.execute_result is not None
    assert updated.execute_result.summary == {
        "migrated": 1,
        "duplicate_skipped": 1,
        "write_error": 0,
        "excluded": 1,
    }
    statuses = {item["source_page_id"]: item["status"] for item in updated.execute_result.items}
    assert statuses == {
        "page-ready": "migrated",
        "page-excluded": "excluded",
        "page-duplicate": "duplicate_skipped",
    }
    assert service._onenote_service.created_pages[0][0] == "section-1"
    assert service._onenote_service.created_pages[0][1] == "Tomatensuppe"


def test_execute_marks_changed_or_missing_sources_as_write_error_and_continues():
    from onenote_import import parse_source_items, rezept_fingerprint

    changed_source = _page_source_item("page-changed", "Tomatensuppe")
    changed_recipe, _ = parse_source_items([changed_source])
    changed_fp = rezept_fingerprint(changed_recipe[0])
    ok_source = _page_source_item("page-ok", "Kuerbissuppe")
    ok_recipe, _ = parse_source_items([ok_source])
    ok_fp = rezept_fingerprint(ok_recipe[0])
    session = _session_with_items(
        MigrationPageCandidate(
            "page-changed",
            "Tomatensuppe",
            True,
            "ready",
            "Tomatensuppe",
            "Vorspeise",
            "Suppe",
            False,
            [],
            changed_fp,
            "Migrated Recipes/Vorspeise/Suppe",
            "",
            "Suppe",
        ),
        MigrationPageCandidate(
            "page-missing",
            "Verschwunden",
            True,
            "ready",
            "Verschwunden",
            "Vorspeise",
            "Suppe",
            False,
            [],
            "missing-fp",
            "Migrated Recipes/Vorspeise/Suppe",
            "",
            "Suppe",
        ),
        MigrationPageCandidate(
            "page-ok",
            "Kuerbissuppe",
            True,
            "ready",
            "Kuerbissuppe",
            "Vorspeise",
            "Suppe",
            False,
            [],
            ok_fp,
            "Migrated Recipes/Vorspeise/Suppe",
            "",
            "Suppe",
        ),
    )
    service = ImportService(
        onenote_service=FakeOneNoteService(
            pages={
                "page-changed": _page_source_item("page-changed", "Tomatensuppe Neu"),
                "page-ok": ok_source,
            },
            missing_pages={"page-missing"},
        )
    )

    updated = service.run_execute(session)

    assert updated.execute_result is not None
    assert updated.execute_result.summary == {
        "migrated": 1,
        "duplicate_skipped": 0,
        "write_error": 2,
        "excluded": 0,
    }
    results = {item["source_page_id"]: item for item in updated.execute_result.items}
    assert results["page-changed"]["status"] == "write_error"
    assert "geaendert" in results["page-changed"]["message"]
    assert results["page-missing"]["status"] == "write_error"
    assert "nicht gefunden" in results["page-missing"]["message"]
    assert results["page-ok"]["status"] == "migrated"
    assert len(service._onenote_service.created_pages) == 1


def test_execute_keeps_dry_run_error_rows_in_error_bucket():
    session = _session_with_items(
        MigrationPageCandidate(
            "page-error",
            "Fehlseite",
            False,
            "error",
            "Fehlseite",
            "Vorspeise",
            "Suppe",
            False,
            ["Pflichtfeld fehlt: Zubereitung"],
            "error-fp",
            "Migrated Recipes/Vorspeise/Suppe",
            "",
            "Suppe",
        ),
    )
    service = ImportService(onenote_service=FakeOneNoteService())

    updated = service.run_execute(session)

    assert updated.execute_result is not None
    assert updated.execute_result.summary == {
        "migrated": 0,
        "duplicate_skipped": 0,
        "write_error": 1,
        "excluded": 0,
    }
    assert updated.execute_result.items == [
        {
            "source_page_id": "page-error",
            "source_page_title": "Fehlseite",
            "status": "write_error",
            "message": "dry-run error: Pflichtfeld fehlt: Zubereitung",
            "written_target_page_id": "",
            "written_target_url": "",
            "planned_target_path": "Migrated Recipes/Vorspeise/Suppe",
        }
    ]
