"""Migration script: state.json v3 → v4 (sprints strictly per-project).

Split-and-migrate: tasks ativas em sprint global órfã viram tasks da
current sprint do projeto correspondente. Sprint órfã vira closed
legacy. Idempotente (v4 já → noop). Dry-run mostra plano sem mutar.
"""
from typing import Any, Dict, List, Optional

from . import sprint as sprint_lib
from . import store


_TERMINAL_STATUSES = ("archived", "done", "rejected")


def _build_resprint_plan(state: Dict[str, Any], orphan_sprint_id: str,
                         valid_projects: List[str]) -> Dict[str, Any]:
    """Lista tasks ativas que precisariam de re-sprint, e detecta erros."""
    to_resprint = []
    errors = []
    for t in state["tasks"]:
        if t.get("sprint_id") != orphan_sprint_id:
            continue
        if t.get("status") in _TERMINAL_STATUSES:
            continue
        proj = t.get("project")
        if proj is None:
            errors.append({"task_id": t["id"], "error": "TASK_MISSING_PROJECT"})
            continue
        if proj not in valid_projects:
            errors.append({
                "task_id": t["id"], "error": "TASK_UNKNOWN_PROJECT",
                "project": proj,
            })
            continue
        to_resprint.append({"task_id": t["id"], "target_project": proj})
    return {"to_resprint": to_resprint, "errors": errors}


def _find_orphan_sprint(state: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    for sp in state["sprints"]:
        if sp.get("project") is None and sp["state"] == "current":
            return sp
    return None


def migrate_to_per_project(actor: str = "bernard",
                           dry_run: bool = False) -> Dict[str, Any]:
    """Migra state.json de v3 (sprints globais) pra v4 (per-project).

    Idempotente: se schema já é v4, retorna noop.
    `dry_run=True` retorna plano sem mutar.
    Fail-fast em data inconsistente (TASK_MISSING_PROJECT, TASK_UNKNOWN_PROJECT).
    """
    state = store.read_state()
    if state.get("schema_version") == 4:
        return {"ok": True, "noop": True, "reason": "already_migrated"}

    valid_projects = store.read_projects()
    orphan = _find_orphan_sprint(state)
    if orphan is None:
        # sem órfã, mas schema é v3 → só faltou o bump
        if not dry_run:
            # Backup defensivo (mesmo no path no-orphan)
            backup_path = store.STATE_PATH.with_suffix(".pre-schema-v4.bak")
            backup_path.write_text(store.STATE_PATH.read_text(encoding="utf-8"),
                                   encoding="utf-8")
            sprint_lib.bootstrap(actor=actor)
            with store.mutate_state() as st:
                st["schema_version"] = 4
                seq = store.next_seq(st)
                store.append_event({
                    "seq": seq, "ts": store.now_iso(),
                    "type": "schema_migrated",
                    "actor": actor, "from_version": 3, "to_version": 4,
                })
                st["last_event_seq"] = seq
            return {"ok": True, "noop": False, "no_orphan": True,
                    "backup_path": str(backup_path)}
        return {"ok": True, "noop": False, "no_orphan": True, "backup_path": None}

    plan = _build_resprint_plan(state, orphan["id"], valid_projects)
    if plan["errors"]:
        raise ValueError(
            f"migration blocked by data errors (fix antes de re-rodar): "
            f"{plan['errors']}"
        )

    if dry_run:
        return {
            "ok": True,
            "dry_run": True,
            "schema_from": 3,
            "schema_to": 4,
            "orphan_sprint_id": orphan["id"],
            "would_resprint": plan["to_resprint"],
            "would_close": orphan["id"],
        }

    # Backup defensivo
    backup_path = store.STATE_PATH.with_suffix(".pre-schema-v4.bak")
    backup_path.write_text(store.STATE_PATH.read_text(encoding="utf-8"),
                           encoding="utf-8")

    # Step 1: bootstrap per-project sprints
    sprint_lib.bootstrap(actor=actor)

    # Step 2-4: re-sprint ativas, fechar órfã, bump schema
    with store.mutate_state() as state:
        # mapa project → current sprint id
        current_by_proj = {}
        for sp in state["sprints"]:
            if sp["state"] == "current" and sp.get("project"):
                current_by_proj[sp["project"]] = sp["id"]

        # re-sprint ativas
        tasks_by_id = {t["id"]: t for t in state["tasks"]}
        for entry in plan["to_resprint"]:
            t = tasks_by_id[entry["task_id"]]
            old_sid = t["sprint_id"]
            new_sid = current_by_proj[entry["target_project"]]
            t["sprint_id"] = new_sid
            t["updated_at"] = store.now_iso()
            seq = store.next_seq(state)
            store.append_event({
                "seq": seq, "ts": store.now_iso(),
                "type": "task_resprinted",
                "actor": actor, "task_id": t["id"],
                "from_sprint_id": old_sid, "to_sprint_id": new_sid,
                "reason": "schema_v4_migration",
            })
            state["last_event_seq"] = seq

        # fechar órfã
        for sp in state["sprints"]:
            if sp["id"] == orphan["id"]:
                sp["state"] = "closed"
                sp["closed_at"] = store.now_iso()
                seq = store.next_seq(state)
                store.append_event({
                    "seq": seq, "ts": store.now_iso(),
                    "type": "sprint_closed",
                    "actor": actor, "sprint_id": sp["id"],
                    "reason": "schema_v4_migration_legacy_global",
                })
                state["last_event_seq"] = seq
                break

        # bump schema
        state["schema_version"] = 4
        seq = store.next_seq(state)
        store.append_event({
            "seq": seq, "ts": store.now_iso(),
            "type": "schema_migrated",
            "actor": actor, "from_version": 3, "to_version": 4,
        })
        state["last_event_seq"] = seq

    return {
        "ok": True,
        "noop": False,
        "schema_from": 3,
        "schema_to": 4,
        "resprinted_count": len(plan["to_resprint"]),
        "closed_orphan": orphan["id"],
        "backup_path": str(backup_path),
    }
