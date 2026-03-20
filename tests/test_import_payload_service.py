from services.contracts import ExportRunContext, ImportedRecipePayload
from services.session import validate_import_payload


def test_export_run_context_keeps_section_and_run_identity():
    ctx = ExportRunContext(
        export_run_id="run-1",
        source_notebook_id="nb-1",
        source_section_id="sec-1",
        source_section_name="Diverse",
        exported_at="2026-03-20T10:00:00Z",
        export_root="exports/run-1",
        exported_page_ids=["page-1", "page-2"],
    )

    assert ctx.export_run_id == "run-1"
    assert ctx.source_section_id == "sec-1"
    assert ctx.exported_at == "2026-03-20T10:00:00Z"


def test_import_payload_rejects_duplicate_source_page_ids():
    payload = ImportedRecipePayload(
        export_run_id="run-1",
        source_section_id="sec-1",
        exported_at="2026-03-20T10:00:00Z",
        recipes=[
            {"source_page_id": "page-1"},
            {"source_page_id": "page-1"},
        ],
    )

    try:
        validate_import_payload(payload, expected_run_id="run-1", expected_section_id="sec-1")
    except RuntimeError as exc:
        assert "source_page_id" in str(exc)
    else:  # pragma: no cover - defensive
        raise AssertionError("Expected duplicate source_page_id rejection")


def test_import_payload_rejects_wrong_run_identity():
    payload = ImportedRecipePayload(
        export_run_id="run-x",
        source_section_id="sec-1",
        exported_at="2026-03-20T10:00:00Z",
        recipes=[{"source_page_id": "page-1"}],
    )

    try:
        validate_import_payload(payload, expected_run_id="run-1", expected_section_id="sec-1")
    except RuntimeError as exc:
        assert "export_run_id" in str(exc)
    else:  # pragma: no cover - defensive
        raise AssertionError("Expected export_run_id mismatch rejection")


def test_import_payload_rejects_wrong_section_identity():
    payload = ImportedRecipePayload(
        export_run_id="run-1",
        source_section_id="sec-x",
        exported_at="2026-03-20T10:00:00Z",
        recipes=[{"source_page_id": "page-1"}],
    )

    try:
        validate_import_payload(payload, expected_run_id="run-1", expected_section_id="sec-1")
    except RuntimeError as exc:
        assert "source_section_id" in str(exc)
    else:  # pragma: no cover - defensive
        raise AssertionError("Expected source_section_id mismatch rejection")


def test_import_payload_rejects_missing_exported_at():
    payload = ImportedRecipePayload(
        export_run_id="run-1",
        source_section_id="sec-1",
        exported_at="",
        recipes=[{"source_page_id": "page-1"}],
    )

    try:
        validate_import_payload(payload, expected_run_id="run-1", expected_section_id="sec-1")
    except RuntimeError as exc:
        assert "exported_at" in str(exc)
    else:  # pragma: no cover - defensive
        raise AssertionError("Expected exported_at rejection")
