from services.contracts import MigrationPageCandidate, MigrationSessionResult

from gui.controller import MainController


class FakeImportService:
    def __init__(self, session):
        self._session = session
        self.executed = False

    def run_dry_run(self, source_scope, target_scope):
        return self._session

    def run_execute(self, session):
        self.executed = True
        return session


def sample_session():
    return MigrationSessionResult(
        session_id="session-1",
        source_scope={"section_id": "src-1"},
        target_scope={"notebook_id": "dst-1"},
        dry_run_items=[
            MigrationPageCandidate(
                source_page_id="ready-page",
                source_page_title="Ready",
                selected=True,
                status="ready",
                recognized_title="Ready",
                target_main_category="Lunch",
                target_subcategory="Salad",
                duplicate=False,
                messages=[],
                fingerprint="fp-ready",
                planned_target_path="Migrated Recipes/Lunch/Salad",
                planned_target_section_id="section-1",
                planned_target_section_name="Salad",
            ),
            MigrationPageCandidate(
                source_page_id="excluded-page",
                source_page_title="Excluded",
                selected=False,
                status="excluded",
                recognized_title="Excluded",
                target_main_category="Lunch",
                target_subcategory="Soup",
                duplicate=False,
                messages=[],
                fingerprint="fp-excluded",
                planned_target_path="Migrated Recipes/Lunch/Soup",
                planned_target_section_id="section-2",
                planned_target_section_name="Soup",
            ),
            MigrationPageCandidate(
                source_page_id="duplicate-page",
                source_page_title="Duplicate",
                selected=False,
                status="duplicate",
                recognized_title="Duplicate",
                target_main_category="Dinner",
                target_subcategory="Pasta",
                duplicate=True,
                messages=["duplicate"],
                fingerprint="fp-duplicate",
                planned_target_path="Migrated Recipes/Dinner/Pasta",
                planned_target_section_id="section-3",
                planned_target_section_name="Pasta",
            ),
            MigrationPageCandidate(
                source_page_id="error-page",
                source_page_title="Error",
                selected=False,
                status="error",
                recognized_title="Error",
                target_main_category="Dinner",
                target_subcategory="Stew",
                duplicate=False,
                messages=["failed"],
                fingerprint="fp-error",
                planned_target_path="Migrated Recipes/Dinner/Stew",
                planned_target_section_id="section-4",
                planned_target_section_name="Stew",
            ),
        ],
        dry_run_summary={"ready": 1, "excluded": 1, "duplicate": 1, "error": 1},
        execute_result=None,
    )


def test_bulk_selection_only_affects_selectable_rows():
    session = sample_session()
    controller = MainController(import_service=FakeImportService(session))
    controller.load_session(session)

    controller.select_none()

    statuses = {item.source_page_id: item.selected for item in controller.session.dry_run_items}
    row_statuses = {item.source_page_id: item.status for item in controller.session.dry_run_items}
    assert statuses["ready-page"] is False
    assert statuses["excluded-page"] is False
    assert statuses["duplicate-page"] is False
    assert statuses["error-page"] is False
    assert row_statuses["ready-page"] == "excluded"
    assert row_statuses["excluded-page"] == "excluded"
    assert row_statuses["duplicate-page"] == "duplicate"
    assert row_statuses["error-page"] == "error"

    controller.select_all()

    statuses = {item.source_page_id: item.selected for item in controller.session.dry_run_items}
    row_statuses = {item.source_page_id: item.status for item in controller.session.dry_run_items}
    assert statuses["ready-page"] is True
    assert statuses["excluded-page"] is True
    assert statuses["duplicate-page"] is False
    assert statuses["error-page"] is False
    assert row_statuses["ready-page"] == "ready"
    assert row_statuses["excluded-page"] == "ready"
    assert row_statuses["duplicate-page"] == "duplicate"
    assert row_statuses["error-page"] == "error"


def test_filter_rows_by_status():
    session = sample_session()
    controller = MainController(import_service=FakeImportService(session))
    controller.load_session(session)

    filtered = controller.filter_items({"duplicate"})

    assert len(filtered) == 1
    assert filtered[0].status == "duplicate"


def test_execute_is_blocked_when_session_is_invalid():
    session = sample_session()
    controller = MainController(import_service=FakeImportService(session))
    controller.load_session(session)
    controller.set_runtime_state(
        auth_state="disconnected",
        source_scope={"section_id": "src-1"},
        target_scope={"notebook_id": "dst-1"},
    )

    result = controller.execute()

    assert result is None
    assert controller.import_service.executed is False


def test_row_selection_toggles_between_ready_and_excluded_only_for_selectable_rows():
    session = sample_session()
    controller = MainController(import_service=FakeImportService(session))
    controller.load_session(session)

    assert controller.set_row_selection("ready-page", False) is True
    assert controller.set_row_selection("excluded-page", True) is True
    assert controller.set_row_selection("duplicate-page", True) is False

    items = {item.source_page_id: item for item in controller.session.dry_run_items}
    assert items["ready-page"].selected is False
    assert items["ready-page"].status == "excluded"
    assert items["excluded-page"].selected is True
    assert items["excluded-page"].status == "ready"
    assert items["duplicate-page"].selected is False
    assert items["duplicate-page"].status == "duplicate"
