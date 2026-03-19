from services.contracts import MigrationPageCandidate, MigrationSessionResult
from services.session import is_session_valid


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
    )

    assert session.execute_result is None


def test_session_invalidates_when_source_scope_changes():
    session = MigrationSessionResult(
        session_id="session-1",
        source_scope={"section_id": "src-1"},
        target_scope={"notebook_id": "dst-1"},
        dry_run_items=[],
        dry_run_summary={},
        execute_result=None,
    )

    assert is_session_valid(
        session,
        {"section_id": "src-1"},
        {"notebook_id": "dst-1"},
        auth_state="connected",
    ) is True
    assert is_session_valid(
        session,
        {"section_id": "src-2"},
        {"notebook_id": "dst-1"},
        auth_state="connected",
    ) is False


def test_session_invalidates_when_auth_is_disconnected():
    session = MigrationSessionResult(
        session_id="session-1",
        source_scope={"section_id": "src-1"},
        target_scope={"notebook_id": "dst-1"},
        dry_run_items=[],
        dry_run_summary={},
        execute_result=None,
    )

    assert is_session_valid(
        session,
        {"section_id": "src-1"},
        {"notebook_id": "dst-1"},
        auth_state="disconnected",
    ) is False


def test_session_invalidates_when_target_scope_changes():
    session = MigrationSessionResult(
        session_id="session-1",
        source_scope={"section_id": "src-1"},
        target_scope={"notebook_id": "dst-1"},
        dry_run_items=[],
        dry_run_summary={},
        execute_result=None,
    )

    assert is_session_valid(
        session,
        {"section_id": "src-1"},
        {"notebook_id": "dst-2"},
        auth_state="connected",
    ) is False
