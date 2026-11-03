"""Project doctor — cross-project drift scan + repair (W5).

Spec: bevox-knowledge/35_specs/openclaw/2026-05-07-project-lifecycle-w5-v1.md
ADR: bevox-knowledge/30_adr/openclaw/ADR-013-project-capability-state-machine.md

Modules:
- scanner: drift + orphan + drafts_pending detection (read-only).
- repair: maps drift → provisioner action (idempotent).
- _render: human-readable output paralelo a render_status.
"""
