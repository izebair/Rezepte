# OneNote Desktop Migration MVP Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a Windows-local desktop app that reads OneNote pages, runs a dry-run migration analysis, lets the user deselect eligible pages, and migrates selected pages into a new OneNote structure under `Migrated Recipes`.

**Architecture:** Keep the existing parsing, taxonomy, review, and report logic as the domain core, but move orchestration behind service boundaries that both the desktop UI and the existing CLI can call. Implement a `tkinter` desktop shell with a controller/presenter layer, in-memory migration sessions, and a OneNote service that isolates Graph auth, hierarchy loading, duplicate checks, and page writes.

**Tech Stack:** Python, tkinter/ttk, msal, requests, pytest, python-dotenv, PyInstaller

---

### Task 1: Service Contracts And Session Models

**Files:**
- Create: `services/__init__.py`
- Create: `services/contracts.py`
- Create: `services/session.py`
- Test: `tests/test_service_contracts.py`

- [ ] **Step 1: Write the failing test**

```python
from services.contracts import MigrationPageCandidate, MigrationSessionResult


def test_migration_session_starts_without_execute_result():
    item = MigrationPageCandidate(
        source_page_id="page-1",
        source_page_title="Tomatensuppe",
        selected=True,
        status="ready",
        recognized_title="Tomatensuppe",
        target_main_category="Vorspeise",
        target_subcategory="Suppen",
        duplicate=False,
        messages=[],
        fingerprint="abc",
        planned_target_path="Migrated Recipes/Vorspeise/Suppen",
        planned_target_section_id="section-1",
        planned_target_section_name="Suppen",
    )

    session = MigrationSessionResult(
        session_id="session-1",
        source_scope={"section_id": "src-1"},
        target_scope={"notebook_id": "nb-1"},
        dry_run_items=[item],
        dry_run_summary={"ready": 1},
        execute_result=None,
    )

    assert session.execute_result is None


def test_session_invalidates_when_source_scope_changes():
    from services.session import is_session_valid

    session = MigrationSessionResult(
        session_id="session-1",
        source_scope={"section_id": "src-1"},
        target_scope={"notebook_id": "dst-1"},
        dry_run_items=[],
        dry_run_summary={},
        execute_result=None,
    )

    assert is_session_valid(session, {"section_id": "src-1"}, {"notebook_id": "dst-1"}, auth_state="connected") is True
    assert is_session_valid(session, {"section_id": "src-2"}, {"notebook_id": "dst-1"}, auth_state="connected") is False
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_service_contracts.py -v`
Expected: FAIL with import or attribute errors because the new service contract types do not exist yet.

- [ ] **Step 3: Write minimal implementation**

```python
from dataclasses import dataclass, field
from typing import Any


@dataclass
class MigrationPageCandidate:
    source_page_id: str
    source_page_title: str
    selected: bool
    status: str
    recognized_title: str
    target_main_category: str
    target_subcategory: str
    duplicate: bool
    messages: list[str]
    fingerprint: str
    planned_target_path: str
    planned_target_section_id: str
    planned_target_section_name: str


@dataclass
class ExecuteResult:
    started_at: str
    finished_at: str
    items: list[dict[str, Any]] = field(default_factory=list)
    summary: dict[str, int] = field(default_factory=dict)


@dataclass
class MigrationSessionResult:
    session_id: str
    source_scope: dict[str, Any]
    target_scope: dict[str, Any]
    dry_run_items: list[MigrationPageCandidate]
    dry_run_summary: dict[str, int]
    execute_result: ExecuteResult | None = None


def is_session_valid(session, source_scope, target_scope, auth_state):
    return (
        auth_state == "connected"
        and session.source_scope == source_scope
        and session.target_scope == target_scope
    )
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_service_contracts.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add services/__init__.py services/contracts.py services/session.py tests/test_service_contracts.py
git commit -m "feat: add migration service contracts"
```

### Task 2: Extract OneNote Graph Service

**Files:**
- Create: `services/onenote_service.py`
- Modify: `onenote_import.py`
- Test: `tests/test_onenote_service.py`

- [ ] **Step 1: Write the failing test**

```python
from services.onenote_service import OneNoteService


def test_duplicate_check_is_limited_to_migrated_recipes_root():
    service = OneNoteService(token_provider=lambda: "token")
    pages = [
        {"id": "src-1", "title": "Tomatensuppe", "fingerprints": ["same"]},
        {"id": "dst-1", "title": "Tomatensuppe", "fingerprints": ["same"]},
    ]

    only_target = service._filter_target_root_pages(
        pages,
        target_root_name="Migrated Recipes",
        target_root_page_ids={"dst-1"},
    )

    assert [page["id"] for page in only_target] == ["dst-1"]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_onenote_service.py -v`
Expected: FAIL because `OneNoteService` and the target-root filtering logic do not exist yet.

- [ ] **Step 3: Write minimal implementation**

```python
class OneNoteService:
    def __init__(self, token_provider):
        self._token_provider = token_provider

    def _filter_target_root_pages(self, pages, target_root_name, target_root_page_ids):
        return [page for page in pages if page.get("id") in target_root_page_ids]
```

Add wrapper methods that move Graph auth and OneNote hierarchy functions out of `onenote_import.py` without changing behavior yet:
- `start_device_flow()`
- `complete_device_flow()`
- `list_notebooks()`
- `list_section_groups()`
- `list_sections()`
- `list_pages()`
- `get_page_source_item()`
- `ensure_target_root()`
- `ensure_category_group()`
- `ensure_subcategory_section()`
- `load_target_fingerprints()`
- `create_recipe_page()`

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_onenote_service.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add services/onenote_service.py onenote_import.py tests/test_onenote_service.py
git commit -m "refactor: extract onenote graph service"
```

### Task 3: Build Dry-Run Import Service

**Files:**
- Create: `services/import_service.py`
- Create: `services/report_service.py`
- Modify: `onenote_import.py`
- Test: `tests/test_import_service_dry_run.py`

- [ ] **Step 1: Write the failing test**

```python
from services.import_service import ImportService
from services.contracts import MigrationSessionResult


class FakeOneNoteService:
    def list_pages(self, source_scope):
        return [{"id": "page-1", "title": "Tomatensuppe"}]

    def get_page_source_item(self, page_id):
        return {
            "id": page_id,
            "title": "Tomatensuppe",
            "text": "Titel: Tomatensuppe\nGruppe: Vorspeise\nKategorie: Suppen\n\nZutaten:\n- 500 ml Wasser\n\nZubereitung:\n1. Kochen",
            "source_type": "onenote_page",
            "media": [],
        }

    def load_target_fingerprints(self, target_scope):
        return set()


def test_dry_run_builds_selectable_session():
    service = ImportService(onenote_service=FakeOneNoteService())

    session = service.run_dry_run(
        source_scope={"section_id": "src-1"},
        target_scope={"notebook_id": "dst-1"},
    )

    assert isinstance(session, MigrationSessionResult)
    assert session.dry_run_items[0].status == "ready"
    assert session.dry_run_items[0].selected is True
    assert session.dry_run_items[0].planned_target_path == "Migrated Recipes/Vorspeise/Suppen"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_import_service_dry_run.py -v`
Expected: FAIL because `ImportService.run_dry_run()` does not exist yet.

- [ ] **Step 3: Write minimal implementation**

```python
class ImportService:
    def __init__(self, onenote_service):
        self._onenote_service = onenote_service

    def run_dry_run(self, source_scope, target_scope):
        pages = self._onenote_service.list_pages(source_scope)
        source_item = self._onenote_service.get_page_source_item(pages[0]["id"])
        recipe = _parse_source_item_to_recipe(source_item)
        candidate = _build_candidate(recipe, source_item, selected=True)
        return MigrationSessionResult(
            session_id="session-1",
            source_scope=source_scope,
            target_scope=target_scope,
            dry_run_items=[candidate],
            dry_run_summary={"ready": 1},
            execute_result=None,
        )
```

Implementation notes:
- Reuse `page_to_source_item`, `_parse_and_validate_blocks`, `_build_report_item`, and taxonomy/review logic instead of rewriting parsing.
- Map dry-run results to `MigrationPageCandidate`.
- Mark `duplicate` and `error` rows as `selected=False`.

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_import_service_dry_run.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add services/import_service.py services/report_service.py onenote_import.py tests/test_import_service_dry_run.py
git commit -m "feat: add one-note dry-run import service"
```

### Task 4: Execute Migration For Selected Pages

**Files:**
- Modify: `services/import_service.py`
- Modify: `services/onenote_service.py`
- Test: `tests/test_import_service_execute.py`

- [ ] **Step 1: Write the failing test**

```python
from services.import_service import ImportService
from services.contracts import MigrationPageCandidate, MigrationSessionResult


class FakeOneNoteService:
    def __init__(self):
        self.created = []

    def load_target_fingerprints(self, target_scope):
        return {"dup"}

    def create_recipe_page(self, recipe, target_scope):
        self.created.append(recipe["titel"])
        return {"id": "new-1", "url": "https://example/page"}


def test_execute_skips_excluded_and_duplicate_items():
    session = MigrationSessionResult(
        session_id="session-1",
        source_scope={"section_id": "src-1"},
        target_scope={"notebook_id": "dst-1"},
        dry_run_items=[
            MigrationPageCandidate("1", "A", True, "ready", "A", "Snack", "Herzhaft", False, [], "ok", "Migrated Recipes/Snack/Herzhaft", "sec-1", "Herzhaft"),
            MigrationPageCandidate("2", "B", False, "excluded", "B", "Snack", "Herzhaft", False, [], "skip", "Migrated Recipes/Snack/Herzhaft", "sec-1", "Herzhaft"),
            MigrationPageCandidate("3", "C", False, "duplicate", "C", "Snack", "Herzhaft", True, [], "dup", "Migrated Recipes/Snack/Herzhaft", "sec-1", "Herzhaft"),
        ],
        dry_run_summary={"ready": 1, "excluded": 1, "duplicate": 1},
        execute_result=None,
    )
    service = ImportService(onenote_service=FakeOneNoteService())

    updated = service.run_execute(session)

    assert updated.execute_result.summary["migrated"] == 1
    assert updated.execute_result.summary["excluded"] == 1
    assert updated.execute_result.summary["duplicate_skipped"] == 1
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_import_service_execute.py -v`
Expected: FAIL because `run_execute()` and execute summaries do not exist yet.

- [ ] **Step 3: Write minimal implementation**

```python
def run_execute(self, session):
    items = []
    summary = {"migrated": 0, "duplicate_skipped": 0, "write_error": 0, "excluded": 0}
    target_fingerprints = self._onenote_service.load_target_fingerprints(session.target_scope)

    for item in session.dry_run_items:
        if item.status == "duplicate":
            items.append({"source_page_id": item.source_page_id, "status": "duplicate_skipped", "message": "duplicate", "written_target_page_id": "", "written_target_url": "", "planned_target_path": item.planned_target_path})
            summary["duplicate_skipped"] += 1
            continue
        if not item.selected:
            items.append({"source_page_id": item.source_page_id, "status": "excluded", "message": "excluded", "written_target_page_id": "", "written_target_url": "", "planned_target_path": item.planned_target_path})
            summary["excluded"] += 1
            continue
        # write selected ready item
```

Implementation notes:
- Count results using the canonical buckets from the spec.
- Recheck duplicates only against the `Migrated Recipes` subtree.
- If a source page changed or disappeared since dry-run, mark that item `write_error` and continue.

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_import_service_execute.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add services/import_service.py services/onenote_service.py tests/test_import_service_execute.py
git commit -m "feat: execute selected one-note migrations"
```

### Task 5: Build The Desktop UI Shell

**Files:**
- Create: `app.pyw`
- Create: `gui/__init__.py`
- Create: `gui/main_window.py`
- Create: `gui/controller.py`
- Test: `tests/test_gui_controller.py`

- [ ] **Step 1: Write the failing test**

```python
from gui.controller import MainController


class FakeImportService:
    def __init__(self, session):
        self._session = session
        self.executed = False

    def run_dry_run(self, source_scope, target_scope):
        return self._session

    def run_execute(self, session):
        self.executed = True
        return session


def test_bulk_selection_only_affects_selectable_rows(sample_session):
    controller = MainController(import_service=FakeImportService(sample_session))
    controller.load_session(sample_session)

    controller.select_none()

    statuses = {item.source_page_id: item.selected for item in controller.session.dry_run_items}
    assert statuses["ready-page"] is False
    assert statuses["excluded-page"] is False
    assert statuses["duplicate-page"] is False
    assert statuses["error-page"] is False


def test_filter_rows_by_status(sample_session):
    controller = MainController(import_service=FakeImportService(sample_session))
    controller.load_session(sample_session)

    filtered = controller.filter_items({"duplicate"})

    assert len(filtered) == 1
    assert filtered[0].status == "duplicate"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_gui_controller.py -v`
Expected: FAIL because the GUI controller does not exist yet.

- [ ] **Step 3: Write minimal implementation**

```python
class MainController:
    def __init__(self, import_service):
        self.import_service = import_service
        self.session = None

    def load_session(self, session):
        self.session = session

    def select_none(self):
        for item in self.session.dry_run_items:
            if item.status in {"ready", "excluded"}:
                item.selected = False
                item.status = "excluded"

    def filter_items(self, allowed_statuses):
        return [item for item in self.session.dry_run_items if item.status in allowed_statuses]
```

Implementation notes:
- Keep the controller UI-free enough to test without a live `tkinter` loop.
- The `ttk.Treeview` should show source page, recognized title, target path, status, and messages.
- Provide actions for login, source loading, dry-run, select all, select none, and execute.
- Block `execute` when `is_session_valid(...)` returns `False`.
- Provide status filters for at least `ready`, `duplicate`, and `error`.
- Run long operations on a background thread and marshal updates back to the main UI thread.

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_gui_controller.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add app.pyw gui/__init__.py gui/main_window.py gui/controller.py tests/test_gui_controller.py
git commit -m "feat: add desktop shell for one-note migration"
```

### Task 6: Rewire CLI And Document Windows Usage

**Files:**
- Modify: `onenote_import.py`
- Modify: `README.md`
- Test: `tests/test_cli_service_bridge.py`

- [ ] **Step 1: Write the failing test**

```python
import onenote_import


def test_main_uses_import_service_for_dry_run(monkeypatch):
    called = {}

    class FakeImportService:
        def run_dry_run(self, source_scope, target_scope):
            called["dry_run"] = (source_scope, target_scope)
            return object()

    monkeypatch.setattr(onenote_import, "build_import_service", lambda: FakeImportService())

    result = onenote_import.main(["--dry-run", "--source-section-id", "src-1", "--target-notebook", "Rezepte"])

    assert result == 0
    assert "dry_run" in called
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_cli_service_bridge.py -v`
Expected: FAIL because `main()` still owns the orchestration directly.

- [ ] **Step 3: Write minimal implementation**

```python
def build_import_service():
    return ImportService(onenote_service=build_onenote_service())


def main(argv=None):
    args = parse_args(argv)
    service = build_import_service()
    if args.dry_run:
        service.run_dry_run(source_scope=_source_scope_from_args(args), target_scope=_target_scope_from_args(args))
        return 0
```

Implementation notes:
- Do not preserve terminal-first behavior as the architectural center.
- Keep CLI compatibility only as a thin developer adapter for OneNote-only automation and regression safety.
- Update the README to make the desktop app the primary usage path and CLI the secondary developer path.

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_cli_service_bridge.py -v`
Expected: PASS

- [ ] **Step 5: Run the focused suite**

Run: `pytest tests/test_service_contracts.py tests/test_onenote_service.py tests/test_import_service_dry_run.py tests/test_import_service_execute.py tests/test_gui_controller.py tests/test_cli_service_bridge.py -v`
Expected: PASS for all new MVP tests

- [ ] **Step 6: Commit**

```bash
git add onenote_import.py README.md tests/test_cli_service_bridge.py
git commit -m "docs: make desktop migration app the primary workflow"
```

### Task 7: MVP Verification And Packaging Prep

**Files:**
- Modify: `README.md`
- Modify: `requirements.txt`
- Create: `desktop_app.spec`
- Test: `tests/test_desktop_app_smoke.py`

- [ ] **Step 1: Write the failing test**

```python
from pathlib import Path


def test_desktop_entrypoint_exists():
    assert Path("app.pyw").exists()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_desktop_app_smoke.py -v`
Expected: FAIL until the desktop entrypoint exists in the repo.

- [ ] **Step 3: Write minimal implementation**

```python
if __name__ == "__main__":
    from gui.main_window import run_app
    run_app()
```

Add:
- `PyInstaller` build instructions to `README.md`
- packaging spec file `desktop_app.spec`
- any missing runtime dependency declarations

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_desktop_app_smoke.py -v`
Expected: PASS

- [ ] **Step 5: Run broader regression suite**

Run: `pytest -q`
Expected: PASS with no regressions in existing parsing/review/report tests

- [ ] **Step 6: Commit**

```bash
git add README.md requirements.txt desktop_app.spec tests/test_desktop_app_smoke.py
git commit -m "build: prepare windows desktop packaging"
```
