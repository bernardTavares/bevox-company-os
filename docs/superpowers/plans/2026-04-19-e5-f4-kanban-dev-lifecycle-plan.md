# E5/F4 Kanban Dev Lifecycle - Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use `superpowers:subagent-driven-development` (recommended) or `superpowers:executing-plans` to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Wave-3 da família F4 — substitui o enum de status do kanban (`backlog/todo/in_progress/done`) por `backlog/ready/in_progress/testing/done/rejected` + flag ortogonal `blocked`, introduz whitelist soft de transições com `--force`/`--reason` auditável, e adiciona hooks (eventos satélites + `GET /next-ready` + slots reservados) prontos pros agentes futuros.

**Architecture:** Backend host-local Python continua sendo SoT da lógica de mutação (`~/.openclaw/kanban-tasks/`). Schema bump 1→2 aditivo. Novo módulo `lib/transitions.py` centraliza whitelist e validação. Mission Control (TS/Next em `~/code/mission-control`) ganha 4 rotas novas, espelha whitelist em TS pra D&D guard, e adapta UI pra 5 colunas + rejected lane + blocked badge/filter/modal. Eventos antigos (`task_moved to:"todo"`) preservados; alias permanente `todo→ready` na projeção.

**Tech Stack:**
- Backend host-local: Python 3 stdlib (mantém sem pip install)
- HTTP layer: Next.js 15 API routes (pattern `respondCli` + `runCli` + `resolveActor`)
- UI: Next.js + React 19 + Tailwind 4
- D&D existente: `@dnd-kit/core` (sem deps novas)
- Tests TS: Vitest (já presente no MC)
- Tests Python: smoke E2E shell (mantém convenção do módulo, sem pytest)

**Spec canônica:** `bevox-knowledge/35_specs/2026-04-19-e5-f4-kanban-dev-lifecycle.md` (commit `2483df0`)

**Plans pares (waves anteriores):** `bevox-knowledge/35_specs/2026-04-17-e5-f4-kanban-tasks-implementation-plan.md`

**Constraint operacional:**
- Wave-1 + wave-2 já delivered e em `main` nos dois repos.
- MC repo: `~/code/mission-control` em `main` (kanban já merged).
- Branch sugerida MC: `feat/e5-f4-kanban-dev-lifecycle` (criar fresh em Phase 0).
- Branch sugerida bevox-knowledge: trabalhar direto em `main` local (padrão F4); push gate humano explícito ao final.
- `npm install` não deve ser necessário (zero deps novas). Se aparecer, **pausar e reportar**.

---

## File Structure

### Host-local (`~/.openclaw/kanban-tasks/`)

```
~/.openclaw/kanban-tasks/
├── lib/
│   ├── transitions.py              # NOVO: whitelist + validação + helpers
│   ├── task.py                     # MODIFICA: VALID_STATUS, move_status, archive; ADICIONA: block, unblock, reopen, _populate_defaults
│   ├── api.py                      # MODIFICA: argparse choices, --force/--reason, alias todo→ready em apply_event, defaults em rebuild
│   ├── sprint.py                   # INALTERADO
│   ├── store.py                    # INALTERADO
│   └── __init__.py                 # INALTERADO
├── smoke_e2e.sh                    # ESTENDE: novos cenários (block/unblock/reopen, satellites, force, alias todo→ready)
└── README.md                       # MODIFICA: status enum atualizado, exemplos novos cmds
```

### Mission Control (`~/code/mission-control`)

```
mission-control/src/
├── app/api/kanban/tasks/
│   ├── [id]/move/route.ts          # MODIFICA: VALID_STATUS atualizado, aceita force/reason
│   ├── [id]/block/route.ts         # NOVO
│   ├── [id]/unblock/route.ts       # NOVO
│   ├── [id]/reopen/route.ts        # NOVO
│   └── next-ready/route.ts         # NOVO
├── app/(dashboard)/kanban/
│   ├── page.tsx                    # MODIFICA: 5 colunas + rejected lane + blocked filter + atalho b
│   └── history/[sprint_id]/page.tsx # MODIFICA: 5 colunas (read-only)
├── components/kanban/
│   ├── Board.tsx                   # MODIFICA: ORDER expandido, D&D guard via transitions.ts
│   ├── TaskCard.tsx                # MODIFICA: blocked badge + tooltip
│   ├── RejectedLane.tsx            # NOVO (espelha pattern de archived inline)
│   ├── BlockedFilter.tsx           # NOVO
│   ├── BlockModal.tsx              # NOVO
│   ├── KeyboardShortcuts.tsx       # MODIFICA: atalho 'b'
│   ├── ShortcutsCheatsheet.tsx     # MODIFICA: documenta 'b'
│   ├── useFilterPersistence.ts     # MODIFICA: bump schema com blockedOnly (mantém v1 com fallback)
│   ├── useFilterPersistence.test.ts # MODIFICA: cobre blockedOnly
│   └── transitions.test.ts         # NOVO
└── lib/kanban/
    ├── statusEnum.ts               # NOVO
    ├── transitions.ts              # NOVO (espelho TS da whitelist)
    ├── stateReader.ts              # MODIFICA: TaskStatus enum + Task type ganha campos novos
    ├── auth.ts                     # INALTERADO
    └── cli.ts                      # INALTERADO
```

### bevox-knowledge

```
40_roadmap/delivery-tracker.yml     # ADICIONA feature F4-kanban-dev-lifecycle
```

---

## Phase 0: Pre-flight + branch setup

### Task 0.1: Verify both repos clean

**Files:** none (read-only)

- [ ] **Step 1: Verify openclaw repo not dirty no escopo wave-3**

```bash
ls -la ~/.openclaw/kanban-tasks/lib/transitions.py 2>/dev/null && echo "WARN: transitions.py already exists" || echo "OK: not yet"
grep -q "VALID_STATUS = (\"backlog\", \"todo\", \"in_progress\", \"done\", \"archived\")" ~/.openclaw/kanban-tasks/lib/task.py && echo "OK: lib/task.py at wave-2 baseline" || echo "WARN: lib/task.py drift"
```

Expected: both OK lines.

- [ ] **Step 2: Verify mission-control repo state**

```bash
cd ~/code/mission-control
git status -s
git branch --show-current
```

Expected: branch `main`. Modificações pré-existentes (CLAUDE.md, src/app/(dashboard)/health/page.tsx) podem estar presentes — **não tocar nelas** durante essa wave.

- [ ] **Step 3: Verify spec canônica acessível**

```bash
ls -la ~/bevox-knowledge/35_specs/2026-04-19-e5-f4-kanban-dev-lifecycle.md
git -C ~/bevox-knowledge log --oneline -1 -- 35_specs/2026-04-19-e5-f4-kanban-dev-lifecycle.md
```

Expected: arquivo existe; último commit é `2483df0` (ou ID equivalente do commit da spec).

### Task 0.2: Criar branch no MC

**Files:** none (git op)

- [ ] **Step 1: Criar branch feat/e5-f4-kanban-dev-lifecycle**

```bash
cd ~/code/mission-control
git checkout -b feat/e5-f4-kanban-dev-lifecycle
git status -s
```

Expected: branch nova criada; modificações pré-existentes (CLAUDE.md, health/page.tsx) seguem ali sem stage — não commitar.

### Task 0.3: Snapshot defensivo do state.json + events.jsonl

**Files:** snapshot temporário

- [ ] **Step 1: Backup quick antes de mexer no schema**

```bash
mkdir -p ~/.openclaw/backups/kanban-tasks
cp ~/.openclaw/kanban-tasks/state.json ~/.openclaw/backups/kanban-tasks/state.json.pre-wave3.$(date -Iseconds)
cp ~/.openclaw/kanban-tasks/events.jsonl ~/.openclaw/backups/kanban-tasks/events.jsonl.pre-wave3.$(date -Iseconds)
ls -la ~/.openclaw/backups/kanban-tasks/ | tail -3
```

Expected: 2 arquivos backup criados. Rollback de emergência: restaurar esses dois.

---

## Phase 1: Schema + módulo transitions (Python)

### Task 1.1: Criar `lib/transitions.py` com whitelist

**Files:**
- Create: `~/.openclaw/kanban-tasks/lib/transitions.py`

- [ ] **Step 1: Criar transitions.py**

```python
"""Status transitions: whitelist canônica + validação soft.

Whitelist (transições não-forçadas):
    backlog     -> ready, in_progress, rejected
    ready       -> backlog, in_progress, rejected
    in_progress -> ready, testing, rejected
    testing     -> in_progress, done, rejected
    done        -> ∅ (terminal — exige reopen)
    rejected    -> ∅ (terminal — exige reopen)

Soft policy: fora da whitelist exige force=True (humano) ou
reason não-vazio (agente).
"""

from typing import Optional

# Status enum canônico (excluindo `archived`, que é ortogonal).
STATUS_ENUM = ("backlog", "ready", "in_progress", "testing", "done", "rejected")

# Status terminais — só saem via cmd `reopen`.
TERMINAL = frozenset({"done", "rejected"})

# Status onde flag `blocked` é permitida.
BLOCKABLE = frozenset({"backlog", "ready", "in_progress", "testing"})

# Whitelist soft. Cada chave -> tuple de destinos válidos sem force.
WHITELIST = {
    "backlog":     ("ready", "in_progress", "rejected"),
    "ready":       ("backlog", "in_progress", "rejected"),
    "in_progress": ("ready", "testing", "rejected"),
    "testing":     ("in_progress", "done", "rejected"),
    "done":        (),
    "rejected":    (),
}


def is_valid_transition(from_status: str, to_status: str) -> bool:
    """True se transição está na whitelist (sem force)."""
    return to_status in WHITELIST.get(from_status, ())


def is_terminal(status: str) -> bool:
    return status in TERMINAL


def is_blockable(status: str) -> bool:
    return status in BLOCKABLE


def validate_or_raise(
    from_status: str,
    to_status: str,
    force: bool,
    reason: Optional[str],
    actor: str,
) -> None:
    """Valida transição. Levanta ValueError em política violada.

    - Transição na whitelist: aceita sempre.
    - Fora da whitelist + actor=='bernard' + force=False: erro INVALID_TRANSITION.
    - Fora da whitelist + actor!='bernard' + reason vazio: erro
      INVALID_TRANSITION_AGENT_NEEDS_REASON.
    - Fora da whitelist + reason ou force: aceita.
    - Tentativa de mover terminal sempre exige force ou reason.
    """
    if to_status not in STATUS_ENUM:
        raise ValueError(f"invalid status: {to_status}")
    if is_valid_transition(from_status, to_status):
        return  # OK, dentro da whitelist
    # fora da whitelist
    is_agent = actor != "bernard"
    if is_agent:
        if not reason or not reason.strip():
            raise ValueError(
                f"INVALID_TRANSITION_AGENT_NEEDS_REASON: "
                f"agent '{actor}' must pass --reason to move {from_status}->{to_status}; "
                f"valid destinations from {from_status}: {WHITELIST.get(from_status, ())}"
            )
        return  # agente com reason: OK
    # humano (bernard) sem force
    if not force:
        raise ValueError(
            f"INVALID_TRANSITION: cannot move {from_status}->{to_status} without --force; "
            f"valid destinations from {from_status}: {WHITELIST.get(from_status, ())}"
        )
    return  # humano com --force: OK
```

- [ ] **Step 2: Sanity import**

```bash
python3 -c "from openclaw_kanban_tasks_lib_test import *" 2>/dev/null || \
PYTHONPATH=~/.openclaw/kanban-tasks python3 -c "
from lib.transitions import STATUS_ENUM, WHITELIST, is_valid_transition, validate_or_raise
assert is_valid_transition('backlog', 'ready')
assert is_valid_transition('backlog', 'in_progress')
assert not is_valid_transition('done', 'in_progress')
assert not is_valid_transition('backlog', 'testing')
try:
    validate_or_raise('done', 'in_progress', force=False, reason=None, actor='bernard')
    assert False, 'should have raised'
except ValueError as e:
    assert 'INVALID_TRANSITION' in str(e)
validate_or_raise('done', 'in_progress', force=True, reason=None, actor='bernard')  # OK
validate_or_raise('done', 'in_progress', force=False, reason='regression', actor='vox')  # OK
print('OK')
"
```

Expected: `OK`.

- [ ] **Step 3: Commit Phase 1.1**

```bash
cd ~/.openclaw
git add kanban-tasks/lib/transitions.py 2>/dev/null || true  # openclaw root may not be repo
ls -la ~/.openclaw/kanban-tasks/lib/transitions.py
echo "Phase 1.1 done — transitions.py landed (host-local, no commit needed if openclaw not git)"
```

Note: `~/.openclaw/` não é repo git tracked (host-local SoT). Não há commit aqui — só sinaliza done.

---

## Phase 2: lib/task.py — adapt + novos métodos

### Task 2.1: Atualizar `VALID_STATUS` + `move_status` com transitions + satellites

**Files:**
- Modify: `~/.openclaw/kanban-tasks/lib/task.py`

- [ ] **Step 1: Atualizar imports e VALID_STATUS**

Substituir a linha 8 (`VALID_STATUS = ("backlog", "todo", "in_progress", "done", "archived")`) e o bloco de imports no topo:

```python
"""Task logic: CRUD, move (status/sprint), archive, block/unblock, reopen."""

from typing import Any, Dict, List, Optional

from . import sprint as sprint_lib
from . import store
from . import transitions

# Status enum canônico (sem `todo`; `archived` é ortogonal).
VALID_STATUS = transitions.STATUS_ENUM + ("archived",)
```

- [ ] **Step 2: Atualizar `create()` para popular defaults dos campos novos**

Substituir o bloco `task = { ... }` em `create()` (linhas ~56-69) por:

```python
        task = {
            "id": tid,
            "title": title.strip(),
            "description": description or "",
            "status": "backlog",
            "sprint_id": sprint_id,
            "project": project,
            "epic_id": epic_id,
            "wave_ref": wave_ref,
            "created_at": ts,
            "updated_at": ts,
            "created_by": actor,
            "archived_at": None,
            # Wave-3 fields:
            "blocked": False,
            "blocked_reason": None,
            "blocked_at": None,
            "rejected_reason": None,
            "dispatch_payload": None,
            "test_result": None,
        }
```

- [ ] **Step 3: Reescrever `move_status` com transitions + satellites + rejected_reason**

Substituir a função `move_status` inteira (linhas 123-145) por:

```python
def move_status(
    task_id: str,
    status: str,
    actor: str = "bernard",
    force: bool = False,
    reason: Optional[str] = None,
) -> Dict[str, Any]:
    """Move task status com whitelist soft. Emite satellites quando aplicável."""
    if status not in transitions.STATUS_ENUM:
        raise ValueError(
            f"invalid status: {status} (use archive/unarchive for archived; "
            f"valid: {transitions.STATUS_ENUM})"
        )
    with store.mutate_state() as state:
        t = find_task(state, task_id)
        if t is None:
            raise ValueError(f"task not found: {task_id}")
        if t["status"] == "archived":
            raise ValueError("task is archived; unarchive first")
        if t["status"] == status:
            return {"ok": True, "noop": True, "task": t}
        old = t["status"]
        # Mover task terminal sempre exige force ou reason
        if transitions.is_terminal(old):
            if not force and (not reason or not reason.strip()):
                raise ValueError(
                    f"TERMINAL_MOVE_REQUIRES_FORCE_OR_REASON: task is in terminal status "
                    f"'{old}'; use `task reopen` cmd or pass --force/--reason"
                )
        # Validação whitelist soft
        transitions.validate_or_raise(old, status, force=force, reason=reason, actor=actor)
        # blocked task indo para terminal: bloquear
        if status in transitions.TERMINAL and t.get("blocked"):
            raise ValueError(
                "MUST_UNBLOCK_BEFORE_TERMINAL: task is blocked; "
                "run `task unblock` before moving to terminal"
            )
        # rejected_reason populado quando movendo pra rejected (precisa reason)
        if status == "rejected":
            if not reason or not reason.strip():
                raise ValueError(
                    "REJECTED_REQUIRES_REASON: moving to 'rejected' requires --reason"
                )
            t["rejected_reason"] = reason.strip()
        # Aplica
        t["status"] = status
        t["updated_at"] = store.now_iso()
        ts = store.now_iso()
        # Evento principal
        seq = store.next_seq(state)
        ev_main: Dict[str, Any] = {
            "seq": seq, "ts": ts, "type": "task_moved",
            "actor": actor, "task_id": task_id, "from": old, "to": status,
        }
        # Forced/reason: incluir só quando truthy (mantém eventos enxutos)
        if force:
            ev_main["forced"] = True
        if reason and reason.strip():
            ev_main["reason"] = reason.strip()
        store.append_event(ev_main)
        state["last_event_seq"] = seq
        # Satellites
        if status == "testing":
            seq2 = store.next_seq(state)
            store.append_event({
                "seq": seq2, "ts": ts, "type": "task_entered_testing",
                "actor": actor, "task_id": task_id, "from": old,
            })
            state["last_event_seq"] = seq2
        elif status == "rejected":
            seq2 = store.next_seq(state)
            store.append_event({
                "seq": seq2, "ts": ts, "type": "task_rejected_with_reason",
                "actor": actor, "task_id": task_id, "from": old,
                "reason": reason.strip(),
            })
            state["last_event_seq"] = seq2
        return {"ok": True, "noop": False, "task": t}
```

- [ ] **Step 4: Adicionar `block()` / `unblock()` ao final do arquivo**

Adicionar antes de `# ============ Project management ============`:

```python
def block(task_id: str, reason: str, actor: str = "bernard") -> Dict[str, Any]:
    """Set blocked=True. Requer reason não-vazio. Rejeita em status terminal."""
    if not reason or not reason.strip():
        raise ValueError("reason is required for block")
    with store.mutate_state() as state:
        t = find_task(state, task_id)
        if t is None:
            raise ValueError(f"task not found: {task_id}")
        if t["status"] == "archived":
            raise ValueError("task is archived; unarchive first")
        if not transitions.is_blockable(t["status"]):
            raise ValueError(
                f"BLOCKED_NOT_ALLOWED_ON_TERMINAL: cannot block task in status '{t['status']}'"
            )
        if t.get("blocked"):
            return {"ok": True, "noop": True, "task": t}
        ts = store.now_iso()
        t["blocked"] = True
        t["blocked_reason"] = reason.strip()
        t["blocked_at"] = ts
        t["updated_at"] = ts
        seq = store.next_seq(state)
        store.append_event({
            "seq": seq, "ts": ts, "type": "task_blocked",
            "actor": actor, "task_id": task_id, "reason": reason.strip(),
        })
        state["last_event_seq"] = seq
        return {"ok": True, "noop": False, "task": t}


def unblock(task_id: str, actor: str = "bernard") -> Dict[str, Any]:
    """Set blocked=False. Idempotente em not-blocked."""
    with store.mutate_state() as state:
        t = find_task(state, task_id)
        if t is None:
            raise ValueError(f"task not found: {task_id}")
        if t["status"] == "archived":
            raise ValueError("task is archived; unarchive first")
        if not t.get("blocked"):
            return {"ok": True, "noop": True, "task": t}
        ts = store.now_iso()
        t["blocked"] = False
        t["blocked_reason"] = None
        t["blocked_at"] = None
        t["updated_at"] = ts
        seq = store.next_seq(state)
        store.append_event({
            "seq": seq, "ts": ts, "type": "task_unblocked",
            "actor": actor, "task_id": task_id,
        })
        state["last_event_seq"] = seq
        return {"ok": True, "noop": False, "task": t}


def reopen(
    task_id: str,
    to_status: str,
    reason: str,
    actor: str = "bernard",
) -> Dict[str, Any]:
    """Reabre task terminal. `to_status` deve ser não-terminal. `reason` obrigatório."""
    if to_status not in transitions.STATUS_ENUM:
        raise ValueError(f"invalid to status: {to_status}")
    if transitions.is_terminal(to_status):
        raise ValueError(f"cannot reopen to terminal status: {to_status}")
    if not reason or not reason.strip():
        raise ValueError("reason is required for reopen")
    with store.mutate_state() as state:
        t = find_task(state, task_id)
        if t is None:
            raise ValueError(f"task not found: {task_id}")
        if t["status"] == "archived":
            raise ValueError("task is archived; unarchive first")
        if not transitions.is_terminal(t["status"]):
            raise ValueError(
                f"TASK_NOT_TERMINAL: task is in '{t['status']}'; reopen only valid from terminal"
            )
        old = t["status"]
        ts = store.now_iso()
        t["status"] = to_status
        # Limpa rejected_reason se reabrindo de rejected
        if old == "rejected":
            t["rejected_reason"] = None
        t["updated_at"] = ts
        seq = store.next_seq(state)
        store.append_event({
            "seq": seq, "ts": ts, "type": "task_reopened",
            "actor": actor, "task_id": task_id, "from": old,
            "to": to_status, "reason": reason.strip(),
        })
        state["last_event_seq"] = seq
        return {"ok": True, "noop": False, "task": t}
```

- [ ] **Step 5: Adaptar `archive()` — auto-unblock antes**

Substituir `archive()` (linhas ~169-185) por:

```python
def archive(task_id: str, actor: str = "bernard") -> Dict[str, Any]:
    with store.mutate_state() as state:
        t = find_task(state, task_id)
        if t is None:
            raise ValueError(f"task not found: {task_id}")
        if t["status"] == "archived":
            return {"ok": True, "noop": True, "task": t}
        ts = store.now_iso()
        # Auto-unblock antes de archive (mantém invariant: archived nunca tem blocked=true)
        if t.get("blocked"):
            t["blocked"] = False
            t["blocked_reason"] = None
            t["blocked_at"] = None
            seq_unblock = store.next_seq(state)
            store.append_event({
                "seq": seq_unblock, "ts": ts, "type": "task_unblocked",
                "actor": actor, "task_id": task_id,
            })
            state["last_event_seq"] = seq_unblock
        t["status"] = "archived"
        t["archived_at"] = ts
        t["updated_at"] = ts
        seq = store.next_seq(state)
        store.append_event({
            "seq": seq, "ts": ts, "type": "task_archived",
            "actor": actor, "task_id": task_id,
        })
        state["last_event_seq"] = seq
        return {"ok": True, "task": t}
```

- [ ] **Step 6: Adaptar `unarchive()` — aceitar enum novo**

Substituir linha 189 dentro de `unarchive`:

```python
    if status not in transitions.STATUS_ENUM:
        raise ValueError(
            f"invalid restore status: {status} (valid: {transitions.STATUS_ENUM})"
        )
```

- [ ] **Step 7: Adaptar `list_tasks()` — adicionar filtro `blocked`**

Substituir assinatura e corpo de `list_tasks`:

```python
def list_tasks(
    sprint: Optional[str] = None,
    status: Optional[str] = None,
    project: Optional[str] = None,
    epic_id: Optional[str] = None,
    archived: bool = False,
    blocked: Optional[bool] = None,
) -> List[Dict[str, Any]]:
    state = store.read_state()
    out: List[Dict[str, Any]] = []
    sprint_id_filter: Optional[str] = None
    if sprint is not None:
        sp = sprint_lib.find_sprint(state, sprint)
        if sp is None:
            raise ValueError(f"sprint not found: {sprint}")
        sprint_id_filter = sp["id"]
    for t in state["tasks"]:
        is_archived = t["status"] == "archived"
        if status is not None:
            if t["status"] != status:
                continue
        else:
            if archived and not is_archived:
                continue
            if not archived and is_archived:
                continue
        if sprint_id_filter and t["sprint_id"] != sprint_id_filter:
            continue
        if project and t.get("project") != project:
            continue
        if epic_id and t.get("epic_id") != epic_id:
            continue
        if blocked is not None and bool(t.get("blocked", False)) != blocked:
            continue
        out.append(t)
    return out
```

- [ ] **Step 8: Sanity check**

```bash
PYTHONPATH=~/.openclaw/kanban-tasks python3 -c "
from lib import task as task_lib
assert 'ready' in task_lib.VALID_STATUS
assert 'todo' not in task_lib.VALID_STATUS
assert hasattr(task_lib, 'block')
assert hasattr(task_lib, 'unblock')
assert hasattr(task_lib, 'reopen')
print('OK')
"
```

Expected: `OK`.

---

## Phase 3: lib/api.py — CLI surface + projeção alias

### Task 3.1: Adaptar argparse `task move`, adicionar `block/unblock/reopen`

**Files:**
- Modify: `~/.openclaw/kanban-tasks/lib/api.py`

- [ ] **Step 1: Atualizar `mv` (task move) na função `build_parser` (linha ~507-510)**

Substituir o bloco `mv = leaf(...)` por:

```python
    mv = leaf(tk_sub, "move")
    mv.add_argument("task_id")
    mv.add_argument(
        "status",
        choices=["backlog", "ready", "in_progress", "testing", "done", "rejected"],
    )
    mv.add_argument("--force", action="store_true",
                    help="bypass whitelist (humano só); emite forced=true no evento")
    mv.add_argument("--reason", default=None,
                    help="motivo da transição (obrigatório para agentes fora da whitelist e para rejected)")
    mv.set_defaults(func=cmd_task_move)
```

- [ ] **Step 2: Atualizar `cmd_task_move` para passar force/reason**

Localizar `cmd_task_move` (perto da linha ~218) e substituir por:

```python
def cmd_task_move(args: argparse.Namespace) -> int:
    res = task_lib.move_status(
        args.task_id, args.status, actor=args.actor,
        force=getattr(args, "force", False),
        reason=getattr(args, "reason", None),
    )
    _print(res, args.json, f"moved: {res['task']['id']} -> {res['task']['status']}")
    return EXIT_OK
```

- [ ] **Step 3: Atualizar `un` (task unarchive) para refletir enum novo**

No bloco `un = leaf(tk_sub, "unarchive")` (linha ~518-521), `--status` continua aceitando string, mas agora valida via lib. Sem mudança no parser; default permanece `backlog`. Apenas garantir consistência:

```python
    un = leaf(tk_sub, "unarchive")
    un.add_argument("task_id")
    un.add_argument(
        "--status",
        default="backlog",
        choices=["backlog", "ready", "in_progress", "testing", "done", "rejected"],
        help="status para restaurar (default: backlog)",
    )
    un.set_defaults(func=cmd_task_unarchive)
```

- [ ] **Step 4: Adicionar `task block` subcommand**

Após o bloco `un.set_defaults(...)`, antes do `ls = leaf(...)` (filtro list):

```python
    bl = leaf(tk_sub, "block")
    bl.add_argument("task_id")
    bl.add_argument("--reason", required=True, help="motivo do bloqueio")
    bl.set_defaults(func=cmd_task_block)

    ub = leaf(tk_sub, "unblock")
    ub.add_argument("task_id")
    ub.set_defaults(func=cmd_task_unblock)

    rp = leaf(tk_sub, "reopen")
    rp.add_argument("task_id")
    rp.add_argument(
        "--to",
        required=True,
        choices=["backlog", "ready", "in_progress", "testing"],
        help="destino (deve ser não-terminal)",
    )
    rp.add_argument("--reason", required=True, help="motivo da reabertura")
    rp.set_defaults(func=cmd_task_reopen)
```

- [ ] **Step 5: Atualizar `ls` (task list) com filtro `--blocked`**

No bloco `ls = leaf(tk_sub, "list")` (linha ~522-528), adicionar:

```python
    ls.add_argument("--sprint")
    ls.add_argument("--status")
    ls.add_argument("--project")
    ls.add_argument("--epic")
    ls.add_argument("--archived", action="store_true")
    ls.add_argument("--blocked", dest="blocked_only", action="store_true",
                    help="só tasks com blocked=true")
    ls.set_defaults(func=cmd_task_list)
```

- [ ] **Step 6: Adicionar `cmd_task_block`, `cmd_task_unblock`, `cmd_task_reopen` handlers**

Localizar onde `cmd_task_unarchive` está definido. Adicionar em seguida:

```python
def cmd_task_block(args: argparse.Namespace) -> int:
    res = task_lib.block(args.task_id, args.reason, actor=args.actor)
    _print(res, args.json, f"blocked: {res['task']['id']} ({args.reason})")
    return EXIT_OK


def cmd_task_unblock(args: argparse.Namespace) -> int:
    res = task_lib.unblock(args.task_id, actor=args.actor)
    _print(res, args.json, f"unblocked: {res['task']['id']}")
    return EXIT_OK


def cmd_task_reopen(args: argparse.Namespace) -> int:
    res = task_lib.reopen(args.task_id, args.to, args.reason, actor=args.actor)
    _print(res, args.json, f"reopened: {res['task']['id']} -> {res['task']['status']} ({args.reason})")
    return EXIT_OK
```

- [ ] **Step 7: Atualizar `cmd_task_list` para passar `blocked` filter**

Localizar `cmd_task_list` (perto da linha ~245-250). Substituir a chamada `task_lib.list_tasks(...)` por:

```python
def cmd_task_list(args: argparse.Namespace) -> int:
    blocked_filter = True if getattr(args, "blocked_only", False) else None
    rows = task_lib.list_tasks(
        sprint=args.sprint, status=args.status, project=args.project,
        epic_id=args.epic, archived=args.archived, blocked=blocked_filter,
    )
    if args.json:
        _print(rows, True)
    else:
        for t in rows:
            print(_format_task_row(t))
    return EXIT_OK
```

- [ ] **Step 8: Atualizar `_format_task_row` (perto de linha ~50)**

Localizar `_format_task_row` (próximo do `_format_sprint`) e substituir por:

```python
def _format_task_row(t: Dict[str, Any]) -> str:
    badges = []
    if t.get("blocked"):
        reason = (t.get("blocked_reason") or "")[:30]
        badges.append(f"[blocked: {reason}]")
    if t.get("status") == "rejected" and t.get("rejected_reason"):
        badges.append(f"[reason: {t['rejected_reason'][:30]}]")
    if t.get("project"):
        badges.append(f"{{project={t['project']}}}")
    if t.get("epic_id"):
        badges.append(f"{{epic={t['epic_id']}}}")
    badge_str = " ".join(badges)
    title = t["title"][:50]
    return f"{t['id']:7s} {t['status']:12s} {title}  {badge_str}"
```

(Substitui o `_format_task_row` atual da linha ~48-52. Confirmar se a função existe nesse formato — se já houver lógica diferente, preservar e só adicionar os 2 badges novos.)

### Task 3.2: Alias `todo→ready` na projeção + defaults na rebuild

**Files:**
- Modify: `~/.openclaw/kanban-tasks/lib/api.py`

- [ ] **Step 1: Adicionar alias permanente no topo de apply_event**

Localizar `apply_event` (perto da linha ~330). No início da função (após a linha que extrai `t = ev["type"]`), adicionar (uma única vez, no topo do arquivo ou início da função):

```python
# Wave-3: alias permanente. Eventos legados com to:"todo" mapeiam para ready
# na projeção. NUNCA reescrever events.jsonl.
TODO_LEGACY_ALIAS = {"todo": "ready"}


def _alias_status(value: Optional[str]) -> Optional[str]:
    if value is None:
        return None
    return TODO_LEGACY_ALIAS.get(value, value)
```

(Posicionar antes da função `apply_event` ou no topo do bloco "projeção". Se não houver bloco claro, colar logo antes de `def apply_event`.)

- [ ] **Step 2: Substituir as escritas de status no apply_event**

Localizar `elif t == "task_moved":` (linha ~370-374) e substituir por:

```python
    elif t == "task_moved":
        for tk in state["tasks"]:
            if tk["id"] == ev["task_id"]:
                tk["status"] = _alias_status(ev["to"])
                tk["updated_at"] = ts
                # Wave-3: popula rejected_reason se evento carrega reason
                if ev.get("to") == "rejected" and ev.get("reason"):
                    tk["rejected_reason"] = ev["reason"]
```

Localizar `elif t == "task_unarchived":` e substituir por:

```python
    elif t == "task_unarchived":
        for tk in state["tasks"]:
            if tk["id"] == ev["task_id"]:
                tk["status"] = _alias_status(ev.get("restored_to", "backlog"))
                tk["archived_at"] = None
                tk["updated_at"] = ts
```

Localizar `elif t == "task_created":` (linha ~355-363) e adicionar os campos novos com defaults:

```python
    elif t == "task_created":
        state["tasks"].append({
            "id": ev["task_id"], "title": ev["title"], "description": "",
            "status": "backlog", "sprint_id": ev["sprint_id"],
            "project": ev.get("project"), "epic_id": ev.get("epic_id"),
            "wave_ref": ev.get("wave_ref"),
            "created_at": ts, "updated_at": ts, "created_by": actor,
            "archived_at": None,
            # Wave-3 defaults:
            "blocked": False, "blocked_reason": None, "blocked_at": None,
            "rejected_reason": None,
            "dispatch_payload": None, "test_result": None,
        })
```

- [ ] **Step 3: Adicionar handlers para os novos event types**

No final do `apply_event` (antes do `elif t == "project_added":`), adicionar:

```python
    elif t == "task_blocked":
        for tk in state["tasks"]:
            if tk["id"] == ev["task_id"]:
                tk["blocked"] = True
                tk["blocked_reason"] = ev.get("reason")
                tk["blocked_at"] = ts
                tk["updated_at"] = ts
    elif t == "task_unblocked":
        for tk in state["tasks"]:
            if tk["id"] == ev["task_id"]:
                tk["blocked"] = False
                tk["blocked_reason"] = None
                tk["blocked_at"] = None
                tk["updated_at"] = ts
    elif t == "task_reopened":
        for tk in state["tasks"]:
            if tk["id"] == ev["task_id"]:
                tk["status"] = _alias_status(ev["to"])
                if ev.get("from") == "rejected":
                    tk["rejected_reason"] = None
                tk["updated_at"] = ts
    elif t in ("task_entered_testing", "task_rejected_with_reason"):
        # Satellites: sem efeito de projeção (informativos pra agentes/audit).
        # task_moved já mexeu no status. Aqui só passa.
        pass
```

- [ ] **Step 4: Backfill de defaults no rebuild para tasks pré-bump**

Localizar `cmd_rebuild` (perto da linha ~395). Após a linha que faz iter_events e antes do write atomic, adicionar normalização:

```python
    # Wave-3: backfill defaults pra tasks pré-schema_version=2
    for tk in state["tasks"]:
        tk.setdefault("blocked", False)
        tk.setdefault("blocked_reason", None)
        tk.setdefault("blocked_at", None)
        tk.setdefault("rejected_reason", None)
        tk.setdefault("dispatch_payload", None)
        tk.setdefault("test_result", None)
    state["schema_version"] = 2
```

(Confirmar onde `cmd_rebuild` faz a montagem do state final. Se a estrutura difere, posicionar o backfill logo antes da escrita atomic.)

- [ ] **Step 5: Atualizar `_format_task_row` se ainda não foi (cobertura backup)**

Garantir que `_format_task_row` usa `t.get("blocked")` em vez de `t["blocked"]` (defensivo pra states pré-rebuild).

- [ ] **Step 6: Sanity test alias**

```bash
cd ~/.openclaw/kanban-tasks
PYTHONPATH=. python3 -c "
from lib.api import _alias_status
assert _alias_status('todo') == 'ready'
assert _alias_status('in_progress') == 'in_progress'
assert _alias_status(None) is None
print('alias OK')
"
```

Expected: `alias OK`.

### Task 3.3: Testar CLI manualmente (smoke quick)

**Files:** none (manual run)

- [ ] **Step 1: Reset state e bootstrap**

```bash
cd ~/.openclaw/kanban-tasks
mv state.json state.json.bak.$(date +%s)
mv events.jsonl events.jsonl.bak.$(date +%s)
./cli.sh sprint init
./cli.sh sprint show
```

Expected: 2 sprints (current + next) listados, schema_version=2 (verificar com `cat state.json | head -3`).

- [ ] **Step 2: Criar task e mover ready**

```bash
./cli.sh task add "wave-3 smoke task" --project openclaw --sprint current
./cli.sh task move T-0001 ready
./cli.sh task list
```

Expected: T-0001 em status `ready`.

- [ ] **Step 3: Block + unblock**

```bash
./cli.sh task block T-0001 --reason "esperando decisao"
./cli.sh task list --blocked
./cli.sh task unblock T-0001
./cli.sh task list --blocked
```

Expected: list `--blocked` mostra T-0001 antes do unblock; vazio depois.

- [ ] **Step 4: Move pra testing — satellite event**

```bash
./cli.sh task move T-0001 in_progress
./cli.sh task move T-0001 testing
./cli.sh events tail --n 5 --task T-0001
```

Expected: 2 eventos consecutivos em `testing` move: `task_moved` + `task_entered_testing`.

- [ ] **Step 5: Move pra rejected — exige reason; satellite event**

```bash
# Sem reason -> erro
./cli.sh task move T-0001 rejected || echo "OK rejected sem reason falha"
# Com reason -> OK
./cli.sh task move T-0001 rejected --reason "scope cut"
./cli.sh events tail --n 5 --task T-0001
./cli.sh task list --status rejected
```

Expected: primeira tentativa falha com `REJECTED_REQUIRES_REASON`. Segunda OK; eventos `task_moved` + `task_rejected_with_reason`. List mostra `[reason: scope cut]`.

- [ ] **Step 6: Reopen**

```bash
./cli.sh task reopen T-0001 --to in_progress --reason "regression flagged"
./cli.sh task list
./cli.sh events tail --n 3 --task T-0001
```

Expected: T-0001 volta pra `in_progress`; evento `task_reopened` presente.

- [ ] **Step 7: Force humano**

```bash
# done direto (não-whitelist)
./cli.sh task move T-0001 done || echo "OK falha sem force"
./cli.sh task move T-0001 done --force --reason "skip testing pra demo"
./cli.sh events tail --n 3 --task T-0001
```

Expected: primeira falha; segunda OK com `forced=true` no evento.

- [ ] **Step 8: Reset pro próximo phase**

```bash
rm state.json events.jsonl
./cli.sh sprint init
```

(Backups gerados em Phase 0 + os .bak desta phase ficam disponíveis se precisar recuperar.)

---

## Phase 4: Smoke E2E backend (estende script)

### Task 4.1: Estender `smoke_e2e.sh` com cenários wave-3

**Files:**
- Modify: `~/.openclaw/kanban-tasks/smoke_e2e.sh`

- [ ] **Step 1: Adicionar bloco wave-3 ao final do smoke_e2e.sh**

Localizar a última linha do smoke (provavelmente após `events tail` ou status check) e anexar:

```bash
echo ""
echo "==> WAVE-3 smoke: dev lifecycle"

echo "==> create T-W3 in current"
W3_ID=$($KT task add "wave-3 smoke E2E" --project openclaw --sprint current --json | python3 -c "import json,sys; print(json.load(sys.stdin)['task']['id'])")
echo "task id: $W3_ID"

echo "==> move backlog -> ready"
$KT task move $W3_ID ready

echo "==> block + list --blocked"
$KT task block $W3_ID --reason "esperando aprovacao"
$KT task list --blocked
COUNT=$($KT task list --blocked --json | python3 -c "import json,sys; print(len(json.load(sys.stdin)))")
test "$COUNT" -ge 1 || { echo "FAIL: list --blocked vazio"; exit 1; }

echo "==> unblock"
$KT task unblock $W3_ID
COUNT=$($KT task list --blocked --json | python3 -c "import json,sys; print(len(json.load(sys.stdin)))")
test "$COUNT" -eq 0 || { echo "FAIL: list --blocked nao vazio apos unblock"; exit 1; }

echo "==> ready -> in_progress -> testing (satellite)"
$KT task move $W3_ID in_progress
$KT task move $W3_ID testing
$KT events tail --n 5 --task $W3_ID --json | python3 -c "
import json, sys
events = json.load(sys.stdin)
types = [e['type'] for e in events]
assert 'task_entered_testing' in types, f'satellite missing: {types}'
print('satellite OK')
"

echo "==> testing -> rejected sem reason (deve falhar)"
$KT task move $W3_ID rejected 2>/dev/null && { echo "FAIL: rejected sem reason aceito"; exit 1; } || echo "OK rejected sem reason barrado"

echo "==> testing -> rejected com reason"
$KT task move $W3_ID rejected --reason "scope cut"
$KT events tail --n 5 --task $W3_ID --json | python3 -c "
import json, sys
events = json.load(sys.stdin)
types = [e['type'] for e in events]
assert 'task_rejected_with_reason' in types, f'satellite missing: {types}'
print('rejected satellite OK')
"
$KT task list --status rejected | grep -q "$W3_ID" || { echo "FAIL: rejected list missing"; exit 1; }

echo "==> reopen rejected -> in_progress"
$KT task reopen $W3_ID --to in_progress --reason "regression flagged"
$KT events tail --n 3 --task $W3_ID --json | python3 -c "
import json, sys
events = json.load(sys.stdin)
types = [e['type'] for e in events]
assert 'task_reopened' in types, f'reopen missing: {types}'
print('reopen OK')
"

echo "==> force move (in_progress -> done sem testing)"
$KT task move $W3_ID done 2>/dev/null && { echo "FAIL: nao-whitelist aceito sem force"; exit 1; } || echo "OK barrado"
$KT task move $W3_ID done --force --reason "demo skip testing"
LAST_EV=$($KT events tail --n 1 --task $W3_ID --json | python3 -c "import json,sys; print(json.load(sys.stdin)[0])")
echo "last ev: $LAST_EV"
echo "$LAST_EV" | python3 -c "
import json, sys, ast
ev = ast.literal_eval(sys.stdin.read().strip())
assert ev.get('forced') is True, f'forced flag missing: {ev}'
print('forced flag OK')
"

echo "==> blocked task barrada de ir pra terminal"
$KT task move $W3_ID in_progress --force --reason "reopen via force"
$KT task block $W3_ID --reason "esperando algo"
$KT task move $W3_ID done --reason "tentando forcar com reason" 2>/dev/null && { echo "FAIL: blocked aceito em terminal"; exit 1; } || echo "OK blocked barrou terminal"
$KT task unblock $W3_ID

echo "==> archive auto-unblock"
$KT task block $W3_ID --reason "test archive auto-unblock"
$KT task archive $W3_ID
$KT events tail --n 3 --task $W3_ID --json | python3 -c "
import json, sys
events = json.load(sys.stdin)
types = [e['type'] for e in events]
assert 'task_unblocked' in types, f'auto-unblock missing: {types}'
assert 'task_archived' in types
print('auto-unblock OK')
"

echo "==> rebuild idempotente (alias todo->ready cobre eventos legados se houver)"
$KT rebuild
$KT status

echo ""
echo "==> WAVE-3 smoke PASSED"
```

- [ ] **Step 2: Rodar smoke completo**

```bash
cd ~/.openclaw/kanban-tasks
bash smoke_e2e.sh
```

Expected: termina com `WAVE-3 smoke PASSED` (sem erros).

- [ ] **Step 3: Restore state pre-smoke**

```bash
# Smoke E2E faz reset no início. Após rodar, state está populado com tasks de teste.
# Para preservar histórico real do Bernard:
ls ~/.openclaw/backups/kanban-tasks/state.json.pre-wave3.* | tail -1 | xargs -I{} cp {} ~/.openclaw/kanban-tasks/state.json
ls ~/.openclaw/backups/kanban-tasks/events.jsonl.pre-wave3.* | tail -1 | xargs -I{} cp {} ~/.openclaw/kanban-tasks/events.jsonl
~/.openclaw/kanban-tasks/cli.sh rebuild
~/.openclaw/kanban-tasks/cli.sh status
```

Expected: state restaurado; rebuild faz alias `todo→ready` se houver tasks legadas; status OK. Verificar que tasks com status `todo` no backup viraram `ready` agora.

### Task 4.2: Update README do módulo

**Files:**
- Modify: `~/.openclaw/kanban-tasks/README.md`

- [ ] **Step 1: Atualizar seção de status enum no README**

Localizar a seção que descreve os 4 status legados e substituir por:

```markdown
## Status canônico (wave-3)

`backlog | ready | in_progress | testing | done | rejected`

+ `archived` (ortogonal — task fora do board, preservada).
+ `blocked` (flag ortogonal — task pausada por dep externa).

### Whitelist soft de transições

```
backlog     -> ready, in_progress, rejected
ready       -> backlog, in_progress, rejected
in_progress -> ready, testing, rejected
testing     -> in_progress, done, rejected
done        -> ∅ (terminal — `task reopen` cmd)
rejected    -> ∅ (terminal — `task reopen` cmd)
```

Fora da whitelist:
- Humano (`--actor bernard`): exige `--force`. Evento ganha `forced=true`.
- Agente (`--actor X`): exige `--reason "..."`. Sem reason, erro.

### Alias legado `todo` → `ready`

Eventos antigos com `to:"todo"` ficam **intactos** em `events.jsonl` (SoT
imutável). A projeção `apply_event` mapeia `todo → ready` no rebuild.
Tasks com `status:"todo"` no `state.json` antigo viram `ready` no próximo
rebuild — sem migration script.

## Cmds wave-3

```bash
# Block / unblock
cli.sh task block T-0042 --reason "esperando spec"
cli.sh task unblock T-0042
cli.sh task list --blocked

# Reopen task terminal
cli.sh task reopen T-0042 --to in_progress --reason "regression flagged"

# Move forçado (humano só, audit explícito)
cli.sh task move T-0042 done --force --reason "skip testing"

# Move com reason (agente)
cli.sh task move T-0042 done --actor vox --reason "passed by tester-agent"
```
```

- [ ] **Step 2: Sanity grep**

```bash
grep -E "(ready|testing|rejected|blocked)" ~/.openclaw/kanban-tasks/README.md | head -10
```

Expected: linhas com novos status presentes.

---

## Phase 5: HTTP API (TS/Next) — espelho TS + 4 rotas + adapt move

### Task 5.1: Criar `lib/kanban/statusEnum.ts`

**Files:**
- Create: `~/code/mission-control/src/lib/kanban/statusEnum.ts`

- [ ] **Step 1: Escrever statusEnum.ts**

```typescript
/**
 * Wave-3: status canônico do kanban-tasks (espelho TS).
 * Whitelist + helpers vivem em `transitions.ts`.
 */

export const STATUS_ENUM = [
  "backlog",
  "ready",
  "in_progress",
  "testing",
  "done",
  "rejected",
] as const;

export type TaskStatus = (typeof STATUS_ENUM)[number] | "archived";

export const STATUS_SET = new Set<string>(STATUS_ENUM);

export const TERMINAL = new Set<TaskStatus>(["done", "rejected"]);

export const BLOCKABLE = new Set<TaskStatus>([
  "backlog",
  "ready",
  "in_progress",
  "testing",
]);

export function isTerminal(s: TaskStatus): boolean {
  return TERMINAL.has(s);
}

export function isBlockable(s: TaskStatus): boolean {
  return BLOCKABLE.has(s);
}
```

- [ ] **Step 2: Sanity tsc**

```bash
cd ~/code/mission-control
npx tsc --noEmit src/lib/kanban/statusEnum.ts 2>&1 | head -20
```

Expected: zero erros (ou só erros pré-existentes não-relacionados).

### Task 5.2: Criar `lib/kanban/transitions.ts` (espelho TS)

**Files:**
- Create: `~/code/mission-control/src/lib/kanban/transitions.ts`
- Create: `~/code/mission-control/src/components/kanban/transitions.test.ts`

- [ ] **Step 1: Escrever transitions.ts**

```typescript
/**
 * Wave-3: espelho TS da whitelist soft definida em
 * `~/.openclaw/kanban-tasks/lib/transitions.py`. Mantida sincronizada
 * manualmente (drift coberto por smoke E2E).
 *
 * Uso: D&D guard na UI MC. Erros HTTP finais vêm da CLI Python.
 */

import { STATUS_ENUM, TERMINAL, type TaskStatus } from "./statusEnum";

type CanonicalStatus = Exclude<TaskStatus, "archived">;

export const WHITELIST: Record<CanonicalStatus, readonly CanonicalStatus[]> = {
  backlog:     ["ready", "in_progress", "rejected"],
  ready:       ["backlog", "in_progress", "rejected"],
  in_progress: ["ready", "testing", "rejected"],
  testing:     ["in_progress", "done", "rejected"],
  done:        [],
  rejected:    [],
};

export function isValidTransition(
  from: TaskStatus,
  to: TaskStatus,
): boolean {
  if (from === "archived" || to === "archived") return false;
  const dests = WHITELIST[from as CanonicalStatus];
  if (!dests) return false;
  return dests.includes(to as CanonicalStatus);
}

/**
 * Helper para a UI: pode arrastar/dropar essa transição sem precisar de force?
 * (UI conservadora: false = mostra toast e não faz POST.)
 */
export function canDragMove(from: TaskStatus, to: TaskStatus): boolean {
  if (from === to) return false;
  if (TERMINAL.has(from)) return false;  // terminal exige reopen, não D&D
  return isValidTransition(from, to);
}

export { STATUS_ENUM };
```

- [ ] **Step 2: Escrever test Vitest**

```typescript
// src/components/kanban/transitions.test.ts
import { describe, expect, it } from "vitest";
import {
  isValidTransition,
  canDragMove,
  WHITELIST,
} from "@/lib/kanban/transitions";

describe("transitions whitelist", () => {
  it("backlog can go to ready/in_progress/rejected", () => {
    expect(isValidTransition("backlog", "ready")).toBe(true);
    expect(isValidTransition("backlog", "in_progress")).toBe(true);
    expect(isValidTransition("backlog", "rejected")).toBe(true);
    expect(isValidTransition("backlog", "testing")).toBe(false);
    expect(isValidTransition("backlog", "done")).toBe(false);
  });

  it("testing can fork to done/in_progress/rejected", () => {
    expect(isValidTransition("testing", "done")).toBe(true);
    expect(isValidTransition("testing", "in_progress")).toBe(true);
    expect(isValidTransition("testing", "rejected")).toBe(true);
    expect(isValidTransition("testing", "ready")).toBe(false);
  });

  it("done and rejected are terminal — no destinations", () => {
    expect(WHITELIST.done).toEqual([]);
    expect(WHITELIST.rejected).toEqual([]);
    expect(canDragMove("done", "in_progress")).toBe(false);
    expect(canDragMove("rejected", "ready")).toBe(false);
  });

  it("canDragMove rejects same-status no-op", () => {
    expect(canDragMove("ready", "ready")).toBe(false);
  });

  it("canDragMove rejects archived involvement", () => {
    expect(canDragMove("archived", "ready")).toBe(false);
    expect(canDragMove("ready", "archived")).toBe(false);
  });
});
```

- [ ] **Step 3: Run tests**

```bash
cd ~/code/mission-control
npx vitest run src/components/kanban/transitions.test.ts
```

Expected: 5 passed, 0 failed.

### Task 5.3: Atualizar `stateReader.ts` Task type

**Files:**
- Modify: `~/code/mission-control/src/lib/kanban/stateReader.ts`

- [ ] **Step 1: Atualizar TaskStatus + Task interface**

Localizar o tipo `TaskStatus` (provavelmente um union literal). Substituir por importação do statusEnum.ts:

```typescript
// No topo do arquivo, junto dos outros imports:
import type { TaskStatus } from "./statusEnum";
export type { TaskStatus };
```

E remover a definição local de `TaskStatus` (se houver).

Atualizar o tipo `Task` para incluir os campos novos:

```typescript
export interface Task {
  id: string;
  title: string;
  description: string;
  status: TaskStatus;
  sprint_id: string;
  project: string | null;
  epic_id: string | null;
  wave_ref: string | null;
  created_at: string;
  updated_at: string;
  created_by: string;
  archived_at: string | null;
  // Wave-3 fields (sempre presentes pós-rebuild):
  blocked: boolean;
  blocked_reason: string | null;
  blocked_at: string | null;
  rejected_reason: string | null;
  dispatch_payload: unknown | null;
  test_result: unknown | null;
}
```

- [ ] **Step 2: Sanity tsc**

```bash
cd ~/code/mission-control
npx tsc --noEmit 2>&1 | grep -E "(stateReader|kanban)" | head -20
```

Expected: zero novos erros relacionados ao kanban (erros pré-existentes em outros módulos OK).

### Task 5.4: Adaptar `move/route.ts` (force/reason + enum novo)

**Files:**
- Modify: `~/code/mission-control/src/app/api/kanban/tasks/[id]/move/route.ts`

- [ ] **Step 1: Reescrever route.ts**

```typescript
import { NextResponse, NextRequest } from "next/server";
import { runCli, respondCli } from "@/lib/kanban/cli";
import { resolveActor } from "@/lib/kanban/auth";
import { STATUS_SET } from "@/lib/kanban/statusEnum";

export const dynamic = "force-dynamic";

/**
 * POST /api/kanban/tasks/[id]/move
 * body: {
 *   status: "backlog" | "ready" | "in_progress" | "testing" | "done" | "rejected",
 *   force?: boolean,
 *   reason?: string
 * }
 * Uso archive/unarchive para virar ou sair de 'archived'.
 * Use POST .../reopen para reabrir done/rejected.
 */
export async function POST(
  req: NextRequest,
  { params }: { params: Promise<{ id: string }> },
) {
  const { id } = await params;
  let body: unknown;
  try {
    body = await req.json();
  } catch {
    return NextResponse.json(
      { error: "invalid_input", detail: "expected JSON body" },
      { status: 400 },
    );
  }
  const bb = (body ?? {}) as Record<string, unknown>;
  if (typeof bb.status !== "string" || !STATUS_SET.has(bb.status)) {
    return NextResponse.json(
      {
        error: "invalid_input",
        detail: `status must be one of: ${[...STATUS_SET].join(", ")}`,
      },
      { status: 400 },
    );
  }
  const args = ["task", "move", id, bb.status];
  if (bb.force === true) args.push("--force");
  if (typeof bb.reason === "string" && bb.reason.trim()) {
    args.push("--reason", bb.reason);
  }
  return respondCli(runCli(args, resolveActor(req)));
}
```

- [ ] **Step 2: Sanity tsc**

```bash
cd ~/code/mission-control
npx tsc --noEmit src/app/api/kanban/tasks/\[id\]/move/route.ts 2>&1 | head
```

Expected: zero erros.

### Task 5.5: Criar `block/route.ts`

**Files:**
- Create: `~/code/mission-control/src/app/api/kanban/tasks/[id]/block/route.ts`

- [ ] **Step 1: Escrever block route**

```typescript
import { NextResponse, NextRequest } from "next/server";
import { runCli, respondCli } from "@/lib/kanban/cli";
import { resolveActor } from "@/lib/kanban/auth";

export const dynamic = "force-dynamic";

/**
 * POST /api/kanban/tasks/[id]/block
 * body: { reason: string }
 */
export async function POST(
  req: NextRequest,
  { params }: { params: Promise<{ id: string }> },
) {
  const { id } = await params;
  let body: unknown;
  try {
    body = await req.json();
  } catch {
    return NextResponse.json(
      { error: "invalid_input", detail: "expected JSON body" },
      { status: 400 },
    );
  }
  const bb = (body ?? {}) as Record<string, unknown>;
  if (typeof bb.reason !== "string" || !bb.reason.trim()) {
    return NextResponse.json(
      { error: "invalid_input", detail: "reason is required (non-empty string)" },
      { status: 400 },
    );
  }
  return respondCli(
    runCli(["task", "block", id, "--reason", bb.reason], resolveActor(req)),
  );
}
```

### Task 5.6: Criar `unblock/route.ts`

**Files:**
- Create: `~/code/mission-control/src/app/api/kanban/tasks/[id]/unblock/route.ts`

- [ ] **Step 1: Escrever unblock route**

```typescript
import { NextRequest } from "next/server";
import { runCli, respondCli } from "@/lib/kanban/cli";
import { resolveActor } from "@/lib/kanban/auth";

export const dynamic = "force-dynamic";

/**
 * POST /api/kanban/tasks/[id]/unblock
 * body: {} (vazio)
 */
export async function POST(
  req: NextRequest,
  { params }: { params: Promise<{ id: string }> },
) {
  const { id } = await params;
  return respondCli(runCli(["task", "unblock", id], resolveActor(req)));
}
```

### Task 5.7: Criar `reopen/route.ts`

**Files:**
- Create: `~/code/mission-control/src/app/api/kanban/tasks/[id]/reopen/route.ts`

- [ ] **Step 1: Escrever reopen route**

```typescript
import { NextResponse, NextRequest } from "next/server";
import { runCli, respondCli } from "@/lib/kanban/cli";
import { resolveActor } from "@/lib/kanban/auth";

export const dynamic = "force-dynamic";

const REOPEN_TARGETS = new Set(["backlog", "ready", "in_progress", "testing"]);

/**
 * POST /api/kanban/tasks/[id]/reopen
 * body: { to: "backlog"|"ready"|"in_progress"|"testing", reason: string }
 */
export async function POST(
  req: NextRequest,
  { params }: { params: Promise<{ id: string }> },
) {
  const { id } = await params;
  let body: unknown;
  try {
    body = await req.json();
  } catch {
    return NextResponse.json(
      { error: "invalid_input", detail: "expected JSON body" },
      { status: 400 },
    );
  }
  const bb = (body ?? {}) as Record<string, unknown>;
  if (typeof bb.to !== "string" || !REOPEN_TARGETS.has(bb.to)) {
    return NextResponse.json(
      {
        error: "invalid_input",
        detail: `to must be one of: ${[...REOPEN_TARGETS].join(", ")}`,
      },
      { status: 400 },
    );
  }
  if (typeof bb.reason !== "string" || !bb.reason.trim()) {
    return NextResponse.json(
      { error: "invalid_input", detail: "reason is required" },
      { status: 400 },
    );
  }
  return respondCli(
    runCli(
      ["task", "reopen", id, "--to", bb.to, "--reason", bb.reason],
      resolveActor(req),
    ),
  );
}
```

### Task 5.8: Criar `tasks/next-ready/route.ts`

**Files:**
- Create: `~/code/mission-control/src/app/api/kanban/tasks/next-ready/route.ts`

- [ ] **Step 1: Escrever next-ready route**

```typescript
import { NextRequest, NextResponse } from "next/server";
import { readState, type Task } from "@/lib/kanban/stateReader";

export const dynamic = "force-dynamic";

/**
 * GET /api/kanban/tasks/next-ready?project=<name>
 * Read-only. Retorna primeira task `ready` & não-blocked do projeto,
 * ordenada por `created_at` ascendente. Sem ?project, retorna primeira
 * de qualquer projeto.
 *
 * Hook pra delivery-dispatcher-agent (não consome / não reserva).
 */
export async function GET(req: NextRequest) {
  const url = new URL(req.url);
  const project = url.searchParams.get("project");
  const state = readState();
  const candidates: Task[] = state.tasks.filter((t: Task) => {
    if (t.status !== "ready") return false;
    if (t.blocked) return false;
    if (project && t.project !== project) return false;
    return true;
  });
  candidates.sort((a, b) => a.created_at.localeCompare(b.created_at));
  return NextResponse.json({ task: candidates[0] ?? null });
}
```

### Task 5.9: Smoke HTTP rotas wave-3 (manual via curl)

**Files:** none (manual)

- [ ] **Step 1: Subir dev server (se não estiver rodando)**

```bash
cd ~/code/mission-control
ls .next/standalone 2>/dev/null && echo "WARN: prod build artifacts present"
# Iniciar dev server (background):
npm run dev > /tmp/mc-dev.log 2>&1 &
echo "MC dev pid: $!"
sleep 3
curl -s http://127.0.0.1:4310/api/kanban/sprints | head -c 200
```

Expected: JSON com sprints retorna; se falhar, checar `/tmp/mc-dev.log`.

- [ ] **Step 2: Criar task de teste via API existente**

```bash
curl -s -X POST http://127.0.0.1:4310/api/kanban/tasks \
  -H "Content-Type: application/json" \
  -H "Cf-Access-Authenticated-User-Email: you@example.com" \
  -d '{"title":"http smoke wave-3","sprint":"current","project":"openclaw"}' | tee /tmp/curl-task.json
TID=$(python3 -c "import json; print(json.load(open('/tmp/curl-task.json'))['task']['id'])")
echo "task: $TID"
```

Expected: task criada, ID `T-NNNN`.

- [ ] **Step 3: Mover ready, depois block via HTTP**

```bash
curl -s -X POST http://127.0.0.1:4310/api/kanban/tasks/$TID/move \
  -H "Content-Type: application/json" \
  -H "Cf-Access-Authenticated-User-Email: you@example.com" \
  -d '{"status":"ready"}'
echo ""
curl -s -X POST http://127.0.0.1:4310/api/kanban/tasks/$TID/block \
  -H "Content-Type: application/json" \
  -H "Cf-Access-Authenticated-User-Email: you@example.com" \
  -d '{"reason":"http smoke block"}'
echo ""
```

Expected: dois 200 OK com payloads de task.

- [ ] **Step 4: GET next-ready (deve devolver null pois T-XXXX está blocked)**

```bash
curl -s "http://127.0.0.1:4310/api/kanban/tasks/next-ready?project=openclaw" \
  -H "Cf-Access-Authenticated-User-Email: you@example.com"
echo ""
```

Expected: `{"task": null}` (ou outra task ready se houver no state — interpretar conforme o estado).

- [ ] **Step 5: Unblock + GET next-ready (deve devolver T-XXXX)**

```bash
curl -s -X POST http://127.0.0.1:4310/api/kanban/tasks/$TID/unblock \
  -H "Content-Type: application/json" \
  -H "Cf-Access-Authenticated-User-Email: you@example.com" \
  -d '{}'
echo ""
curl -s "http://127.0.0.1:4310/api/kanban/tasks/next-ready?project=openclaw" \
  -H "Cf-Access-Authenticated-User-Email: you@example.com"
echo ""
```

Expected: GET devolve `{"task": {"id":"T-XXXX",...}}` (a task que acabou de unblockar; ou outra ready mais antiga).

- [ ] **Step 6: Force move via HTTP (rejected sem reason → 400; com reason → OK)**

```bash
# rejected sem reason — espera 400
curl -s -X POST http://127.0.0.1:4310/api/kanban/tasks/$TID/move \
  -H "Content-Type: application/json" \
  -H "Cf-Access-Authenticated-User-Email: you@example.com" \
  -d '{"status":"rejected"}'
echo ""
# rejected com reason — OK
curl -s -X POST http://127.0.0.1:4310/api/kanban/tasks/$TID/move \
  -H "Content-Type: application/json" \
  -H "Cf-Access-Authenticated-User-Email: you@example.com" \
  -d '{"status":"rejected","reason":"http smoke reject"}'
echo ""
```

Expected: primeiro 400 com `error: invalid_input` ou `error` da CLI; segundo 200 OK.

- [ ] **Step 7: Reopen via HTTP**

```bash
curl -s -X POST http://127.0.0.1:4310/api/kanban/tasks/$TID/reopen \
  -H "Content-Type: application/json" \
  -H "Cf-Access-Authenticated-User-Email: you@example.com" \
  -d '{"to":"in_progress","reason":"http smoke reopen"}'
echo ""
```

Expected: 200 OK; task volta a `in_progress`.

- [ ] **Step 8: Cleanup task de teste**

```bash
curl -s -X POST http://127.0.0.1:4310/api/kanban/tasks/$TID/archive \
  -H "Content-Type: application/json" \
  -H "Cf-Access-Authenticated-User-Email: you@example.com" \
  -d '{}'
echo ""
# Parar dev server se foi iniciado nesta phase:
# pkill -f "next dev" 2>/dev/null
```

Expected: 200 OK.

### Task 5.10: Commit Phase 5 backend MC

**Files:** git commit

- [ ] **Step 1: Stage só os arquivos da wave-3**

```bash
cd ~/code/mission-control
git add src/lib/kanban/statusEnum.ts \
        src/lib/kanban/transitions.ts \
        src/components/kanban/transitions.test.ts \
        src/lib/kanban/stateReader.ts \
        src/app/api/kanban/tasks/\[id\]/move/route.ts \
        src/app/api/kanban/tasks/\[id\]/block \
        src/app/api/kanban/tasks/\[id\]/unblock \
        src/app/api/kanban/tasks/\[id\]/reopen \
        src/app/api/kanban/tasks/next-ready
git status -s
```

Expected: só os arquivos wave-3 staged. CLAUDE.md e health/page.tsx **não** staged.

- [ ] **Step 2: Commit**

```bash
git commit -m "$(cat <<'EOF'
feat(e5-f4-wave3): kanban dev lifecycle - backend (HTTP API)

Wave-3 da família F4 (kanban-tasks). Espelha o backend host-local
(`~/.openclaw/kanban-tasks/lib/transitions.py`) na camada TS:

- statusEnum.ts + transitions.ts: enum canônico (backlog, ready,
  in_progress, testing, done, rejected) + whitelist soft (espelho do
  Python pra D&D guard na UI).
- move/route.ts: aceita force + reason no body.
- block/route.ts, unblock/route.ts, reopen/route.ts: novas rotas.
- next-ready/route.ts: GET hook pro delivery-dispatcher-agent futuro
  (read-only; primeira task ready & não-blocked do projeto).
- stateReader.ts: Task ganha campos blocked, blocked_reason,
  blocked_at, rejected_reason, dispatch_payload, test_result.

Vitest: transitions.test.ts cobre whitelist + canDragMove.

Spec: bevox-knowledge/35_specs/2026-04-19-e5-f4-kanban-dev-lifecycle.md

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
git log --oneline -1
```

Expected: commit criado. CLAUDE.md/health/page.tsx seguem unstaged.

---

## Phase 6: UI MC — 5 colunas + rejected lane + blocked badge/filter/modal

### Task 6.1: Atualizar `Board.tsx` ORDER + D&D guard

**Files:**
- Modify: `~/code/mission-control/src/components/kanban/Board.tsx`

- [ ] **Step 1: Atualizar ORDER constant**

Substituir:
```typescript
const ORDER = ["backlog", "todo", "in_progress", "done"] as const;
```

Por:
```typescript
import { canDragMove } from "@/lib/kanban/transitions";

const ORDER = ["backlog", "ready", "in_progress", "testing", "done"] as const;
```

- [ ] **Step 2: Adicionar D&D guard via canDragMove no handleDragEnd**

Localizar o handler do `DndContext` `onDragEnd`. Antes da chamada `onMove(...)`, adicionar guard:

```typescript
const handleDragEnd = (e: DragEndEvent) => {
  if (!e.over) return;
  const taskId = String(e.active.id);
  const targetStatus = String(e.over.id) as TaskStatus;
  const task = tasks.find((t) => t.id === taskId);
  if (!task) return;
  // Wave-3: D&D guard — UI não força. Toast em transição inválida.
  if (!canDragMove(task.status, targetStatus)) {
    onInvalidDrop?.(task, targetStatus);
    return;
  }
  onMove(taskId, targetStatus);
};
```

E adicionar `onInvalidDrop?: (task: Task, target: TaskStatus) => void` ao tipo `Props`. O parent (`page.tsx`) implementa o toast.

- [ ] **Step 3: Sanity tsc**

```bash
cd ~/code/mission-control
npx tsc --noEmit src/components/kanban/Board.tsx 2>&1 | head -10
```

Expected: zero novos erros.

### Task 6.2: Criar `BlockModal.tsx`

**Files:**
- Create: `~/code/mission-control/src/components/kanban/BlockModal.tsx`

- [ ] **Step 1: Escrever BlockModal**

```typescript
"use client";

import { useEffect, useState } from "react";

interface Props {
  taskId: string;
  taskTitle: string;
  onConfirm: (reason: string) => void;
  onCancel: () => void;
}

export function BlockModal({ taskId, taskTitle, onConfirm, onCancel }: Props) {
  const [reason, setReason] = useState("");
  useEffect(() => {
    const onEsc = (e: KeyboardEvent) => { if (e.key === "Escape") onCancel(); };
    window.addEventListener("keydown", onEsc);
    return () => window.removeEventListener("keydown", onEsc);
  }, [onCancel]);
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40">
      <div className="bg-zinc-900 border border-zinc-700 rounded p-4 w-96 max-w-full">
        <h2 className="text-sm font-semibold mb-2">
          Block {taskId}: <span className="opacity-70">{taskTitle}</span>
        </h2>
        <label className="block text-xs mb-1 opacity-70">Reason (required):</label>
        <input
          autoFocus
          type="text"
          value={reason}
          onChange={(e) => setReason(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === "Enter" && reason.trim()) onConfirm(reason.trim());
          }}
          className="w-full px-2 py-1 bg-zinc-800 border border-zinc-700 rounded text-sm"
        />
        <div className="mt-3 flex justify-end gap-2">
          <button
            type="button"
            onClick={onCancel}
            className="px-3 py-1 text-sm rounded border border-zinc-700"
          >
            Cancel
          </button>
          <button
            type="button"
            disabled={!reason.trim()}
            onClick={() => onConfirm(reason.trim())}
            className="px-3 py-1 text-sm rounded bg-amber-700 disabled:opacity-50"
          >
            Block
          </button>
        </div>
      </div>
    </div>
  );
}
```

### Task 6.3: Atualizar `TaskCard.tsx` com badge blocked

**Files:**
- Modify: `~/code/mission-control/src/components/kanban/TaskCard.tsx`

- [ ] **Step 1: Adicionar badge blocked no card**

Localizar o JSX do card. Adicionar próximo ao título (ou no footer do card) um badge condicional:

```tsx
{task.blocked && (
  <span
    title={task.blocked_reason ?? ""}
    className="inline-flex items-center px-1.5 py-0.5 text-xs rounded bg-amber-700/60 text-amber-100 mr-1"
    aria-label={`blocked: ${task.blocked_reason ?? ""}`}
  >
    🚫 blocked
  </span>
)}
```

E para tasks rejected, badge inline com reason truncado:

```tsx
{task.status === "rejected" && task.rejected_reason && (
  <span
    title={task.rejected_reason}
    className="inline-flex items-center px-1.5 py-0.5 text-xs rounded bg-red-900/60 text-red-100 mr-1"
  >
    {task.rejected_reason.slice(0, 30)}
    {task.rejected_reason.length > 30 ? "…" : ""}
  </span>
)}
```

- [ ] **Step 2: Atenuar visualmente cards blocked (opacity)**

No wrapper top-level do card, adicionar:

```tsx
className={`... ${task.blocked ? "opacity-75" : ""}`}
```

(Manter classes existentes; só anexar a condicional.)

### Task 6.4: Criar `RejectedLane.tsx`

**Files:**
- Create: `~/code/mission-control/src/components/kanban/RejectedLane.tsx`

- [ ] **Step 1: Escrever RejectedLane (espelha pattern de archived inline)**

```typescript
"use client";

import { useState } from "react";
import type { Task } from "@/lib/kanban/stateReader";
import { TaskCard } from "./TaskCard";

interface Props {
  rejected: Task[];
  onOpenDetail: (taskId: string) => void;
  onArchive: (taskId: string) => void;
  focusedId?: string | null;
}

export function RejectedLane({ rejected, onOpenDetail, onArchive, focusedId }: Props) {
  const [open, setOpen] = useState(false);
  if (rejected.length === 0) return null;
  return (
    <section className="mt-4 border-t border-zinc-800 pt-3">
      <button
        type="button"
        onClick={() => setOpen((o) => !o)}
        className="text-xs opacity-70 hover:opacity-100 flex items-center gap-2"
        aria-expanded={open}
      >
        <span>{open ? "▼" : "▶"}</span>
        <span>Rejected ({rejected.length})</span>
      </button>
      {open && (
        <div className="mt-2 grid grid-cols-1 md:grid-cols-3 lg:grid-cols-5 gap-2">
          {rejected.map((t) => (
            <TaskCard
              key={t.id}
              task={t}
              onArchive={onArchive}
              onOpenDetail={onOpenDetail}
              focused={focusedId === t.id}
            />
          ))}
        </div>
      )}
    </section>
  );
}
```

(Confirmar interface props do `TaskCard` real e ajustar.)

### Task 6.5: Atualizar `useFilterPersistence.ts` com `blockedOnly`

**Files:**
- Modify: `~/code/mission-control/src/components/kanban/useFilterPersistence.ts`
- Modify: `~/code/mission-control/src/components/kanban/useFilterPersistence.test.ts`

- [ ] **Step 1: Adicionar campo `blockedOnly` na interface Filters**

Localizar o tipo `Filters` (provavelmente exportado). Adicionar:

```typescript
export interface Filters {
  project: string | null;
  search: string;
  sprint: "current" | "next";
  showArchived: boolean;
  blockedOnly: boolean;  // wave-3
}

const DEFAULTS: Filters = {
  project: null,
  search: "",
  sprint: "current",
  showArchived: false,
  blockedOnly: false,  // wave-3
};
```

- [ ] **Step 2: Update default + parse fallback gracioso**

Onde o hook lê `localStorage.kanban_filters_v1` e faz parse, garantir que `blockedOnly` defaulta a `false` se ausente. Padrão típico:

```typescript
function parseFilters(raw: string | null): Filters {
  if (!raw) return DEFAULTS;
  try {
    const parsed = JSON.parse(raw);
    return {
      project: typeof parsed.project === "string" ? parsed.project : null,
      search: typeof parsed.search === "string" ? parsed.search : "",
      sprint: parsed.sprint === "next" ? "next" : "current",
      showArchived: parsed.showArchived === true,
      blockedOnly: parsed.blockedOnly === true,  // wave-3
    };
  } catch {
    return DEFAULTS;
  }
}
```

- [ ] **Step 3: Atualizar `useFilterPersistence.test.ts`**

Adicionar test cases:

```typescript
it("blockedOnly defaults to false when key absent in v1", () => {
  localStorage.setItem(
    "kanban_filters_v1",
    JSON.stringify({ project: null, search: "", sprint: "current", showArchived: false }),
  );
  const { result } = renderHook(() => useFilterPersistence("kanban_filters_v1"));
  expect(result.current[0].blockedOnly).toBe(false);
});

it("persists blockedOnly toggle", () => {
  const { result } = renderHook(() => useFilterPersistence("kanban_filters_v1"));
  act(() => result.current[1]({ ...result.current[0], blockedOnly: true }));
  const stored = JSON.parse(localStorage.getItem("kanban_filters_v1")!);
  expect(stored.blockedOnly).toBe(true);
});
```

- [ ] **Step 4: Run tests**

```bash
cd ~/code/mission-control
npx vitest run src/components/kanban/useFilterPersistence.test.ts
```

Expected: tests passam (incluindo os novos).

### Task 6.6: Atualizar `KeyboardShortcuts.tsx` + `ShortcutsCheatsheet.tsx`

**Files:**
- Modify: `~/code/mission-control/src/components/kanban/KeyboardShortcuts.tsx`
- Modify: `~/code/mission-control/src/components/kanban/ShortcutsCheatsheet.tsx`

- [ ] **Step 1: Adicionar binding `b` no shortcut map**

Em `KeyboardShortcuts.tsx`, no objeto/array de bindings, adicionar:

```typescript
{ key: "b", description: "Block/unblock focused task", action: "toggleBlock" }
```

(Adaptar à estrutura concreta — pode ser switch/case dentro do `keydown` handler. Se for switch, adicionar:)

```typescript
case "b":
  if (focusedTask && !TERMINAL.has(focusedTask.status)) {
    onToggleBlock(focusedTask);
    e.preventDefault();
  }
  break;
```

E adicionar `onToggleBlock?: (task: Task) => void` na interface de props do hook.

- [ ] **Step 2: Atualizar ShortcutsCheatsheet**

Localizar a lista de atalhos no modal cheatsheet. Adicionar entrada:

```tsx
<li><kbd>b</kbd> — block/unblock focused task</li>
```

(Posicionar na seção "Mutação" junto com `n`, `→`, `←`, `m`, `a`, `e`, `c`.)

### Task 6.7: Atualizar `kanban/page.tsx` — fiação completa

**Files:**
- Modify: `~/code/mission-control/src/app/(dashboard)/kanban/page.tsx`

- [ ] **Step 1: Imports adicionais**

```typescript
import { RejectedLane } from "@/components/kanban/RejectedLane";
import { BlockModal } from "@/components/kanban/BlockModal";
import { TERMINAL } from "@/lib/kanban/statusEnum";
```

- [ ] **Step 2: State pra modal de block**

Adicionar próximo aos outros `useState`:

```typescript
const [blockModalTask, setBlockModalTask] = useState<Task | null>(null);
```

- [ ] **Step 3: Handler block/unblock**

```typescript
const onToggleBlock = useCallback((task: Task) => {
  if (TERMINAL.has(task.status)) return;
  if (task.blocked) {
    // unblock direto sem modal
    void optimisticUpdate(
      setTasks,
      (prev) => prev.map((t) =>
        t.id === task.id ? { ...t, blocked: false, blocked_reason: null, blocked_at: null } : t),
      () => api(`/api/kanban/tasks/${task.id}/unblock`, { method: "POST", body: "{}" }),
    );
  } else {
    setBlockModalTask(task);
  }
}, [setTasks]);

const onBlockConfirm = useCallback(async (reason: string) => {
  if (!blockModalTask) return;
  const task = blockModalTask;
  setBlockModalTask(null);
  await optimisticUpdate(
    setTasks,
    (prev) => prev.map((t) =>
      t.id === task.id ? { ...t, blocked: true, blocked_reason: reason, blocked_at: new Date().toISOString() } : t),
    () => api(`/api/kanban/tasks/${task.id}/block`, {
      method: "POST",
      body: JSON.stringify({ reason }),
    }),
  );
}, [blockModalTask, setTasks]);
```

- [ ] **Step 4: Handler invalid drop (toast)**

```typescript
const onInvalidDrop = useCallback((task: Task, target: TaskStatus) => {
  if (TERMINAL.has(task.status)) {
    showToast(`Reopen via CLI: cli.sh task reopen ${task.id} --to ${target}`);
  } else {
    showToast(`Move not allowed: ${task.status} → ${target}. Use CLI with --force if intended.`);
  }
}, []);
```

(Usar o toast existente do MC — `showToast` do helper já presente. Se não houver, usar `console.warn` como fallback.)

- [ ] **Step 5: Filter blockedOnly**

Atualizar onde `tasks` é filtrado pra render do board:

```typescript
const visibleTasks = useMemo(() => {
  let v = tasks;
  if (filters.project) v = v.filter((t) => t.project === filters.project);
  if (filters.search.trim()) {
    const q = filters.search.toLowerCase();
    v = v.filter((t) => t.title.toLowerCase().includes(q) || t.id.toLowerCase().includes(q));
  }
  if (filters.blockedOnly) v = v.filter((t) => t.blocked);
  return v;
}, [tasks, filters]);

const blockedCount = useMemo(() => visibleTasks.filter((t) => t.blocked).length, [visibleTasks]);
const rejectedTasks = useMemo(() => visibleTasks.filter((t) => t.status === "rejected"), [visibleTasks]);
const boardTasks = useMemo(() => visibleTasks.filter((t) => t.status !== "rejected"), [visibleTasks]);
```

- [ ] **Step 6: Render — TopBar com toggle blocked + counter**

Próximo aos outros filtros do `<TopBar>`, adicionar checkbox + counter:

```tsx
<label className="flex items-center gap-1 text-xs">
  <input
    type="checkbox"
    checked={filters.blockedOnly}
    onChange={(e) => setFilters({ ...filters, blockedOnly: e.target.checked })}
  />
  Show blocked only
</label>
<span className="text-xs opacity-70">Blocked: {blockedCount}</span>
```

(Posicionar dentro do `<TopBar>` ou adjacente, conforme layout existente.)

- [ ] **Step 7: Render — Board recebe boardTasks + onInvalidDrop**

```tsx
<Board
  tasks={boardTasks}
  onMove={handleMove}
  onArchive={handleArchive}
  onOpenDetail={handleOpenDetail}
  onInvalidDrop={onInvalidDrop}
  focusedId={focusedId}
/>
<RejectedLane
  rejected={rejectedTasks}
  onOpenDetail={handleOpenDetail}
  onArchive={handleArchive}
  focusedId={focusedId}
/>
{/* ArchivedLane existente continua abaixo */}
```

- [ ] **Step 8: Wire keyboard shortcut `b`**

Onde `useKeyboardShortcuts` é chamado, passar `onToggleBlock`:

```typescript
useKeyboardShortcuts({ onToggleBlock, /* ...outros handlers */ });
```

- [ ] **Step 9: Render BlockModal condicionalmente**

No JSX próximo aos outros modais:

```tsx
{blockModalTask && (
  <BlockModal
    taskId={blockModalTask.id}
    taskTitle={blockModalTask.title}
    onConfirm={onBlockConfirm}
    onCancel={() => setBlockModalTask(null)}
  />
)}
```

- [ ] **Step 10: Sanity tsc + vitest**

```bash
cd ~/code/mission-control
npx tsc --noEmit 2>&1 | grep -E "(page\.tsx|kanban)" | head -20
npx vitest run src/components/kanban/
```

Expected: zero novos erros tsc relacionados; testes Vitest passam.

### Task 6.8: Atualizar `history/[sprint_id]/page.tsx` — 5 colunas read-only

**Files:**
- Modify: `~/code/mission-control/src/app/(dashboard)/kanban/history/[sprint_id]/page.tsx`

- [ ] **Step 1: Confirmar uso atual**

```bash
grep -n "ORDER\|backlog\|todo" ~/code/mission-control/src/app/\(dashboard\)/kanban/history/\[sprint_id\]/page.tsx
```

Esperado: encontrar `ORDER` ou enum hardcoded similar.

- [ ] **Step 2: Atualizar ORDER (ou import) pra 5 colunas + RejectedLane**

Substituir a lista de status pelas 5 colunas + render de `RejectedLane` para tasks rejected do sprint histórico:

```typescript
const HISTORY_ORDER = ["backlog", "ready", "in_progress", "testing", "done"] as const;
```

E renderizar `<RejectedLane rejected={tasks.filter(t => t.status === "rejected")} ... />` se houver. Read-only: passar `onOpenDetail` que só abre drawer (sem mutação) e omitir `onArchive`.

(O detalhe exato depende da estrutura atual da página — confirmar com `grep`/`Read` antes de editar.)

- [ ] **Step 3: Sanity tsc**

```bash
cd ~/code/mission-control
npx tsc --noEmit src/app/\(dashboard\)/kanban/history/\[sprint_id\]/page.tsx 2>&1 | head -10
```

Expected: zero erros novos.

### Task 6.9: UI smoke browser (manual)

**Files:** none (manual)

- [ ] **Step 1: Subir dev server**

```bash
cd ~/code/mission-control
npm run dev > /tmp/mc-dev.log 2>&1 &
echo "MC pid: $!"
sleep 4
```

- [ ] **Step 2: Abrir browser em http://127.0.0.1:4310/kanban**

Manual checklist:
- [ ] 5 colunas visíveis (backlog, ready, in_progress, testing, done)
- [ ] Lane "Rejected" colapsada visível abaixo (se houver tasks rejected)
- [ ] ArchivedLane (existente) abaixo da rejected lane
- [ ] Filter "Show blocked only" + counter "Blocked: N" no TopBar
- [ ] D&D arrastar card de `backlog` para `ready` → move OK
- [ ] D&D arrastar card de `done` para `in_progress` → toast "Reopen via CLI..." + sem mudança
- [ ] D&D arrastar card de `backlog` para `testing` → toast "Move not allowed..."
- [ ] Foco em card → atalho `b` → modal abre → reason "manual smoke" → submit → card ganha badge `🚫 blocked` + opacity reduzida
- [ ] Atalho `b` em card já blocked → unblock direto sem modal → badge some
- [ ] Filter `Show blocked only` → toggla → mostra só blocked
- [ ] `?` cheatsheet → `b` documentado

- [ ] **Step 3: Stop dev server (se desejado)**

```bash
pkill -f "next dev" 2>/dev/null
```

### Task 6.10: Commit Phase 6 UI

**Files:** git commit

- [ ] **Step 1: Stage arquivos UI**

```bash
cd ~/code/mission-control
git add src/components/kanban/Board.tsx \
        src/components/kanban/TaskCard.tsx \
        src/components/kanban/RejectedLane.tsx \
        src/components/kanban/BlockModal.tsx \
        src/components/kanban/KeyboardShortcuts.tsx \
        src/components/kanban/ShortcutsCheatsheet.tsx \
        src/components/kanban/useFilterPersistence.ts \
        src/components/kanban/useFilterPersistence.test.ts \
        src/app/\(dashboard\)/kanban/page.tsx \
        src/app/\(dashboard\)/kanban/history/\[sprint_id\]/page.tsx
git status -s
```

Expected: arquivos UI staged. CLAUDE.md/health/page.tsx unstaged.

- [ ] **Step 2: Commit**

```bash
git commit -m "$(cat <<'EOF'
feat(e5-f4-wave3): kanban dev lifecycle - UI MC

- Board.tsx: 5 colunas (backlog, ready, in_progress, testing, done) +
  D&D guard via canDragMove (transições inválidas viram toast, sem POST).
- RejectedLane.tsx: lane secundária colapsável (espelha pattern de
  ArchivedLane) abaixo do board.
- BlockModal.tsx: modal pra coletar reason ao bloquear via atalho `b`.
- TaskCard.tsx: badge `🚫 blocked` + tooltip de reason; opacity 75% em
  cards blocked; badge inline com rejected_reason em rejected.
- KeyboardShortcuts.tsx + ShortcutsCheatsheet.tsx: atalho `b` toggla
  blocked (modal se ativando, unblock direto se já blocked).
- useFilterPersistence: campo blockedOnly (default false) + tests.
- page.tsx: TopBar ganha "Show blocked only" + counter "Blocked: N";
  rejected tasks separadas do board; modal block conectado.
- history/[sprint_id]/page.tsx: 5 colunas read-only + rejected lane.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
git log --oneline -2
```

Expected: 2 commits no branch (Phase 5 backend + Phase 6 UI).

---

## Phase 7: Smoke E2E full (host-local + HTTP + UI)

### Task 7.1: Re-rodar smoke E2E backend

**Files:** none

- [ ] **Step 1: Rodar smoke completo**

```bash
cd ~/.openclaw/kanban-tasks
bash smoke_e2e.sh 2>&1 | tail -30
```

Expected: termina com `WAVE-3 smoke PASSED`.

### Task 7.2: Smoke replay determinístico

**Files:** none

- [ ] **Step 1: Validar replay reproduce state idêntico**

```bash
cd ~/.openclaw/kanban-tasks
# Backup state.json atual:
cp state.json /tmp/state.before-rebuild.json
./cli.sh rebuild
diff <(python3 -c "import json; print(json.dumps(json.load(open('/tmp/state.before-rebuild.json')), sort_keys=True, indent=2))") \
     <(python3 -c "import json; print(json.dumps(json.load(open('state.json')), sort_keys=True, indent=2))") \
  | head -30
```

Expected: diff vazio ou só `generated_at` diferente (timestamp do rebuild). Sem diff em `tasks` ou `sprints`.

### Task 7.3: Smoke alias `todo→ready` (state legado)

**Files:** none

- [ ] **Step 1: Restaurar backup pré-wave3 e rebuild**

```bash
LATEST_BACKUP=$(ls -t ~/.openclaw/backups/kanban-tasks/state.json.pre-wave3.* | head -1)
cp "$LATEST_BACKUP" /tmp/state.legacy.json
LATEST_EVENTS=$(ls -t ~/.openclaw/backups/kanban-tasks/events.jsonl.pre-wave3.* | head -1)
cp "$LATEST_EVENTS" /tmp/events.legacy.jsonl
# Verificar se há tasks com status "todo":
python3 -c "
import json
state = json.load(open('/tmp/state.legacy.json'))
todos = [t for t in state['tasks'] if t['status'] == 'todo']
print(f'tasks com status=todo: {len(todos)}')
for t in todos: print(f'  {t[\"id\"]}: {t[\"title\"][:40]}')
"
```

Expected: lista as tasks legadas com `todo`. Se zero, o teste é vácuo (mas confirma que upstream está limpo).

- [ ] **Step 2: Restaurar e rebuild — confirmar alias**

```bash
cd ~/.openclaw/kanban-tasks
cp /tmp/state.legacy.json state.json
cp /tmp/events.legacy.jsonl events.jsonl
./cli.sh rebuild
python3 -c "
import json
state = json.load(open('state.json'))
todos = [t for t in state['tasks'] if t['status'] == 'todo']
readys = [t for t in state['tasks'] if t['status'] == 'ready']
print(f'tasks com status=todo (esperado 0): {len(todos)}')
print(f'tasks com status=ready: {len(readys)}')
assert len(todos) == 0, f'alias falhou: ainda há {len(todos)} todos'
print('alias OK')
"
```

Expected: `alias OK`; zero `todo` no state pós-rebuild.

- [ ] **Step 3: Verificar events.jsonl preservado**

```bash
grep -c '"to": "todo"' ~/.openclaw/kanban-tasks/events.jsonl || echo "zero events legados"
```

Expected: count > 0 (events.jsonl preservou history) OU "zero events legados" (se não havia). Importante: NÃO foi reescrito.

### Task 7.4: HTTP smoke `next-ready`

**Files:** none

- [ ] **Step 1: Subir dev MC (se não estiver)**

```bash
cd ~/code/mission-control
pgrep -f "next dev" >/dev/null || npm run dev > /tmp/mc-dev.log 2>&1 &
sleep 3
```

- [ ] **Step 2: Validar next-ready devolve task ou null corretamente**

```bash
# Sem filter project — primeira ready de qualquer projeto
curl -s "http://127.0.0.1:4310/api/kanban/tasks/next-ready" \
  -H "Cf-Access-Authenticated-User-Email: you@example.com" | python3 -m json.tool
```

Expected: `{"task": {...}}` com primeira task `ready` & não-blocked do state, ou `{"task": null}` se nenhuma.

- [ ] **Step 3: Cleanup dev server (opcional)**

```bash
pkill -f "next dev" 2>/dev/null || true
```

### Task 7.5: Tests TS pass

**Files:** none

- [ ] **Step 1: Run vitest completo no kanban**

```bash
cd ~/code/mission-control
npx vitest run src/components/kanban/ src/lib/kanban/
```

Expected: todos passam (incluindo transitions.test.ts e useFilterPersistence.test.ts atualizados).

---

## Phase 8: Tracker update + push gate humano

### Task 8.1: Atualizar `delivery-tracker.yml`

**Files:**
- Modify: `~/bevox-knowledge/40_roadmap/delivery-tracker.yml`

- [ ] **Step 1: Adicionar entrada F4-kanban-dev-lifecycle**

Localizar o bloco do E5 features (próximo das linhas 104-114, onde já estão F4-sprint-planning e F4-kanban-rich-ui). Adicionar **após F4-kanban-rich-ui**:

```yaml
      - id: F4-kanban-dev-lifecycle
        status: delivered
        delivered_at: 2026-04-XX  # PREENCHER com data real do delivery
        features:
          - "kanban-tasks status enum estendido para ciclo dev (backlog, ready, in_progress, testing, done, rejected) substituindo o legado backlog/todo/in_progress/done"
          - "blocked como flag ortogonal (blocked + blocked_reason + blocked_at) em vez de status — preserva contexto de onde a task estava"
          - "whitelist soft de transicoes em lib/transitions.py + espelho TS lib/kanban/transitions.ts; --force (humano) e --reason (agente) auditaveis no evento task_moved (forced=true, reason='...')"
          - "task reopen cmd dedicado pra terminais (done/rejected) com evento task_reopened proprio"
          - "alias permanente todo->ready na projecao (apply_event); events.jsonl preservado intacto"
          - "novos cmds CLI: task block, task unblock, task reopen; flags task list --blocked"
          - "novas rotas HTTP MC: POST /api/kanban/tasks/[id]/block|unblock|reopen + GET /api/kanban/tasks/next-ready (hook delivery-dispatcher futuro)"
          - "UI MC /kanban: 5 colunas (backlog, ready, in_progress, testing, done), RejectedLane secundaria colapsavel, blocked badge + tooltip + filter Show blocked only + counter, atalho `b` (modal reason ou unblock direto), D&D guard via canDragMove (transicoes invalidas viram toast sem POST)"
          - "schema_version 2 aditivo (rejected_reason, blocked, blocked_reason, blocked_at, dispatch_payload, test_result); rebuild idempotente backfilla defaults"
          - "hooks pra agentes futuros: eventos satellites task_entered_testing, task_rejected_with_reason; slots reservados dispatch_payload + test_result (schema-only nesta wave)"
        spec: 35_specs/2026-04-19-e5-f4-kanban-dev-lifecycle.md
```

- [ ] **Step 2: Validar YAML**

```bash
cd ~/bevox-knowledge
python3 -c "
import yaml
d = yaml.safe_load(open('40_roadmap/delivery-tracker.yml'))
e5 = next((e for e in d['epics'] if e['id'] == 'E5'), None)
assert e5, 'E5 not found'
features = [f['id'] for w in e5.get('waves', []) for f in w.get('features', [])]
print(f'E5 features: {features}')
" 2>/dev/null || \
python3 -c "
import yaml
d = yaml.safe_load(open('40_roadmap/delivery-tracker.yml'))
print('top-level keys:', list(d.keys())[:5])
print('E5 entries:')
import json
for k, v in d.items():
    if 'E5' in str(k) or 'e5' in str(k).lower():
        print(f'  {k}: ...')
" 2>&1 | head -20
```

Expected: YAML parsing OK (estrutura concreta varia — confirmar que `F4-kanban-dev-lifecycle` aparece na lista).

### Task 8.2: Commit tracker em bevox-knowledge

**Files:** git commit

- [ ] **Step 1: Stage só o tracker**

```bash
cd ~/bevox-knowledge
git add 40_roadmap/delivery-tracker.yml
git status -s
```

Expected: só `delivery-tracker.yml` staged. READMEs modificados pre-existentes seguem unstaged.

- [ ] **Step 2: Commit**

```bash
git commit -m "$(cat <<'EOF'
feat(E5/F4): kanban dev lifecycle wave 3 delivered

Wave-3 da família F4 (kanban-tasks): enum de status estendido
(backlog/ready/in_progress/testing/done/rejected) + flag ortogonal
blocked + whitelist soft de transições + hooks pra agentes futuros
(task_entered_testing, task_rejected_with_reason, GET next-ready,
slots dispatch_payload/test_result reservados).

Backend: ~/.openclaw/kanban-tasks/lib/transitions.py + adapt task.py
+ alias todo->ready na projeção (events.jsonl preservado).
HTTP: 4 rotas novas + adapt move (force/reason).
UI: 5 colunas + RejectedLane + BlockModal + atalho `b` + D&D guard.

Spec: 35_specs/2026-04-19-e5-f4-kanban-dev-lifecycle.md (commit 2483df0)
Plan: ~/.openclaw/docs/superpowers/plans/2026-04-19-e5-f4-kanban-dev-lifecycle-plan.md
MC branch: feat/e5-f4-kanban-dev-lifecycle

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
git log --oneline -2
```

Expected: novo commit; o anterior é `2483df0` (spec).

### Task 8.3: PUSH GATE — humano explícito

**STOP — não automatizar.**

Esta task é gate humano. Bernard confirma e empurra.

- [ ] **Step 1: Mostrar o que será pushado nos 2 repos**

```bash
echo "=== bevox-knowledge ==="
cd ~/bevox-knowledge
git log --oneline origin/main..HEAD

echo ""
echo "=== mission-control ==="
cd ~/code/mission-control
git log --oneline origin/main..HEAD 2>/dev/null || \
  git log --oneline origin/main..feat/e5-f4-kanban-dev-lifecycle 2>/dev/null
echo ""
echo "branch atual MC:"
git branch --show-current
```

Expected:
- bevox-knowledge: 2 commits (spec `2483df0` + tracker `feat(E5/F4)...wave 3 delivered`)
- mission-control: 2 commits no branch `feat/e5-f4-kanban-dev-lifecycle` (Phase 5 backend + Phase 6 UI)

- [ ] **Step 2: Bernard decide: push ou pausa**

Bernard escolhe:
- **Push agora (paralelo nos 2 repos)**:
  ```bash
  # Em terminais separados, ou sequencial:
  ( cd ~/bevox-knowledge && git push origin main )
  ( cd ~/code/mission-control && git push -u origin feat/e5-f4-kanban-dev-lifecycle )
  # Depois: abrir PR do branch MC pra main no GitHub.
  ```
- **Pausar e revisar**:
  - Diff completo: `git diff origin/main..HEAD`
  - Voltar atrás: `git reset --soft HEAD~1` (manter alterações staged)

- [ ] **Step 3: PR no MC (quando Bernard decidir)**

```bash
cd ~/code/mission-control
gh pr create --title "feat(e5-f4-wave3): kanban dev lifecycle" --body "$(cat <<'EOF'
## Summary

Wave-3 da família F4 (kanban-tasks):
- 5 colunas peer (backlog/ready/in_progress/testing/done) substituindo backlog/todo/in_progress/done
- `rejected` como status terminal em lane secundária colapsável (padrão ArchivedLane)
- `blocked` como flag ortogonal (`🚫` badge + tooltip + filter "Show blocked only")
- whitelist soft com `--force`/`--reason` auditável; D&D guard na UI
- 4 rotas HTTP novas + adapt `/move` aceitando force/reason
- Hooks pra agentes futuros: eventos satellites + `GET /next-ready` + slots reservados

## Test plan

- [ ] Smoke E2E backend (`bash ~/.openclaw/kanban-tasks/smoke_e2e.sh`) passa com `WAVE-3 smoke PASSED`
- [ ] Vitest passa (`npx vitest run src/components/kanban/ src/lib/kanban/`)
- [ ] Browser manual: 5 colunas + RejectedLane visível; blocked badge + filter; atalho `b`; D&D guard mostra toast em transição inválida
- [ ] Tasks legadas com `status:"todo"` viraram `ready` via alias (verificar em `/kanban/history/[sprint_id]`)
- [ ] `GET /api/kanban/tasks/next-ready?project=openclaw` devolve task `ready & !blocked`

🤖 Generated with [Claude Code](https://claude.com/claude-code)
EOF
)"
```

Expected: PR aberto. URL devolvida — Bernard mergea quando estiver satisfeito.

---

## Self-review (executado durante writing)

### Spec coverage
- §2 modelo dados: Phases 2.1 step 2 + 3.2 step 4 (defaults + bump schema). ✓
- §3 transições + reopen + blocked rules: Phase 1.1 (transitions.py) + 2.1 step 3 (move_status) + 2.1 step 4 (block/unblock/reopen) + 2.1 step 5 (archive auto-unblock). ✓
- §5 eventos novos + alias projeção: Phase 2.1 step 3 (satellites) + Phase 3.2 step 1-3 (alias + handlers). ✓
- §6 CLI: Phase 3.1 (argparse + subcomandos) + Phase 3.1 step 8 (formato output). ✓
- §7 HTTP API: Phase 5.4-5.8 (move adapt + 4 rotas novas). ✓
- §8 UI MC: Phase 6.1-6.8 (Board, RejectedLane, BlockModal, TaskCard badge, filter, atalho b, history view). ✓
- §9 boundary agentes (escopo B hooks-only): coberto via eventos satellites + next-ready + slots reservados (sem write-path). ✓
- §10 DoD smoke E2E: Phase 4.1 (smoke_e2e.sh extensão) + 7.1-7.5 (replays). ✓
- §11 risks: backup defensivo Phase 0.3; alias documentado; rebuild idempotente. ✓

### Placeholder scan
- "PREENCHER com data real do delivery" em Phase 8.1 step 1 — **intencional**, gate humano.
- "STOP — não automatizar" em Phase 8.3 — **intencional**, push gate humano.
- Nenhum TBD/TODO técnico não-resolvido.

### Type consistency
- `STATUS_ENUM` (Python) e `STATUS_ENUM` (TS) compartilham mesma lista de 6 valores. ✓
- `move_status(task_id, status, actor, force, reason)` — assinatura consistente entre `task.py` e `cmd_task_move` em `api.py`. ✓
- `Task` interface TS ganha exatamente os 6 campos novos definidos em `task.py.create()`. ✓
- `WHITELIST` Python (transitions.py) idêntica em estrutura à `WHITELIST` TS (transitions.ts). ✓
- `canDragMove` (TS) é o helper UI; `is_valid_transition` (Python) é o canon — UI usa o primeiro com semântica restritiva extra (terminal sempre falha). ✓

---

## Notas operacionais

- **Push gate humano (Phase 8.3):** Bernard decide timing. Não automatizar.
- **Branch MC:** `feat/e5-f4-kanban-dev-lifecycle` — não merger via squash sem Bernard ver diff.
- **Memória:** atualizar `~/.claude/projects/-home-you--openclaw/memory/e5_f4_kanban_tasks_state.md` ao terminar (nova feature delivered, branch ainda em PR).
- **Backup state.json:** Phase 0.3 cria; manter por 30 dias antes de purgar.
- **Drift `transitions.py` ↔ `transitions.ts`:** se aparecer dor real, considerar codegen (Python → TS) como wave futura.
