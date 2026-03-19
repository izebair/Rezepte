from __future__ import annotations

from typing import Any

import onenote_import
from services.onenote_service import OneNoteService


class FakeResponse:
    def __init__(self, *, json_data: Any | None = None, text: str = "", status_code: int = 200) -> None:
        self._json_data = json_data
        self.text = text
        self.status_code = status_code
        self.headers: dict[str, str] = {}

    def json(self) -> Any:
        return self._json_data

    def raise_for_status(self) -> None:
        return None


class FakeMsalApp:
    def __init__(self) -> None:
        self.started_scopes: list[str] | None = None
        self.completed_flow: dict[str, Any] | None = None

    def initiate_device_flow(self, *, scopes: list[str]) -> dict[str, Any]:
        self.started_scopes = scopes
        return {"user_code": "ABC-123", "message": "Open browser"}

    def acquire_token_by_device_flow(self, flow: dict[str, Any]) -> dict[str, Any]:
        self.completed_flow = flow
        return {"access_token": "token-123"}


class FakeMsalModule:
    def __init__(self) -> None:
        self.app = FakeMsalApp()
        self.client_id: str | None = None
        self.authority: str | None = None

    def PublicClientApplication(self, *, client_id: str, authority: str) -> FakeMsalApp:
        self.client_id = client_id
        self.authority = authority
        return self.app


def test_duplicate_check_is_limited_to_migrated_recipes_root() -> None:
    service = OneNoteService(token_provider=lambda: "token")
    pages = [
        {"id": "src-1", "title": "Tomatensuppe", "path": "Andere Wurzel/Suppen/Tomate"},
        {"id": "dst-1", "title": "Tomatensuppe", "path": "Migrated Recipes/Suppen/Tomate"},
        {"id": "dst-2", "title": "Kuerbis", "path": ["Migrated Recipes", "Suppen", "Kuerbis"]},
        {"id": "dst-3", "title": "Snack", "path": "migrated recipes/Snacks/Knusper"},
    ]

    only_target = service._filter_target_root_pages(
        pages,
        target_root_name="Migrated Recipes",
        target_root_page_ids={"dst-1", "dst-2"},
    )

    assert [page["id"] for page in only_target] == ["dst-1", "dst-2"]


def test_duplicate_check_ignores_matching_ids_outside_requested_root() -> None:
    service = OneNoteService(token_provider=lambda: "token")
    pages = [
        {"id": "page-1", "path": "Archiv/Suppen/Tomate"},
        {"id": "page-2", "path": "Migrated Recipes/Suppen/Tomate"},
    ]

    only_target = service._filter_target_root_pages(
        pages,
        target_root_name="Migrated Recipes",
        target_root_page_ids={"page-1", "page-2"},
    )

    assert [page["id"] for page in only_target] == ["page-2"]


def test_start_and_complete_device_flow_use_configured_authority() -> None:
    fake_msal = FakeMsalModule()
    service = OneNoteService(
        token_provider=lambda: "token",
        client_id="client-id",
        tenant_id="tenant-id",
        scopes=["User.Read", "Notes.ReadWrite"],
        msal_module=fake_msal,
    )

    flow = service.start_device_flow()
    result = service.complete_device_flow(flow)

    assert flow["user_code"] == "ABC-123"
    assert result["access_token"] == "token-123"
    assert fake_msal.client_id == "client-id"
    assert fake_msal.authority == "https://login.microsoftonline.com/tenant-id"
    assert fake_msal.app.started_scopes == ["User.Read", "Notes.ReadWrite"]
    assert fake_msal.app.completed_flow == flow


def test_load_target_fingerprints_only_reads_pages_below_target_root() -> None:
    fingerprint = "a" * 64
    responses = [
        FakeResponse(json_data={"value": [{"id": "root-1", "displayName": "Migrated Recipes"}]}),
        FakeResponse(json_data={"value": [{"id": "cat-1", "displayName": "Suppen"}]}),
        FakeResponse(json_data={"value": [{"id": "sec-1", "displayName": "Tomatensuppen"}]}),
        FakeResponse(json_data={"value": [{"id": "page-1", "title": "Im Zielbaum"}]}),
        FakeResponse(text=f"<html>REZEPTE_IMPORT_ID:{fingerprint}</html>"),
    ]
    request_urls: list[str] = []

    def fake_request_with_retry(method: str, url: str, headers: dict[str, str], **kwargs: Any) -> FakeResponse:
        request_urls.append(url)
        return responses.pop(0)

    service = OneNoteService(
        token_provider=lambda: "token-123",
        request_with_retry=fake_request_with_retry,
    )

    fingerprints = service.load_target_fingerprints("notebook-1", target_root_name="Migrated Recipes")

    assert fingerprints == {fingerprint}
    assert request_urls == [
        "https://graph.microsoft.com/v1.0/me/onenote/notebooks/notebook-1/sectionGroups",
        "https://graph.microsoft.com/v1.0/me/onenote/sectionGroups/root-1/sectionGroups",
        "https://graph.microsoft.com/v1.0/me/onenote/sectionGroups/cat-1/sections?$select=id,displayName",
        "https://graph.microsoft.com/v1.0/me/onenote/sections/sec-1/pages?$select=id,title",
        "https://graph.microsoft.com/v1.0/me/onenote/pages/page-1/content",
    ]


def test_importer_notebook_fingerprints_delegate_to_hierarchy_aware_service(monkeypatch: Any) -> None:
    calls: list[tuple[str, str]] = []

    class FakeService:
        def load_notebook_fingerprints(self, notebook_id: str) -> set[str]:
            calls.append(("load_notebook_fingerprints", notebook_id))
            return {"deep-fingerprint"}

        def fingerprint_in_notebook(self, notebook_id: str, fingerprint: str) -> bool:
            calls.append(("fingerprint_in_notebook", notebook_id))
            return fingerprint == "deep-fingerprint"

    monkeypatch.setattr(onenote_import, "build_onenote_service", lambda: FakeService())
    monkeypatch.setattr(
        onenote_import,
        "notebook_sections_laden",
        lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("flat notebook traversal should not be used")),
    )
    monkeypatch.setattr(
        onenote_import,
        "section_fingerprints_laden",
        lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("section fingerprint traversal should not be used")),
    )

    assert onenote_import.notebook_fingerprints_laden("token-123", "notebook-1") == {"deep-fingerprint"}
    assert onenote_import.fingerprint_in_notebook("token-123", "notebook-1", "deep-fingerprint") is True
    assert calls == [
        ("load_notebook_fingerprints", "notebook-1"),
        ("fingerprint_in_notebook", "notebook-1"),
    ]


def test_importer_section_group_wrapper_creates_fixed_root_before_category_group(monkeypatch: Any) -> None:
    calls: list[tuple[str, str, str]] = []

    class FakeService:
        def ensure_target_root(self, notebook_id: str, root_name: str = "Migrated Recipes") -> str:
            calls.append(("ensure_target_root", notebook_id, root_name))
            return "root-1"

        def ensure_category_group(self, root_group_id: str, group_name: str) -> str:
            calls.append(("ensure_category_group", root_group_id, group_name))
            return "group-1"

    monkeypatch.setattr(onenote_import, "build_onenote_service", lambda: FakeService())

    group_id = onenote_import.section_group_id_finden_oder_erstellen("token-123", "notebook-1", "Suppen")

    assert group_id == "group-1"
    assert calls == [
        ("ensure_target_root", "notebook-1", "Migrated Recipes"),
        ("ensure_category_group", "root-1", "Suppen"),
    ]
