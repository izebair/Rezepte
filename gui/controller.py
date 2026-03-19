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
        return session

    def request_login(self):
        login_action = getattr(self.import_service, "request_login", None)
        if callable(login_action):
            return login_action()
        return None

    def login(self):
        return self.request_login()

    def request_source_load(self):
        source_action = getattr(self.import_service, "request_source_load", None)
        if callable(source_action):
            return source_action()
        return None

    def load_source(self):
        return self.request_source_load()

    def request_dry_run(self, source_scope: dict | None = None, target_scope: dict | None = None):
        if source_scope is not None or target_scope is not None:
            self.set_runtime_state(source_scope=source_scope, target_scope=target_scope)
        if self.source_scope is None or self.target_scope is None:
            self.last_error = "source and target scopes are required"
            return None
        session = self.import_service.run_dry_run(self.source_scope, self.target_scope)
        return self.load_session(session)

    def dry_run(self, source_scope: dict | None = None, target_scope: dict | None = None):
        return self.request_dry_run(source_scope=source_scope, target_scope=target_scope)

    def set_status_filter(self, status: str | None) -> None:
        if status in FILTERABLE_STATUSES:
            self.status_filter = status
        else:
            self.status_filter = None

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
        if self.session is None:
            return False
        source_scope = self.source_scope if self.source_scope is not None else self.session.source_scope
        target_scope = self.target_scope if self.target_scope is not None else self.session.target_scope
        return self.session_validator(self.session, source_scope, target_scope, self.auth_state)

    def request_execute(self):
        if not self.can_execute():
            self.last_error = "session is invalid"
            return None
        updated_session = self.import_service.run_execute(self.session)
        return self.load_session(updated_session)

    def execute(self):
        return self.request_execute()

    def _items(self):
        if self.session is None:
            return []
        return self.session.dry_run_items

    def _find_item(self, source_page_id: str):
        for item in self._items():
            if item.source_page_id == source_page_id:
                return item
        return None
