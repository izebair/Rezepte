from __future__ import annotations

import onenote_import


def test_main_uses_import_service_for_dry_run(monkeypatch):
    called: dict[str, object] = {}

    class FakeImportService:
        def run_dry_run(self, source_scope, target_scope):
            called["dry_run"] = (source_scope, target_scope)
            return object()

    monkeypatch.setattr(onenote_import, "_validate_config", lambda **kwargs: None)
    monkeypatch.setattr(
        onenote_import,
        "anmelden",
        lambda: (_ for _ in ()).throw(AssertionError("anmelden should not be called for dry-run")),
    )
    monkeypatch.setattr(onenote_import, "build_import_service", lambda: FakeImportService())

    result = onenote_import.main(
        [
            "--dry-run",
            "--source-type",
            "onenote-section",
            "--source-section-id",
            "src-1",
        ]
    )

    assert result == 0
    assert called["dry_run"] == (
        {"section_id": "src-1"},
        {"notebook_name": onenote_import.NOTEBOOK_NAME or ""},
    )


def test_start_login_returns_gui_contract_without_printing(monkeypatch, capsys):
    flow = {
        "message": "Open the browser to continue",
        "user_code": "ABC-123",
        "verification_uri": "https://example.test/device",
        "expires_in": 900,
        "extra": "ignored",
    }

    class FakeService:
        def start_device_flow(self):
            return flow

        def complete_device_flow(self, received_flow):
            raise AssertionError(f"complete_device_flow should not be called: {received_flow}")

    monkeypatch.setattr(onenote_import, "build_onenote_service", lambda: FakeService())

    result = onenote_import.start_login()
    captured = capsys.readouterr()

    assert captured.out == ""
    assert result == {
        "message": "Open the browser to continue",
        "user_code": "ABC-123",
        "verification_uri": "https://example.test/device",
        "expires_in": 900,
    }


def test_complete_login_uses_last_started_flow(monkeypatch):
    started_flow = {"user_code": "ABC-123"}
    calls: list[dict[str, object]] = []

    class FakeService:
        def start_device_flow(self):
            return started_flow

        def complete_device_flow(self, received_flow):
            calls.append(received_flow)
            return {"access_token": "token-123"}

    monkeypatch.setattr(onenote_import, "build_onenote_service", lambda: FakeService())

    onenote_import.start_login()
    result = onenote_import.complete_login(None)

    assert result == {"access_token": "token-123"}
    assert calls == [started_flow]
