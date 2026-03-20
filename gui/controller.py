from __future__ import annotations

from typing import Iterable

from services.contracts import MigrationSessionResult
from services.session import is_session_valid

SELECTABLE_STATUSES = {"ready", "excluded"}
FILTERABLE_STATUSES = {"ready", "excluded", "duplicate", "error"}


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
            result = login_action()
            if isinstance(result, dict) and str(result.get("access_token") or "").strip():
                self.auth_state = "connected"
                self.pending_login_payload = None
                self.last_error = None
            elif isinstance(result, dict) and (
                str(result.get("user_code") or "").strip()
                or str(result.get("verification_uri") or "").strip()
                or str(result.get("message") or "").strip()
            ):
                self.auth_state = "pending"
                self.pending_login_payload = dict(result)
                self.last_error = None
            else:
                self.last_error = "login returned no usable result"
            return result
        self.last_error = "login is not available"
        return None

    def login(self):
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
            else:
                self.last_error = "login completion returned no access token"
            return result
        self.last_error = "login completion is not available"
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

    def get_source_choice_labels(self) -> list[str]:
        return [choice["label"] for choice in self.source_choices]

    def get_target_choice_labels(self) -> list[str]:
        return [choice["label"] for choice in self.target_choices]

    def set_source_choice(self, choice_label: str) -> bool:
        return self._apply_choice_by_label(self.source_choices, choice_label, kind="source")

    def set_target_choice(self, choice_label: str) -> bool:
        return self._apply_choice_by_label(self.target_choices, choice_label, kind="target")

    def toggle_row_selection(self, source_page_id: str) -> bool:
        item = self._find_item(source_page_id)
        if item is None or item.status not in SELECTABLE_STATUSES:
            return False
        return self.set_row_selection(source_page_id, not item.selected)

    def filter_items(self, allowed_statuses: Iterable[str]):
        allowed = set(allowed_statuses)
        return [item for item in self._items() if item.status in allowed]

    def get_visible_items(self):
        if self.status_filter is None:
            return list(self._items())
        return self.filter_items({self.status_filter})

    def select_all(self) -> None:
        for item in self._items():
            if item.status in SELECTABLE_STATUSES:
                item.selected = True
                if item.status == "excluded":
                    item.status = "ready"

    def select_none(self) -> None:
        for item in self._items():
            if item.status in SELECTABLE_STATUSES:
                item.selected = False
                item.status = "excluded"

    def set_row_selection(self, source_page_id: str, selected: bool) -> bool:
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
        if self.session is None:
            return "run a dry run first"
        source_scope = self.source_scope if self.source_scope is not None else self.session.source_scope
        target_scope = self.target_scope if self.target_scope is not None else self.session.target_scope
        if self.session_validator(self.session, source_scope, target_scope, self.auth_state):
            return None
        return "dry-run session is out of date"

    def request_execute(self):
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
