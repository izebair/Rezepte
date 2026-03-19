from __future__ import annotations

import queue
import threading
import tkinter as tk
from tkinter import ttk

from .controller import MainController


class MainWindow:
    def __init__(self, root: tk.Tk, controller: MainController):
        self.root = root
        self.controller = controller
        self._work_queue: queue.Queue[tuple[str, object]] = queue.Queue()
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

        toolbar = ttk.Frame(outer)
        toolbar.pack(fill="x")

        ttk.Button(toolbar, text="Login", command=self._on_login).pack(side="left")
        ttk.Button(toolbar, text="Load Source", command=self._on_source_load).pack(side="left", padx=(6, 0))
        ttk.Button(toolbar, text="Dry Run", command=self._on_dry_run).pack(side="left", padx=(6, 0))
        ttk.Button(toolbar, text="Select All", command=self._on_select_all).pack(side="left", padx=(18, 0))
        ttk.Button(toolbar, text="Select None", command=self._on_select_none).pack(side="left", padx=(6, 0))
        ttk.Button(toolbar, text="Execute", command=self._on_execute).pack(side="left", padx=(18, 0))

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
        self.tree = ttk.Treeview(outer, columns=columns, show="headings", height=20)
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

    def _set_status(self, message: str):
        self.status_var.set(message)

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
        self.controller.request_source_load()
        self._set_status("Source load requested")

    def _on_dry_run(self):
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
            self._set_status("Execute blocked: session invalid")
            return
        self._set_status("Running migration...")
        self._run_background(self.controller.request_execute, self._handle_session_loaded)

    def _on_filter_changed(self, _event):
        status = self.status_filter.get()
        self.controller.set_status_filter(None if status == "all" else status)
        self._refresh_rows()

    def _handle_session_loaded(self, session):
        if session is not None:
            self.controller.load_session(session)
            self._set_status("Session loaded")

    def _handle_login_result(self, result):
        if isinstance(result, dict) and str(result.get("access_token") or "").strip():
            self._set_status("OneNote login successful")
            return
        self._set_status("OneNote login did not complete")


class _PlaceholderImportService:
    def run_dry_run(self, source_scope, target_scope):  # pragma: no cover - UI placeholder
        raise NotImplementedError("Dry run service wiring is not configured yet")

    def run_execute(self, session):  # pragma: no cover - UI placeholder
        raise NotImplementedError("Execute service wiring is not configured yet")

    def request_login(self):  # pragma: no cover - UI placeholder
        return None

    def request_source_load(self):  # pragma: no cover - UI placeholder
        return None


def run_app(import_service=None):
    root = tk.Tk()
    controller = MainController(import_service=import_service or _PlaceholderImportService())
    MainWindow(root, controller).run()
