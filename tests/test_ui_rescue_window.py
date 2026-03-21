from __future__ import annotations

import tkinter as tk
from tkinter import ttk

from gui.controller import MainController
from gui.main_window import MainWindow


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
        build_window(root)

        assert widget_texts(root, ttk.Label).count("Notebook") >= 1
        assert "Abschnitt exportieren" in widget_texts(root, ttk.Button)
        assert "Aufbereitetes JSON importieren" in widget_texts(root, ttk.Button)
    finally:
        root.destroy()


def test_login_code_is_rendered_in_copyable_field():
    root = build_test_root()
    try:
        window = build_window(root)

        assert window.login_code_entry.cget("state") == "readonly"
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
