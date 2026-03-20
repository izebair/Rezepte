import pytest

from services.contracts import ExportRunContext, ImportedRecipePayload
from services.import_payload_service import ImportPayloadService
from services.import_service import ImportService
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


def test_import_payload_service_preserves_row_order_and_marks_missing_rows():
    service = ImportPayloadService()
    rows = [
        {"source_page_id": "page-1", "source_page_title": "Kuchen"},
        {"source_page_id": "page-2", "source_page_title": "Suppe"},
    ]
    payload = {
        "export_run_id": "run-1",
        "source_section_id": "sec-1",
        "exported_at": "2026-03-20T10:00:00Z",
        "recipes": [
            {
                "source_page_id": "page-1",
                "title": "Kuchen",
                "target_main_category": "Dessert",
                "target_subcategory": "Kuchen",
                "fingerprint": "fp-ready",
                "images": [],
            }
        ],
    }

    result = service.reconcile_rows(
        rows,
        payload,
        export_run_id="run-1",
        source_section_id="sec-1",
        exported_at="2026-03-20T10:00:00Z",
    )

    assert [row["source_page_id"] for row in result] == ["page-1", "page-2"]
    assert result[0]["title"] == "Kuchen"
    assert result[0]["import_state"] == "present"
    assert result[1]["source_page_id"] == "page-2"
    assert result[1]["import_state"] == "missing"


def test_import_payload_service_rejects_unknown_source_page_ids():
    service = ImportPayloadService()
    rows = [{"source_page_id": "page-1"}]
    payload = {
        "export_run_id": "run-1",
        "source_section_id": "sec-1",
        "exported_at": "2026-03-20T10:00:00Z",
        "recipes": [{"source_page_id": "page-x"}],
    }

    with pytest.raises(RuntimeError, match="source_page_id"):
        service.reconcile_rows(
            rows,
            payload,
            export_run_id="run-1",
            source_section_id="sec-1",
            exported_at="2026-03-20T10:00:00Z",
        )


def test_import_payload_service_rejects_wrong_exported_at():
    service = ImportPayloadService()
    rows = [{"source_page_id": "page-1"}]
    payload = {
        "export_run_id": "run-1",
        "source_section_id": "sec-1",
        "exported_at": "2026-03-20T10:01:00Z",
        "recipes": [{"source_page_id": "page-1"}],
    }

    with pytest.raises(RuntimeError, match="exported_at"):
        service.reconcile_rows(
            rows,
            payload,
            export_run_id="run-1",
            source_section_id="sec-1",
            exported_at="2026-03-20T10:00:00Z",
        )


class _FakeOneNoteService:
    def __init__(self, *, target_fingerprints=None) -> None:
        self._target_fingerprints = set(target_fingerprints or set())

    def load_target_fingerprints(self, target_scope):
        assert target_scope == {"notebook_id": "dst-1"}
        return set(self._target_fingerprints)


def test_import_service_translates_reconciled_rows_into_final_statuses():
    service = ImportService(onenote_service=_FakeOneNoteService(target_fingerprints={"fp-duplicate"}))
    rows = [
        {"source_page_id": "page-ready", "source_page_title": "Ready"},
        {"source_page_id": "page-missing", "source_page_title": "Missing"},
        {"source_page_id": "page-duplicate", "source_page_title": "Duplicate"},
    ]
    payload = {
        "export_run_id": "run-1",
        "source_section_id": "sec-1",
        "exported_at": "2026-03-20T10:00:00Z",
        "recipes": [
            {
                "source_page_id": "page-ready",
                "title": "Ready",
                "target_main_category": "Dessert",
                "target_subcategory": "Cake",
                "fingerprint": "fp-ready",
                "images": [],
            },
            {
                "source_page_id": "page-duplicate",
                "title": "Duplicate",
                "target_main_category": "Dessert",
                "target_subcategory": "Cake",
                "fingerprint": "fp-duplicate",
                "images": [],
            },
        ],
    }

    result = service.apply_import_payload(
        rows,
        payload,
        export_run_id="run-1",
        source_section_id="sec-1",
        exported_at="2026-03-20T10:00:00Z",
        target_scope={"notebook_id": "dst-1"},
    )

    assert [row["source_page_id"] for row in result] == ["page-ready", "page-missing", "page-duplicate"]
    assert result[0]["status"] == "Bereit"
    assert result[0]["selected"] is True
    assert result[1]["status"] == "Fehlt noch"
    assert result[1]["selected"] is False
    assert result[2]["status"] == "Duplikat"
    assert result[2]["selected"] is False
