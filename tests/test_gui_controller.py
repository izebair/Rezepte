from services.contracts import MigrationPageCandidate, MigrationSessionResult

from gui.controller import MainController


class FakeImportService:
    def __init__(self, session):
        self._session = session
        self.executed = False
        self.login_result = None
        self.completed_login_result = None
        self.source_load_result = None
        self.dry_run_error = None

    def run_dry_run(self, source_scope, target_scope):
        if self.dry_run_error is not None:
            raise self.dry_run_error
        return self._session

    def run_execute(self, session):
        self.executed = True
        return session

    def request_login(self):
        return self.login_result

    def complete_login(self, flow=None):
        return self.completed_login_result

    def request_source_load(self):
        return self.source_load_result


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


def test_login_marks_controller_connected_when_access_token_is_returned():
    session = sample_session()
    service = FakeImportService(session)
    service.login_result = {"access_token": "token-123"}
    controller = MainController(import_service=service)

    result = controller.request_login()

    assert result == {"access_token": "token-123"}
    assert controller.auth_state == "connected"
    assert controller.last_error is None


def test_login_marks_controller_pending_when_device_flow_is_returned():
    session = sample_session()
    service = FakeImportService(session)
    service.login_result = {
        "message": "Open browser",
        "user_code": "ABC-123",
        "verification_uri": "https://example.test/device",
    }
    controller = MainController(import_service=service)

    result = controller.request_login()

    assert result == service.login_result
    assert controller.auth_state == "pending"
    assert controller.last_error is None


def test_complete_login_marks_controller_connected():
    session = sample_session()
    service = FakeImportService(session)
    service.completed_login_result = {"access_token": "token-123"}
    controller = MainController(import_service=service)

    result = controller.complete_login({"user_code": "ABC-123"})

    assert result == {"access_token": "token-123"}
    assert controller.auth_state == "connected"
    assert controller.last_error is None


def test_source_load_populates_choice_state_and_defaults_scopes():
    session = sample_session()
    service = FakeImportService(session)
    service.source_load_result = [
        {
            "id": "nb-1",
            "displayName": "Notebook A",
            "defaultSectionId": "sec-1",
            "sections": [
                {"id": "sec-1", "displayName": "Breakfast"},
                {"id": "sec-2", "displayName": "Lunch"},
            ],
        },
        {
            "id": "nb-2",
            "displayName": "Notebook B",
            "sections": [{"id": "sec-3", "displayName": "Dinner"}],
        },
    ]
    controller = MainController(import_service=service)

    result = controller.request_source_load()

    assert result == service.source_load_result
    assert [choice["id"] for choice in controller.source_choices] == ["sec-1", "sec-2", "sec-3"]
    assert [choice["id"] for choice in controller.target_choices] == ["nb-1", "nb-2"]
    assert controller.source_scope["section_id"] == "sec-1"
    assert controller.target_scope["notebook_id"] == "nb-1"
    assert controller.last_error is None


def test_dry_run_surfaces_errors_instead_of_stalling():
    session = sample_session()
    service = FakeImportService(session)
    service.dry_run_error = RuntimeError("dry run failed")
    controller = MainController(import_service=service)
    controller.set_runtime_state(
        auth_state="connected",
        source_scope={"section_id": "src-1"},
        target_scope={"notebook_id": "dst-1"},
    )

    result = controller.request_dry_run()

    assert result is None
    assert controller.last_error == "dry run failed"


def test_dry_run_is_blocked_until_login_is_connected():
    session = sample_session()
    controller = MainController(import_service=FakeImportService(session))
    controller.set_runtime_state(
        auth_state="disconnected",
        source_scope={"section_id": "src-1"},
        target_scope={"notebook_id": "dst-1"},
    )

    result = controller.request_dry_run()

    assert result is None
    assert controller.last_error == "login required"


def test_toggle_row_selection_flips_selectable_rows_only():
    session = sample_session()
    controller = MainController(import_service=FakeImportService(session))
    controller.load_session(session)

    assert controller.toggle_row_selection("ready-page") is True
    assert controller.toggle_row_selection("ready-page") is True
    assert controller.toggle_row_selection("duplicate-page") is False

    items = {item.source_page_id: item for item in controller.session.dry_run_items}
    assert items["ready-page"].selected is True
    assert items["ready-page"].status == "ready"
    assert items["duplicate-page"].status == "duplicate"


def test_selected_labels_stay_in_sync_with_narrower_runtime_scopes():
    session = sample_session()
    service = FakeImportService(session)
    service.source_load_result = [
        {
            "id": "nb-1",
            "displayName": "Notebook A",
            "sections": [
                {"id": "src-1", "displayName": "Breakfast"},
                {"id": "src-2", "displayName": "Lunch"},
            ],
        },
        {
            "id": "dst-1",
            "displayName": "Target Notebook",
            "sections": [{"id": "other-sec", "displayName": "Ignore"}],
        },
    ]
    controller = MainController(import_service=service)

    controller.request_source_load()
    controller.load_session(session)

    assert controller.selected_source_choice == "Notebook A (nb-1) / Breakfast (src-1)"
    assert controller.selected_target_choice == "Target Notebook (dst-1)"
