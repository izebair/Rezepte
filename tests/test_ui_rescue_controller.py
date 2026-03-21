from gui.controller import MainController


class FakeImportService:
    pass


def test_source_tree_stays_disabled_until_login_succeeds():
    controller = MainController(import_service=FakeImportService())

    assert controller.auth_state == "disconnected"
    assert controller.can_load_source_tree() is False


def test_selecting_section_loads_raw_rows_with_disabled_selection():
    controller = MainController(import_service=FakeImportService())
    controller.auth_state = "connected"

    controller.load_raw_section_rows(
        {"section_id": "sec-1"},
        [{"source_page_id": "page-1", "source_page_title": "Kuchen"}],
    )

    assert controller.rows[0]["status"] == "Roh"
    assert controller.rows[0]["action_label"] == "Aufbereitung ausstehend"
    assert controller.rows[0]["selected"] is False
    assert controller.rows[0]["selectable"] is False


def test_section_switch_clears_previous_enrichment():
    controller = MainController(import_service=FakeImportService())
    controller.active_export_run_id = "run-1"
    controller.rows = [{"source_page_id": "page-1", "status": "Bereit"}]

    controller.on_section_changed({"section_id": "sec-2"})

    assert controller.active_export_run_id is None
    assert controller.rows == []


def test_ready_rows_are_selected_by_default_after_json_import():
    class ImportReadyService:
        def apply_import_payload(self, rows, payload, **kwargs):
            rows[0]["status"] = "Bereit"
            rows[0]["selected"] = True
            rows[0]["selectable"] = True
            return rows

    controller = MainController(import_service=ImportReadyService())
    controller.target_scope = {"notebook_id": "dst-1"}
    controller.active_export_context = type(
        "Ctx",
        (),
        {
            "export_run_id": "run-1",
            "source_section_id": "sec-1",
            "exported_at": "2026-03-20T10:00:00Z",
        },
    )()
    controller.rows = [{"source_page_id": "page-1", "source_page_title": "Kuchen"}]

    rows = controller.request_json_import({"recipes": []})

    assert rows[0]["status"] == "Bereit"
    assert rows[0]["selected"] is True


def test_failed_rows_can_be_reset_to_retryable_ready_state():
    controller = MainController(import_service=FakeImportService())
    controller.rows = [{"source_page_id": "page-1", "status": "Migrationsfehler", "selected": False, "selectable": False}]

    controller.reset_failed_rows()

    assert controller.rows[0]["status"] == "Bereit"
    assert controller.rows[0]["selected"] is True


def test_toggle_row_selection_supports_ready_rows_from_json_import():
    controller = MainController(import_service=FakeImportService())
    controller.rows = [
        {
            "source_page_id": "page-1",
            "status": "Bereit",
            "selected": True,
            "selectable": True,
        }
    ]

    toggled = controller.toggle_row_selection("page-1")

    assert toggled is True
    assert controller.rows[0]["selected"] is False


def test_select_all_applies_to_bereit_rows_in_active_ui_rows():
    controller = MainController(import_service=FakeImportService())
    controller.rows = [
        {
            "source_page_id": "page-1",
            "status": "Bereit",
            "selected": False,
            "selectable": True,
        },
        {
            "source_page_id": "page-2",
            "status": "Fehlt noch",
            "selected": False,
            "selectable": False,
        },
    ]

    controller.select_all()

    assert controller.rows[0]["selected"] is True
    assert controller.rows[1]["selected"] is False


def test_loading_raw_rows_keeps_active_source_choice_visible():
    controller = MainController(import_service=FakeImportService())
    controller.selected_source_choice = "Rezepte (nb-1) / Diverse (sec-1)"

    controller.load_raw_section_rows(
        {"notebook_id": "nb-1", "section_id": "sec-1"},
        [{"source_page_id": "page-1", "source_page_title": "Kuchen"}],
    )

    assert controller.selected_source_choice == "Rezepte (nb-1) / Diverse (sec-1)"
