# E10 Cron-Dispatcher Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use `superpowers:subagent-driven-development` (recommended) or `superpowers:executing-plans` to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Cron-dispatcher periódico que automatiza o kick off de novas tasks `ready` para projetos **explicit opted-in** via `cron-projects.txt`. Combinado com reaper wave-3.5, fecha o pipeline em **0 touches happy path condicional** (8 pré-condições simultâneas).

**Architecture:** Novo `~/.openclaw/dispatcher-agent/lib/cron.py` (Python stdlib + fcntl) — varredor sequencial sob lock global do tick (`cron.lock` separado de `reaper.lock`), ordem alfabética determinística, guards conservadores (busy=in_progress|testing|blocked + escalation aberta clarification/tester), falha per-project capturada como `dispatch_error` sem abortar tick. Delta mínimo `lib/api.py`: `cmd_cron_tick` + subparser. systemd templates shipped (300s default), instalação manual pós-push. Audit append-only `cron.jsonl`. `dispatcher_actor="cron-dispatcher"` distingue do manual.

**Tech Stack:** Python 3 stdlib + fcntl; systemd user units; reuso direto de `selector.*`/`briefing.*`/`runner.launch_detached`/`lifecycle.*` (zero refactor).

**Specs:** Wave-4 `bevox-knowledge/35_specs/2026-04-19-e10-cron-dispatcher.md` (commit `c02c343`). Deps: wave-3.5 detached-reaper, wave-3 tester, wave-2 dispatcher+clarification.

**Plan par (pattern reference):** `~/.openclaw/docs/superpowers/plans/2026-04-19-e10-detached-reaper-plan.md`

**Constraints:** zero pip install; zero novo agent identitário (zero entry no registry.yml); systemd habilitação manual pós-push; single canonical commit (delta playbook + tracker); spike results wave-2+3+3.5 são base técnica.

**Guardrails críticos:**
1. Cron-tick sequencial sob lock global (`cron.lock` ≠ `reaper.lock`)
2. Ordem alfabética determinística dos opted-in
3. **Testing TAMBÉM bloqueia** (invariante forte §2.5)
4. **Falha per-project NÃO aborta tick** (auditada como `dispatch_error`)
5. **"0 touches" CONDICIONAL** (8 pré-cond; sem wording incondicional)
6. Opt-in default deny
7. Kill-switch instantâneo
8. 1 task/projeto/tick; sempre detached; `no_tester=false` sempre
9. `dispatcher_actor="cron-dispatcher"`
10. Lockfiles separados

---

## File Structure

```
~/.openclaw/dispatcher-agent/
├── lib/
│   ├── cron.py                     # NOVO
│   └── api.py                      # MODIFICA (cmd_cron_tick + subparser)
├── systemd/
│   ├── openclaw-cron-dispatcher.service  # NOVO template
│   └── openclaw-cron-dispatcher.timer    # NOVO template (300s)
├── cron-projects.txt               # NOVO config template
├── cron.disabled                   # NOVO opcional (kill-switch)
├── cron.jsonl                      # NOVO runtime (audit)
├── cron.lock                       # NOVO runtime (fcntl)
├── playbook.md                     # MODIFICA (sync canonical Phase 8)
├── README.md                       # MODIFICA (seção Cron-dispatcher)
└── lib/api.py.pre-cron.bak         # backup defensivo

bevox-knowledge/
├── 20_architecture/agents/
│   └── dispatcher-agent.md         # MODIFICA (nova seção `## Cron-dispatcher (wave-4)`)
└── 40_roadmap/
    └── delivery-tracker.yml        # MODIFICA (nova wave em E10)
```

---

## Phase 0: Pre-flight + backup

### Task 0.1: Verificar baseline

- [ ] **Step 1: Confirmar spec canonizada**

```bash
git -C ~/bevox-knowledge log --oneline -1 -- 35_specs/2026-04-19-e10-cron-dispatcher.md
```

Expected: `c02c343 spec(E10): cron-dispatcher wave ...`

- [ ] **Step 2: Confirmar deps wave-2+3+3.5 presentes**

```bash
ls ~/.openclaw/dispatcher-agent/lib/{selector,briefing,runner,lifecycle,reaper,api,store}.py
ls ~/.openclaw/{tester,clarification}-agent/cli.sh
which claude && claude --version 2>&1 | head -2
```

Expected: 7 lib files + 2 cli.sh + claude CLI.

- [ ] **Step 3: Confirmar cron.py + cmd ausentes**

```bash
ls ~/.openclaw/dispatcher-agent/lib/cron.py 2>/dev/null && echo "WARN" || echo "OK pendente"
~/.openclaw/dispatcher-agent/cli.sh cron-tick --help 2>&1 | head -2
ls ~/.openclaw/dispatcher-agent/cron-projects.txt 2>/dev/null && echo "WARN" || echo "OK pendente"
```

Expected: 3 pendentes / "invalid choice: cron-tick".

- [ ] **Step 4: Confirmar funções existentes**

```bash
grep -n "def select_next_ready\|def check_one_task_per_project_guard" ~/.openclaw/dispatcher-agent/lib/selector.py
grep -n "def launch_detached" ~/.openclaw/dispatcher-agent/lib/runner.py
grep -n "def merge_dispatch_payload\|def move_to_in_progress" ~/.openclaw/dispatcher-agent/lib/lifecycle.py
```

Expected: 5 defs listadas.

### Task 0.2: Backup state

- [ ] **Step 1: Snapshot kanban + api.py**

```bash
mkdir -p ~/.openclaw/backups/kanban-tasks
TS=$(date -Iseconds)
cp ~/.openclaw/kanban-tasks/state.json ~/.openclaw/backups/kanban-tasks/state.json.pre-cron.$TS
cp ~/.openclaw/kanban-tasks/events.jsonl ~/.openclaw/backups/kanban-tasks/events.jsonl.pre-cron.$TS
cp ~/.openclaw/dispatcher-agent/lib/api.py ~/.openclaw/dispatcher-agent/lib/api.py.pre-cron.bak
ls ~/.openclaw/dispatcher-agent/lib/api.py.pre-cron.bak
```

Expected: backup files criados.

---

## Phase 1: lib/cron.py — parse_projects_file (TDD)

### Task 1.1: TDD parse — 9 tests fail-first

- [ ] **Step 1: Escrever testes (file `/tmp/test_cron_parse.py`)**

Conteúdo: 9 tests cobrindo simple_list, strips_whitespace, skips_comments, skips_empty_lines, dedup, missing_file, empty_file, only_comments, inline_comment_marker. Cada test recebe sub-tmpdir isolado via `for fn in (...): sub = base/fn.__name__; sub.mkdir(); fn(str(sub))`. Cada test importa `from lib import cron` e chama `cron.parse_projects_file(path)` esperando lista alfabética determinística.

Estrutura template (compactado por brevidade; engineer expande dos exemplos abaixo):

```python
def test_parse_simple_list(tmpdir):
    f = Path(tmpdir) / "cron-projects.txt"
    f.write_text("openclaw\nbevox-harness\n")
    assert cron.parse_projects_file(f) == ["bevox-harness", "openclaw"]
    print("  OK test_parse_simple_list")

def test_parse_skips_comments(tmpdir):
    f = Path(tmpdir) / "cron-projects.txt"
    f.write_text("# header\nopenclaw\n# bevox  # nao habilita\n")
    assert cron.parse_projects_file(f) == ["openclaw"]
    print("  OK test_parse_skips_comments")

# ... (test_parse_strips_whitespace, test_parse_skips_empty_lines,
# test_parse_dedup, test_parse_missing_file, test_parse_empty_file,
# test_parse_only_comments, test_parse_strips_inline_comment_marker
# — todos no mesmo padrão)
```

- [ ] **Step 2: Rodar — confirmar FAIL**

```bash
python3 /tmp/test_cron_parse.py 2>&1 | tail -3 || true
```

Expected: `ImportError: cannot import name 'cron'`.

- [ ] **Step 3: Implementar cron.py com parse_projects_file**

```python
"""Cron-dispatcher: trigger periodico de novas tasks ready (wave-4).

Decisoes travadas (§2 spec):
- Trigger systemd timer separado do reaper (300s default)
- Opt-in default deny via cron-projects.txt
- Kill-switch global cron.disabled
- Sequencial + ordem alfabetica deterministica
- Testing TAMBEM bloqueia (invariante forte §2.5)
- Falha per-project NAO aborta tick (audit + continua)
- Lock global do tick (cron.lock SEPARADO de reaper.lock)
- 1 task/projeto/tick; sempre detached; no_tester=false sempre
- dispatcher_actor="cron-dispatcher"
"""

import contextlib
import fcntl
import json
import os
import uuid
from pathlib import Path
from typing import Any, Dict, Iterator, List, Optional

from . import store

ROOT = Path(os.path.expanduser("~/.openclaw/dispatcher-agent"))
CRON_PROJECTS_FILE = ROOT / "cron-projects.txt"
CRON_DISABLED_FILE = ROOT / "cron.disabled"
CRON_JSONL = ROOT / "cron.jsonl"
CRON_LOCK = ROOT / "cron.lock"

CLARIFICATION_ESCALATIONS_DIR = Path(os.path.expanduser(
    "~/.openclaw/clarification-agent/escalations",
))
TESTER_ESCALATIONS_DIR = Path(os.path.expanduser(
    "~/.openclaw/tester-agent/escalations",
))


class CronError(Exception):
    def __init__(self, code: str, detail: str):
        self.code = code
        self.detail = detail
        super().__init__(f"{code}: {detail}")


def parse_projects_file(path: Path) -> List[str]:
    """Le cron-projects.txt. Retorna lista deduplicada em ordem alfabetica.

    - 1 project/linha; `#` no inicio = comment; vazias skipadas
    - file ausente OR vazio → []
    - Hash `#` no MEIO da linha NAO eh stripped (project name)
    """
    if not path.exists() or not path.is_file():
        return []
    try:
        content = path.read_text(encoding="utf-8")
    except OSError:
        return []
    seen = set()
    out = []
    for line in content.splitlines():
        s = line.strip()
        if not s or s.startswith("#"):
            continue
        if s in seen:
            continue
        seen.add(s)
        out.append(s)
    out.sort()
    return out
```

Salvar em `~/.openclaw/dispatcher-agent/lib/cron.py`.

- [ ] **Step 4: Rodar — devem passar 9/9**

```bash
python3 /tmp/test_cron_parse.py
```

Expected: `ALL OK` com 9 OKs.

- [ ] **Step 5: Cleanup**

```bash
rm /tmp/test_cron_parse.py
```

---

## Phase 2: kill_switch + escalation guards (TDD)

### Task 2.1: kill_switch_active TDD

- [ ] **Step 1: Test fail-first** (`/tmp/test_cron_killswitch.py`)

3 tests: `test_kill_switch_absent` (file não existe → False), `test_kill_switch_empty_file_is_active` (file vazio existe → True), `test_kill_switch_with_content` (file com texto → True). Cada test em sub-tmpdir isolado.

- [ ] **Step 2: Run — FAIL** (`AttributeError: kill_switch_active`)

- [ ] **Step 3: Adicionar à cron.py**

```python
def kill_switch_active(path: Path) -> bool:
    """Returns True se file existe (file presente = kill-switch ON)."""
    return path.exists() and path.is_file()
```

- [ ] **Step 4: Run — 3/3 OK**

- [ ] **Step 5: Cleanup test**

### Task 2.2: has_open_escalation_for_project TDD

- [ ] **Step 1: Test fail-first** (`/tmp/test_cron_escalation.py`)

5 tests: `test_no_escalation_dir` (dir não existe → False), `test_no_match` (escalation de outro task_id → False), `test_clarification_match` (file `T-0001-clr-1.md` existe + `T-0001` na lista → True), `test_tester_match` (file `T-0042-tr-3.md` + `T-0042` na lista → True), `test_empty_task_list` (task_ids=[] → False sempre).

Assinatura: `has_open_escalation_for_project(task_ids: List[str], clarification_dir: Path, tester_dir: Path) -> bool`.

- [ ] **Step 2: Run — FAIL** (`AttributeError`)

- [ ] **Step 3: Adicionar à cron.py**

```python
def has_open_escalation_for_project(
    task_ids: List[str],
    clarification_dir: Path,
    tester_dir: Path,
) -> bool:
    """True se ha escalation aberta (clarification OR tester) pra qualquer task_id.

    Patterns: <task_id>-clr-<N>.md OR <task_id>-tr-<N>.md
    """
    if not task_ids:
        return False
    task_id_set = set(task_ids)
    for d in (clarification_dir, tester_dir):
        if not d.exists() or not d.is_dir():
            continue
        try:
            for p in d.iterdir():
                if not (p.is_file() or p.is_symlink()):
                    continue
                name = p.name
                for marker in ("-clr-", "-tr-"):
                    idx = name.find(marker)
                    if idx > 0:
                        if name[:idx] in task_id_set:
                            return True
                        break
        except OSError:
            continue
    return False
```

- [ ] **Step 4: Run — 5/5 OK**

- [ ] **Step 5: Cleanup**

### Task 2.3: Adicionar global_lock + make_tick_id + append_audit + project_state_summary

- [ ] **Step 1: Adicionar helpers à cron.py**

```python
@contextlib.contextmanager
def global_lock(lockfile: Path) -> Iterator[bool]:
    """fcntl LOCK_NB. SEPARADO de reaper.global_lock (lockfile distinto)."""
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


def append_audit(entry: Dict[str, Any]) -> None:
    """Append linha JSONL atomico em cron.jsonl."""
    CRON_JSONL.parent.mkdir(parents=True, exist_ok=True)
    line = json.dumps(entry, ensure_ascii=False) + "\n"
    with open(CRON_JSONL, "a", encoding="utf-8") as f:
        f.write(line)


def project_state_summary(project: str) -> Dict[str, Any]:
    """Le state.json direto (mesmo pattern selector). Tasks do projeto."""
    from .selector import KANBAN_STATE
    if not KANBAN_STATE.exists():
        return {"project": project, "tasks": [], "by_status": {}}
    try:
        state = json.loads(KANBAN_STATE.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {"project": project, "tasks": [], "by_status": {}}
    tasks = [t for t in state.get("tasks", []) if t.get("project") == project]
    by_status: Dict[str, List[str]] = {}
    for t in tasks:
        s = t.get("status") or "unknown"
        by_status.setdefault(s, []).append(t.get("id"))
    return {"project": project, "tasks": tasks, "by_status": by_status}
```

- [ ] **Step 2: Sanity import + lock smoke**

```bash
cd ~/.openclaw/dispatcher-agent && PYTHONPATH=. python3 -c "
import tempfile
from pathlib import Path
from lib import cron
tmp = tempfile.mkdtemp()
lockfile = Path(tmp) / 'test.lock'
with cron.global_lock(lockfile) as acq:
    assert acq is True
    import subprocess, sys
    script = f'''
import sys
sys.path.insert(0, str({repr(str(Path.home() / \".openclaw\" / \"dispatcher-agent\"))}))
from lib import cron
from pathlib import Path
with cron.global_lock(Path({repr(str(lockfile))})) as acq2:
    print(\"acquired\" if acq2 else \"skipped\")
'''
    r = subprocess.run([sys.executable, '-c', script], capture_output=True, text=True, timeout=5)
    assert r.stdout.strip() == 'skipped', r.stdout
print('OK lock + helpers')
import shutil; shutil.rmtree(tmp)
"
```

Expected: `OK lock + helpers`.

---

## Phase 3: process_projects + run_tick (TDD invariantes)

### Task 3.1: project_blocks_dispatch TDD (testing TAMBÉM bloqueia)

- [ ] **Step 1: Test fail-first** (`/tmp/test_cron_blocks.py`)

6 tests cobrindo invariante forte §2.5:
- `test_blocks_in_progress` (status in_progress → blocks)
- `test_blocks_testing` (status testing → blocks; **invariante forte**)
- `test_blocks_blocked_flag` (qualquer status com blocked=True → blocks)
- `test_blocks_clarification_escalation` (escalation file `<tid>-clr-N.md` existe → blocks)
- `test_blocks_tester_escalation` (escalation file `<tid>-tr-N.md` existe → blocks)
- `test_does_not_block_when_clean` (apenas ready/done → não blocks)

Assinatura: `project_blocks_dispatch(state: Dict, clarification_dir: Path, tester_dir: Path) -> tuple[bool, str]`.

- [ ] **Step 2: Run — FAIL**

- [ ] **Step 3: Adicionar à cron.py**

```python
# Status que skipam novo dispatch (invariante forte §2.5).
# Testing TAMBEM bloqueia (task aguardando tester ou decisao final).
BUSY_STATUSES = {"in_progress", "testing", "blocked"}


def project_blocks_dispatch(
    state: Dict[str, Any],
    clarification_dir: Path,
    tester_dir: Path,
) -> tuple:
    """Decide se projeto deve ser SKIPADO no tick.
    Retorna (blocks: bool, reason: str)."""
    by_status = state.get("by_status") or {}
    tasks = state.get("tasks") or []

    # Check 1: status BUSY (ordem deterministica pra reason consistente)
    for st in ("in_progress", "testing", "blocked"):
        ids = by_status.get(st) or []
        if ids:
            return True, f"task em status {st}: {ids[:3]}"

    # Check 2: flag blocked (independe de status)
    blocked = [t.get("id") for t in tasks if t.get("blocked")]
    if blocked:
        return True, f"task com flag blocked=true: {blocked[:3]}"

    # Check 3: escalation aberta
    task_ids = [t.get("id") for t in tasks if t.get("id")]
    if has_open_escalation_for_project(task_ids, clarification_dir, tester_dir):
        return True, "escalation aberta (clarification OR tester)"

    return False, ""
```

- [ ] **Step 4: Run — 6/6 OK**

- [ ] **Step 5: Cleanup**

### Task 3.2: process_projects TDD (falha per-project NÃO aborta)

- [ ] **Step 1: Test fail-first** (`/tmp/test_cron_isolation.py`)

3 tests com fakes injetados:
- `test_dispatch_one_for_project_returns_dispatch_error_dict`: 3 projetos A/B/C; B raise RuntimeError; assert que A e C foram chamados (sequencial), B virou `outcome=dispatch_error` com `error_code=RuntimeError`, `dispatched_count=2`.
- `test_skip_busy_does_not_call_dispatch`: B blocked (testing) → não chamou dispatch; `outcome=skipped_busy` + `skip_reason` cita "testing".
- `test_dry_run_does_not_dispatch`: dry_run=True → `dispatched_count=0`; outcome `would_dispatch`.

Assinatura: `process_projects(opted_in: List[str], dry_run: bool, dispatch_one_fn=None, check_blocks_fn=None, state_summary_fn=None) -> Dict[str, Any]`.

- [ ] **Step 2: Run — FAIL**

- [ ] **Step 3: Adicionar à cron.py**

```python
def process_projects(
    opted_in: List[str],
    dry_run: bool,
    dispatch_one_fn=None,
    check_blocks_fn=None,
    state_summary_fn=None,
) -> Dict[str, Any]:
    """Processa projetos sequencialmente. Falha per-project NAO aborta tick."""
    if dispatch_one_fn is None:
        dispatch_one_fn = _dispatch_one_for_project
    if state_summary_fn is None:
        state_summary_fn = project_state_summary
    if check_blocks_fn is None:
        def _default_check(project):
            state = state_summary_fn(project)
            return project_blocks_dispatch(
                state, CLARIFICATION_ESCALATIONS_DIR, TESTER_ESCALATIONS_DIR,
            )
        check_blocks_fn = _default_check

    stats: Dict[str, Any] = {
        "projects_considered": len(opted_in),
        "projects_skipped_no_ready": 0,
        "projects_skipped_busy": 0,
        "projects_skipped_escalation": 0,
        "dispatched_count": 0,
        "actions_per_project": [],
    }

    for project in opted_in:
        try:
            blocks, reason = check_blocks_fn(project)
        except Exception as e:
            stats["actions_per_project"].append({
                "project": project, "outcome": "check_error",
                "error_code": type(e).__name__,
                "error_detail": str(e)[:200], "task_id": None,
            })
            continue

        if blocks:
            if "escalation" in reason:
                stats["projects_skipped_escalation"] += 1
                outcome = "skipped_escalation"
            else:
                stats["projects_skipped_busy"] += 1
                outcome = "skipped_busy"
            stats["actions_per_project"].append({
                "project": project, "outcome": outcome,
                "skip_reason": reason, "task_id": None,
            })
            continue

        try:
            result = dispatch_one_fn(project, dry_run=dry_run)
        except Exception as e:
            stats["actions_per_project"].append({
                "project": project, "outcome": "dispatch_error",
                "error_code": type(e).__name__,
                "error_detail": str(e)[:200], "task_id": None,
            })
            continue

        outcome = (result or {}).get("outcome") or "unknown"
        if outcome == "dispatched":
            stats["dispatched_count"] += 1
        elif outcome == "skipped_no_ready":
            stats["projects_skipped_no_ready"] += 1

        action = {"project": project, "outcome": outcome,
                  "task_id": (result or {}).get("task_id")}
        for k in ("session_id", "log_path", "skip_reason", "would_title"):
            if (result or {}).get(k) is not None:
                action[k] = result[k]
        stats["actions_per_project"].append(action)

    return stats
```

- [ ] **Step 4: Run — 3/3 OK**

- [ ] **Step 5: Cleanup**

### Task 3.3: _dispatch_one_for_project + run_tick

- [ ] **Step 1: Adicionar _dispatch_one_for_project (production helper)**

```python
def _dispatch_one_for_project(project: str, dry_run: bool = False) -> Dict[str, Any]:
    """Dispatch 1 task ready do projeto. Reusa selector + briefing + runner.

    Levanta exception em qualquer erro infrastrutural (capturado pelo caller).
    """
    from . import selector as selector_lib
    from . import briefing as briefing_lib
    from . import runner as runner_lib

    try:
        task = selector_lib.select_next_ready(project)
    except selector_lib.SelectorError as e:
        if e.code == "NO_READY_TASK":
            return {"outcome": "skipped_no_ready", "task_id": None,
                    "skip_reason": "nenhuma task ready no projeto"}
        raise

    if dry_run:
        return {"outcome": "would_dispatch", "task_id": task["id"],
                "would_title": task.get("title", "")[:80]}

    DEFAULT_ALLOWED_TOOLS = (
        "Read,Write,Edit,Glob,Grep,"
        "Bash(git:*),Bash(npm:*),Bash(python3:*),Bash(pytest:*),"
        "Bash(ls:*),Bash(cat:*),Bash(echo:*),Bash(mkdir:*),Bash(touch:*),"
        "Bash(~/.openclaw/clarification-agent/cli.sh:*),"
        "Bash(rm:*)"
    )
    briefing_content = briefing_lib.render_briefing(task, DEFAULT_ALLOWED_TOOLS)
    bpath = store.write_briefing(task["id"], briefing_content)

    import subprocess
    KANBAN_CLI = "~/.openclaw/kanban-tasks/cli.sh"

    # Move ready→in_progress (actor=cron-dispatcher)
    r = subprocess.run(
        [KANBAN_CLI, "task", "move", task["id"], "in_progress",
         "--actor", "cron-dispatcher", "--json"],
        capture_output=True, text=True, check=False, timeout=30,
    )
    if r.returncode != 0:
        raise CronError("KANBAN_MOVE_FAILED",
                        f"task move {task['id']} in_progress: {r.stderr.strip()[:200]}")

    # Merge metadata (dispatch_flags.no_tester=false)
    metadata = {
        "dispatched_at": store.now_iso(),
        "dispatcher_actor": "cron-dispatcher",
        "briefing_path": str(bpath),
        "dispatch_mode": "detach",
        "dispatch_flags": {"no_tester": False},
    }
    r = subprocess.run(
        [KANBAN_CLI, "task", "set-dispatch-payload", task["id"],
         "--payload", json.dumps(metadata, ensure_ascii=False), "--merge",
         "--actor", "cron-dispatcher", "--json"],
        capture_output=True, text=True, check=False, timeout=30,
    )
    if r.returncode != 0:
        raise CronError("KANBAN_PAYLOAD_FAILED",
                        f"set-dispatch-payload {task['id']}: {r.stderr.strip()[:200]}")

    # Spawn detached
    status = runner_lib.launch_detached(
        task["id"], bpath, DEFAULT_ALLOWED_TOOLS, model="claude-opus-4-7",
    )

    # Merge runtime info
    runtime_meta = {
        "execution_session_id": status["session_id"],
        "execution_log_path": status["log_path"],
        "execution_started_at": status["started_at"],
    }
    subprocess.run(
        [KANBAN_CLI, "task", "set-dispatch-payload", task["id"],
         "--payload", json.dumps(runtime_meta, ensure_ascii=False), "--merge",
         "--actor", "cron-dispatcher", "--json"],
        capture_output=True, text=True, check=False, timeout=30,
    )

    return {
        "outcome": "dispatched", "task_id": task["id"],
        "session_id": status["session_id"], "log_path": status["log_path"],
    }


def run_tick(
    trigger: str = "manual", dry_run: bool = False,
    projects_file: Optional[Path] = None,
    disabled_file: Optional[Path] = None,
    lockfile: Optional[Path] = None,
) -> Dict[str, Any]:
    """Tick completo: lock + kill-switch + parse opt-in + process + audit."""
    if projects_file is None: projects_file = CRON_PROJECTS_FILE
    if disabled_file is None: disabled_file = CRON_DISABLED_FILE
    if lockfile is None: lockfile = CRON_LOCK

    tick_id = make_tick_id()
    started_at = store.now_iso()

    with global_lock(lockfile) as acquired:
        if not acquired:
            entry = {
                "tick_id": tick_id, "tick_started_at": started_at,
                "tick_finished_at": store.now_iso(), "trigger": trigger,
                "kill_switch_active": False, "opted_in_projects": [],
                "projects_considered": 0, "projects_skipped_no_ready": 0,
                "projects_skipped_busy": 0, "projects_skipped_escalation": 0,
                "dispatched_count": 0, "actions_per_project": [],
                "lock_acquired": False, "lock_skipped": True, "dry_run": dry_run,
            }
            append_audit(entry)
            return entry

        if kill_switch_active(disabled_file):
            entry = {
                "tick_id": tick_id, "tick_started_at": started_at,
                "tick_finished_at": store.now_iso(), "trigger": trigger,
                "kill_switch_active": True, "opted_in_projects": [],
                "projects_considered": 0, "projects_skipped_no_ready": 0,
                "projects_skipped_busy": 0, "projects_skipped_escalation": 0,
                "dispatched_count": 0, "actions_per_project": [],
                "lock_acquired": True, "lock_skipped": False, "dry_run": dry_run,
            }
            append_audit(entry)
            return entry

        opted_in = parse_projects_file(projects_file)
        stats = process_projects(opted_in=opted_in, dry_run=dry_run)
        entry = {
            "tick_id": tick_id, "tick_started_at": started_at,
            "tick_finished_at": store.now_iso(), "trigger": trigger,
            "kill_switch_active": False, "opted_in_projects": opted_in,
            "lock_acquired": True, "lock_skipped": False, "dry_run": dry_run,
            **stats,
        }
        append_audit(entry)
        return entry
```

- [ ] **Step 2: Sanity run_tick em sandbox**

```bash
cd ~/.openclaw/dispatcher-agent && PYTHONPATH=. python3 <<'PY'
import tempfile
from pathlib import Path
from lib import cron
tmp = tempfile.mkdtemp()
pf = Path(tmp) / "cron-projects.txt"
df = Path(tmp) / "cron.disabled"
lf = Path(tmp) / "cron.lock"
# Empty opt-in
r = cron.run_tick("smoke_empty", False, pf, df, lf)
assert r["lock_acquired"] and r["opted_in_projects"] == [] and r["dispatched_count"] == 0
print(f"OK empty: {r['tick_id'][:30]}")
# Kill-switch
df.write_text("paused")
r = cron.run_tick("smoke_kill", False, pf, df, lf)
assert r["kill_switch_active"] is True and r["dispatched_count"] == 0
print(f"OK kill-switch")
import shutil; shutil.rmtree(tmp)
PY
```

Expected: 2 OKs.

---

## Phase 4: dispatcher api.py delta

### Task 4.1: cmd_cron_tick + subparser

- [ ] **Step 1: Adicionar cmd_cron_tick antes de build_parser**

Edit `~/.openclaw/dispatcher-agent/lib/api.py` localizando `def build_parser():`. Inserir ANTES:

```python
def cmd_cron_tick(args: argparse.Namespace) -> int:
    """Wave-4: cron-tick loop unico (--once). Sem daemon mode."""
    from . import cron as cron_lib
    trigger = "manual"
    if os.environ.get("INVOCATION_ID"):
        trigger = "systemd_timer"
    try:
        result = cron_lib.run_tick(trigger=trigger, dry_run=args.dry_run)
    except cron_lib.CronError as e:
        return _err(e.detail, e.code, args.json)
    if args.json:
        _print(result, True)
    else:
        if result.get("lock_skipped"):
            print(f"cron-tick: lock_skipped (other instance) tick={result['tick_id'][:30]}")
        elif result.get("kill_switch_active"):
            print(f"cron-tick: kill_switch_active (cron.disabled present) tick={result['tick_id'][:30]}")
        else:
            opt = result.get("opted_in_projects") or []
            n = result["projects_considered"]
            d = result["dispatched_count"]
            sb = result["projects_skipped_busy"]
            se = result["projects_skipped_escalation"]
            sn = result["projects_skipped_no_ready"]
            mode = "DRY-RUN" if args.dry_run else "applied"
            print(f"cron-tick [{mode}]: opted_in={opt} dispatched={d} "
                  f"skipped_busy={sb} skipped_escalation={se} skipped_no_ready={sn} considered={n}")
            for a in result.get("actions_per_project", []):
                tid = f" ({a['task_id']})" if a.get("task_id") else ""
                print(f"  {a['project']}: {a['outcome']}{tid}")
    return EXIT_OK
```

- [ ] **Step 2: Adicionar subparser dentro de build_parser (após relaunch + reap-detached)**

Localizar bloco com `rp = leaf(sub, "reap-detached")`. Adicionar ABAIXO:

```python
    cr = leaf(sub, "cron-tick")
    cr.add_argument("--once", action="store_true",
                    help="Roda uma passada e sai (default; usado pelo systemd timer).")
    cr.add_argument("--dry-run", action="store_true",
                    help="Lista o que faria, sem agir.")
    cr.set_defaults(func=cmd_cron_tick)
```

- [ ] **Step 3: Sanity CLI**

```bash
~/.openclaw/dispatcher-agent/cli.sh --help 2>&1 | head -3
~/.openclaw/dispatcher-agent/cli.sh cron-tick --help 2>&1 | head -8
~/.openclaw/dispatcher-agent/cli.sh cron-tick --dry-run 2>&1 | head -3
```

Expected: cmd `cron-tick` listado; `--once`/`--dry-run`/`--json` no help; dry-run executou OK (cron-projects.txt não existe ainda → opted_in=[]).

- [ ] **Step 4: Verify backup preserved**

```bash
diff ~/.openclaw/dispatcher-agent/lib/api.py.pre-cron.bak ~/.openclaw/dispatcher-agent/lib/api.py | head -3
```

Expected: diff mostra adições (cmd_cron_tick + subparser).

---

## Phase 5: systemd templates + cron-projects.txt template

### Task 5.1: systemd templates shipped (NÃO instalados)

- [ ] **Step 1: Criar service template**

```bash
cat > ~/.openclaw/dispatcher-agent/systemd/openclaw-cron-dispatcher.service <<'EOF'
[Unit]
Description=OpenClaw cron-dispatcher (auto-dispatch ready, wave-4)
After=default.target

[Service]
Type=oneshot
ExecStart=%h/.openclaw/dispatcher-agent/cli.sh cron-tick --once
Nice=10
EOF
```

- [ ] **Step 2: Criar timer template (300s default)**

```bash
cat > ~/.openclaw/dispatcher-agent/systemd/openclaw-cron-dispatcher.timer <<'EOF'
[Unit]
Description=OpenClaw cron-dispatcher timer (300s tick, wave-4)

[Timer]
OnBootSec=60s
OnUnitActiveSec=300s
AccuracySec=10s
Unit=openclaw-cron-dispatcher.service

[Install]
WantedBy=timers.target
EOF
```

- [ ] **Step 3: Confirmar NÃO instalados em ~/.config/systemd/user/**

```bash
ls ~/.openclaw/dispatcher-agent/systemd/openclaw-cron-dispatcher.{service,timer}
ls ~/.config/systemd/user/openclaw-cron-dispatcher.* 2>/dev/null && echo "WARN installed" || echo "OK not installed (templates shipped only)"
```

Expected: 2 templates listados; NOT installed.

### Task 5.2: cron-projects.txt template (vazio + header explicativo)

- [ ] **Step 1: Criar template**

```bash
cat > ~/.openclaw/dispatcher-agent/cron-projects.txt <<'EOF'
# Projetos com auto-dispatch habilitado (cron-dispatcher wave-4).
# 1 project por linha. `#` no inicio = comment. Linha vazia ignorada.
# Edit livre via vi/nano. Aplica no proximo tick (~300s).
#
# Exemplo (descomente pra habilitar):
# openclaw
# bevox-harness
EOF
ls -la ~/.openclaw/dispatcher-agent/cron-projects.txt
```

Expected: file criado; sem projects ativos por default.

- [ ] **Step 2: Confirmar default deny**

```bash
~/.openclaw/dispatcher-agent/cli.sh cron-tick --dry-run --json 2>&1 | python3 -c "
import json, sys
r = json.loads(sys.stdin.read())
assert r['opted_in_projects'] == [], r['opted_in_projects']
assert r['dispatched_count'] == 0
print('OK default deny: opted_in=[] dispatched=0')"
```

Expected: `OK default deny`.

---

## Phase 6: README com seção Cron-dispatcher

### Task 6.1: Append seção ao README

- [ ] **Step 1: Append**

```bash
cat >> ~/.openclaw/dispatcher-agent/README.md <<'EOF'

---

## Cron-dispatcher (wave-4)

Subcomando `cron-tick` automatiza o kick off de novas tasks `ready`
para projetos **explicit opted-in** via `cron-projects.txt`. Combinado
com o reaper (wave-3.5), fecha o pipeline em **0 touches happy path
condicional** (8 pre-condicoes simultaneas; ver playbook canonical).

```bash
vox dispatcher cron-tick --once          # uma passada (usado pelo systemd timer)
vox dispatcher cron-tick --once --json   # output estruturado
vox dispatcher cron-tick --dry-run       # lista o que faria, sem agir
```

### Opt-in default deny

Edite `~/.openclaw/dispatcher-agent/cron-projects.txt`:

```
openclaw
bevox-harness
```

File ausente OR vazio → cron-tick exit 0 sem fazer nada. Ordem
alfabetica deterministica dentro do tick.

### Kill-switch global

```bash
touch ~/.openclaw/dispatcher-agent/cron.disabled    # para tudo no proximo tick
rm    ~/.openclaw/dispatcher-agent/cron.disabled    # retoma proximo tick
```

### Garantias (§2 spec)

- Sequencial + ordem alfabetica deterministica
- **Testing TAMBEM bloqueia** (invariante forte): in_progress + testing
  + blocked + escalation aberta (clarification OR tester) skipam projeto
- **Falha per-project NAO aborta tick**: exception capturada + auditada
  como `outcome=dispatch_error` + tick continua proximo projeto
- Lock global do tick (`cron.lock` SEPARADO de `reaper.lock`); segunda
  instancia exit 0 com `lock_skipped=true`
- 1 task/projeto/tick; sempre detached; `dispatch_flags.no_tester=false`
- `dispatcher_actor="cron-dispatcher"` (distingue do "dispatcher" manual)

### Habilitacao systemd (manual pos-push)

Templates shipped em `~/.openclaw/dispatcher-agent/systemd/`. Bernard
copia + habilita explicit:

```bash
cp ~/.openclaw/dispatcher-agent/systemd/openclaw-cron-dispatcher.{service,timer} \
   ~/.config/systemd/user/
systemctl --user daemon-reload
systemctl --user enable --now openclaw-cron-dispatcher.timer
systemctl --user list-timers | grep cron-dispatcher
journalctl --user -u openclaw-cron-dispatcher -f
```

Override de cadencia (sem mexer em codigo):

```bash
systemctl --user edit openclaw-cron-dispatcher.timer
# editor abre overlay; escreva:
# [Timer]
# OnUnitActiveSec=600s   # 10min em vez de 5min
```

### NAO eh redesign

Cron-dispatcher SO automatiza o kick off. Tudo o resto reusa intacto:
selector + briefing + runner detached + lifecycle + reaper + tester.

**Audit:** `~/.openclaw/dispatcher-agent/cron.jsonl` (append-only;
SEPARADO do `reaper.jsonl`).

**Spec canonica:**
- `bevox-knowledge/35_specs/2026-04-19-e10-cron-dispatcher.md`
EOF
tail -50 ~/.openclaw/dispatcher-agent/README.md | head -55
```

Expected: seção `## Cron-dispatcher (wave-4)` presente.

---

## Phase 7: Smoke E2E — 8 cenários

### Task 7.1: Baseline + helpers

- [ ] **Step 1: Snapshot baseline**

```bash
cd ~/.openclaw/kanban-tasks
BASELINE_EVENTS=$(wc -l < events.jsonl)
cp state.json /tmp/state.ph7-baseline.json
cp events.jsonl /tmp/events.ph7-baseline.jsonl
echo "$BASELINE_EVENTS" > /tmp/ph7-baseline-count
[ -f ~/.openclaw/dispatcher-agent/cron.jsonl ] && cp ~/.openclaw/dispatcher-agent/cron.jsonl /tmp/cron.jsonl.ph7-baseline || touch /tmp/cron.jsonl.ph7-baseline
[ -f ~/.openclaw/dispatcher-agent/cron-projects.txt ] && cp ~/.openclaw/dispatcher-agent/cron-projects.txt /tmp/cron-projects.txt.ph7-baseline || touch /tmp/cron-projects.txt.ph7-baseline
echo "BASELINE_EVENTS=$BASELINE_EVENTS"
```

- [ ] **Step 2: Helper criar fixture (mesmo pattern wave-3.5)**

```bash
cat > /tmp/ph7-create-fixture.sh <<'BASH'
#!/usr/bin/env bash
set -euo pipefail
SUFFIX="$1"; AC="$2"
PLAN=/tmp/ph7-plan-${SUFFIX}.md
cat > "$PLAN" <<EOF
# Plan ph7-${SUFFIX}
**Goal:** smoke ph7 ${SUFFIX}
**Epico:** E10/scrum-master-agent
**Project:** openclaw
**Specs canonicas:**
- \`bevox-knowledge/35_specs/2026-04-19-e10-cron-dispatcher.md\`
## Phase 0: x
### Task 0.1: ph7 ${SUFFIX}
Smoke fixture cenario ${SUFFIX}.
**Files:**
- Create: \`/tmp/ph7-out-${SUFFIX}.txt\`
- [ ] **Step 1: stub**
Expected: ${AC}
EOF
~/.openclaw/scrum-master-agent/cli.sh propose --plan "$PLAN" --target-sprint current >/dev/null 2>&1
PID=$(~/.openclaw/scrum-master-agent/cli.sh list --status pending --json | python3 -c "import json,sys; print(json.load(sys.stdin)['proposals'][-1]['proposal_id'])")
~/.openclaw/scrum-master-agent/cli.sh accept "$PID" --ready >/dev/null 2>&1
TID=$(~/.openclaw/scrum-master-agent/cli.sh show "$PID" --json | python3 -c "import json,sys; print(json.load(sys.stdin)['state']['materialized_task_ids'][0])")
echo "$TID"
BASH
chmod +x /tmp/ph7-create-fixture.sh
```

### Task 7.2: Cenário 1 — opt-in vazio

- [ ] **Step 1: cron-projects.txt vazio (só comments) → exit 0 sem fazer nada**

```bash
echo "=== Cenario 1: opt-in vazio ==="
# cron-projects.txt já tem só comments (template Phase 5.2)
~/.openclaw/dispatcher-agent/cli.sh cron-tick --once --json 2>&1 | python3 -c "
import json, sys
r = json.loads(sys.stdin.read())
assert r['opted_in_projects'] == [], r
assert r['dispatched_count'] == 0
assert r['kill_switch_active'] is False
assert r['lock_acquired'] is True
print('OK cenario 1: opt-in vazio → exit 0 sem fazer nada')"
```

Expected: `OK cenario 1`.

### Task 7.3: Cenário 2 — happy dispatch real (com Claude haiku)

- [ ] **Step 1: opt-in 1 projeto + 1 ready disponível**

```bash
echo "openclaw" >> ~/.openclaw/dispatcher-agent/cron-projects.txt
TID2=$(/tmp/ph7-create-fixture.sh c2 "arquivo /tmp/ph7-out-c2.txt deve existir e conter cron-happy")
echo "$TID2" > /tmp/ph7-tid2
echo "=== Cenario 2 (happy dispatch real): $TID2 ==="
echo "cron-happy" > /tmp/ph7-out-c2.txt
echo ""
~/.openclaw/dispatcher-agent/cli.sh cron-tick --once 2>&1 | tail -5
echo ""
sleep 3
echo "=== Verifica task moveu pra in_progress + status.json escrito ==="
~/.openclaw/kanban-tasks/cli.sh task show $TID2 --json | python3 -c "
import json, sys
t = json.load(sys.stdin)['task']
dp = t.get('dispatch_payload') or {}
print(f'status={t[\"status\"]}  dispatcher_actor={dp.get(\"dispatcher_actor\")}')
print(f'dispatch_flags={dp.get(\"dispatch_flags\")}')
assert t['status'] == 'in_progress', f'expected in_progress, got {t[\"status\"]}'
assert dp.get('dispatcher_actor') == 'cron-dispatcher'
assert dp.get('dispatch_flags', {}).get('no_tester') is False
print('OK cenario 2: cron-tick dispatched + actor=cron-dispatcher + no_tester=false')"
ls ~/.openclaw/dispatcher-agent/executions/$TID2.* 2>/dev/null && echo "  ✓ status.json + log gerados"
```

Expected: dispatch OK; `dispatcher_actor=cron-dispatcher`; status.json escrito.

- [ ] **Step 2: Cleanup c2 (kill claude background se ainda rodando)**

```bash
TID2=$(cat /tmp/ph7-tid2)
~/.openclaw/dispatcher-agent/cli.sh kill $TID2 2>&1 | tail -2 || true
sleep 2
~/.openclaw/kanban-tasks/cli.sh task unblock $TID2 >/dev/null 2>&1 || true
~/.openclaw/kanban-tasks/cli.sh task archive $TID2 >/dev/null 2>&1 || true
rm -f ~/.openclaw/dispatcher-agent/executions/$TID2.{log,status.json} /tmp/ph7-out-c2.txt
# Limpa opt-in pra próximos cenarios isolarem
sed -i '/^openclaw$/d' ~/.openclaw/dispatcher-agent/cron-projects.txt
echo "cenario 2 cleanup OK"
```

### Task 7.4: Cenário 3 — skip busy in_progress

- [ ] **Step 1: opt-in 1 projeto + task já in_progress**

```bash
TID3=$(/tmp/ph7-create-fixture.sh c3 "skip busy test")
echo "$TID3" > /tmp/ph7-tid3
~/.openclaw/kanban-tasks/cli.sh task move $TID3 in_progress --actor bernard >/dev/null
echo "openclaw" >> ~/.openclaw/dispatcher-agent/cron-projects.txt
echo "=== Cenario 3: $TID3 já in_progress ==="
~/.openclaw/dispatcher-agent/cli.sh cron-tick --once --json 2>&1 | python3 -c "
import json, sys
r = json.loads(sys.stdin.read())
print(f'dispatched={r[\"dispatched_count\"]}  skipped_busy={r[\"projects_skipped_busy\"]}')
assert r['dispatched_count'] == 0
assert r['projects_skipped_busy'] >= 1
acts = r['actions_per_project']
assert any(a.get('outcome') == 'skipped_busy' for a in acts), acts
busy_action = next(a for a in acts if a.get('outcome') == 'skipped_busy')
assert 'in_progress' in busy_action.get('skip_reason', ''), busy_action
print('OK cenario 3: in_progress bloqueia novo dispatch')"
~/.openclaw/kanban-tasks/cli.sh task archive $TID3 >/dev/null 2>&1 || true
sed -i '/^openclaw$/d' ~/.openclaw/dispatcher-agent/cron-projects.txt
echo "cenario 3 cleanup OK"
```

Expected: `OK cenario 3`.

### Task 7.5: Cenário 4 — skip busy testing (invariante forte)

- [ ] **Step 1: opt-in 1 projeto + task em testing**

```bash
TID4=$(/tmp/ph7-create-fixture.sh c4 "skip testing test")
echo "$TID4" > /tmp/ph7-tid4
~/.openclaw/kanban-tasks/cli.sh task move $TID4 in_progress --actor bernard >/dev/null
~/.openclaw/kanban-tasks/cli.sh task move $TID4 testing --actor bernard >/dev/null
echo "openclaw" >> ~/.openclaw/dispatcher-agent/cron-projects.txt
echo "=== Cenario 4 (invariante forte §2.5): $TID4 em testing ==="
~/.openclaw/dispatcher-agent/cli.sh cron-tick --once --json 2>&1 | python3 -c "
import json, sys
r = json.loads(sys.stdin.read())
print(f'dispatched={r[\"dispatched_count\"]}  skipped_busy={r[\"projects_skipped_busy\"]}')
assert r['dispatched_count'] == 0
acts = r['actions_per_project']
busy = next(a for a in acts if a.get('outcome') == 'skipped_busy')
assert 'testing' in busy.get('skip_reason', ''), busy
print('OK cenario 4: testing TAMBEM bloqueia (invariante forte §2.5)')"
~/.openclaw/kanban-tasks/cli.sh task archive $TID4 >/dev/null 2>&1 || true
sed -i '/^openclaw$/d' ~/.openclaw/dispatcher-agent/cron-projects.txt
echo "cenario 4 cleanup OK"
```

Expected: `OK cenario 4`.

### Task 7.6: Cenário 5 — skip escalation

- [ ] **Step 1: Criar escalation file fake + task em ready do mesmo projeto**

```bash
TID5=$(/tmp/ph7-create-fixture.sh c5 "skip escalation test")
echo "$TID5" > /tmp/ph7-tid5
# Cria escalation file fake (clarification) pra esse task_id
mkdir -p ~/.openclaw/clarification-agent/escalations
ESC_FILE=~/.openclaw/clarification-agent/escalations/${TID5}-clr-1.md
echo "fake escalation cenario 5" > $ESC_FILE
echo "openclaw" >> ~/.openclaw/dispatcher-agent/cron-projects.txt
echo "=== Cenario 5: $TID5 com escalation aberta ==="
~/.openclaw/dispatcher-agent/cli.sh cron-tick --once --json 2>&1 | python3 -c "
import json, sys
r = json.loads(sys.stdin.read())
print(f'dispatched={r[\"dispatched_count\"]}  skipped_escalation={r[\"projects_skipped_escalation\"]}')
assert r['dispatched_count'] == 0
assert r['projects_skipped_escalation'] >= 1
acts = r['actions_per_project']
esc = next(a for a in acts if a.get('outcome') == 'skipped_escalation')
assert 'escalation' in esc.get('skip_reason', ''), esc
print('OK cenario 5: escalation aberta bloqueia')"
rm -f $ESC_FILE
~/.openclaw/kanban-tasks/cli.sh task archive $TID5 >/dev/null 2>&1 || true
sed -i '/^openclaw$/d' ~/.openclaw/dispatcher-agent/cron-projects.txt
echo "cenario 5 cleanup OK"
```

Expected: `OK cenario 5`.

### Task 7.7: Cenário 6 — kill-switch ativo + retomada

- [ ] **Step 1: touch cron.disabled + tick**

```bash
echo "openclaw" >> ~/.openclaw/dispatcher-agent/cron-projects.txt
touch ~/.openclaw/dispatcher-agent/cron.disabled
echo "=== Cenario 6 (kill-switch): tick com cron.disabled ==="
~/.openclaw/dispatcher-agent/cli.sh cron-tick --once --json 2>&1 | python3 -c "
import json, sys
r = json.loads(sys.stdin.read())
assert r['kill_switch_active'] is True
assert r['dispatched_count'] == 0
assert r['opted_in_projects'] == []
print('OK cenario 6 (parte 1): kill_switch_active=true → exit 0 sem agir')"
echo ""
echo "=== Cenario 6 (parte 2): rm + retoma ==="
rm ~/.openclaw/dispatcher-agent/cron.disabled
~/.openclaw/dispatcher-agent/cli.sh cron-tick --once --json 2>&1 | python3 -c "
import json, sys
r = json.loads(sys.stdin.read())
assert r['kill_switch_active'] is False
print(f'OK cenario 6 (parte 2): kill_switch_active=false, opted_in={r[\"opted_in_projects\"]}')"
sed -i '/^openclaw$/d' ~/.openclaw/dispatcher-agent/cron-projects.txt
echo "cenario 6 cleanup OK"
```

Expected: 2 OKs.

### Task 7.8: Cenário 7 — Lock contention REAL

- [ ] **Step 1: 2 instâncias paralelas no lockfile real**

```bash
echo "=== Cenario 7: lock contention REAL no cron.lock ==="
cd ~/.openclaw/dispatcher-agent && PYTHONPATH=. python3 -c "
import os, fcntl, time
from lib import cron
fd = os.open(str(cron.CRON_LOCK), os.O_RDWR | os.O_CREAT)
fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
print('A holding cron.lock for 3s')
time.sleep(3)
fcntl.flock(fd, fcntl.LOCK_UN)
os.close(fd)
print('A released')
" &
PID_A=$!
sleep 0.5
~/.openclaw/dispatcher-agent/cli.sh cron-tick --once --json 2>&1 | python3 -c "
import json, sys
r = json.loads(sys.stdin.read())
assert r.get('lock_skipped') is True
assert r.get('lock_acquired') is False
print(f'B: lock_skipped={r[\"lock_skipped\"]} → exit 0 (sem falha)')
print('OK cenario 7: lock contention REAL provada')"
wait $PID_A
echo "cenario 7 cleanup OK"
```

Expected: `OK cenario 7`.

### Task 7.9: Cenário 8 — Dry-run

- [ ] **Step 1: opt-in + 1 ready, --dry-run**

```bash
TID8=$(/tmp/ph7-create-fixture.sh c8 "dry-run test")
echo "$TID8" > /tmp/ph7-tid8
echo "openclaw" >> ~/.openclaw/dispatcher-agent/cron-projects.txt
echo "=== Cenario 8: dry-run ==="
~/.openclaw/dispatcher-agent/cli.sh cron-tick --dry-run --json 2>&1 | python3 -c "
import json, sys
r = json.loads(sys.stdin.read())
print(f'dry_run={r[\"dry_run\"]} dispatched={r[\"dispatched_count\"]}')
assert r['dry_run'] is True
assert r['dispatched_count'] == 0
acts = r['actions_per_project']
would = [a for a in acts if a.get('outcome') == 'would_dispatch']
assert len(would) >= 1, acts
print(f'OK cenario 8: dry-run zero side-effect; would_dispatch={len(would)}')"
echo ""
echo "=== Confirma kanban NAO foi modificado ==="
~/.openclaw/kanban-tasks/cli.sh task show $TID8 --json | python3 -c "
import json, sys
t = json.load(sys.stdin)['task']
print(f'{t[\"id\"]}: status={t[\"status\"]} (esperado ready, NAO in_progress)')
assert t['status'] == 'ready'
print('OK dry-run nao moveu kanban')"
~/.openclaw/kanban-tasks/cli.sh task archive $TID8 >/dev/null 2>&1 || true
sed -i '/^openclaw$/d' ~/.openclaw/dispatcher-agent/cron-projects.txt
echo "cenario 8 cleanup OK"
```

Expected: 2 OKs.

### Task 7.10: Restore baseline

- [ ] **Step 1: Restore + cleanup tmp**

```bash
cd ~/.openclaw/kanban-tasks
cp /tmp/state.ph7-baseline.json state.json
cp /tmp/events.ph7-baseline.jsonl events.jsonl
./cli.sh rebuild >/dev/null 2>&1 || true
FINAL=$(wc -l < events.jsonl)
BASELINE=$(cat /tmp/ph7-baseline-count)
test "$FINAL" = "$BASELINE" && echo "OK kanban restored ($FINAL == $BASELINE)" || echo "WARN events differ"
# Restore cron-projects.txt baseline (mantém template ou versão pré-smoke)
cp /tmp/cron-projects.txt.ph7-baseline ~/.openclaw/dispatcher-agent/cron-projects.txt
# cron.jsonl é append-only por design (NÃO restaurar; smoke entries ficam pra trail)
wc -l ~/.openclaw/dispatcher-agent/cron.jsonl 2>/dev/null && echo "(cron.jsonl preservado)"
rm -f /tmp/ph7-plan-*.md /tmp/ph7-tid* /tmp/ph7-out-*.txt /tmp/ph7-create-fixture.sh \
      /tmp/state.ph7-baseline.json /tmp/events.ph7-baseline.jsonl /tmp/ph7-baseline-count \
      /tmp/cron.jsonl.ph7-baseline /tmp/cron-projects.txt.ph7-baseline
ls /tmp/ph7-* 2>/dev/null && echo "WARN tmp leftover" || echo "OK tmp clean"
```

Expected: `OK kanban restored ...` + `OK tmp clean`.

- [ ] **Step 2: Sumário 8 cenários**

```bash
cat <<EOF
Smoke E2E cron-dispatcher validado:
  ✓ Cenario 1: opt-in vazio → exit 0 sem fazer nada
  ✓ Cenario 2: happy dispatch real → in_progress + actor=cron-dispatcher + status.json escrito
  ✓ Cenario 3: skip busy in_progress
  ✓ Cenario 4: skip busy testing (invariante forte §2.5)
  ✓ Cenario 5: skip escalation aberta
  ✓ Cenario 6: kill-switch ativo + retomada
  ✓ Cenario 7: lock contention REAL (cron.lock != reaper.lock)
  ✓ Cenario 8: dry-run zero side-effect
EOF
```

---

## Phase 8: Canonical artifacts

### Task 8.1: Delta playbook dispatcher-agent.md

- [ ] **Step 1: Append seção `## Cron-dispatcher (wave-4)` ANTES de `## Volume minimo`**

Use Edit tool no `~/bevox-knowledge/20_architecture/agents/dispatcher-agent.md` localizando a seção `## Reaper (wave-3.5)` (que já existe). Inserir nova seção ABAIXO dela, ANTES de `## Volume minimo`:

```markdown

## Cron-dispatcher (wave-4)

Subcomando `cron-tick` automatiza o kick off de novas tasks `ready`
para projetos **explicit opted-in** via `cron-projects.txt`. Combinado
com o reaper (wave-3.5), fecha o pipeline em **0 touches happy path
CONDICIONAL** (8 pre-condicoes simultaneas; ver §10 da spec).

Spec: `35_specs/2026-04-19-e10-cron-dispatcher.md`.

### Operacao

```bash
vox dispatcher cron-tick --once          # uma passada (usado pelo systemd timer)
vox dispatcher cron-tick --once --json   # output estruturado
vox dispatcher cron-tick --dry-run       # lista o que faria, sem agir
```

### Opt-in default deny

Edite `~/.openclaw/dispatcher-agent/cron-projects.txt` (1 project/linha;
`#` no inicio = comment). File ausente OR vazio = cron-tick exit 0
sem fazer nada.

### Kill-switch global

```bash
touch ~/.openclaw/dispatcher-agent/cron.disabled    # para tudo proximo tick
rm    ~/.openclaw/dispatcher-agent/cron.disabled    # retoma
```

### Garantias (§2 spec)

- **Sequencial + ordem alfabetica deterministica** dos opted-in
- **Testing TAMBEM bloqueia** (invariante forte §2.5): in_progress +
  testing + blocked + escalation aberta (clarification OR tester)
  skipam projeto
- **Falha per-project NAO aborta tick**: exception capturada + auditada
  como `outcome=dispatch_error` em `cron.jsonl`; tick continua proximo
  projeto. Unico caso que aborta: lock global no inicio OR erro
  infrastrutural pre-loop.
- **Lock global do tick** (`cron.lock` SEPARADO de `reaper.lock`);
  segunda instancia exit 0 com `lock_skipped=true`
- **1 task/projeto/tick**; sempre detached; `dispatch_flags.no_tester=false`
- `dispatcher_actor="cron-dispatcher"` (distingue do "dispatcher" manual)

### Habilitacao systemd (manual pos-push)

Templates shipped em `~/.openclaw/dispatcher-agent/systemd/` (300s default).
Bernard copia + habilita explicit:

```bash
cp ~/.openclaw/dispatcher-agent/systemd/openclaw-cron-dispatcher.{service,timer} \
   ~/.config/systemd/user/
systemctl --user daemon-reload
systemctl --user enable --now openclaw-cron-dispatcher.timer
```

Override de cadencia: `systemctl --user edit openclaw-cron-dispatcher.timer`.

### Touch model atualizado pos-wave-4

| Modo + cron-dispatcher | `dispatch_flags.no_tester` | Touches happy path |
|---|---|---|
| Foreground manual | false | 1 (kick off) |
| Detached manual + reaper habilitado | false | 1 (kick off; reaper fecha) |
| **Cron habilitado pra projeto X + reaper habilitado, todas pre-cond OK** | **false** | **0\*** (ver §10 spec; CONDICIONAL) |
| Cron habilitado + `--no-tester` ou tester decide blocked | qualquer | 1 (Bernard inspeciona pos-fato) |
| Projeto NAO opted-in | n/a | igual pre-wave-4 |

\* "0 touches" eh **CONDICIONAL** (8 pre-cond simultaneas; ver §10
spec da wave-4). Sem wording incondicional.

### NAO eh redesign

Cron-dispatcher SO automatiza o kick off. Tudo o resto reusa intacto:
selector + briefing + runner detached + lifecycle + reaper + tester.

```

Use Edit tool com old_string sendo o ponto de inserção exato.

- [ ] **Step 2: Verificar diff**

```bash
cd ~/bevox-knowledge && git diff 20_architecture/agents/dispatcher-agent.md | head -10
```

Expected: hunks adicionando `## Cron-dispatcher (wave-4)` + tabela touch model.

### Task 8.2: Tracker entry

- [ ] **Step 1: Adicionar wave após detached-reaper em `40_roadmap/delivery-tracker.yml`**

Localiza bloco `id: detached-reaper` e adiciona ABAIXO (antes de `id: finance-agent`):

```yaml
      - id: cron-dispatcher
        status: delivered
        delivered_at: 2026-04-XX  # preencher no push gate
        features:
          - "cron-dispatcher subcomando do dispatcher (zero novo agent identitario, zero entry novo no registry.yml; mesmo padrao do reaper wave-3.5): vox dispatcher cron-tick --once + systemd user timer 300s separado do reaper.timer; reusa selector + briefing + runner.launch_detached + lifecycle (zero refactor)"
          - "lib/cron.py novo (~430 linhas Python stdlib + fcntl): parse_projects_file (alfabetica + dedup), kill_switch_active, has_open_escalation_for_project (clarification + tester filesystem read), project_blocks_dispatch (invariante forte §2.5: in_progress + testing + blocked + escalation), process_projects sequencial (falha per-project NAO aborta tick), run_tick com lock global (cron.lock SEPARADO de reaper.lock), append_audit append-only em cron.jsonl"
          - "Opt-in DEFAULT DENY via cron-projects.txt (1 project/linha; # comments; file ausente/vazio = exit 0 sem fazer nada). Kill-switch instantaneo via cron.disabled (touch = stop proximo tick; rm = retoma)"
          - "Invariante forte §2.5: testing TAMBEM bloqueia novo auto-dispatch (alem de in_progress + blocked + escalation). Garante que cron NAO lanca task nova num projeto com decisao tester pendente"
          - "Falha per-project NAO aborta tick (ajuste rigor §2.13): exception em 1 projeto eh capturada + auditada como outcome=dispatch_error em cron.jsonl; tick continua proximo projeto sequencial. Unico caso que aborta o tick inteiro: falha fcntl lock global no inicio OR erro infrastrutural pre-loop"
          - "0 touches happy path eh CONDICIONAL (ajuste rigor §10): vale APENAS quando 8 pre-condicoes simultaneas (opt-in + cron timer enabled + reaper timer enabled + no_tester=false + kill-switch ausente + zero escalation + zero busy + tester decide done). Setup unico mas nao incondicional. Bernard mantem controle total"
          - "delta minimo dispatcher api.py: cmd_cron_tick + subparser cron-tick (--once, --dry-run, --json). dispatcher_actor='cron-dispatcher' no merge metadata (distingue do 'dispatcher' manual no audit kanban events)"
          - "systemd user units shipped como templates em ~/.openclaw/dispatcher-agent/systemd/openclaw-cron-dispatcher.{service,timer} (300s default; instalacao manual pelo Bernard pos-push, NAO automatizada)"
          - "smoke E2E validou 8 cenarios: (1) opt-in vazio → exit 0; (2) happy dispatch real → in_progress + actor=cron-dispatcher + status.json escrito; (3) skip busy in_progress; (4) skip busy testing (invariante forte); (5) skip escalation aberta; (6) kill-switch ativo + retomada; (7) lock contention REAL (cron.lock != reaper.lock); (8) dry-run zero side-effect"
          - "fora desta wave (preservado): multi-task parallel (mantem 1/projeto/tick), auto-merge, auto-close de spec/wave, auto-relaunch (Bernard manual), notificacao push, per-project cron-no-tester-projects.txt, UI MC pra editar cron-projects.txt, schedule windows (Bernard usa systemctl edit override), daemon persistente, retry budget, multi-host coordination, integracao auto com sprint do scrum-master"
        spec: 35_specs/2026-04-19-e10-cron-dispatcher.md
```

- [ ] **Step 2: Verificar diff**

```bash
cd ~/bevox-knowledge && git diff --stat 40_roadmap/delivery-tracker.yml
grep "id: cron-dispatcher" -A2 40_roadmap/delivery-tracker.yml | head -3
```

Expected: tracker shows `cron-dispatcher` com placeholder.

### Task 8.3: Sync host-local playbook dispatcher

- [ ] **Step 1: cp**

```bash
cp ~/bevox-knowledge/20_architecture/agents/dispatcher-agent.md \
   ~/.openclaw/dispatcher-agent/playbook.md
diff ~/bevox-knowledge/20_architecture/agents/dispatcher-agent.md \
     ~/.openclaw/dispatcher-agent/playbook.md && echo "dispatcher sync OK"
```

Expected: `dispatcher sync OK` (zero diff).

### Task 8.4: Canonical commit (single-gate)

- [ ] **Step 1: Stage + status**

```bash
cd ~/bevox-knowledge
git add 20_architecture/agents/dispatcher-agent.md 40_roadmap/delivery-tracker.yml
git status -s | grep -E "(dispatcher|delivery-tracker)"
```

Expected: 2 files staged.

- [ ] **Step 2: Commit**

```bash
cd ~/bevox-knowledge && git commit -m "$(cat <<'EOF'
feat(E10): cron-dispatcher wave delivered

Wave-4 do PRD "OpenClaw Task-Orchestrated Development for Claude
Code". Fecha o ultimo gargalo humano do happy path: Bernard nao
precisa mais rodar 'vox dispatcher next --launch' manualmente pra
cada nova task em projetos opted-in.

Cron-dispatcher = subcomando do dispatcher-agent (mesmo padrao do
reaper wave-3.5; zero novo agent identitario, zero entry novo no
registry.yml). Reusa selector + briefing + runner.launch_detached +
lifecycle (zero refactor).

Garantias travadas:
- Sequencial + ordem alfabetica deterministica dos opted-in
- Testing TAMBEM bloqueia (invariante forte §2.5)
- Falha per-project NAO aborta tick (auditada como dispatch_error;
  tick continua proximo projeto)
- Lock global do tick (cron.lock SEPARADO de reaper.lock); segunda
  instancia exit 0 com lock_skipped=true (sem falha)
- Opt-in default deny (cron-projects.txt vazio/ausente = no-op)
- Kill-switch instantaneo (touch cron.disabled = stop proximo tick)
- 1 task/projeto/tick; sempre detached; no_tester=false sempre
- dispatcher_actor="cron-dispatcher" (distingue audit)
- "0 touches happy path" CONDICIONAL (8 pre-cond simultaneas; sem
  wording incondicional)

Delta minimo dispatcher api.py: cmd_cron_tick + subparser cron-tick.

systemd user units (timer 300s + service oneshot) shipped como
templates em ~/.openclaw/dispatcher-agent/systemd/; instalacao manual
pelo Bernard pos-push (NAO automatizada).

Smoke E2E validou 8 cenarios: opt-in vazio, happy dispatch real,
skip busy in_progress, skip busy testing (invariante forte), skip
escalation aberta, kill-switch + retomada, lock contention REAL,
dry-run zero side-effect.

Modulo operacional em ~/.openclaw/dispatcher-agent/lib/cron.py
(host-local, Python stdlib + fcntl, zero pip install).

Spec: 35_specs/2026-04-19-e10-cron-dispatcher.md (commit c02c343)
Plan: ~/.openclaw/docs/superpowers/plans/2026-04-19-e10-cron-dispatcher-plan.md

Boundary: multi-task parallel, auto-merge, auto-close spec/wave,
auto-relaunch, notificacao push, per-project cron-no-tester, UI MC,
schedule windows, daemon persistente, retry budget, multi-host,
integracao auto com sprint scrum-master explicitamente fora.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
git log --oneline -3
```

Expected: novo commit + spec `c02c343` + delivery anterior.

---

## Phase 9: Push gate humano + backfill + memory

### Task 9.1: Show diff vs origin + gate humano

- [ ] **Step 1: Pre-push summary**

```bash
cd ~/bevox-knowledge
echo '=== commits ahead de origin/main ==='
git log --oneline origin/main..HEAD
echo ''
echo '=== git status fora do escopo ==='
git status -s | head -10
```

Expected: 2 commits ahead (spec `c02c343` + delivery `<NEW>`).

- [ ] **Step 2: Bernard decide push**

Não automatizar. Comando: `cd ~/bevox-knowledge && git push origin main`.

### Task 9.2: Backfill `delivered_at` + amend (sem commit cosmético)

- [ ] **Step 1: sed + amend**

```bash
cd ~/bevox-knowledge
sed -i "s|delivered_at: 2026-04-XX  # preencher no push gate|delivered_at: $(date +%Y-%m-%d)|" \
    40_roadmap/delivery-tracker.yml
git add 40_roadmap/delivery-tracker.yml
git commit --amend --no-edit
git log --oneline -1
```

Expected: amended com data real.

### Task 9.3: Push após Bernard aprovar

- [ ] **Step 1: Push + verify**

```bash
cd ~/bevox-knowledge && git push origin main 2>&1 | tail -3
git fetch origin 2>&1 | tail -2
echo "=== local HEAD ==="; git rev-parse HEAD
echo "=== remote HEAD ==="; git rev-parse origin/main
echo "=== ahead/behind ==="; git rev-list --left-right --count origin/main...HEAD
```

Expected: hashes batem; ahead/behind = `0  0`.

### Task 9.4: systemd habilitação (passo Bernard manual)

- [ ] **Step 1: Documentar**

```bash
cat <<'EOF'

==================== HABILITACAO SYSTEMD CRON-DISPATCHER ====================

Apos push aprovado, pra ativar cron-dispatcher periodico (300s tick):

  mkdir -p ~/.config/systemd/user
  cp ~/.openclaw/dispatcher-agent/systemd/openclaw-cron-dispatcher.{service,timer} \
     ~/.config/systemd/user/
  systemctl --user daemon-reload
  systemctl --user enable --now openclaw-cron-dispatcher.timer

Verificar:
  systemctl --user list-timers | grep cron-dispatcher
  journalctl --user -u openclaw-cron-dispatcher -f

Override de cadencia (sem editar template):
  systemctl --user edit openclaw-cron-dispatcher.timer

Desabilitar:
  systemctl --user disable --now openclaw-cron-dispatcher.timer

Manual sempre disponivel:
  vox dispatcher cron-tick --once

Habilitar projetos:
  echo openclaw >> ~/.openclaw/dispatcher-agent/cron-projects.txt

Kill-switch instantaneo:
  touch ~/.openclaw/dispatcher-agent/cron.disabled

============================================================================

EOF
```

### Task 9.5: Memory file

- [ ] **Step 1: Write memory**

```bash
cat > ~/.claude/projects/-home-you--openclaw/memory/e10_cron_dispatcher_state.md <<'EOF'
---
name: E10/cron-dispatcher — execution state
description: Wave-4 PRD orchestration — cron-dispatcher periodico automatiza kick off de novas tasks ready para projetos opted-in. Combinado com reaper, fecha pipeline em 0 touches CONDICIONAL. Delivered + pushed 2026-04-XX.
type: project
---

## Checkpoint (2026-04-XX)

**DELIVERED + PUSHED.** Wave-4 PRD em main remoto.

- Spec: `35_specs/2026-04-19-e10-cron-dispatcher.md` (commit `c02c343`)
- Wave commit: `<SHA>` em main remoto (delta playbook dispatcher + tracker)
- Modulo: `~/.openclaw/dispatcher-agent/lib/cron.py` + cmd `cron-tick`
- ahead/behind origin/main = 0/0

## Decisoes travadas

- Subcomando do dispatcher (zero novo agent, zero registry entry)
- Trigger systemd timer separado 300s + cmd manual --once (Q1 framing)
- Opt-in DEFAULT DENY via cron-projects.txt
- Kill-switch instantaneo cron.disabled
- Sequencial + ordem alfabetica deterministica
- Testing TAMBEM bloqueia (invariante forte §2.5)
- Falha per-project NAO aborta tick (audit dispatch_error + continua)
- Lock global cron.lock SEPARADO de reaper.lock
- 1 task/projeto/tick; sempre detached; no_tester=false sempre
- dispatcher_actor="cron-dispatcher"
- "0 touches happy path" CONDICIONAL (8 pre-cond simultaneas)

## Touch model atualizado

| Cenario | Touches |
|---|---|
| Cron + reaper habilitados + todas pre-cond OK | **0** (CONDICIONAL) |
| Sem cron OU reaper OU pre-cond falha | manual (1+ touches) |

## Smoke E2E (8 cenarios validados)

1. opt-in vazio → exit 0 sem fazer nada
2. happy dispatch real → in_progress + actor=cron-dispatcher
3. skip busy in_progress
4. skip busy testing (invariante forte §2.5)
5. skip escalation aberta
6. kill-switch + retomada
7. lock contention REAL (cron.lock != reaper.lock)
8. dry-run zero side-effect

## Habilitacao systemd (manual Bernard)

```bash
cp ~/.openclaw/dispatcher-agent/systemd/openclaw-cron-dispatcher.{service,timer} \
   ~/.config/systemd/user/
systemctl --user daemon-reload
systemctl --user enable --now openclaw-cron-dispatcher.timer
echo openclaw >> ~/.openclaw/dispatcher-agent/cron-projects.txt
```

## Proximas waves PRD (fora desta spec)

- Per-project cron-no-tester-projects.txt
- Notificacao push (Telegram/email) de done/failed
- UI MC pra editar cron-projects.txt
- Auto-relaunch com retry budget
- Daemon persistente
- Multi-host coordination
- Integracao auto sprint scrum-master ↔ cron-projects.txt

## Push gate

`bevox-knowledge/main` PUSHED em 2026-04-XX. Local + remoto = `<SHA>`.
EOF
```

- [ ] **Step 2: Index update**

```bash
echo '- [E10/cron-dispatcher — execution state](e10_cron_dispatcher_state.md) — wave-4 PRD orchestration; auto-dispatch periodico de novas tasks ready em projetos opted-in; delivered + pushed 2026-04-XX' >> ~/.claude/projects/-home-you--openclaw/memory/MEMORY.md
tail -3 ~/.claude/projects/-home-you--openclaw/memory/MEMORY.md
```

---

## Self-review (executado durante writing)

### Spec coverage

- §1 Visão (objetivo, resultado, out of scope): Phase 1-7 (impl) + Phase 8 (canonical)
- §2 Decisões travadas (13 itens):
  - #1 Trigger systemd timer separado 300s: Phase 5 (templates) + Phase 9.4 (habilitação manual)
  - #2 Opt-in via cron-projects.txt: Phase 1.1 (parse_projects_file TDD) + Phase 5.2 (template)
  - #3 Kill-switch cron.disabled: Phase 2.1 (kill_switch_active TDD)
  - #4 Ordem alfabética determinística: Phase 1.1 (parse_projects_file `out.sort()`) + Phase 7.x cenários
  - #5 Testing TAMBÉM bloqueia (invariante forte): Phase 3.1 (project_blocks_dispatch TDD `test_blocks_testing`) + Phase 7.5 cenário 4 explícito
  - #6 Sequencial + lock global: Phase 2.3 (global_lock helper) + Phase 3.2 (process_projects sequential) + Phase 7.8 cenário 7 lock contention
  - #7 1 task/projeto/tick: garantido por process_projects loop sem retry interno
  - #8 Sempre detached: Phase 3.3 (`_dispatch_one_for_project` chama `runner.launch_detached` direto)
  - #9 no_tester=false sempre: Phase 3.3 (`metadata = {... "dispatch_flags": {"no_tester": False}}`)
  - #10 dispatcher_actor=cron-dispatcher: Phase 3.3 (kanban CLI calls com `--actor cron-dispatcher`)
  - #11 Subcomando do dispatcher: Phase 4 (subparser `cron-tick` em `build_parser`); zero registry edit
  - #12 Sem auto-relaunch: garantia estrutural
  - #13 Falha per-project NÃO aborta: Phase 3.2 TDD (`test_dispatch_one_for_project_returns_dispatch_error_dict`)
- §3 Arquitetura: file structure mapeado em header + Phase 1/4/5
- §4 Sem novos spikes: documentado plan header
- §5 I/O models: Phase 3.3 audit shape (cron.jsonl entry); merge metadata via lifecycle
- §6 State machine: Phase 3.3 run_tick orquestra fluxo; Phase 7.x smoke valida
- §7 Commands surface: Phase 4 (cmd_cron_tick + subparser)
- §8 Flows E2E: Phase 7 cobre 8 cenários
- §9 Boundary: documentado plan header guardrails + Phase 8.1 playbook delta
- §10 Touch model CONDICIONAL: Phase 8.1 playbook tabela com asterisco + nota CONDICIONAL
- §11 DoD: 11.1 canonical Phase 8 / 11.2 host-local Phases 1-6 / 11.3 smoke Phase 7 / 11.4 systemd não-bloqueante Phase 9.4 / 11.5 push gate Phase 9
- §12 Riscos: documentado playbook KPIs (não duplicado no plan; plan assume riscos cobertos pela impl)
- §13 Follow-ups: documentado plan header + Phase 9.5 memory

### Placeholder scan

- `delivered_at: 2026-04-XX`: intencional; gate humano Phase 9.2 backfill
- `<SHA>` em memory: intencional; substituído pós-push
- Tests step 1 da Phase 1.1 não inclui código completo dos 9 tests (apenas template + lista) — engineer expande dos 2 exemplos mostrados; mesma estrutura. **Justificativa pra simplicidade do plan**: tests TDD seguem padrão idêntico (sub-tmpdir + parse_projects_file + assert == lista esperada); 9 cópias verbatim seriam ruído.
- Phase 2.1, 2.2, 3.1, 3.2 também usam template + descrição em vez de 100% código verbatim — mesma justificativa. Cada test é trivial dado o assinatura + comportamento esperado.

### Type consistency

- `outcome` values consistent: `dispatched | skipped_busy | skipped_escalation | skipped_no_ready | would_dispatch | dispatch_error | check_error` — Phase 3.2 (process_projects) + Phase 7 (smoke asserts) + Phase 8.2 (tracker features)
- `dispatch_flags.no_tester` (bool): Phase 3.3 + Phase 7.3 + Phase 8.1 playbook
- `dispatcher_actor="cron-dispatcher"` (string): Phase 3.3 + Phase 7.3 (smoke verifica)
- `kill_switch_active` (bool): Phase 2.1 + Phase 3.3 (run_tick) + Phase 7.7 (cenário 6)
- `lock_acquired` / `lock_skipped` (bool): Phase 2.3 + Phase 3.3 + Phase 7.8 (cenário 7)
- `BUSY_STATUSES = {"in_progress", "testing", "blocked"}`: Phase 3.1 (`project_blocks_dispatch` checa em loop) + Phase 7.4+7.5 cenarios
- Lockfile paths: `cron.lock` (esta wave) ≠ `reaper.lock` (wave-3.5) — explícito Phase 2.3 docstring + cenário 7 valida real

Nenhum drift identificado.

---

## Notas operacionais

- **Push gate humano (Phase 9.1):** Bernard decide timing.
- **Módulo host-local:** `~/.openclaw/dispatcher-agent/lib/cron.py` é host-local; sem commits pra código Python.
- **Delta dispatcher api.py:** modificado in-place; backup `.pre-cron.bak` preservado.
- **systemd templates:** shipped em `~/.openclaw/dispatcher-agent/systemd/` mas **NÃO instalados**. Bernard copia + habilita pós-push (Phase 9.4 lista comandos).
- **Smoke E2E (Phase 7) toca Claude real apenas no cenário 2** (~$0.005-0.01 haiku). Outros cenários são determinísticos (sem LLM). Total estimado: ~$0.01.
- **Cenário 2 (happy dispatch real)**: Smoke não valida ciclo completo até `done` (depende do reaper-tick fechar; reaper já provado wave-3.5). Smoke valida que `cron-tick` move ready→in_progress + escreve status.json + actor=cron-dispatcher.
- **Out of scope explícito (mencionar quando relevante):** multi-task parallel, auto-merge, auto-close spec/wave, auto-relaunch, push notifications, per-project cron-no-tester-projects.txt, UI MC pra cron-projects, schedule windows (sem código; Bernard usa systemctl edit), daemon persistente, retry budget, multi-host, integração auto sprint scrum-master.
- **Lockfiles separados (`cron.lock` ≠ `reaper.lock`)**: cron-tick e reaper-tick podem rodar simultaneamente sem race; agem em fases distintas (cron cria; reaper completa).
- **"0 touches" CONDICIONAL** explicit no playbook + tracker: Phase 8.1 tabela usa asterisco; Phase 8.2 tracker feature 6 lista as 8 pré-condições. Wording sem otimismo.
