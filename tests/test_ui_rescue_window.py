from __future__ import annotations

import tkinter as tk
from tkinter import ttk

from gui.controller import MainController
from gui.main_window import MainWindow
import gui.main_window as main_window_module


class FakeImportService:
    pass


def build_test_root() -> tk.Tk:
    root = tk.Tk()
    root.withdraw()
    return root


def build_window(root: tk.Tk) -> MainWindow:
    controller = MainController(import_service=FakeImportService())
    controller.source_choices = [
        {
            "id": "sec-1",
            "label": "Rezepte (nb-1) / Diverse (sec-1)",
            "scope": {"section_id": "sec-1", "notebook_id": "nb-1"},
        }
    ]
    return MainWindow(root, controller)


def widget_texts(root: tk.Misc, widget_type: type[tk.Widget]) -> list[str]:
    values: list[str] = []

    def walk(widget: tk.Misc) -> None:
        if isinstance(widget, widget_type):
            text = str(widget.cget("text") or "").strip()
            if text:
                values.append(text)
        for child in widget.winfo_children():
            walk(child)

    walk(root)
    return values


def test_main_window_shows_left_hierarchy_and_top_actions():
    root = build_test_root()
    try:
        window = build_window(root)

        assert widget_texts(root, ttk.Label).count("Notebook") >= 1
        assert "Alle auswählen" in widget_texts(root, ttk.Button)
        assert "Abschnitt exportieren" in widget_texts(root, ttk.Button)
        assert "Aufbereitetes JSON importieren" in widget_texts(root, ttk.Button)
        assert "Export-Ordner öffnen" in widget_texts(root, ttk.Button)
        assert "Pfad kopieren" in widget_texts(root, ttk.Button)
        assert "Prompt öffnen" in widget_texts(root, ttk.Button)
        assert "Prompt kopieren" in widget_texts(root, ttk.Button)
        assert "Nur bereit" in widget_texts(root, ttk.Button)
        assert "Fehlt noch" in widget_texts(root, ttk.Button)
        assert "Duplikate" in widget_texts(root, ttk.Button)
        assert "Fehler" in widget_texts(root, ttk.Button)
        assert window.status_filter_combo.winfo_exists() == 1
        assert window.tree.heading("source")["text"] == "Quelle"
        assert window.tree.heading("target")["text"] == "Ziel"
        assert window.tree.heading("status")["text"] == "Status"
        assert window.tree.heading("action")["text"] == "Aktion"
    finally:
        root.destroy()


def test_login_code_is_rendered_in_copyable_field():
    root = build_test_root()
    try:
        window = build_window(root)

        assert window.login_code_entry.cget("state") == "readonly"
    finally:
        root.destroy()


def test_login_error_enables_retry_button():
    root = build_test_root()
    try:
        window = build_window(root)
        window.controller.auth_state = "error"
        window.controller.login_banner_state = "error"
        window.controller.last_error = "network down"

        window._sync_state_controls()

        assert window.retry_login_button.instate(["!disabled"])
    finally:
        root.destroy()


def test_failed_rows_enable_reset_button():
    root = build_test_root()
    try:
        window = build_window(root)
        window.controller.rows = [
            {
                "source_page_id": "page-1",
                "source_page_title": "Kuchen",
                "status": "Migrationsfehler",
                "selected": False,
                "selectable": False,
            }
        ]

        window._refresh_rows()

        assert window.reset_failed_button.instate(["!disabled"])
    finally:
        root.destroy()


def test_export_context_card_shows_generated_files_and_import_summary():
    root = build_test_root()
    try:
        window = build_window(root)
        window.controller.active_export_context = type(
            "Ctx",
            (),
            {
                "export_root": "exports/run-1",
                "export_run_id": "run-1",
                "source_section_name": "Diverse",
            },
        )()
        window.controller.rows = [
            {
                "source_page_id": "page-1",
                "source_page_title": "Kuchen",
                "status": "Bereit",
                "selected": True,
                "selectable": True,
            },
            {
                "source_page_id": "page-2",
                "source_page_title": "Suppe",
                "status": "Fehlt noch",
                "selected": False,
                "selectable": False,
            },
        ]

        window._sync_state_controls()

        assert "exports/run-1" in window.export_context_var.get()
        assert "Diverse" in window.export_context_var.get()
        assert "run-1" in window.export_context_var.get()
        assert "section_export.md" in window.export_files_var.get()
        assert "import_prompt.md" in window.export_files_var.get()
        assert "1 bereit" in window.import_summary_var.get()
        assert "1 fehlt noch" in window.import_summary_var.get()
        assert "2 Eintraege" in window.row_summary_var.get()
        assert "1 ausgewaehlt" in window.row_summary_var.get()
        assert window.open_export_button.instate(["!disabled"])
        assert window.copy_export_path_button.instate(["!disabled"])
        assert window.open_prompt_button.instate(["!disabled"])
        assert window.copy_prompt_button.instate(["!disabled"])
        assert "JSON importieren" in window.flow_state_var.get()
    finally:
        root.destroy()


def test_status_filter_can_hide_non_matching_rows():
    root = build_test_root()
    try:
        window = build_window(root)
        window.controller.rows = [
            {"source_page_id": "page-1", "source_page_title": "Kuchen", "status": "Bereit", "selected": True, "selectable": True},
            {"source_page_id": "page-2", "source_page_title": "Suppe", "status": "Fehlt noch", "selected": False, "selectable": False},
        ]
        window.controller.set_status_filter("Bereit")

        window._refresh_rows()

        assert window.tree.get_children() == ("page-1",)
    finally:
        root.destroy()


def test_flow_state_switches_to_migration_when_ready_rows_exist():
    root = build_test_root()
    try:
        window = build_window(root)
        window.controller.active_export_context = type(
            "Ctx",
            (),
            {"export_root": "exports/run-1", "export_run_id": "run-1"},
        )()
        window.controller.rows = [
            {"source_page_id": "page-1", "source_page_title": "Kuchen", "status": "Bereit", "selected": True, "selectable": True},
        ]

        window._sync_state_controls()

        assert "Migration starten" in window.flow_state_var.get()
    finally:
        root.destroy()


def test_row_summary_reports_ready_missing_and_failed_counts():
    root = build_test_root()
    try:
        window = build_window(root)
        window.controller.rows = [
            {"source_page_id": "page-1", "source_page_title": "Kuchen", "status": "Bereit", "selected": True, "selectable": True},
            {"source_page_id": "page-2", "source_page_title": "Suppe", "status": "Fehlt noch", "selected": False, "selectable": False},
            {"source_page_id": "page-3", "source_page_title": "Brot", "status": "Migrationsfehler", "selected": False, "selectable": False},
        ]

        window._sync_state_controls()

        assert "3 Eintraege" in window.row_summary_var.get()
        assert "1 bereit" in window.row_summary_var.get()
        assert "1 fehlt" in window.row_summary_var.get()
        assert "1 Fehler" in window.row_summary_var.get()
    finally:
        root.destroy()


def test_quick_filter_button_sets_status_filter_and_updates_rows():
    root = build_test_root()
    try:
        window = build_window(root)
        window.controller.rows = [
            {"source_page_id": "page-1", "source_page_title": "Kuchen", "status": "Bereit", "selected": True, "selectable": True},
            {"source_page_id": "page-2", "source_page_title": "Suppe", "status": "Fehlt noch", "selected": False, "selectable": False},
        ]

        window._apply_quick_filter("Fehlt noch")

        assert window.controller.status_filter == "Fehlt noch"
        assert window.tree.get_children() == ("page-2",)
    finally:
        root.destroy()


def test_row_details_show_selected_entry_context():
    root = build_test_root()
    try:
        window = build_window(root)
        window.controller.rows = [
            {
                "source_page_id": "page-1",
                "source_page_title": "Kuchen",
                "target_subcategory": "Dessert/Kuchen",
                "status": "Fehlt noch",
                "action_label": "Kategorie fehlt",
                "selected": False,
                "selectable": False,
            }
        ]

        window._show_row_details("page-1")

        assert "Kuchen" in window.detail_source_var.get()
        assert "Dessert/Kuchen" in window.detail_target_var.get()
        assert "Fehlt noch" in window.detail_status_var.get()
        assert "Kategorie fehlt" in window.detail_action_var.get()
    finally:
        root.destroy()


def test_clicking_non_selection_column_keeps_checkbox_state():
    root = build_test_root()
    try:
        window = build_window(root)
        window.controller.rows = [
            {
                "source_page_id": "page-1",
                "source_page_title": "Kuchen",
                "status": "Bereit",
                "selected": True,
                "selectable": True,
            }
        ]

        window._handle_row_interaction("page-1", "#2")

        assert window.controller.rows[0]["selected"] is True
        assert window._selected_row_id == "page-1"
    finally:
        root.destroy()


def test_clicking_selection_column_toggles_ready_row():
    root = build_test_root()
    try:
        window = build_window(root)
        window.controller.rows = [
            {
                "source_page_id": "page-1",
                "source_page_title": "Kuchen",
                "status": "Bereit",
                "selected": True,
                "selectable": True,
            }
        ]

        window._handle_row_interaction("page-1", "#1")

        assert window.controller.rows[0]["selected"] is False
    finally:
        root.destroy()


def test_code_required_login_does_not_open_browser_automatically():
    root = build_test_root()
    original_open = main_window_module.webbrowser.open
    calls: list[str] = []
    try:
        main_window_module.webbrowser.open = lambda url: calls.append(url) or True
        window = build_window(root)

        window._handle_login_result(
            {
                "message": "Open browser",
                "user_code": "ABC-123",
                "verification_uri": "https://example.test/device",
            }
        )

        assert calls == []
        assert "Code" in window.status_var.get()
    finally:
        main_window_module.webbrowser.open = original_open
        root.destroy()


def test_refresh_sidebar_preserves_manual_collapse_when_choices_do_not_change():
    root = build_test_root()
    try:
        window = build_window(root)
        window._refresh_sidebar()
        window.left_tree.item("notebook-1", open=False)

        window._refresh_sidebar()

        assert window.left_tree.item("notebook-1", "open") in (False, 0)
    finally:
        root.destroy()


def test_drain_work_queue_without_work_does_not_force_row_refresh():
    root = build_test_root()
    try:
        window = build_window(root)
        refresh_calls = {"count": 0}

        def fake_refresh_rows():
            refresh_calls["count"] += 1

        window._refresh_rows = fake_refresh_rows  # type: ignore[method-assign]
        window._drain_work_queue()

        assert refresh_calls["count"] == 0
    finally:
        root.destroy()


def test_visible_labels_do_not_show_technical_ids():
    root = build_test_root()
    try:
        build_window(root)

        assert "(nb-" not in " ".join(widget_texts(root, ttk.Label))
        assert "(sec-" not in " ".join(widget_texts(root, ttk.Label))
    finally:
        root.destroy()
