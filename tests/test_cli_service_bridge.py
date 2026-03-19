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
