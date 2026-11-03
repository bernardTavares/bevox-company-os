"""Reaper: varredor periodico de executions detached.

Wave-3.5 do PRD orchestration. Fecha loop detached que para em testing
(limitacao §10.2 da spec do tester-agent).

Decisoes travadas (§2 da spec detached-reaper):
- Sequencial + ordem deterministica (started_at asc, tie-break filename)
- Lock global do lote (fcntl 1x por tick)
- Idempotente (post_action_applied=true skipa)
- Carve-out dispatch_flags.no_tester explicito
- Transparente (audit so em reaper.jsonl)
"""

import contextlib
import fcntl
import json
import os
import signal
import sys
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterator, List, Optional

from . import store

# UBN block_scanner integration (Task 9)
try:
    from . import block_scanner as _block_scanner_module
    from . import escalation_dispatcher as _escalation_dispatcher_module
except ImportError:
    _block_scanner_module = None  # type: ignore
    _escalation_dispatcher_module = None  # type: ignore

ROOT = Path(os.path.expanduser("~/.openclaw/dispatcher-agent"))
REAPER_JSONL = ROOT / "reaper.jsonl"
REAPER_LOCK = ROOT / "reaper.lock"
EXECUTIONS_DIR = ROOT / "executions"


class ReaperError(Exception):
    def __init__(self, code: str, detail: str):
        self.code = code
        self.detail = detail
        super().__init__(f"{code}: {detail}")


@contextlib.contextmanager
def global_lock(lockfile: Path) -> Iterator[bool]:
    """fcntl exclusive lock. Yields True se adquirido, False se contention.

    fcntl libera automaticamente no close do file descriptor (kernel).
    Nao bloqueante (LOCK_NB): segunda instancia retorna False imediato.
    """
    lockfile.parent.mkdir(parents=True, exist_ok=True)
    fd = os.open(str(lockfile), os.O_RDWR | os.O_CREAT, 0o644)
    try:
        try:
            fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
            yield True
        except (BlockingIOError, OSError):
            yield False
    finally:
        try:
            fcntl.flock(fd, fcntl.LOCK_UN)
        except OSError:
            pass
        os.close(fd)


def make_tick_id() -> str:
    return f"{store.now_iso()}-{uuid.uuid4().hex[:8]}"


def scan_executions(executions_dir: Path) -> List[Dict[str, Any]]:
    """Le todos os <task_id>.status.json sob executions_dir.

    Retorna lista ordenada deterministicamente:
    - primario: started_at ascendente (FIFO de quem comecou primeiro)
    - tie-break: nome do arquivo ascendente (alfabetico)

    Ignora corrupt files (JSON invalido). Dir inexistente -> [].
    """
    if not executions_dir.exists() or not executions_dir.is_dir():
        return []
    out: List[Dict[str, Any]] = []
    for p in executions_dir.iterdir():
        if not p.is_file() or not p.name.endswith(".status.json"):
            continue
        try:
            with open(p, "r", encoding="utf-8") as f:
                data = json.load(f)
        except (OSError, json.JSONDecodeError):
            continue
        data["_status_path"] = str(p)
        data["_status_filename"] = p.name
        out.append(data)
    out.sort(key=lambda d: (d.get("started_at") or "",
                            d.get("_status_filename") or ""))
    return out


def _pid_alive(pid: int) -> bool:
    """Check if pid esta alive via os.kill(pid, 0)."""
    if not pid:
        return False
    try:
        os.kill(pid, 0)
        return True
    except (OSError, ProcessLookupError):
        return False


def _detect_idle_finalize(jsonl_path: Optional[Path]) -> bool:
    """True if last assistant msg is text-only (no tool_use) AND idle > threshold.

    Reads jsonl_path full file. Scans backwards for first assistant msg.
    If that message contains tool_use → still active → False.
    Else compute delta_t between message timestamp and now; if > threshold → True.

    Tolerates corrupt lines (per-line try/except). Returns False on missing
    path, missing file, no valid lines, no assistant message, missing
    timestamp, or unparseable timestamp.
    """
    if jsonl_path is None or not jsonl_path.exists():
        return False
    try:
        with open(jsonl_path, "r", encoding="utf-8") as f:
            raw_lines = f.readlines()
    except OSError:
        return False
    last_assistant = None
    for line in reversed(raw_lines):
        line = line.strip()
        if not line:
            continue
        try:
            d = json.loads(line)
        except json.JSONDecodeError:
            continue
        msg = d.get("message") or {}
        if msg.get("role") != "assistant":
            continue
        content = msg.get("content") or []
        if not isinstance(content, list):
            continue
        has_tool_use = any(isinstance(c, dict) and c.get("type") == "tool_use"
                           for c in content)
        if has_tool_use:
            return False  # Still in middle of tool chain
        last_assistant = d
        break
    if last_assistant is None:
        return False
    ts = last_assistant.get("timestamp")
    parsed = _parse_iso_safe(ts)
    if parsed is None:
        return False
    delta = (datetime.now(timezone.utc) - parsed).total_seconds()
    return delta > IDLE_FINALIZE_THRESHOLD_S


def _idle_finalize_action(task_id: str, status: Dict[str, Any]) -> None:
    """SIGINT → 15s grace → SIGTERM → 15s grace → SIGKILL.

    No-op when no pid. Uses os.kill (works for transient systemd-run units
    spawned by runner.py — pid is the claude-cli subprocess).
    """
    pid = status.get("pid")
    if not pid:
        return

    # Stage 1: SIGINT (graceful interrupt; allows flush)
    try:
        os.kill(pid, signal.SIGINT)
    except (OSError, ProcessLookupError):
        return  # Already gone

    deadline = time.monotonic() + GRACE_SIGINT_SECONDS
    while time.monotonic() < deadline:
        if not _pid_alive(pid):
            return
        time.sleep(1)

    # Stage 2: SIGTERM (firmer)
    try:
        os.kill(pid, signal.SIGTERM)
    except (OSError, ProcessLookupError):
        return

    deadline = time.monotonic() + GRACE_SIGTERM_SECONDS
    while time.monotonic() < deadline:
        if not _pid_alive(pid):
            return
        time.sleep(1)

    # Stage 3: SIGKILL (last resort; OS unconditional)
    try:
        os.kill(pid, signal.SIGKILL)
    except (OSError, ProcessLookupError):
        pass


def classify_execution(status: Dict[str, Any],
                      kanban_task: Optional[Dict[str, Any]] = None,
                      session_jsonl_path: Optional[Path] = None) -> str:
    """Classify execution status into reaper action.

    Returns:
      'idle_finalize'    — alive + JSONL idle > IDLE_FINALIZE_THRESHOLD_S (Bug A)
      'still_running'    — alive + JSONL still active OR session jsonl unavailable
      'needs_reap'       — finished_at == None AND process dead/no pid
      'needs_lifecycle'  — finished_at + NOT post_action_applied
      'needs_reinvoke'   — finished_at + post_action_applied + tester re-needed (Bug C)
      'already_reaped'   — finished_at + post_action_applied + (no re-invoke needed)

    Does not modify status. No side-effects. No I/O except _detect_idle_finalize
    (which reads jsonl when path provided).

    Backwards compat: kanban_task=None and session_jsonl_path=None preserve
    legacy behavior (5 outcomes, no idle/reinvoke detection).
    """
    pid = status.get("pid")
    if status.get("finished_at") is None:
        if pid and _pid_alive(pid):
            # Bug A check: did Claude already finish but subprocess hangs?
            if session_jsonl_path is not None and _detect_idle_finalize(session_jsonl_path):
                return "idle_finalize"
            return "still_running"
        return "needs_reap"

    if not status.get("post_action_applied"):
        return "needs_lifecycle"

    # Bug C check: task came back to testing after inconclusive
    if kanban_task is not None and _needs_tester_reinvoke(kanban_task, status):
        return "needs_reinvoke"

    return "already_reaped"


def append_audit(entry: Dict[str, Any]) -> None:
    """Append linha JSONL atomico em reaper.jsonl.

    Append POSIX (<PIPE_BUF=4KB linux) eh atomico; nossas linhas <1KB.
    """
    REAPER_JSONL.parent.mkdir(parents=True, exist_ok=True)
    line = json.dumps(entry, ensure_ascii=False) + "\n"
    with open(REAPER_JSONL, "a", encoding="utf-8") as f:
        f.write(line)


def _read_dispatch_flags_no_tester(task_id: str) -> bool:
    """Le dispatch_payload.dispatch_flags.no_tester via kanban CLI.

    Retorna False (default conservador) se ausente ou erro.
    """
    import subprocess
    KANBAN_CLI = f"{Path.home()}/.openclaw/kanban-tasks/cli.sh"
    try:
        r = subprocess.run(
            [KANBAN_CLI, "task", "show", task_id, "--json"],
            capture_output=True, text=True, check=False, timeout=10,
        )
    except (OSError, subprocess.TimeoutExpired):
        return False
    if r.returncode != 0:
        return False
    try:
        data = json.loads(r.stdout)
    except json.JSONDecodeError:
        return False
    task = data.get("task") or {}
    dp = task.get("dispatch_payload") or {}
    flags = dp.get("dispatch_flags") or {}
    return bool(flags.get("no_tester"))


# F3.2: Legacy executor safety net helpers
def _is_legacy_executor(unit_name: str) -> bool:
    """Returns True se unit NÃO tem RuntimeMaxSec set (RuntimeMaxUSec=infinity).

    Property name canônico do systemd é RuntimeMaxUSec; valor 'infinity' indica
    que não foi setado. Pre-F3.1 dispatchers criavam units sem deadline.
    """
    import subprocess
    try:
        result = subprocess.run(
            ["systemctl", "--user", "show",
             "--property=RuntimeMaxUSec", "--value", unit_name],
            capture_output=True, text=True, timeout=5, check=False,
        )
        return result.stdout.strip() == "infinity"
    except (subprocess.TimeoutExpired, OSError):
        return False


def _executor_age_hours(unit_name: str) -> float:
    """Returns hours since unit's ActiveEnterTimestamp (epoch usec via systemctl).
    Returns 0.0 se unit não existe ou parse falha."""
    import subprocess
    try:
        result = subprocess.run(
            ["systemctl", "--user", "show",
             "--property=ActiveEnterTimestamp", "--value", unit_name],
            capture_output=True, text=True, timeout=5, check=False,
        )
        ts_str = result.stdout.strip()
        if not ts_str or ts_str == "0":
            return 0.0
        # Try systemd display format first: "Wed 2026-04-29 19:16:00 -03".
        # Strip locale-dependent weekday prefix (systemd output respects
        # locale do user — pode ser "Qua" em pt_BR; só nos importa o resto).
        # Pad timezone offset com "00" se vier truncado ("-03" vs "-0300"):
        # %z requer ±HHMM mas systemd às vezes emite ±HH.
        try:
            ts_no_dow = ts_str.split(" ", 1)[1] if " " in ts_str else ts_str
            parts = ts_no_dow.rsplit(" ", 1)
            if len(parts) == 2 and len(parts[1]) == 3 and parts[1][0] in "+-":
                ts_no_dow = f"{parts[0]} {parts[1]}00"
            dt = datetime.strptime(ts_no_dow, "%Y-%m-%d %H:%M:%S %z")
            return (datetime.now(timezone.utc) - dt).total_seconds() / 3600
        except (ValueError, IndexError):
            # Fallback: raw epoch usec (test fixture format)
            try:
                usec = int(ts_str)
                dt = datetime.fromtimestamp(usec / 1_000_000, tz=timezone.utc)
                return (datetime.now(timezone.utc) - dt).total_seconds() / 3600
            except ValueError:
                return 0.0
    except (subprocess.TimeoutExpired, OSError):
        return 0.0


def _list_active_executor_units() -> List[str]:
    """List 'claude-task-*.service' units in active state."""
    import subprocess
    try:
        result = subprocess.run(
            ["systemctl", "--user", "list-units",
             "--type=service", "--state=active",
             "--no-legend", "--plain", "--no-pager"],
            capture_output=True, text=True, timeout=5, check=False,
        )
        units = []
        for line in result.stdout.splitlines():
            parts = line.split()
            if not parts:
                continue
            unit = parts[0]
            if unit.startswith("claude-task-") and unit.endswith(".service"):
                units.append(unit)
        return units
    except (subprocess.TimeoutExpired, OSError):
        return []


def _executor_legacy_reaper_stage() -> dict:
    """Kill legacy executors (sem RuntimeMaxSec) vivos > 12h.

    Kill switch: OPENCLAW_REAPER_EXECUTOR_LEGACY=0 desabilita.
    """
    import subprocess
    if os.environ.get("OPENCLAW_REAPER_EXECUTOR_LEGACY") == "0":
        return {"skipped_disabled": 1}
    threshold_hours = 12.0
    stats = {"checked": 0, "killed": 0, "errors": 0}
    for unit in _list_active_executor_units():
        stats["checked"] += 1
        if not _is_legacy_executor(unit):
            continue
        age = _executor_age_hours(unit)
        if age < threshold_hours:
            continue
        try:
            subprocess.run(
                ["systemctl", "--user", "stop", unit],
                capture_output=True, text=True, timeout=10, check=False,
            )
            stats["killed"] += 1
            # Extract task_id from unit name pattern "claude-task-T-XXXX-...service"
            task_id = "?"
            if unit.startswith("claude-task-T-"):
                rest = unit[len("claude-task-"):]
                parts = rest.split("-", 2)
                if len(parts) >= 2:
                    task_id = f"{parts[0]}-{parts[1]}"
            append_audit({
                "type": "executor_killed_legacy",
                "ts": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
                "unit": unit,
                "age_hours": round(age, 2),
                "task_id": task_id,
            })
        except (subprocess.TimeoutExpired, OSError):
            stats["errors"] += 1
    return stats


def process_executions(
    entries: List[Dict[str, Any]], dry_run: bool = False,
) -> Dict[str, Any]:
    """Processa lote sequencialmente. Retorna stats agregados pra audit.

    Reusa runner.reap_finished + lifecycle.process_finished_session +
    api._invoke_tester (todos existentes wave-2+3). Zero refactor desses.

    Idempotencia: 'already_reaped' eh skipado SEM side-effect; auditado
    em skipped_already_reaped + actions_per_task entry com stage='skip'
    pra observabilidade.
    """
    from . import runner, lifecycle
    from .api import _invoke_tester  # heritage wave-3

    stats: Dict[str, Any] = {
        "considered_executions": len(entries),
        "skipped_already_reaped": 0,
        "skipped_still_running": 0,
        "reaped_count": 0,
        "tester_invoked_count": 0,
        "reinvoke_scheduled_count": 0,
        "idle_finalized_count": 0,
        "actions_per_task": [],
    }

    kanban_state = _load_kanban_state()

    for entry in entries:
        task_id = entry.get("task_id")
        if not task_id:
            continue
        kanban_task = _find_kanban_task(kanban_state, task_id)
        sess_path = _resolve_session_jsonl_path(kanban_task, entry)
        cls = classify_execution(entry, kanban_task=kanban_task,
                                 session_jsonl_path=sess_path)

        if cls == "already_reaped":
            stats["skipped_already_reaped"] += 1
            stats["actions_per_task"].append({
                "task_id": task_id, "stage": "skip",
                "outcome": "already_reaped",
                "test_run_id": None,
            })
            continue
        if cls == "still_running":
            stats["skipped_still_running"] += 1
            stats["actions_per_task"].append({
                "task_id": task_id, "stage": "skip",
                "outcome": "still_running",
                "test_run_id": None,
            })
            continue

        if cls == "needs_reinvoke":
            # Bug C fix: reset post_action_applied + audit; next tick will
            # see needs_lifecycle and re-invoke tester via existing flow.
            if not dry_run:
                entry["post_action_applied"] = False
                # Drop scan-only metadata before persisting (avoid pollution)
                persist = {k: v for k, v in entry.items()
                           if not k.startswith("_status_")}
                status_path = Path(entry["_status_path"])
                status_path.write_text(
                    json.dumps(persist, ensure_ascii=False, indent=2),
                    encoding="utf-8",
                )
            stats["reinvoke_scheduled_count"] += 1
            stats["actions_per_task"].append({
                "task_id": task_id, "stage": "reinvoke",
                "outcome": "reinvoke_scheduled",
                "test_run_id": None,
            })
            # Audit (one event per reinvoke for traceability).
            # tick_id not surfaced to process_executions; leaving None to
            # avoid an invasive signature change — reaper.jsonl still captures.
            append_audit({
                "tick_id": None,
                "event": "reinvoke_scheduled",
                "task_id": task_id,
                "test_run_count": ((kanban_task or {}).get("dispatch_payload", {})
                                                      .get("test_result", {})
                                                      .get("test_run_count")),
                "ts": store.now_iso(),
            })
            continue

        if cls == "idle_finalize":
            if not dry_run:
                _idle_finalize_action(task_id, entry)
            stats["idle_finalized_count"] += 1
            stats["actions_per_task"].append({
                "task_id": task_id, "stage": "idle_finalize",
                "outcome": "idle_finalize_triggered",
                "test_run_id": None,
            })
            append_audit({
                "tick_id": None,  # process_executions doesn't have parent tick_id
                "event": "idle_finalize_triggered",
                "task_id": task_id,
                "pid": entry.get("pid"),
                "ts": store.now_iso(),
            })
            continue

        if dry_run:
            stats["actions_per_task"].append({
                "task_id": task_id, "stage": "dry_run",
                "outcome": f"would_handle_{cls}",
                "test_run_id": None,
            })
            continue

        post_action = ""
        # needs_reap: roda runner.reap_finished pra detectar exit + atualizar status.json
        if cls == "needs_reap":
            try:
                reaped_status = runner.reap_finished(task_id)
            except Exception as e:
                stats["actions_per_task"].append({
                    "task_id": task_id, "stage": "reaped",
                    "outcome": f"reap_error:{type(e).__name__}",
                    "test_run_id": None,
                })
                continue
            if reaped_status is None or reaped_status.get("finished_at") is None:
                stats["actions_per_task"].append({
                    "task_id": task_id, "stage": "reaped",
                    "outcome": "not_yet_finished",
                    "test_run_id": None,
                })
                continue
            stats["reaped_count"] += 1
            stats["actions_per_task"].append({
                "task_id": task_id, "stage": "reaped",
                "outcome": "exit_detected",
                "test_run_id": None,
            })

        # needs_lifecycle (incl. fall-through de needs_reap): aplica lifecycle
        try:
            lc_result = lifecycle.process_finished_session(task_id)
            post_action = lc_result.get("post_action") or "unknown"
            stats["actions_per_task"].append({
                "task_id": task_id, "stage": "lifecycle_applied",
                "outcome": post_action,
                "test_run_id": None,
            })
        except Exception as e:
            stats["actions_per_task"].append({
                "task_id": task_id, "stage": "lifecycle_applied",
                "outcome": f"lifecycle_error:{type(e).__name__}",
                "test_run_id": None,
            })
            continue

        # Se virou testing E no_tester=False, invoca tester
        if "auto_moved_to_testing" in post_action:
            no_tester = _read_dispatch_flags_no_tester(task_id)
            if no_tester:
                stats["actions_per_task"].append({
                    "task_id": task_id, "stage": "tester_invoked",
                    "outcome": "skipped_no_tester_flag",
                    "test_run_id": None,
                })
            else:
                invoked, summary = _invoke_tester(task_id, json_mode=True)
                if invoked:
                    stats["tester_invoked_count"] += 1
                stats["actions_per_task"].append({
                    "task_id": task_id, "stage": "tester_invoked",
                    "outcome": (summary.get("decision") or "tester_no_decision")
                    if invoked else "tester_invoke_failed",
                    "test_run_id": summary.get("test_run_id"),
                })

    return stats


# ----------------------------------------------------------------------------
# Resilience helpers (spec 2026-04-29-tester-and-reaper-resilience)
# ----------------------------------------------------------------------------

IDLE_FINALIZE_THRESHOLD_S = int(os.environ.get(
    "OPENCLAW_REAPER_IDLE_THRESHOLD", "180"))
GRACE_SIGINT_SECONDS = 15
GRACE_SIGTERM_SECONDS = 15
REINVOKE_BACKOFF_SCHEDULE = {1: 30, 2: 90, 3: 300, 4: 600}

KANBAN_STATE = Path(f"{Path.home()}/.openclaw/kanban-tasks/state.json")


def _load_kanban_state() -> Dict[str, Any]:
    """Load kanban state.json. Returns {} dict on error (degrade gracefully)."""
    try:
        with open(KANBAN_STATE, "r", encoding="utf-8") as f:
            return json.load(f) or {}
    except (OSError, json.JSONDecodeError):
        return {}


def _block_scanner_stage(state: dict) -> dict:
    """UBN stage: scan blocks + dispatch escalations.
    Try/except local — não derruba outros stages.

    Spec: bevox-knowledge/35_specs/openclaw/2026-04-30-universal-block-notifier.md §3, §6.7
    """
    stats = {"candidates_found": 0, "escalations_created": 0, "telegram_sent": 0,
             "retry_attempted": 0, "retry_succeeded": 0,
             "errors": 0, "skipped_kill_switch": False}
    if os.environ.get("OPENCLAW_REAPER_DISABLE_BLOCK_SCANNER") == "1":
        stats["skipped_kill_switch"] = True
        return stats
    if _block_scanner_module is None or _escalation_dispatcher_module is None:
        stats["errors"] += 1
        print("WARN: UBN modules not available", file=sys.stderr)
        return stats
    try:
        candidates = _block_scanner_module.scan_all(state)
        stats["candidates_found"] = len(candidates)
        for c in candidates:
            try:
                seq = _block_scanner_module.next_escalation_seq(c.task_id)
                path = _escalation_dispatcher_module.render_escalation_file(c, seq)
                stats["escalations_created"] += 1
                result = _escalation_dispatcher_module.dispatch_telegram(path, c)
                if result.get("sent"):
                    stats["telegram_sent"] += 1
            except Exception as e:
                stats["errors"] += 1
                print(f"UBN escalation failed for {c.task_id}: {e}", file=sys.stderr)

        # Retry undispatched escalations (Telegram falhou anteriormente)
        try:
            undispatched = _block_scanner_module.find_undispatched_open_escalations()
            for path, frontmatter in undispatched:
                stats["retry_attempted"] += 1
                try:
                    cand = _block_scanner_module.Candidate(
                        task_id=frontmatter.get("task_id", "?"),
                        criterion=frontmatter.get("criterion", "blocked"),
                        block_session_key=(frontmatter.get("block_session_key")
                                           if frontmatter.get("block_session_key") != "(none)"
                                           else None),
                        block_reason=frontmatter.get("block_reason", "(unknown)"),
                        project=(frontmatter.get("project")
                                 if frontmatter.get("project") not in ("(unknown)", None)
                                 else None),
                    )
                    result = _escalation_dispatcher_module.dispatch_telegram(path, cand)
                    if result.get("sent"):
                        stats["retry_succeeded"] += 1
                except Exception as e:
                    stats["errors"] += 1
                    print(f"UBN retry failed for {path.name}: {e}", file=sys.stderr)
        except Exception as e:
            stats["errors"] += 1
            print(f"UBN retry loop failed: {e}", file=sys.stderr)

    except Exception as e:
        stats["errors"] += 1
        print(f"UBN block_scanner stage failed: {e}", file=sys.stderr)
    return stats


def _find_kanban_task(kanban: Dict[str, Any], task_id: str) -> Optional[Dict[str, Any]]:
    for t in (kanban.get("tasks") or []):
        if t.get("id") == task_id:
            return t
    return None


def _resolve_session_jsonl_path(kanban_task: Optional[Dict[str, Any]],
                                exec_status: Dict[str, Any]) -> Optional[Path]:
    """Find ~/.claude/projects/<encoded_path>/<session_id>.jsonl.

    Returns None if session_id missing.
    """
    sess_id = (exec_status.get("sprint_session_id")
               or (kanban_task or {}).get("dispatch_payload", {}).get("execution_session_id"))
    if not sess_id:
        return None
    project = (kanban_task or {}).get("project")
    if project:
        project_path = f"{Path.home()}/code/{project}"
    else:
        project_path = f"{Path.home()}"
    encoded = project_path.replace("/", "-").rstrip("-") or "-"
    return Path.home() / ".claude" / "projects" / encoded / f"{sess_id}.jsonl"


def _backoff_delay_for(retry_count: int) -> int:
    """Geometric ratio 3x with cap at 10min (Bernard decision #4).

    1 -> 30s, 2 -> 90s, 3 -> 300s, 4 -> 600s, 5+ -> 600s (cap).
    """
    return REINVOKE_BACKOFF_SCHEDULE.get(retry_count, 600)


def _parse_iso_safe(ts: str) -> Optional[datetime]:
    """Parse ISO timestamp tolerating Z suffix; returns datetime or None."""
    if not ts or not isinstance(ts, str):
        return None
    try:
        s = ts.replace("Z", "+00:00") if ts.endswith("Z") else ts
        dt = datetime.fromisoformat(s)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt
    except (TypeError, ValueError):
        return None


def _needs_tester_reinvoke(kanban_task: Dict[str, Any],
                           exec_status: Dict[str, Any]) -> bool:
    """True if kanban indicates task came back to testing AND last test was
    inconclusive AND backoff window expired.

    Used when classify_execution sees finished_at + post_action_applied=True;
    instead of returning 'already_reaped' (legacy), checks if tester needs
    a second chance.

    exec_status is reserved for upcoming integration (Task 7-8) where
    classify_execution may pass additional execution-state context; current
    gating decision relies only on kanban_task fields.
    """
    if (kanban_task or {}).get("status") != "testing":
        return False
    tr = ((kanban_task or {}).get("dispatch_payload") or {}).get("test_result") or {}
    if tr.get("last_test_overall") != "inconclusive":
        return False
    last_test_at = tr.get("last_test_finished_at")
    test_count = tr.get("test_run_count", 1)
    if not last_test_at:
        return True  # 1st chance, no prior record
    parsed = _parse_iso_safe(last_test_at)
    if parsed is None:
        return False  # defensive: don't loop on malformed timestamps
    delay_seconds = _backoff_delay_for(test_count)
    elapsed = (datetime.now(timezone.utc) - parsed).total_seconds()
    return elapsed >= delay_seconds


def run_tick(
    trigger: str = "manual", dry_run: bool = False,
    executions_dir: Optional[Path] = None,
    lockfile: Optional[Path] = None,
) -> Dict[str, Any]:
    """Tick completo do reaper: lock + scan + process + audit.

    Returns audit entry dict (tambem appended em reaper.jsonl).

    Idempotencia: executions com post_action_applied=true sao skipadas
    sem reprocessamento (visivel no audit como skipped_already_reaped +
    stage='skip' outcome='already_reaped').
    """
    if executions_dir is None:
        executions_dir = EXECUTIONS_DIR
    if lockfile is None:
        lockfile = REAPER_LOCK

    tick_id = make_tick_id()
    started_at = store.now_iso()

    with global_lock(lockfile) as acquired:
        if not acquired:
            entry = {
                "tick_id": tick_id, "tick_started_at": started_at,
                "tick_finished_at": store.now_iso(), "trigger": trigger,
                "considered_executions": 0,
                "skipped_already_reaped": 0,
                "skipped_still_running": 0,
                "reaped_count": 0,
                "tester_invoked_count": 0,
                "actions_per_task": [],
                "lock_acquired": False,
                "lock_skipped": True,
                "dry_run": dry_run,
            }
            append_audit(entry)
            return entry

        entries = scan_executions(executions_dir)
        stats = process_executions(entries, dry_run=dry_run)
        entry = {
            "tick_id": tick_id, "tick_started_at": started_at,
            "tick_finished_at": store.now_iso(), "trigger": trigger,
            "lock_acquired": True, "lock_skipped": False,
            "dry_run": dry_run,
            **stats,
        }
        # UBN stage (independent — won't break reaper if fails)
        try:
            kanban_state_for_ubn = _load_kanban_state()
            entry["ubn"] = _block_scanner_stage(kanban_state_for_ubn)
        except Exception as e:
            entry["ubn"] = {"errors": 1, "exception": str(e)}
        # F3.2: Executor legacy reaper stage (independent — won't break reaper if fails)
        try:
            entry["executor_legacy"] = _executor_legacy_reaper_stage()
        except Exception as e:
            entry["executor_legacy"] = {"errors": 1, "exception": str(e)}
        append_audit(entry)
        return entry
