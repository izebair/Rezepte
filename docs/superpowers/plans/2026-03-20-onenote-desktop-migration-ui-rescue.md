# OneNote Desktop Migration UI Rescue Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the misleading desktop MVP flow with an honest Windows-style wizard that auto-signs in, shows a left notebook/section hierarchy, exports one Markdown package per selected section, reimports external JSON enrichment, supports per-row selection, and runs safe bulk migration back to OneNote.

**Architecture:** Keep OneNote read/write and recipe parsing in services, but introduce an explicit export/import run contract between the desktop app and external enrichment. Make the desktop UI stateful around one active section/export run at a time, with the app owning row statuses and migration outcomes while external JSON only supplies enrichment data.

**Tech Stack:** Python, tkinter/ttk, msal, requests, pytest, python-dotenv, PyInstaller

---

## File Structure

### Existing files to modify

- `app.pyw`
  Desktop startup, local `.venv` bootstrap, service wiring for auto-login and the new export/import workflow.

- `gui/controller.py`
  UI state machine, active export run state, selection/status rules, login/source gating, retry handling.

- `gui/main_window.py`
  Actual Windows-facing layout: left hierarchy, right grid, copyable login code, export/import actions, row selection, migration result display.

- `services/contracts.py`
  Contracts for export runs, enriched rows, migration states, and JSON import payloads.

- `services/session.py`
  Session/run validation helpers.

- `services/import_service.py`
  Dry-run execution, JSON reconciliation, migration result application, duplicate recheck on write.

- `services/onenote_service.py`
  OneNote hierarchy loading, page/media export helpers, target duplicate checks, page writes.

- `README.md`
  Product usage docs for the honest export -> external AI -> JSON reimport -> migrate flow.

### New files to create

- `services/export_package_service.py`
  Builds the export package for one section: Markdown, images, metadata, deterministic file naming.

- `services/import_payload_service.py`
  Validates imported JSON, enforces run IDs and source-page joins, and maps imported enrichment onto existing rows.

- `tests/test_export_package_service.py`
  Export package creation, stable file naming, image reference handling.

- `tests/test_import_payload_service.py`
  JSON schema, run identity, duplicate/unknown row rejection, missing entries handling.

- `tests/test_ui_rescue_controller.py`
  Auto-login states, disabled hierarchy before auth, section switching, row status matrix, retry/reset behavior.

- `tests/test_ui_rescue_window.py`
  Main window layout wiring: left hierarchy, copyable login code, context actions, button state transitions.

### Ownership clarifications

- `services/export_package_service.py`
  Owns metadata-file serialization for the export package, including `export_run_id`, `source_notebook_id`, `source_section_id`, `exported_at`, and exported page references.

- `services/import_payload_service.py`
  Owns the concrete JSON schema validation and the reconciliation envelope rules for `export_run_id`, `source_section_id`, and `source_page_id`.

- `services/import_service.py`
  Owns app-side derivation of final row status from enrichment plus OneNote duplicate lookups. This is where `Bereit`, `Fehlt noch`, `Fehler`, and pre-migration `Duplikat` are computed before the UI enables selection.

## Task 1: Lock The Run Contract

**Files:**
- Modify: `services/contracts.py`
- Modify: `services/session.py`
- Test: `tests/test_import_payload_service.py`

- [ ] **Step 1: Write the failing tests**

```python
from services.contracts import ExportRunContext, ImportedRecipePayload


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


def test_import_payload_requires_matching_run_and_unique_source_ids():
    duplicate_payload = ImportedRecipePayload(
        export_run_id="run-1",
        source_section_id="sec-1",
        recipes=[{"source_page_id": "page-1"}, {"source_page_id": "page-1"}],
    )

    try:
        validate_import_payload(duplicate_payload, expected_run_id="run-1", expected_section_id="sec-1")
    except RuntimeError as exc:
        assert "source_page_id" in str(exc)


def test_import_payload_rejects_wrong_run_identity():
    payload = ImportedRecipePayload(
        export_run_id="run-x",
        source_section_id="sec-1",
        recipes=[{"source_page_id": "page-1"}],
    )

    try:
        validate_import_payload(payload, expected_run_id="run-1", expected_section_id="sec-1")
    except RuntimeError as exc:
        assert "export_run_id" in str(exc)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_import_payload_service.py -v`
Expected: FAIL because the new export/import contract types do not exist yet.

- [ ] **Step 3: Write minimal implementation**

Implement contract dataclasses for:
- active export run context
- imported JSON payload envelope
- enriched row data needed by the app

Add validation helpers in `services/session.py` for:
- active run ID matching
- section ID matching
- unique `source_page_id` enforcement
- required `exported_at` field preservation

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_import_payload_service.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add services/contracts.py services/session.py tests/test_import_payload_service.py
git commit -m "feat: add export and import run contracts"
```

## Task 2: Build Section Export Packages

**Files:**
- Create: `services/export_package_service.py`
- Modify: `services/onenote_service.py`
- Test: `tests/test_export_package_service.py`

- [ ] **Step 1: Write the failing tests**

```python
from services.export_package_service import ExportPackageService


class FakeOneNoteService:
    def list_pages(self, section_id):
        return [{"id": "page-1", "title": "Kuchen"}]

    def get_page_source_item(self, page):
        return {"id": page["id"], "title": page["title"], "text": "Rohtext", "media": [{"name": "bild.jpg", "bytes": b"img"}]}


def test_export_package_creates_markdown_images_and_metadata(tmp_path):
    service = ExportPackageService(FakeOneNoteService())

    result = service.export_section(
        notebook_id="nb-1",
        notebook_name="Rezepte",
        section_id="sec-1",
        section_name="Diverse",
        output_root=tmp_path,
    )

    assert result.export_run_id
    assert (tmp_path / result.export_run_id / "section_export.md").exists()
    assert (tmp_path / result.export_run_id / "images").exists()
    assert result.exported_at
    assert result.exported_page_ids == ["page-1"]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_export_package_service.py -v`
Expected: FAIL because the export package service does not exist yet.

- [ ] **Step 3: Write minimal implementation**

Implement:
- deterministic export folder layout per run
- `section_export.md`
- metadata file with `export_run_id`, notebook/section IDs, page IDs
- `exported_at` timestamp in metadata
- unique image filenames using page ID + ordinal
- relative image paths suitable for later JSON references

Extend `services/onenote_service.py` with the minimal media export helpers needed by this service.

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_export_package_service.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add services/export_package_service.py services/onenote_service.py tests/test_export_package_service.py
git commit -m "feat: add section export package service"
```

## Task 3: Validate And Reconcile Imported JSON

**Files:**
- Create: `services/import_payload_service.py`
- Modify: `services/import_service.py`
- Test: `tests/test_import_payload_service.py`

- [ ] **Step 1: Write the failing tests**

```python
from services.import_payload_service import ImportPayloadService


def test_import_payload_marks_missing_rows_as_fehlt_noch():
    service = ImportPayloadService()
    rows = [{"source_page_id": "page-1"}, {"source_page_id": "page-2"}]
    payload = {
        "export_run_id": "run-1",
        "source_section_id": "sec-1",
        "recipes": [{"source_page_id": "page-1", "title": "Kuchen", "target_main_category": "Dessert", "target_subcategory": "Kuchen", "images": []}],
    }

    result = service.reconcile_rows(rows, payload, export_run_id="run-1", source_section_id="sec-1")

    assert result[0]["status"] == "Bereit"
    assert result[1]["status"] == "Fehlt noch"


def test_import_payload_rejects_unknown_source_page_ids():
    service = ImportPayloadService()
    rows = [{"source_page_id": "page-1"}]
    payload = {
        "export_run_id": "run-1",
        "source_section_id": "sec-1",
        "recipes": [{"source_page_id": "page-x"}],
    }

    try:
        service.reconcile_rows(rows, payload, export_run_id="run-1", source_section_id="sec-1")
    except RuntimeError as exc:
        assert "source_page_id" in str(exc)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_import_payload_service.py -v`
Expected: FAIL because JSON reconciliation is not implemented.

- [ ] **Step 3: Write minimal implementation**

Implement reconciliation rules exactly as specified:
- require matching `export_run_id`
- require matching `source_section_id`
- reject duplicate or unknown `source_page_id`
- preserve row order
- enrich existing rows in place
- set missing rows to `Fehlt noch`
- mark rows with missing image references as `Fehler`
- let the app compute final status, not the imported JSON
- perform the first duplicate lookup before migration and mark those rows as `Duplikat`

Thread the result into `services/import_service.py` so the desktop UI can apply the imported enrichment to its active section list.

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_import_payload_service.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add services/import_payload_service.py services/import_service.py tests/test_import_payload_service.py
git commit -m "feat: add json reconciliation for active export runs"
```

## Task 4: Rescue The Controller State Machine

**Files:**
- Modify: `gui/controller.py`
- Modify: `app.pyw`
- Test: `tests/test_ui_rescue_controller.py`

- [ ] **Step 1: Write the failing tests**

```python
from gui.controller import MainController


def test_source_tree_stays_disabled_until_login_succeeds():
    controller = MainController(import_service=object())

    assert controller.auth_state == "disconnected"
    assert controller.can_load_source_tree() is False


def test_selecting_section_loads_raw_rows_with_disabled_selection():
    controller = MainController(import_service=object())
    controller.auth_state = "connected"

    controller.load_raw_section_rows(
        {"section_id": "sec-1"},
        [{"source_page_id": "page-1", "source_page_title": "Kuchen"}],
    )

    assert controller.rows[0]["status"] == "Roh"
    assert controller.rows[0]["action_label"] == "Aufbereitung ausstehend"
    assert controller.rows[0]["selected"] is False
    assert controller.rows[0]["selectable"] is False


def test_section_switch_clears_previous_enrichment():
    controller = MainController(import_service=object())
    controller.active_export_run_id = "run-1"
    controller.rows = [{"source_page_id": "page-1", "status": "Bereit"}]

    controller.on_section_changed({"section_id": "sec-2"})

    assert controller.active_export_run_id is None
    assert controller.rows == []
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_ui_rescue_controller.py -v`
Expected: FAIL because the controller does not yet model the new wizard state rules.

- [ ] **Step 3: Write minimal implementation**

Add controller state for:
- auto-login lifecycle
- disabled hierarchy before auth
- login banner states: pending, code-required, error
- active notebook/section selection
- active export run context
- current rows for the selected section
- imported enrichment state
- migration result reset path for `Migrationsfehler`
- retry action for failed login on the same page

Add raw-row initialization behavior:
- selecting a section immediately loads rows as `Roh`
- action label is `Aufbereitung ausstehend`
- selection stays disabled until JSON import

Remove/retire obsolete interaction concepts:
- explicit login button flow
- fake “analysis” gating
- misleading selection defaults on raw rows

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_ui_rescue_controller.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add app.pyw gui/controller.py tests/test_ui_rescue_controller.py
git commit -m "feat: add controller state machine for ui rescue flow"
```

## Task 5: Rebuild The Main Window Layout

**Files:**
- Modify: `gui/main_window.py`
- Test: `tests/test_ui_rescue_window.py`

- [ ] **Step 1: Write the failing tests**

```python
def test_main_window_shows_left_hierarchy_and_top_actions():
    root = build_test_root()
    window = build_window(root)

    assert widget_texts(root, ttk.Label).count("Notebook") >= 1
    assert "Abschnitt exportieren" in widget_texts(root, ttk.Button)
    assert "Aufbereitetes JSON importieren" in widget_texts(root, ttk.Button)


def test_login_code_is_rendered_in_copyable_field():
    root = build_test_root()
    window = build_window(root)

    assert window.login_code_entry.cget("state") == "readonly"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_ui_rescue_window.py -v`
Expected: FAIL because the main window still uses the old toolbar-first layout.

- [ ] **Step 3: Write minimal implementation**

Rebuild the desktop UI to match the approved design:
- left sidebar with flow context + notebook/section tree
- right pane with banner + top action row + stable table
- copyable login code field
- optional browser-open action for code-required login state
- `Erneut versuchen` action for failed login state
- no visible IDs
- no login button
- no complete-login button as standard path
- no prominent `Select None`
- top actions limited to the current context

Define a small Tk test harness in `tests/test_ui_rescue_window.py`:
- helper to build a hidden root window
- helper to instantiate `MainWindow`
- helper to collect widget texts by class
- direct references for important widgets that must remain testable

Keep the tone Windows-native and restrained, not flashy.

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_ui_rescue_window.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add gui/main_window.py tests/test_ui_rescue_window.py
git commit -m "feat: rebuild desktop window for wizard rescue flow"
```

## Task 6: Wire Export, Import, Selection, And Retry Through The UI

**Files:**
- Modify: `gui/controller.py`
- Modify: `gui/main_window.py`
- Modify: `services/import_service.py`
- Test: `tests/test_ui_rescue_controller.py`

- [ ] **Step 1: Write the failing tests**

```python
def test_ready_rows_are_selected_by_default_after_json_import():
    assert rows[0]["status"] == "Bereit"
    assert rows[0]["selected"] is True


def test_failed_rows_can_be_reset_to_retryable_ready_state():
    controller.reset_failed_rows()
    assert rows[0]["status"] == "Bereit"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_ui_rescue_controller.py -v`
Expected: FAIL because the post-import and retry behavior is incomplete.

- [ ] **Step 3: Write minimal implementation**

Implement:
- row selection only for `Bereit`
- `Alle auswählen` only on eligible rows
- JSON import action that enriches current raw rows
- `Fehlgeschlagene zurücksetzen`
- active run invalidation when the user re-exports or switches section
- keep `Duplikat` rows unselectable after the first app-side duplicate check

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_ui_rescue_controller.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add gui/controller.py gui/main_window.py services/import_service.py tests/test_ui_rescue_controller.py
git commit -m "feat: wire export import selection and retry flow"
```

## Task 7: Finalize Bulk Migration Result Transparency

**Files:**
- Modify: `services/import_service.py`
- Modify: `gui/controller.py`
- Modify: `gui/main_window.py`
- Test: `tests/test_import_service_execute.py`
- Test: `tests/test_ui_rescue_controller.py`

- [ ] **Step 1: Write the failing tests**

```python
def test_execute_marks_success_and_failure_rows_individually():
    assert results["page-1"]["status"] == "Migriert"
    assert results["page-2"]["status"] == "Migrationsfehler"


def test_execute_rechecks_duplicates_at_write_time():
    assert results["page-3"]["status"] == "Duplikat"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_import_service_execute.py tests/test_ui_rescue_controller.py -v`
Expected: FAIL because execute results are not yet fully mapped back to the approved UI states.

- [ ] **Step 3: Write minimal implementation**

Map execute results back to the UI row state model:
- `Migriert`
- `Migrationsfehler`
- newly detected duplicate during write-time recheck

Add summary counters for:
- migrated
- duplicate during write
- failed

Expose them in the UI after each bulk run.

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_import_service_execute.py tests/test_ui_rescue_controller.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add services/import_service.py gui/controller.py gui/main_window.py tests/test_import_service_execute.py tests/test_ui_rescue_controller.py
git commit -m "feat: add transparent bulk migration results"
```

## Task 8: Documentation And Regression

**Files:**
- Modify: `README.md`
- Test: `tests/test_app_service.py`
- Test: `tests/test_ui_rescue_controller.py`
- Test: `tests/test_ui_rescue_window.py`
- Test: `tests/test_import_payload_service.py`
- Test: `tests/test_export_package_service.py`

- [ ] **Step 1: Write the failing or missing documentation checks**

Add or extend tests to cover:
- app startup bootstrap and auto-login entry path
- export package creation
- JSON reconciliation and stale-run rejection
- section switch state reset
- retry reset behavior

- [ ] **Step 2: Run targeted tests**

Run: `pytest tests/test_app_service.py tests/test_export_package_service.py tests/test_import_payload_service.py tests/test_ui_rescue_controller.py tests/test_ui_rescue_window.py -v`
Run: `pytest tests/test_app_service.py tests/test_export_package_service.py tests/test_import_payload_service.py tests/test_import_service_execute.py tests/test_ui_rescue_controller.py tests/test_ui_rescue_window.py -v`
Expected: PASS once all rescue flow pieces are complete.

- [ ] **Step 3: Update docs**

Document:
- startup and auto-login expectation
- export package files
- external AI enrichment contract
- JSON reimport flow
- image handling
- migration retry behavior

- [ ] **Step 4: Run full regression**

Run: `pytest -q`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add README.md tests/test_app_service.py tests/test_export_package_service.py tests/test_import_payload_service.py tests/test_ui_rescue_controller.py tests/test_ui_rescue_window.py
git commit -m "docs: describe ui rescue migration workflow"
```
