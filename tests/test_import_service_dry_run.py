from services.contracts import MigrationSessionResult
from services.import_service import ImportService


class FakeOneNoteService:
    def __init__(self) -> None:
        self._pages = {
            "page-ready": {
                "id": "page-ready",
                "title": "Tomatensuppe",
                "text": (
                    "Titel: Tomatensuppe\n"
                    "Gruppe: Vorspeise\n"
                    "Kategorie: Suppe\n\n"
                    "Zutaten:\n"
                    "- 500 ml Wasser\n\n"
                    "Zubereitung:\n"
                    "1. Kochen"
                ),
                "source_type": "onenote_page",
                "media": [],
            },
            "page-duplicate": {
                "id": "page-duplicate",
                "title": "Tomatensuppe Kopie",
                "text": (
                    "Titel: Tomatensuppe\n"
                    "Gruppe: Vorspeise\n"
                    "Kategorie: Suppe\n\n"
                    "Zutaten:\n"
                    "- 500 ml Wasser\n\n"
                    "Zubereitung:\n"
                    "1. Kochen"
                ),
                "source_type": "onenote_page",
                "media": [],
            },
            "page-error": {
                "id": "page-error",
                "title": "Unvollstaendig",
                "text": (
                    "Titel: Unvollstaendig\n"
                    "Gruppe: Vorspeise\n"
                    "Kategorie: Suppe\n\n"
                    "Zutaten:\n"
                    "- 500 ml Wasser"
                ),
                "source_type": "onenote_page",
                "media": [],
            },
        }

    def list_pages(self, section_id):
        assert section_id == "src-1"
        return [
            {"id": "page-ready", "title": "Tomatensuppe"},
            {"id": "page-duplicate", "title": "Tomatensuppe Kopie"},
            {"id": "page-error", "title": "Unvollstaendig"},
        ]

    def get_page_source_item(self, page):
        page_id = page["id"] if isinstance(page, dict) else page
        return dict(self._pages[page_id])

    def load_target_fingerprints(self, target_scope):
        assert target_scope == {"notebook_id": "dst-1"}
        ready_fp = "82ef932e727176f006db1016227d5712e9271501b89bb938f2abc2a2cb1d535e"
        return {ready_fp}


def test_dry_run_builds_session_with_ready_duplicate_and_error_rows():
    service = ImportService(onenote_service=FakeOneNoteService())

    session = service.run_dry_run(
        source_scope={"section_id": "src-1"},
        target_scope={"notebook_id": "dst-1"},
    )

    assert isinstance(session, MigrationSessionResult)
    assert session.execute_result is None

    items = {item.source_page_id: item for item in session.dry_run_items}

    ready_item = items["page-ready"]
    assert ready_item.status == "duplicate"
    assert ready_item.selected is False
    assert ready_item.duplicate is True
    assert ready_item.planned_target_path == "Migrated Recipes/Vorspeise/Suppe"

    duplicate_item = items["page-duplicate"]
    assert duplicate_item.status == "duplicate"
    assert duplicate_item.selected is False
    assert duplicate_item.duplicate is True
    assert duplicate_item.planned_target_path == "Migrated Recipes/Vorspeise/Suppe"

    error_item = items["page-error"]
    assert error_item.status == "error"
    assert error_item.selected is False
    assert error_item.duplicate is False
    assert error_item.planned_target_path == "Migrated Recipes/Vorspeise/Suppe"
    assert "Pflichtfeld fehlt: Zubereitung" in error_item.messages

    assert session.dry_run_summary["duplicate"] == 2
    assert session.dry_run_summary["error"] == 1


def test_dry_run_marks_non_duplicate_valid_rows_as_selected():
    service = ImportService(onenote_service=FakeOneNoteService())
    service._onenote_service.load_target_fingerprints = lambda target_scope: set()

    session = service.run_dry_run(
        source_scope={"section_id": "src-1"},
        target_scope={"notebook_id": "dst-1"},
    )

    items = {item.source_page_id: item for item in session.dry_run_items}

    assert items["page-ready"].status == "ready"
    assert items["page-ready"].selected is True
    assert items["page-ready"].planned_target_path == "Migrated Recipes/Vorspeise/Suppe"
    assert items["page-duplicate"].status == "duplicate"
    assert items["page-duplicate"].selected is False
    assert session.dry_run_summary["ready"] == 1
    assert session.dry_run_summary["duplicate"] == 1
