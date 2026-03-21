from __future__ import annotations

import json
from pathlib import Path
from typing import Iterable

from services.contracts import ExportRunContext, MigrationSessionResult
from services.session import is_session_valid

SELECTABLE_STATUSES = {"ready", "excluded", "Bereit"}
FILTERABLE_STATUSES = {"ready", "excluded", "duplicate", "error", "Bereit", "Roh", "Fehlt noch", "Migrationsfehler", "Duplikat", "Migriert"}


class MainController:
    def __init__(self, import_service, session_validator=is_session_valid):
        self.import_service = import_service
        self.session_validator = session_validator
        self.session: MigrationSessionResult | None = None
        self.auth_state = "disconnected"
        self.source_scope: dict | None = None
        self.target_scope: dict | None = None
        self.pending_login_payload: dict | None = None
        self.source_choices: list[dict] = []
        self.target_choices: list[dict] = []
        self.selected_source_choice: str | None = None
        self.selected_target_choice: str | None = None
        self.status_filter: str | None = None
        self.last_error: str | None = None
        self.login_banner_state = "idle"
        self.login_message = ""
        self.login_code = ""
        self.login_uri = ""
        self.rows: list[dict] = []
        self.active_export_run_id: str | None = None
        self.active_export_context: ExportRunContext | None = None

    def set_runtime_state(
        self,
        *,
        auth_state: str | None = None,
        source_scope: dict | None = None,
        target_scope: dict | None = None,
    ) -> None:
        if auth_state is not None:
            self.auth_state = auth_state
        if source_scope is not None:
            self.source_scope = source_scope
        if target_scope is not None:
            self.target_scope = target_scope

    def load_session(self, session: MigrationSessionResult) -> MigrationSessionResult:
        self.session = session
        self.source_scope = session.source_scope
        self.target_scope = session.target_scope
        self.status_filter = self.status_filter if self.status_filter in FILTERABLE_STATUSES else None
        self.last_error = None
        self._sync_selected_choices_with_scopes()
        return session

    def request_login(self):
        login_action = getattr(self.import_service, "request_login", None)
        if callable(login_action):
            try:
                result = login_action()
            except Exception as exc:
                self.auth_state = "error"
                self.pending_login_payload = None
                self.last_error = str(exc)
                self.login_banner_state = "error"
                self.login_message = ""
                self.login_code = ""
                self.login_uri = ""
                return None
            if isinstance(result, dict) and str(result.get("access_token") or "").strip():
                self.auth_state = "connected"
                self.pending_login_payload = None
                self.last_error = None
                self.login_banner_state = "idle"
                self.login_message = ""
                self.login_code = ""
                self.login_uri = ""
            elif isinstance(result, dict) and (
                str(result.get("user_code") or "").strip()
                or str(result.get("verification_uri") or "").strip()
                or str(result.get("message") or "").strip()
            ):
                self.auth_state = "pending"
                self.pending_login_payload = dict(result)
                self.last_error = None
                self.login_banner_state = "code-required"
                self.login_message = str(result.get("message") or "").strip()
                self.login_code = str(result.get("user_code") or "").strip()
                self.login_uri = str(result.get("verification_uri") or "").strip()
            else:
                self.auth_state = "error"
                self.pending_login_payload = None
                self.last_error = "login returned no usable result"
                self.login_banner_state = "error"
                self.login_message = ""
                self.login_code = ""
                self.login_uri = ""
            return result
        self.auth_state = "error"
        self.pending_login_payload = None
        self.last_error = "login is not available"
        self.login_banner_state = "error"
        self.login_message = ""
        self.login_code = ""
        self.login_uri = ""
        return None

    def login(self):
        return self.request_login()

    def retry_login(self):
        self.last_error = None
        return self.request_login()

    def complete_login(self, flow: dict | None = None):
        login_action = getattr(self.import_service, "complete_login", None)
        if callable(login_action):
            login_flow = flow if flow is not None else self.pending_login_payload
            try:
                result = login_action(login_flow)
            except Exception as exc:
                self.last_error = str(exc)
                return None
            if isinstance(result, dict) and str(result.get("access_token") or "").strip():
                self.auth_state = "connected"
                self.pending_login_payload = None
                self.last_error = None
                self.login_banner_state = "idle"
                self.login_message = ""
                self.login_code = ""
                self.login_uri = ""
            else:
                self.last_error = "login completion returned no access token"
                self.login_banner_state = "error"
            return result
        self.last_error = "login completion is not available"
        self.login_banner_state = "error"
        return None

    def request_source_load(self):
        source_action = getattr(self.import_service, "request_source_load", None)
        if callable(source_action):
            result = source_action()
            self._load_scope_choices(result)
            if not self.source_scope and self.source_choices:
                self._apply_source_choice(self.source_choices[0])
            if not self.target_scope and self.target_choices:
                self._apply_target_choice(self.target_choices[0])
            if self.source_choices or self.target_choices:
                self.last_error = None
            else:
                self.last_error = "no source or target choices were returned"
            return result
        self.last_error = "source loading is not available"
        return None

    def load_source(self):
        return self.request_source_load()

    def request_dry_run(self, source_scope: dict | None = None, target_scope: dict | None = None):
        if source_scope is not None or target_scope is not None:
            self.set_runtime_state(source_scope=source_scope, target_scope=target_scope)
        block_reason = self.get_dry_run_block_reason()
        if block_reason is not None:
            self.last_error = block_reason
            return None
        try:
            session = self.import_service.run_dry_run(self.source_scope, self.target_scope)
        except Exception as exc:
            self.last_error = str(exc)
            return None
        return self.load_session(session)

    def dry_run(self, source_scope: dict | None = None, target_scope: dict | None = None):
        return self.request_dry_run(source_scope=source_scope, target_scope=target_scope)

    def set_status_filter(self, status: str | None) -> None:
        if status in FILTERABLE_STATUSES:
            self.status_filter = status
        else:
            self.status_filter = None

    def can_load_source_tree(self) -> bool:
        return self.auth_state == "connected"

    def on_section_changed(self, section_scope: dict) -> None:
        self.source_scope = dict(section_scope)
        self.active_export_run_id = None
        self.active_export_context = None
        self.rows = []

    def load_raw_section_rows(self, section_scope: dict, rows: list[dict]) -> list[dict]:
        self.on_section_changed(section_scope)
        raw_rows: list[dict] = []
        for row in rows:
            source_page_id = str(row.get("source_page_id") or row.get("id") or "").strip()
            source_page_title = str(row.get("source_page_title") or row.get("title") or "").strip()
            raw_rows.append(
                {
                    "source_page_id": source_page_id,
                    "source_page_title": source_page_title,
                    "selected": False,
                    "selectable": False,
                    "status": "Roh",
                    "action_label": "Aufbereitung ausstehend",
                    "target_label": "",
                    "messages": [],
                }
            )
        self.rows = raw_rows
        return raw_rows

    def request_section_rows(self) -> list[dict] | None:
        if not self.can_load_source_tree():
            self.last_error = "login required"
            return None
        if self.source_scope is None:
            self.last_error = "select a source section"
            return None
        action = getattr(self.import_service, "load_section_rows", None)
        if not callable(action):
            self.last_error = "section loading is not available"
            return None
        rows = action(self.source_scope)
        self.last_error = None
        return self.load_raw_section_rows(self.source_scope, rows)

    def request_section_export(self, output_root: str | Path | None = None) -> ExportRunContext | None:
        if self.source_scope is None:
            self.last_error = "select a source section"
            return None
        action = getattr(self.import_service, "export_section", None)
        if not callable(action):
            self.last_error = "section export is not available"
            return None
        export_root = Path(output_root) if output_root is not None else Path.cwd() / "exports"
        context = action(self.source_scope, output_root=export_root)
        self.active_export_context = context
        self.active_export_run_id = context.export_run_id
        self.last_error = None
        return context

    def request_json_import(self, payload_or_path: dict | str | Path) -> list[dict] | None:
        if self.active_export_context is None:
            self.last_error = "run export first"
            return None
        if self.target_scope is None:
            self.last_error = "select a target notebook"
            return None
        action = getattr(self.import_service, "apply_import_payload", None)
        if not callable(action):
            self.last_error = "json import is not available"
            return None
        payload = self._load_payload(payload_or_path)
        self.rows = action(
            self.rows,
            payload,
            export_run_id=self.active_export_context.export_run_id,
            source_section_id=self.active_export_context.source_section_id,
            exported_at=self.active_export_context.exported_at,
            target_scope=self.target_scope,
        )
        self.last_error = None
        return self.rows

    def reset_failed_rows(self) -> list[dict]:
        for row in self.rows:
            if str(row.get("status") or "") == "Migrationsfehler":
                row["status"] = "Bereit"
                row["selected"] = True
                row["selectable"] = True
                row["action_label"] = "Bereit"
        return self.rows

    def get_source_choice_labels(self) -> list[str]:
        return [choice["label"] for choice in self.source_choices]

    def get_target_choice_labels(self) -> list[str]:
        return [choice["label"] for choice in self.target_choices]

    def set_source_choice(self, choice_label: str) -> bool:
        return self._apply_choice_by_label(self.source_choices, choice_label, kind="source")

    def set_target_choice(self, choice_label: str) -> bool:
        return self._apply_choice_by_label(self.target_choices, choice_label, kind="target")

    def toggle_row_selection(self, source_page_id: str) -> bool:
        row = self._find_row(source_page_id)
        if row is not None:
            if not self._row_is_selectable(row):
                return False
            row["selected"] = not bool(row.get("selected"))
            return True
        item = self._find_item(source_page_id)
        if item is None or item.status not in SELECTABLE_STATUSES:
            return False
        return self.set_row_selection(source_page_id, not item.selected)

    def filter_items(self, allowed_statuses: Iterable[str]):
        allowed = set(allowed_statuses)
        if self.rows:
            return [row for row in self.rows if str(row.get("status") or "") in allowed]
        return [item for item in self._items() if item.status in allowed]

    def get_visible_items(self):
        if self.status_filter is None:
            return list(self._items())
        return self.filter_items({self.status_filter})

    def select_all(self) -> None:
        if self.rows:
            for row in self.rows:
                if self._row_is_selectable(row):
                    row["selected"] = True
            return
        for item in self._items():
            if item.status in SELECTABLE_STATUSES:
                item.selected = True
                if item.status == "excluded":
                    item.status = "ready"

    def select_none(self) -> None:
        if self.rows:
            for row in self.rows:
                if self._row_is_selectable(row):
                    row["selected"] = False
            return
        for item in self._items():
            if item.status in SELECTABLE_STATUSES:
                item.selected = False
                item.status = "excluded"

    def set_row_selection(self, source_page_id: str, selected: bool) -> bool:
        row = self._find_row(source_page_id)
        if row is not None:
            if not self._row_is_selectable(row):
                return False
            row["selected"] = selected
            return True
        item = self._find_item(source_page_id)
        if item is None or item.status not in SELECTABLE_STATUSES:
            return False
        item.selected = selected
        item.status = "ready" if selected else "excluded"
        return True

    def can_execute(self) -> bool:
        return self.get_execute_block_reason() is None

    def can_request_dry_run(self) -> bool:
        return self.get_dry_run_block_reason() is None

    def get_dry_run_block_reason(self) -> str | None:
        if self.auth_state == "pending":
            return "finish login in browser"
        if self.auth_state != "connected":
            return "login required"
        if self.source_scope is None:
            return "select a source section"
        if self.target_scope is None:
            return "select a target notebook"
        return None

    def get_execute_block_reason(self) -> str | None:
        if self.auth_state == "pending":
            return "finish login in browser"
        if self.auth_state != "connected":
            return "login required"
        if self.rows and self.active_export_context is not None:
            if self.target_scope is None:
                return "select a target notebook"
            if any(bool(row.get("selected")) and str(row.get("status") or "") == "Bereit" for row in self.rows):
                return None
            return "import prepared rows first"
        if self.session is None:
            return "run a dry run first"
        source_scope = self.source_scope if self.source_scope is not None else self.session.source_scope
        target_scope = self.target_scope if self.target_scope is not None else self.session.target_scope
        if self.session_validator(self.session, source_scope, target_scope, self.auth_state):
            return None
        return "dry-run session is out of date"

    def request_execute(self):
        if self.rows and self.active_export_context is not None:
            block_reason = self.get_execute_block_reason()
            if block_reason is not None:
                self.last_error = block_reason
                return None
            action = getattr(self.import_service, "execute_import_rows", None)
            if not callable(action):
                self.last_error = "execute is not available"
                return None
            try:
                self.rows = action(self.rows, target_scope=self.target_scope)
            except Exception as exc:
                self.last_error = str(exc)
                return None
            return self.rows
        block_reason = self.get_execute_block_reason()
        if block_reason is not None:
            self.last_error = block_reason
            return None
        try:
            updated_session = self.import_service.run_execute(self.session)
        except Exception as exc:
            self.last_error = str(exc)
            return None
        return self.load_session(updated_session)

    def execute(self):
        return self.request_execute()

    def _items(self):
        if self.session is None:
            return []
        return self.session.dry_run_items

    def _load_scope_choices(self, result) -> None:
        source_choices: list[dict] = []
        target_choices: list[dict] = []
        if isinstance(result, dict):
            source_choices.extend(self._extract_source_choices(result.get("source_choices") or result.get("source") or []))
            target_choices.extend(self._extract_target_choices(result.get("target_choices") or result.get("target") or []))
            if not source_choices and isinstance(result.get("notebooks"), list):
                source_choices.extend(self._extract_source_choices(result["notebooks"]))
            if not target_choices and isinstance(result.get("notebooks"), list):
                target_choices.extend(self._extract_target_choices(result["notebooks"]))
        elif isinstance(result, list):
            source_choices.extend(self._extract_source_choices(result))
            target_choices.extend(self._extract_target_choices(result))
        self.source_choices = source_choices
        self.target_choices = target_choices
        self._sync_selected_choices_with_scopes()

    def _extract_source_choices(self, entries) -> list[dict]:
        choices: list[dict] = []
        if not isinstance(entries, list):
            return choices
        for entry in entries:
            if not isinstance(entry, dict):
                continue
            choices.extend(self._source_choices_from_entry(entry))
        return choices

    def _extract_target_choices(self, entries) -> list[dict]:
        choices: list[dict] = []
        if not isinstance(entries, list):
            return choices
        for entry in entries:
            choice = self._target_choice_from_entry(entry)
            if choice is not None:
                choices.append(choice)
        return choices

    def _source_choices_from_entry(self, entry: dict) -> list[dict]:
        notebook_id = self._choice_id(entry, ("notebook_id", "id"))
        notebook_label = self._choice_label(entry, notebook_id, ("displayName", "name", "title"))
        choices: list[dict] = []

        sections = entry.get("sections")
        if isinstance(sections, list) and notebook_id:
            for section in sections:
                if not isinstance(section, dict):
                    continue
                section_id = self._choice_id(section, ("section_id", "id"))
                if not section_id:
                    continue
                choices.append(
                    self._build_choice(
                        kind="source",
                        choice_id=section_id,
                        label=self._choice_label(section, section_id, ("displayName", "name", "title"), prefix=notebook_label),
                        scope={
                            "section_id": section_id,
                            "notebook_id": notebook_id,
                        },
                    )
                )
            return choices

        section_id = self._choice_id(entry, ("section_id", "defaultSectionId", "default_section_id", "id"))
        if section_id:
            choices.append(
                self._build_choice(
                    kind="source",
                    choice_id=section_id,
                    label=self._choice_label(entry, section_id, ("displayName", "name", "title")),
                    scope={
                        "section_id": section_id,
                        **({"notebook_id": notebook_id} if notebook_id else {}),
                    },
                )
            )
        return choices

    def _target_choice_from_entry(self, entry: dict) -> dict | None:
        notebook_id = self._choice_id(entry, ("notebook_id", "id"))
        if not notebook_id:
            return None
        return self._build_choice(
            kind="target",
            choice_id=notebook_id,
            label=self._choice_label(entry, notebook_id, ("displayName", "name", "title")),
            scope={
                "notebook_id": notebook_id,
                **({"name": str(entry.get("displayName") or entry.get("name") or "").strip()} if entry.get("displayName") or entry.get("name") else {}),
            },
        )

    def _build_choice(self, *, kind: str, choice_id: str, label: str, scope: dict) -> dict:
        return {
            "kind": kind,
            "id": choice_id,
            "label": label,
            "scope": scope,
        }

    def _choice_id(self, entry: dict, keys: tuple[str, ...]) -> str:
        for key in keys:
            value = str(entry.get(key) or "").strip()
            if value:
                return value
        return ""

    def _choice_label(self, entry: dict, fallback_id: str, keys: tuple[str, ...], prefix: str | None = None) -> str:
        label = ""
        for key in keys:
            value = str(entry.get(key) or "").strip()
            if value:
                label = value
                break
        if not label:
            label = fallback_id
        if prefix:
            label = f"{prefix} / {label}"
        return f"{label} ({fallback_id})"

    def _apply_choice_by_label(self, choices: list[dict], choice_label: str, *, kind: str) -> bool:
        for choice in choices:
            if choice["label"] == choice_label:
                if kind == "source":
                    self._apply_source_choice(choice)
                else:
                    self._apply_target_choice(choice)
                return True
        return False

    def _apply_source_choice(self, choice: dict) -> None:
        self.selected_source_choice = choice["label"]
        self.source_scope = dict(choice["scope"])

    def _apply_target_choice(self, choice: dict) -> None:
        self.selected_target_choice = choice["label"]
        self.target_scope = dict(choice["scope"])

    def _sync_selected_choices_with_scopes(self) -> None:
        self.selected_source_choice = self._find_choice_label(self.source_choices, self.source_scope)
        self.selected_target_choice = self._find_choice_label(self.target_choices, self.target_scope)

    def _find_choice_label(self, choices: list[dict], scope: dict | None) -> str | None:
        if scope is None:
            return None
        for choice in choices:
            choice_scope = choice.get("scope")
            if isinstance(choice_scope, dict) and self._scope_matches(choice_scope, scope):
                return choice["label"]
        return None

    def _scope_matches(self, choice_scope: dict, active_scope: dict) -> bool:
        for key, value in active_scope.items():
            if choice_scope.get(key) != value:
                return False
        return True

    def _find_item(self, source_page_id: str):
        for item in self._items():
            if item.source_page_id == source_page_id:
                return item
        return None

    def _find_row(self, source_page_id: str) -> dict | None:
        for row in self.rows:
            if str(row.get("source_page_id") or "") == source_page_id:
                return row
        return None

    def _row_is_selectable(self, row: dict) -> bool:
        if "selectable" in row:
            return bool(row.get("selectable"))
        return str(row.get("status") or "") in SELECTABLE_STATUSES

    def _load_payload(self, payload_or_path: dict | str | Path) -> dict:
        if isinstance(payload_or_path, dict):
            return dict(payload_or_path)
        path = Path(payload_or_path)
        return json.loads(path.read_text(encoding="utf-8"))
