from __future__ import annotations

import importlib.util
from pathlib import Path


def _load_app_module():
    app_path = Path(__file__).resolve().parents[1] / "app.pyw"
    spec = importlib.util.spec_from_file_location("desktop_app", app_path)
    module = importlib.util.module_from_spec(spec)
    assert spec is not None
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def test_default_desktop_service_requests_login_via_onenote_import(monkeypatch):
    app = _load_app_module()
    calls: list[str] = []

    monkeypatch.setattr(app.onenote_import, "anmelden", lambda: calls.append("anmelden") or {"access_token": "token"})

    service = app.DesktopAppService()
    result = service.request_login()

    assert result == {"access_token": "token"}
    assert calls == ["anmelden"]
