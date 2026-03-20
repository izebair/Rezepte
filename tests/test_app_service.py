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

    monkeypatch.setattr(
        app.onenote_import,
        "start_login",
        lambda: calls.append("start_login")
        or {
            "message": "Open browser",
            "user_code": "ABC-123",
            "verification_uri": "https://example.test/login",
            "expires_in": 900,
        },
    )

    service = app.DesktopAppService()
    result = service.request_login()

    assert result == {
        "message": "Open browser",
        "user_code": "ABC-123",
        "verification_uri": "https://example.test/login",
        "expires_in": 900,
    }
    assert calls == ["start_login"]


def test_desktop_service_complete_login_forwards_flow(monkeypatch):
    app = _load_app_module()
    calls: list[dict[str, object]] = []

    monkeypatch.setattr(
        app.onenote_import,
        "complete_login",
        lambda flow: calls.append(flow) or {"access_token": "token-123"},
    )

    service = app.DesktopAppService()
    flow = {"user_code": "ABC-123"}
    result = service.complete_login(flow)

    assert result == {"access_token": "token-123"}
    assert calls == [flow]


def test_desktop_service_request_source_load_enriches_notebooks_with_sections(monkeypatch):
    app = _load_app_module()

    class FakeOneNoteService:
        def list_notebooks(self):
            return [
                {"id": "nb-1", "displayName": "Recipes"},
                {"id": "nb-2", "displayName": "Archive"},
            ]

        def list_sections(self, notebook_id, *, parent_type="notebook"):
            assert parent_type == "notebook"
            return [
                {"id": f"{notebook_id}-sec-1", "displayName": f"{notebook_id} Breakfast"},
                {"id": f"{notebook_id}-sec-2", "displayName": f"{notebook_id} Dinner"},
            ]

    monkeypatch.setattr(app.onenote_import, "build_onenote_service", lambda: FakeOneNoteService())
    monkeypatch.setattr(app.onenote_import, "build_import_service", lambda: object())

    service = app.DesktopAppService()

    result = service.request_source_load()

    assert result == [
        {
            "id": "nb-1",
            "displayName": "Recipes",
            "defaultSectionId": "nb-1-sec-1",
            "sections": [
                {"id": "nb-1-sec-1", "displayName": "nb-1 Breakfast"},
                {"id": "nb-1-sec-2", "displayName": "nb-1 Dinner"},
            ],
        },
        {
            "id": "nb-2",
            "displayName": "Archive",
            "defaultSectionId": "nb-2-sec-1",
            "sections": [
                {"id": "nb-2-sec-1", "displayName": "nb-2 Breakfast"},
                {"id": "nb-2-sec-2", "displayName": "nb-2 Dinner"},
            ],
        },
    ]
