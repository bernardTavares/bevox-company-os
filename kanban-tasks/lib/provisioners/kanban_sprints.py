"""provision_kanban_sprints — wraps step_2_kanban_bootstrap.

Creates 1 current + 1 next sprint for slug in kanban-tasks state.json.
Idempotent: helpers (`task.add_project`, `sprint.bootstrap`) are themselves
no-op when entry already exists.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional


@dataclass
class SprintsResult:
    state: str  # provisioned | partial | absent
    sprints_created: int = 0
    error: Optional[str] = None


def provision_kanban_sprints(
    slug: str,
    *,
    actor: str = "bernard",
) -> SprintsResult:
    """Bootstrap kanban sprints for slug.

    Args:
        slug: project id.
        actor: who initiated (logged in events.jsonl).

    Returns:
        SprintsResult.
    """
    from lib.project_factory import step_2_kanban_bootstrap

    try:
        details = step_2_kanban_bootstrap(slug, actor=actor)
    except Exception as e:  # broad catch — bootstrap is best-effort
        return SprintsResult(state="absent", error=str(e))

    sprints_created = details.get("sprints_created") or 0
    return SprintsResult(
        state="provisioned",
        sprints_created=sprints_created,
    )
