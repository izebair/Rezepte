from __future__ import annotations

import os
import queue
import re
import threading
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, ttk
import webbrowser
from typing import Any

from .controller import MainController

TECHNICAL_SUFFIX_RE = re.compile(r"\s*\(([^()]*-[^()]*)\)$")


def _strip_technical_suffix(text: str | None) -> str:
    value = (text or "").strip()
    if not value:
        return ""
    return TECHNICAL_SUFFIX_RE.sub("", value).strip()


def _split_source_label(text: str | None) -> tuple[str, str]:
    cleaned = (text or "").strip()
    if " / " in cleaned:
        notebook, section = cleaned.split(" / ", 1)
        notebook = _strip_technical_suffix(notebook.strip()) or "Notebook"
        section = _strip_technical_suffix(section.strip()) or cleaned
        return notebook, section
    return "Notebook", _strip_technical_suffix(cleaned) or ""


class MainWindow:
    def __init__(
        self,
        root: tk.Tk,
        controller: MainController,
        *,
        auto_login: bool = True,
        poll_work_queue: bool = True,
    ):
        self.root = root
        self.controller = controller
        self._work_queue: queue.Queue[tuple[str, object]] = queue.Queue()
        self._selected_row_id: str | None = None
        self._tree_label_by_item: dict[str, str] = {}
        self._target_choice_by_display: dict[str, str] = {}
        self._sidebar_signature: tuple[str, ...] = ()
        self._poll_work_queue = poll_work_queue
        self._build_ui()
        self._sync_state_controls()
        self._refresh_rows()
        if auto_login:
            self._set_status("OneNote-Anmeldung wird gestartet ...")
            self._run_background(self.controller.request_login, self._handle_login_result)
        if self._poll_work_queue:
            self.root.after(100, self._drain_work_queue)

    def run(self):
        self.root.mainloop()

    def _build_ui(self) -> None:
        self.root.title("OneNote Migration UI Rescue")
        self.root.geometry("1280x760")

        shell = ttk.Frame(self.root, padding=12)
        shell.pack(fill="both", expand=True)

        paned = ttk.PanedWindow(shell, orient="horizontal")
        paned.pack(fill="both", expand=True)

        left_panel = ttk.Frame(paned, padding=(0, 0, 10, 0))
        right_panel = ttk.Frame(paned)
        paned.add(left_panel, weight=1)
        paned.add(right_panel, weight=3)

        self.notebook_header = ttk.Label(left_panel, text="Notebook")
        self.notebook_header.pack(anchor="w")
        self.sections_header = ttk.Label(left_panel, text="Abschnitte")
        self.sections_header.pack(anchor="w", pady=(0, 8))

        left_tree_frame = ttk.Frame(left_panel)
        left_tree_frame.pack(fill="both", expand=True)
        self.left_tree = ttk.Treeview(left_tree_frame, show="tree", selectmode="browse", height=18)
        left_tree_scrollbar = ttk.Scrollbar(left_tree_frame, orient="vertical", command=self.left_tree.yview)
        self.left_tree.configure(yscrollcommand=left_tree_scrollbar.set)
        self.left_tree.pack(side="left", fill="both", expand=True)
        left_tree_scrollbar.pack(side="right", fill="y")
        self.left_tree.bind("<<TreeviewSelect>>", self._on_left_tree_selected)

        status_header = ttk.Frame(right_panel)
        status_header.pack(fill="x")

        self.auth_state_var = tk.StringVar(value="Anmeldung: disconnected")
        self.source_scope_var = tk.StringVar(value="Quellabschnitt: nicht gewählt")
        self.target_scope_var = tk.StringVar(value="Zielnotebook: nicht gewählt")
        self.login_message_var = tk.StringVar(value="Login: nicht gestartet")
        self.login_code_var = tk.StringVar(value="")
        self.login_uri_var = tk.StringVar(value="")
        self.export_context_var = tk.StringVar(value="Kein Export aktiv")
        self.export_files_var = tk.StringVar(value="Erzeugt bei Export: section_export.md, import_prompt.md, images, metadata.json")
        self.import_summary_var = tk.StringVar(value="Noch keine JSON-Aufbereitung importiert")
        self.flow_state_var = tk.StringVar(value="Schritt 1 von 4: Quelle waehlen")
        self.row_summary_var = tk.StringVar(value="Keine Eintraege geladen")
        self.detail_source_var = tk.StringVar(value="Quelle: kein Eintrag ausgewaehlt")
        self.detail_target_var = tk.StringVar(value="Ziel: -")
        self.detail_status_var = tk.StringVar(value="Status: -")
        self.detail_action_var = tk.StringVar(value="Aktion: -")
        self.status_var = tk.StringVar(value="Bereit")

        ttk.Label(status_header, textvariable=self.auth_state_var).pack(anchor="w")
        ttk.Label(status_header, textvariable=self.source_scope_var).pack(anchor="w")
        ttk.Label(status_header, textvariable=self.target_scope_var).pack(anchor="w")

        target_row = ttk.Frame(right_panel)
        target_row.pack(fill="x", pady=(10, 0))
        ttk.Label(target_row, text="Zielnotebook").pack(side="left")
        self.target_choice_var = tk.StringVar(value="")
        self.target_combo = ttk.Combobox(target_row, textvariable=self.target_choice_var, state="readonly", width=40)
        self.target_combo.pack(side="left", padx=(8, 0))
        self.target_combo.bind("<<ComboboxSelected>>", self._on_target_choice_changed)

        login_card = ttk.LabelFrame(right_panel, text="Anmeldung", padding=10)
        login_card.pack(fill="x", pady=(10, 0))
        login_card.columnconfigure(1, weight=1)
        ttk.Label(login_card, textvariable=self.login_message_var).grid(row=0, column=0, columnspan=2, sticky="w")
        ttk.Label(login_card, text="Login-Code").grid(row=1, column=0, sticky="w", pady=(8, 0))
        self.login_code_entry = ttk.Entry(login_card, textvariable=self.login_code_var, state="readonly", width=26)
        self.login_code_entry.grid(row=1, column=1, sticky="w", padx=(8, 0), pady=(8, 0))
        self.copy_code_button = ttk.Button(login_card, text="Code kopieren", command=self._copy_login_code)
        self.copy_code_button.grid(row=1, column=2, padx=(8, 0), pady=(8, 0), sticky="w")
        self.open_browser_button = ttk.Button(login_card, text="Browser öffnen", command=self._open_login_uri)
        self.open_browser_button.grid(row=1, column=3, padx=(8, 0), pady=(8, 0), sticky="w")
        self.retry_login_button = ttk.Button(login_card, text="Erneut anmelden", command=self._on_retry_login)
        self.retry_login_button.grid(row=1, column=4, padx=(8, 0), pady=(8, 0), sticky="w")
        ttk.Label(login_card, textvariable=self.login_uri_var).grid(row=2, column=0, columnspan=5, sticky="w", pady=(8, 0))

        action_row = ttk.Frame(right_panel)
        action_row.pack(fill="x", pady=(10, 0))
        filter_row = ttk.Frame(action_row)
        filter_row.pack(side="left")
        ttk.Label(filter_row, text="Statusfilter").pack(side="left")
        self.status_filter_var = tk.StringVar(value="Alle")
        self.status_filter_combo = ttk.Combobox(
            filter_row,
            textvariable=self.status_filter_var,
            state="readonly",
            width=18,
            values=["Alle", "Roh", "Bereit", "Fehlt noch", "Duplikat", "Migrationsfehler", "Migriert"],
        )
        self.status_filter_combo.pack(side="left", padx=(8, 0))
        self.status_filter_combo.bind("<<ComboboxSelected>>", self._on_status_filter_changed)
        buttons = ttk.Frame(action_row)
        buttons.pack(side="right")
        self.export_button = ttk.Button(buttons, text="Abschnitt exportieren", command=self._on_export_section)
        self.export_button.pack(side="left")
        self.import_button = ttk.Button(
            buttons,
            text="Aufbereitetes JSON importieren",
            command=self._on_import_json,
        )
        self.import_button.pack(side="left", padx=(8, 0))
        self.select_all_button = ttk.Button(buttons, text="Alle auswählen", command=self._on_select_all)
        self.select_all_button.pack(side="left", padx=(8, 0))
        self.reset_failed_button = ttk.Button(
            buttons,
            text="Fehlgeschlagene zurücksetzen",
            command=self._on_reset_failed,
        )
        self.reset_failed_button.pack(side="left", padx=(8, 0))
        self.migrate_button = ttk.Button(buttons, text="Migration starten", command=self._on_execute)
        self.migrate_button.pack(side="left", padx=(8, 0))

        context_card = ttk.LabelFrame(right_panel, text="Export und Aufbereitung", padding=10)
        context_card.pack(fill="x", pady=(10, 0))
        ttk.Label(context_card, textvariable=self.flow_state_var).pack(anchor="w")
        ttk.Label(context_card, textvariable=self.export_context_var).pack(anchor="w")
        ttk.Label(context_card, textvariable=self.export_files_var).pack(anchor="w", pady=(4, 0))
        ttk.Label(context_card, textvariable=self.import_summary_var).pack(anchor="w", pady=(4, 0))
        context_actions = ttk.Frame(context_card)
        context_actions.pack(anchor="w", pady=(8, 0))
        self.open_export_button = ttk.Button(context_actions, text="Export-Ordner öffnen", command=self._open_export_folder)
        self.open_export_button.pack(side="left")
        self.copy_export_path_button = ttk.Button(context_actions, text="Pfad kopieren", command=self._copy_export_path)
        self.copy_export_path_button.pack(side="left", padx=(8, 0))
        self.open_prompt_button = ttk.Button(context_actions, text="Prompt öffnen", command=self._open_import_prompt)
        self.open_prompt_button.pack(side="left", padx=(8, 0))
        self.copy_prompt_button = ttk.Button(context_actions, text="Prompt kopieren", command=self._copy_import_prompt)
        self.copy_prompt_button.pack(side="left", padx=(8, 0))
        quick_filter_row = ttk.Frame(context_card)
        quick_filter_row.pack(anchor="w", pady=(8, 0))
        ttk.Label(quick_filter_row, text="Schnellfilter").pack(side="left")
        ttk.Button(quick_filter_row, text="Nur bereit", command=lambda: self._apply_quick_filter("Bereit")).pack(side="left", padx=(8, 0))
        ttk.Button(quick_filter_row, text="Fehlt noch", command=lambda: self._apply_quick_filter("Fehlt noch")).pack(side="left", padx=(8, 0))
        ttk.Button(quick_filter_row, text="Duplikate", command=lambda: self._apply_quick_filter("Duplikat")).pack(side="left", padx=(8, 0))
        ttk.Button(quick_filter_row, text="Fehler", command=lambda: self._apply_quick_filter("Migrationsfehler")).pack(side="left", padx=(8, 0))

        rows_card = ttk.LabelFrame(right_panel, text="Aufbereitung", padding=10)
        rows_card.pack(fill="both", expand=True, pady=(10, 0))
        ttk.Label(rows_card, textvariable=self.row_summary_var).pack(anchor="w", pady=(0, 8))

        columns = ("selected", "source", "target", "status", "action")
        self.tree = ttk.Treeview(rows_card, columns=columns, show="headings", selectmode="browse", height=18)
        self.tree.heading("selected", text="Auswahl")
        self.tree.heading("source", text="Quelle")
        self.tree.heading("target", text="Ziel")
        self.tree.heading("status", text="Status")
        self.tree.heading("action", text="Aktion")
        self.tree.column("selected", width=80, anchor="center")
        self.tree.column("source", width=360)
        self.tree.column("target", width=280)
        self.tree.column("status", width=120, anchor="center")
        self.tree.column("action", width=280)
        self.tree.pack(fill="both", expand=True)
        self.tree.bind("<ButtonRelease-1>", self._on_tree_click)
        detail_card = ttk.LabelFrame(rows_card, text="Ausgewaehlter Eintrag", padding=10)
        detail_card.pack(fill="x", pady=(10, 0))
        ttk.Label(detail_card, textvariable=self.detail_source_var).pack(anchor="w")
        ttk.Label(detail_card, textvariable=self.detail_target_var).pack(anchor="w", pady=(4, 0))
        ttk.Label(detail_card, textvariable=self.detail_status_var).pack(anchor="w", pady=(4, 0))
        ttk.Label(detail_card, textvariable=self.detail_action_var).pack(anchor="w", pady=(4, 0))

        ttk.Label(right_panel, textvariable=self.status_var).pack(fill="x", pady=(8, 0))

    def _refresh_sidebar(self) -> None:
        signature = tuple(
            str(choice.get("label") or "").strip()
            for choice in getattr(self.controller, "source_choices", [])
            if isinstance(choice, dict)
        )
        if signature == self._sidebar_signature:
            return
        self._sidebar_signature = signature
        for row_id in self.left_tree.get_children():
            self.left_tree.delete(row_id)
        self._tree_label_by_item.clear()

        notebooks: dict[str, str] = {}
        notebook_item_ids: dict[str, str] = {}

        for choice in getattr(self.controller, "source_choices", []):
            if not isinstance(choice, dict):
                continue
            raw_label = str(choice.get("label") or "").strip()
            if not raw_label:
                continue

            notebook_label, section_label = _split_source_label(raw_label)
            notebook_item_id = notebooks.get(notebook_label)
            if notebook_item_id is None:
                notebook_item_id = f"notebook-{len(notebooks) + 1}"
                notebooks[notebook_label] = notebook_item_id
                notebook_item_ids[notebook_label] = notebook_item_id
                self.left_tree.insert("", "end", iid=notebook_item_id, text=notebook_label, open=True)

            section_item_id = f"{notebook_item_ids[notebook_label]}-section-{len(self.left_tree.get_children(notebook_item_ids[notebook_label])) + 1}"
            self.left_tree.insert(
                notebook_item_ids[notebook_label],
                "end",
                iid=section_item_id,
                text=section_label,
            )
            self._tree_label_by_item[section_item_id] = raw_label

    def _refresh_rows(self) -> None:
        for row_id in self.tree.get_children():
            self.tree.delete(row_id)

        if self.controller.rows:
            for item in self.controller.get_visible_rows():
                row_id = str(item.get("source_page_id") or "")
                self.tree.insert(
                    "",
                    "end",
                    iid=row_id,
                    values=(
                        "ja" if item.get("selected") else "nein",
                        str(item.get("source_page_title") or ""),
                        str(item.get("target_subcategory") or item.get("target_label") or ""),
                        str(item.get("status") or ""),
                        str(item.get("action_label") or item.get("import_state") or ""),
                    ),
                )
        else:
            for item in self.controller.get_visible_items():
                selected = "ja" if item.selected else "nein"
                messages = "; ".join(item.messages)
                self.tree.insert(
                    "",
                    "end",
                    iid=item.source_page_id,
                    values=(
                        selected,
                        item.source_page_title,
                        item.planned_target_path,
                        item.status,
                        messages,
                    ),
                )

        if self._selected_row_id in self.tree.get_children():
            self.tree.selection_set(self._selected_row_id)
            self.tree.focus(self._selected_row_id)
            self._show_row_details(self._selected_row_id)
        else:
            self._clear_row_details()
        self._sync_state_controls()

    def _sync_state_controls(self) -> None:
        self.auth_state_var.set(f"Anmeldung: {self.controller.auth_state}")
        self.source_scope_var.set(f"Quellabschnitt: {self._clean_scope_label(self.controller.selected_source_choice)}")
        self.target_scope_var.set(f"Zielnotebook: {self._clean_scope_label(self.controller.selected_target_choice)}")

        login_message = self.controller.login_message.strip()
        login_code = self.controller.login_code.strip()
        login_uri = self.controller.login_uri.strip()
        self.login_message_var.set(f"Login: {login_message or 'nicht gestartet'}")
        self.login_code_var.set(login_code)
        self.login_uri_var.set(login_uri)
        export_context = getattr(self.controller, "active_export_context", None)
        total_rows = len(self.controller.rows)
        if total_rows == 0:
            self.row_summary_var.set("Keine Eintraege geladen")
        else:
            selected_count = sum(1 for row in self.controller.rows if bool(row.get("selected")))
            ready_count = sum(1 for row in self.controller.rows if str(row.get("status") or "") == "Bereit")
            missing_count = sum(1 for row in self.controller.rows if str(row.get("status") or "") == "Fehlt noch")
            failed_count = sum(1 for row in self.controller.rows if str(row.get("status") or "") == "Migrationsfehler")
            self.row_summary_var.set(
                f"{total_rows} Eintraege, {selected_count} ausgewaehlt, {ready_count} bereit, {missing_count} fehlt, {failed_count} Fehler"
            )
        if export_context is None:
            if self.controller.source_scope is None:
                self.flow_state_var.set("Schritt 1 von 4: Quelle waehlen")
            else:
                self.flow_state_var.set("Schritt 2 von 4: Abschnitt exportieren")
            self.export_context_var.set("Kein Export aktiv")
            self.export_files_var.set("Erzeugt bei Export: section_export.md, import_prompt.md, images, metadata.json")
            self.import_summary_var.set("Noch keine JSON-Aufbereitung importiert")
        else:
            export_root = str(getattr(export_context, "export_root", "") or "").strip()
            export_run_id = str(getattr(export_context, "export_run_id", "") or "").strip()
            source_section_name = str(getattr(export_context, "source_section_name", "") or "").strip()
            self.export_context_var.set(
                f"Aktiver Export: {source_section_name or 'unbekannter Abschnitt'} | Lauf: {export_run_id or 'unbekannt'} | Ordner: {export_root or 'unbekannt'}"
            )
            self.export_files_var.set("Dateien: section_export.md, import_prompt.md, images, metadata.json")
            ready_count = sum(1 for row in self.controller.rows if str(row.get('status') or '') == "Bereit")
            missing_count = sum(1 for row in self.controller.rows if str(row.get('status') or '') == "Fehlt noch")
            duplicate_count = sum(1 for row in self.controller.rows if str(row.get('status') or '') == "Duplikat")
            migrated_count = sum(1 for row in self.controller.rows if str(row.get('status') or '') == "Migriert")
            if not self.controller.rows:
                self.flow_state_var.set("Schritt 3 von 4: JSON importieren")
                self.import_summary_var.set("Export bereit. Jetzt JSON extern aufbereiten und importieren.")
            else:
                parts: list[str] = []
                if ready_count:
                    parts.append(f"{ready_count} bereit")
                if missing_count:
                    parts.append(f"{missing_count} fehlt noch")
                if duplicate_count:
                    parts.append(f"{duplicate_count} Duplikat")
                if migrated_count:
                    parts.append(f"{migrated_count} migriert")
                if ready_count:
                    self.flow_state_var.set("Schritt 4 von 4: Migration starten")
                else:
                    self.flow_state_var.set("Schritt 3 von 4: JSON pruefen und vervollstaendigen")
                self.import_summary_var.set("Aufbereitung: " + (", ".join(parts) if parts else "noch keine importierten Ergebnisse"))
        has_export_root = bool(str(getattr(export_context, "export_root", "") or "").strip()) if export_context is not None else False
        self._target_choice_by_display = {
            self._clean_scope_label(str(choice.get("label") or "")): str(choice.get("label") or "")
            for choice in self.controller.target_choices
            if isinstance(choice, dict)
        }
        self.target_combo["values"] = list(self._target_choice_by_display.keys())
        self.target_choice_var.set(self._clean_scope_label(self.controller.selected_target_choice))
        self.status_filter_var.set(self.controller.status_filter or "Alle")

        self._refresh_sidebar()

        export_ready = self.controller.can_load_source_tree() and self.controller.source_scope is not None
        import_ready = self.controller.active_export_run_id is not None and bool(self.controller.rows)
        self._set_button_state(self.export_button, export_ready and self._has_callable_action(("request_section_export", "export_section")))
        self._set_button_state(self.import_button, import_ready and self._has_callable_action(("request_json_import", "import_json")))
        has_selectable_rows = any(bool(row.get("selectable")) for row in self.controller.rows)
        retry_ready = self.controller.login_banner_state == "error" or self.controller.auth_state in {"disconnected", "error"}
        has_failed_rows = any(str(row.get("status") or "") == "Migrationsfehler" for row in self.controller.rows)
        self._set_button_state(self.open_export_button, has_export_root)
        self._set_button_state(self.copy_export_path_button, has_export_root)
        self._set_button_state(self.open_prompt_button, has_export_root)
        self._set_button_state(self.copy_prompt_button, has_export_root)
        self._set_button_state(self.select_all_button, has_selectable_rows and callable(getattr(self.controller, "select_all", None)))
        self._set_button_state(self.retry_login_button, retry_ready and self._has_callable_action(("retry_login", "request_login")))
        self._set_button_state(self.reset_failed_button, has_failed_rows and callable(getattr(self.controller, "reset_failed_rows", None)))
        self._set_button_state(self.migrate_button, self.controller.can_execute())
        self._set_button_state(self.copy_code_button, bool(login_code))
        self._set_button_state(self.open_browser_button, bool(login_uri))

    def _set_button_state(self, button: ttk.Button, enabled: bool) -> None:
        button.state(["!disabled"] if enabled else ["disabled"])

    def _has_callable_action(self, names: tuple[str, ...]) -> bool:
        for name in names:
            action = getattr(self.controller, name, None)
            if callable(action):
                return True
        return False

    def _clean_scope_label(self, label: str | None) -> str:
        value = (label or "").strip()
        if " / " in value:
            return " / ".join(part for part in (_strip_technical_suffix(part.strip()) for part in value.split(" / ")) if part) or "nicht gewählt"
        cleaned = _strip_technical_suffix(value)
        return cleaned or "nicht gewählt"

    def _run_background(self, task, on_success=None) -> None:
        def worker() -> None:
            try:
                result = task()
                self._work_queue.put(("success", (result, on_success)))
            except Exception as exc:  # pragma: no cover - defensive UI guard
                self._work_queue.put(("error", exc))

        threading.Thread(target=worker, daemon=True).start()

    def _drain_work_queue(self) -> None:
        refreshed = False
        try:
            while True:
                kind, payload = self._work_queue.get_nowait()
                if kind == "success":
                    result, on_success = payload
                    if callable(on_success):
                        on_success(result)
                else:
                    self._set_status(f"Operation failed: {payload}")
                refreshed = True
        except queue.Empty:
            pass
        finally:
            if refreshed:
                self._refresh_rows()
            if self._poll_work_queue:
                self.root.after(100, self._drain_work_queue)

    def _set_status(self, message: str) -> None:
        self.status_var.set(message)

    def _on_export_section(self) -> None:
        action = self._resolve_action(("request_section_export", "export_section"))
        if action is None:
            self._set_status("Abschnittsexport ist noch nicht verdrahtet")
            return
        self._set_status("Abschnitt wird exportiert ...")
        self._run_background(action, self._handle_generic_action_result)

    def _on_import_json(self) -> None:
        action = getattr(self.controller, "request_json_import", None)
        if not callable(action):
            self._set_status("JSON-Import ist noch nicht verdrahtet")
            return
        payload_path = filedialog.askopenfilename(
            title="Aufbereitetes JSON auswählen",
            filetypes=[("JSON-Dateien", "*.json"), ("Alle Dateien", "*.*")],
        )
        if not payload_path:
            self._set_status("JSON-Import abgebrochen")
            return
        self._set_status("JSON wird importiert ...")
        self._run_background(lambda: action(payload_path), self._handle_generic_action_result)

    def _on_execute(self) -> None:
        if not self.controller.can_execute():
            self._set_status(self.controller.get_execute_block_reason() or "Execute blocked")
            self._sync_state_controls()
            return
        self._set_status("Migration wird gestartet ...")
        self._run_background(self.controller.request_execute, self._handle_session_loaded)

    def _on_retry_login(self) -> None:
        action = self._resolve_action(("retry_login", "request_login"))
        if action is None:
            self._set_status("Anmeldung kann nicht erneut gestartet werden")
            return
        self._set_status("OneNote-Anmeldung wird erneut gestartet ...")
        self._run_background(action, self._handle_login_result)

    def _on_reset_failed(self) -> None:
        action = getattr(self.controller, "reset_failed_rows", None)
        if not callable(action):
            self._set_status("Fehlgeschlagene Einträge können nicht zurückgesetzt werden")
            return
        failed_before = sum(1 for row in self.controller.rows if str(row.get("status") or "") == "Migrationsfehler")
        reset_rows = action()
        failed_after = sum(1 for row in reset_rows if str(row.get("status") or "") == "Migrationsfehler")
        reset_count = max(failed_before - failed_after, 0)
        self._set_status(f"Fehlgeschlagene Einträge zurückgesetzt: {reset_count}")
        self._refresh_rows()

    def _on_select_all(self) -> None:
        action = getattr(self.controller, "select_all", None)
        if not callable(action):
            self._set_status("Auswahl kann nicht gesammelt gesetzt werden")
            return
        action()
        self._set_status("Alle bereiten Einträge ausgewählt")
        self._refresh_rows()

    def _resolve_action(self, names: tuple[str, ...]):
        for name in names:
            action = getattr(self.controller, name, None)
            if callable(action):
                return action
        return None

    def _handle_generic_action_result(self, result: object) -> None:
        if result is None and getattr(self.controller, "last_error", None):
            self._set_status(str(self.controller.last_error))
        elif hasattr(result, "export_root"):
            self._set_status(f"Export erstellt: {getattr(result, 'export_root', '')}. Ordner und Prompt sind jetzt verfügbar.")
        elif isinstance(result, list) and self.controller.rows:
            if self.controller.active_export_run_id is not None and any("status" in row for row in self.controller.rows):
                self._set_status(f"JSON importiert: {len(result)} Einträge abgeglichen")
            else:
                self._set_status(f"{len(result)} Quellseiten geladen")
        elif isinstance(result, list) and self.controller.source_choices:
            self._set_status("Notebooks und Abschnitte geladen")
        elif result is None:
            self._set_status("Aktion abgeschlossen")
        else:
            self._set_status("Aktion abgeschlossen")
        self._refresh_rows()

    def _on_left_tree_selected(self, _event: object) -> None:
        row_id = self.left_tree.focus()
        if not row_id:
            return
        choice_label = self._tree_label_by_item.get(row_id)
        if not choice_label:
            return
        if self.controller.set_source_choice(choice_label):
            self._set_status("Abschnitt ausgewählt")
            self._run_background(self.controller.request_section_rows, self._handle_generic_action_result)
        else:
            self._set_status("Abschnitt konnte nicht ausgewählt werden")
        self._sync_state_controls()

    def _on_target_choice_changed(self, _event: object) -> None:
        display_label = self.target_choice_var.get()
        raw_label = self._target_choice_by_display.get(display_label)
        if raw_label and self.controller.set_target_choice(raw_label):
            self._set_status("Zielnotebook ausgewählt")
        else:
            self._set_status("Zielnotebook konnte nicht ausgewählt werden")
        self._sync_state_controls()

    def _on_status_filter_changed(self, _event: object) -> None:
        selected_filter = self.status_filter_var.get().strip()
        self.controller.set_status_filter(None if selected_filter == "Alle" else selected_filter)
        self._set_status("Statusfilter aktualisiert")
        self._refresh_rows()

    def _apply_quick_filter(self, status: str) -> None:
        self.controller.set_status_filter(status)
        self.status_filter_var.set(status)
        self._set_status("Statusfilter aktualisiert")
        self._refresh_rows()

    def _on_tree_click(self, event: tk.Event) -> None:
        row_id = self.tree.identify_row(event.y)
        if not row_id:
            return
        self._handle_row_interaction(row_id, self.tree.identify_column(event.x))
        self._refresh_rows()

    def _handle_row_interaction(self, row_id: str, column_id: str) -> None:
        self._selected_row_id = row_id
        toggled = False
        if column_id == "#1":
            if self.controller.rows:
                for row in self.controller.rows:
                    if row.get("source_page_id") == row_id and row.get("selectable"):
                        row["selected"] = not bool(row.get("selected"))
                        toggled = True
                        break
            elif self.controller.toggle_row_selection(row_id):
                toggled = True
        self._show_row_details(row_id)
        self._set_status("Zeilenauswahl aktualisiert" if toggled else "Eintrag ausgewaehlt")

    def _show_row_details(self, row_id: str) -> None:
        row = None
        for item in self.controller.rows:
            if str(item.get("source_page_id") or "") == row_id:
                row = item
                break
        if row is None:
            self._clear_row_details()
            return
        self.detail_source_var.set(f"Quelle: {str(row.get('source_page_title') or '').strip() or row_id}")
        self.detail_target_var.set(
            f"Ziel: {str(row.get('target_subcategory') or row.get('target_label') or '').strip() or '-'}"
        )
        self.detail_status_var.set(f"Status: {str(row.get('status') or '').strip() or '-'}")
        self.detail_action_var.set(
            f"Aktion: {str(row.get('action_label') or row.get('import_state') or '').strip() or '-'}"
        )

    def _clear_row_details(self) -> None:
        self.detail_source_var.set("Quelle: kein Eintrag ausgewaehlt")
        self.detail_target_var.set("Ziel: -")
        self.detail_status_var.set("Status: -")
        self.detail_action_var.set("Aktion: -")

    def _handle_session_loaded(self, session: object) -> None:
        if session is None:
            self._set_status(getattr(self.controller, "last_error", None) or "Operation failed")
        elif isinstance(session, list):
            migrated = sum(1 for row in session if str(row.get("status") or "") == "Migriert")
            failed = sum(1 for row in session if str(row.get("status") or "") == "Migrationsfehler")
            duplicates = sum(1 for row in session if str(row.get("status") or "") == "Duplikat")
            self._set_status(f"Migration beendet: {migrated} migriert, {duplicates} Duplikate, {failed} Fehler")
        else:
            self._set_status("Sitzung geladen")
        self._refresh_rows()

    def _handle_login_result(self, result: object) -> None:
        if isinstance(result, dict) and str(result.get("access_token") or "").strip():
            self._set_status("OneNote-Anmeldung erfolgreich, Notebooks werden geladen ...")
            self._run_background(self.controller.request_source_load, self._handle_generic_action_result)
        elif isinstance(result, dict) and (
            str(result.get("user_code") or "").strip()
            or str(result.get("verification_uri") or "").strip()
            or str(result.get("message") or "").strip()
        ):
            self._set_status("Code kopieren, Browser per Button öffnen und dann Microsoft-Anmeldung abschließen.")
            self._run_background(self.controller.complete_login, self._handle_login_result)
        else:
            self._set_status(getattr(self.controller, "last_error", None) or "OneNote-Anmeldung nicht abgeschlossen")
        self._sync_state_controls()

    def _copy_login_code(self) -> None:
        code = self.login_code_var.get().strip()
        if not code:
            return
        self.root.clipboard_clear()
        self.root.clipboard_append(code)
        self._set_status("Login-Code kopiert")

    def _open_login_uri(self) -> None:
        verification_uri = self.login_uri_var.get().strip()
        if not verification_uri:
            return
        try:
            webbrowser.open(verification_uri)
            self._set_status("Browser geöffnet")
        except Exception:
            self._set_status("Browser konnte nicht geöffnet werden")

    def _copy_export_path(self) -> None:
        export_context = getattr(self.controller, "active_export_context", None)
        export_root = str(getattr(export_context, "export_root", "") or "").strip()
        if not export_root:
            self._set_status("Kein Export-Ordner verfügbar")
            return
        self.root.clipboard_clear()
        self.root.clipboard_append(export_root)
        self._set_status("Export-Pfad kopiert")

    def _open_export_folder(self) -> None:
        export_context = getattr(self.controller, "active_export_context", None)
        export_root = str(getattr(export_context, "export_root", "") or "").strip()
        if not export_root:
            self._set_status("Kein Export-Ordner verfügbar")
            return
        try:
            os.startfile(export_root)
            self._set_status("Export-Ordner geöffnet")
        except Exception:
            self._set_status("Export-Ordner konnte nicht geöffnet werden")

    def _copy_import_prompt(self) -> None:
        export_context = getattr(self.controller, "active_export_context", None)
        export_root = str(getattr(export_context, "export_root", "") or "").strip()
        if not export_root:
            self._set_status("Kein Export-Ordner verfügbar")
            return
        prompt_path = os.path.join(export_root, "import_prompt.md")
        try:
            prompt_text = Path(prompt_path).read_text(encoding="utf-8")
        except Exception:
            self._set_status("Prompt konnte nicht gelesen werden")
            return
        self.root.clipboard_clear()
        self.root.clipboard_append(prompt_text)
        self._set_status("Prompt kopiert")

    def _open_import_prompt(self) -> None:
        export_context = getattr(self.controller, "active_export_context", None)
        export_root = str(getattr(export_context, "export_root", "") or "").strip()
        if not export_root:
            self._set_status("Kein Export-Ordner verfügbar")
            return
        prompt_path = os.path.join(export_root, "import_prompt.md")
        if not os.path.exists(prompt_path):
            self._set_status("Prompt-Datei fehlt")
            return
        try:
            os.startfile(prompt_path)
            self._set_status("Prompt geöffnet")
        except Exception:
            self._set_status("Prompt konnte nicht geöffnet werden")


class _PlaceholderImportService:
    def run_dry_run(self, source_scope, target_scope):  # pragma: no cover - UI placeholder
        raise NotImplementedError("Dry run service wiring is not configured yet")

    def run_execute(self, session):  # pragma: no cover - UI placeholder
        raise NotImplementedError("Execute service wiring is not configured yet")

    def request_login(self):  # pragma: no cover - UI placeholder
        return None

    def complete_login(self, flow=None):  # pragma: no cover - UI placeholder
        return None

    def request_source_load(self):  # pragma: no cover - UI placeholder
        return None


def run_app(import_service=None):
    root = tk.Tk()
    controller = MainController(import_service=import_service or _PlaceholderImportService())
    MainWindow(root, controller).run()
