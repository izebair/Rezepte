from __future__ import annotations

from typing import Any

from .contracts import MigrationSessionResult


def is_session_valid(
    session: MigrationSessionResult,
    source_scope: dict[str, Any],
    target_scope: dict[str, Any],
    auth_state: str,
) -> bool:
    if auth_state != "connected":
        return False
    if session.source_scope != source_scope:
        return False
    if session.target_scope != target_scope:
        return False
    return True
