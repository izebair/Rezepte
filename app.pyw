from __future__ import annotations

import os
from pathlib import Path
import sys
from typing import Any

_APP_ROOT = Path(__file__).resolve().parent


def _bootstrap_local_venv() -> bool:
    site_packages = _APP_ROOT / ".venv" / "Lib" / "site-packages"
    if not site_packages.exists():
        return False
    site_packages_str = str(site_packages)
    if site_packages_str not in sys.path:
        sys.path.insert(0, site_packages_str)
    scripts_dir = _APP_ROOT / ".venv" / "Scripts"
    scripts_dir_str = str(scripts_dir)
    current_path = os.environ.get("PATH", "")
    if scripts_dir.exists() and scripts_dir_str not in current_path.split(os.pathsep):
        os.environ["PATH"] = scripts_dir_str + os.pathsep + current_path
    return True


_bootstrap_local_venv()

import onenote_import
from gui.main_window import run_app


class DesktopAppService:
    def __init__(self) -> None:
        self._import_service = onenote_import.build_import_service()
        self._onenote_service = onenote_import.build_onenote_service()
        self._login_flow: dict[str, Any] | None = None

    def start_login(self) -> dict[str, Any]:
        login = onenote_import.start_login()
        self._login_flow = getattr(onenote_import, "_CURRENT_DEVICE_FLOW", None)
        return login

    def complete_login(self, flow: dict[str, Any] | None = None) -> dict[str, Any]:
        if flow is not None:
            self._login_flow = flow
        login_flow = flow if flow is not None else self._login_flow
        result = onenote_import.complete_login(login_flow)
        self._login_flow = None
        return result

    def request_login(self) -> dict[str, Any]:
        return self.start_login()

    def request_source_load(self) -> list[dict[str, Any]]:
        notebooks = self._onenote_service.list_notebooks()
        enriched_notebooks: list[dict[str, Any]] = []
        for notebook in notebooks:
            notebook_id = str(notebook.get("id") or "").strip()
            if not notebook_id:
                continue
            sections = self._onenote_service.list_sections(notebook_id, parent_type="notebook")
            enriched = dict(notebook)
            enriched["sections"] = sections
            if sections and not enriched.get("defaultSectionId"):
                enriched["defaultSectionId"] = sections[0].get("id")
            enriched_notebooks.append(enriched)
        return enriched_notebooks

    def run_dry_run(self, source_scope, target_scope):
        return self._import_service.run_dry_run(source_scope, target_scope)

    def run_execute(self, session):
        return self._import_service.run_execute(session)


if __name__ == "__main__":
    run_app(import_service=DesktopAppService())
