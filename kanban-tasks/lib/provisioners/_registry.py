"""Capability → provisioner mapping for `openclaw project adopt`.

Order matters: caller iterates ADOPT_ORDER to provision sequentially per
spec §Sequência de adopt (detect → diff → act). Order encodes read-time
dependencies (ex: workspace must exist before persona writes IDENTITY.md).
"""
from __future__ import annotations

# Fixed ordering for adopt iteration, per W4 spec.
ADOPT_ORDER = (
    "code_repo",
    "knowledge_slot",
    "workspace",
    "persona",
    "bot",
    "telegram_topics",
    "kanban_sprints",
    "mission_control",
)

# Human label per capability (for tables / prompts). Mirrors render_status.
CAPABILITY_LABELS = {
    "code_repo": "code_repo",
    "knowledge_slot": "knowledge_slot",
    "workspace": "workspace",
    "persona": "persona",
    "bot": "bot",
    "telegram_topics": "telegram_topics",
    "kanban_sprints": "kanban_sprints",
    "mission_control": "mission_control",
}
