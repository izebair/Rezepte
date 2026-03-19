from __future__ import annotations

from typing import Any

import onenote_import
from gui.main_window import run_app


class DesktopAppService:
    def __init__(self) -> None:
        self._import_service = onenote_import.build_import_service()
        self._onenote_service = onenote_import.build_onenote_service()

    def request_login(self) -> dict[str, Any]:
        return onenote_import.anmelden()

    def request_source_load(self) -> list[dict[str, Any]]:
        return self._onenote_service.list_notebooks()

    def run_dry_run(self, source_scope, target_scope):
        return self._import_service.run_dry_run(source_scope, target_scope)

    def run_execute(self, session):
        return self._import_service.run_execute(session)


if __name__ == "__main__":
    run_app(import_service=DesktopAppService())
