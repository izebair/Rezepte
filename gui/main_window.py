from __future__ import annotations

import queue
import threading
import tkinter as tk
from tkinter import ttk
import webbrowser

from .controller import MainController


class MainWindow:
    def __init__(self, root: tk.Tk, controller: MainController):
        self.root = root
        self.controller = controller
        self._work_queue: queue.Queue[tuple[str, object]] = queue.Queue()
        self._selected_row_id: str | None = None
        self._build_ui()
        self._refresh_rows()
        self.root.after(100, self._drain_work_queue)

    def run(self):
        self.root.mainloop()

    def _build_ui(self):
        self.root.title("OneNote Migration MVP")
        self.root.geometry("1200x720")

        outer = ttk.Frame(self.root, padding=12)
        outer.pack(fill="both", expand=True)

        strip = ttk.LabelFrame(outer, text="State & Selection", padding=10)
        strip.pack(fill="x")

        self.auth_state_var = tk.StringVar(value="Auth: disconnected")
        self.source_state_var = tk.StringVar(value="Source: not loaded")
        self.target_state_var = tk.StringVar(value="Target: not selected")
        self.login_message_var = tk.StringVar(value="Login: not started")
        self.login_code_var = tk.StringVar(value="")
        self.login_uri_var = tk.StringVar(value="")
        self.dry_run_gate_var = tk.StringVar(value="Dry Run: blocked")
        self.execute_gate_var = tk.StringVar(value="Execute: blocked")
        self.source_choice_var = tk.StringVar(value="")
        self.target_choice_var = tk.StringVar(value="")

        status_row = ttk.Frame(strip)
        status_row.pack(fill="x")
        ttk.Label(status_row, textvariable=self.auth_state_var).pack(side="left")
        ttk.Label(status_row, textvariable=self.source_state_var, padding=(18, 0, 0, 0)).pack(side="left")
        ttk.Label(status_row, textvariable=self.target_state_var, padding=(18, 0, 0, 0)).pack(side="left")

        login_row = ttk.Frame(strip)
        login_row.pack(fill="x", pady=(8, 0))
        ttk.Label(login_row, textvariable=self.login_message_var).pack(side="left")
        ttk.Label(login_row, textvariable=self.login_code_var, padding=(18, 0, 0, 0)).pack(side="left")
        ttk.Label(login_row, textvariable=self.login_uri_var, padding=(18, 0, 0, 0)).pack(side="left")

        selection_row = ttk.Frame(strip)
        selection_row.pack(fill="x", pady=(8, 0))
        ttk.Label(selection_row, text="Source section").pack(side="left")
        self.source_combo = ttk.Combobox(selection_row, textvariable=self.source_choice_var, state="readonly", width=42)
        self.source_combo.pack(side="left", padx=(8, 16))
        self.source_combo.bind("<<ComboboxSelected>>", self._on_source_choice_changed)

        ttk.Label(selection_row, text="Target notebook").pack(side="left")
        self.target_combo = ttk.Combobox(selection_row, textvariable=self.target_choice_var, state="readonly", width=42)
        self.target_combo.pack(side="left", padx=(8, 16))
        self.target_combo.bind("<<ComboboxSelected>>", self._on_target_choice_changed)

        ttk.Button(selection_row, text="Login", command=self._on_login).pack(side="left")
        self.complete_login_button = ttk.Button(selection_row, text="Complete Login", command=self._on_complete_login)
        self.complete_login_button.pack(side="left", padx=(6, 0))
        ttk.Button(selection_row, text="Load Source", command=self._on_source_load).pack(side="left", padx=(6, 0))
        self.dry_run_button = ttk.Button(selection_row, text="Dry Run", command=self._on_dry_run)
        self.dry_run_button.pack(side="left", padx=(6, 0))
        ttk.Button(selection_row, text="Select All", command=self._on_select_all).pack(side="left", padx=(18, 0))
        ttk.Button(selection_row, text="Select None", command=self._on_select_none).pack(side="left", padx=(6, 0))
        self.execute_button = ttk.Button(selection_row, text="Execute", command=self._on_execute)
        self.execute_button.pack(side="left", padx=(18, 0))

        gate_row = ttk.Frame(strip)
        gate_row.pack(fill="x", pady=(8, 0))
        ttk.Label(gate_row, textvariable=self.dry_run_gate_var).pack(side="left")
        ttk.Label(gate_row, textvariable=self.execute_gate_var, padding=(18, 0, 0, 0)).pack(side="left")

        filter_frame = ttk.Frame(outer)
        filter_frame.pack(fill="x", pady=(12, 0))
        ttk.Label(filter_frame, text="Filter status:").pack(side="left")

        self.status_filter = tk.StringVar(value="all")
        filter_box = ttk.Combobox(
            filter_frame,
            textvariable=self.status_filter,
            state="readonly",
            values=("all", "ready", "duplicate", "error"),
            width=16,
        )
        filter_box.pack(side="left", padx=(8, 0))
        filter_box.bind("<<ComboboxSelected>>", self._on_filter_changed)

        columns = ("selected", "status", "title", "target", "messages")
        self.tree = ttk.Treeview(outer, columns=columns, show="headings", height=20, selectmode="browse")
        self.tree.heading("selected", text="Selected")
        self.tree.heading("status", text="Status")
        self.tree.heading("title", text="Source / Title")
        self.tree.heading("target", text="Planned Target")
        self.tree.heading("messages", text="Messages")
        self.tree.column("selected", width=80, anchor="center")
        self.tree.column("status", width=110, anchor="center")
        self.tree.column("title", width=320)
        self.tree.column("target", width=360)
        self.tree.column("messages", width=320)
        self.tree.pack(fill="both", expand=True, pady=(12, 0))
        self.tree.bind("<ButtonRelease-1>", self._on_tree_click)

        self.status_var = tk.StringVar(value="Ready")
        ttk.Label(outer, textvariable=self.status_var).pack(fill="x", pady=(8, 0))

    def _refresh_rows(self):
        for row_id in self.tree.get_children():
            self.tree.delete(row_id)

        for item in self.controller.get_visible_items():
            selected = "yes" if item.selected else "no"
            messages = "; ".join(item.messages)
            self.tree.insert(
                "",
                "end",
                iid=item.source_page_id,
                values=(
                    selected,
                    item.status,
                    f"{item.source_page_title} / {item.recognized_title}",
                    item.planned_target_path,
                    messages,
                ),
            )
        if self._selected_row_id in self.tree.get_children():
            self.tree.selection_set(self._selected_row_id)
            self.tree.focus(self._selected_row_id)
        self._sync_state_controls()

    def _set_status(self, message: str):
        self.status_var.set(message)

    def _sync_state_controls(self):
        self.auth_state_var.set(f"Auth: {self.controller.auth_state}")
        self.source_state_var.set(f"Source: {self.controller.selected_source_choice or 'not loaded'}")
        self.target_state_var.set(f"Target: {self.controller.selected_target_choice or 'not selected'}")
        pending_login = self.controller.pending_login_payload or {}
        login_message = str(pending_login.get("message") or "").strip()
        login_code = str(pending_login.get("user_code") or "").strip()
        login_uri = str(pending_login.get("verification_uri") or "").strip()
        self.login_message_var.set(f"Login: {login_message or 'not started'}")
        self.login_code_var.set(f"Code: {login_code}" if login_code else "")
        self.login_uri_var.set(f"URL: {login_uri}" if login_uri else "")

        source_labels = self.controller.get_source_choice_labels()
        target_labels = self.controller.get_target_choice_labels()
        self.source_combo["values"] = source_labels
        self.target_combo["values"] = target_labels

        if self.controller.selected_source_choice in source_labels:
            self.source_choice_var.set(self.controller.selected_source_choice or "")

        if self.controller.selected_target_choice in target_labels:
            self.target_choice_var.set(self.controller.selected_target_choice or "")

        dry_run_reason = self.controller.get_dry_run_block_reason()
        execute_reason = self.controller.get_execute_block_reason()
        self.dry_run_gate_var.set("Dry Run: ready" if dry_run_reason is None else f"Dry Run: blocked ({dry_run_reason})")
        self.execute_gate_var.set("Execute: ready" if execute_reason is None else f"Execute: blocked ({execute_reason})")
        self.complete_login_button.state(["!disabled"] if pending_login else ["disabled"])
        self.dry_run_button.state(["!disabled"] if dry_run_reason is None else ["disabled"])
        self.execute_button.state(["!disabled"] if execute_reason is None else ["disabled"])

    def _run_background(self, task, on_success=None):
        def worker():
            try:
                result = task()
                self._work_queue.put(("success", (result, on_success)))
            except Exception as exc:  # pragma: no cover - defensive UI guard
                self._work_queue.put(("error", exc))

        threading.Thread(target=worker, daemon=True).start()

    def _drain_work_queue(self):
        try:
            while True:
                kind, payload = self._work_queue.get_nowait()
                if kind == "success":
                    result, on_success = payload
                    if callable(on_success):
                        on_success(result)
                else:
                    self._set_status(f"Operation failed: {payload}")
        except queue.Empty:
            pass
        finally:
            self._refresh_rows()
            self.root.after(100, self._drain_work_queue)

    def _on_login(self):
        self._set_status("Starting OneNote login...")
        self._run_background(self.controller.request_login, self._handle_login_result)

    def _on_source_load(self):
        self._set_status("Loading source choices...")
        self._run_background(self.controller.request_source_load, self._handle_source_load_result)

    def _on_complete_login(self):
        if not self.controller.pending_login_payload:
            self._set_status("No pending login to complete")
            self._sync_state_controls()
            return
        self._set_status("Completing OneNote login...")
        self._run_background(self.controller.complete_login, self._handle_login_result)

    def _on_dry_run(self):
        if not self.controller.can_request_dry_run():
            self._set_status(self.controller.get_dry_run_block_reason() or "Dry run blocked")
            self._sync_state_controls()
            return
        self._set_status("Running dry run...")
        self._run_background(self.controller.request_dry_run, self._handle_session_loaded)

    def _on_select_all(self):
        self.controller.select_all()
        self._refresh_rows()

    def _on_select_none(self):
        self.controller.select_none()
        self._refresh_rows()

    def _on_execute(self):
        if not self.controller.can_execute():
            self._set_status(self.controller.get_execute_block_reason() or "Execute blocked")
            self._sync_state_controls()
            return
        self._set_status("Running migration...")
        self._run_background(self.controller.request_execute, self._handle_session_loaded)

    def _on_source_choice_changed(self, _event):
        if self.controller.set_source_choice(self.source_choice_var.get()):
            self._set_status("Source section selected")
        else:
            self._set_status("Source selection not found")
        self._refresh_rows()

    def _on_target_choice_changed(self, _event):
        if self.controller.set_target_choice(self.target_choice_var.get()):
            self._set_status("Target notebook selected")
        else:
            self._set_status("Target selection not found")
        self._refresh_rows()

    def _on_tree_click(self, event):
        row_id = self.tree.identify_row(event.y)
        if not row_id:
            return
        self._selected_row_id = row_id
        if self.controller.toggle_row_selection(row_id):
            self._set_status("Row selection updated")
        self._refresh_rows()

    def _on_filter_changed(self, _event):
        status = self.status_filter.get()
        self.controller.set_status_filter(None if status == "all" else status)
        self._refresh_rows()

    def _handle_source_load_result(self, result):
        if result is None or self.controller.last_error:
            self._set_status(self.controller.last_error or "Source load failed")
        else:
            self._set_status("Source choices loaded")
        self._refresh_rows()

    def _handle_session_loaded(self, session):
        if session is None:
            self._set_status(self.controller.last_error or "Operation failed")
        else:
            self._set_status("Session loaded")
        self._refresh_rows()

    def _handle_login_result(self, result):
        if isinstance(result, dict) and str(result.get("access_token") or "").strip():
            self._set_status("OneNote login successful")
        elif isinstance(result, dict) and (
            str(result.get("user_code") or "").strip()
            or str(result.get("verification_uri") or "").strip()
            or str(result.get("message") or "").strip()
        ):
            verification_uri = str(result.get("verification_uri") or "").strip()
            if verification_uri:
                try:
                    webbrowser.open(verification_uri)
                except Exception:
                    pass
            self._set_status("Open browser, sign in, then click Complete Login")
        else:
            self._set_status(self.controller.last_error or "OneNote login did not complete")
        self._refresh_rows()


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
