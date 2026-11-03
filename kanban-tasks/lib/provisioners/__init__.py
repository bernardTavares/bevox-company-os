"""Provisioners package — programmatic wrappers over external skill helpers.

Each module here exposes a `provision_<X>` function that orchestrates
sequenced shell helpers from a canonical skill (per ADR-014). The wrappers
keep `project_factory.create_project` thin: orchestrator stays in
`project_factory.py`, side-effecting choreography moves here.

Modules:
- knowledge: provisions ADR-010 canonical 9 subfolders for a project slug
  in bevox-knowledge, via the `bevox-knowledge-contribute` skill helpers
  (per ADR-014 §Amendment 2 + spec
  `35_specs/openclaw/2026-05-07-project-lifecycle-w2-v1.md`).
"""
