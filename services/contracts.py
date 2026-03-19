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
    summary: dict[str, Any] = field(default_factory=dict)


@dataclass
class MigrationSessionResult:
    session_id: str
    source_scope: dict[str, Any]
    target_scope: dict[str, Any]
    dry_run_items: list[MigrationPageCandidate]
    dry_run_summary: dict[str, Any]
    execute_result: ExecuteResult | None = None
