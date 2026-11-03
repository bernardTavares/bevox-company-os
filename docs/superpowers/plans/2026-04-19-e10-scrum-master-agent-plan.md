# E10 Scrum Master Agent Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use `superpowers:subagent-driven-development` (recommended) or `superpowers:executing-plans` to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Entregar o `scrum-master-agent` — Hub-dispatch supervisionado que lê um implementation plan e propõe a materialização das Tasks do plan como tasks do kanban-tasks, com proposta JSON em arquivo, accept all-or-nothing, e projeção 1 plan Task = 1 kanban task.

**Architecture:** Módulo host-local em `~/.openclaw/scrum-master-agent/` (Python stdlib + bash entrypoint, herda convenção F4). Pattern Hub-dispatch: Vox carrega playbook canônico como working context; zero daemon/scheduler. Enabling delta mínimo no kanban-tasks (`task set-dispatch-payload` subcmd). Canonical artifacts em `bevox-knowledge` (playbook + registry + tracker).

**Tech Stack:**
- Host-local: Python 3 stdlib (zero pip install), bash entrypoint, jsonl events
- Canonical: knowledge-sync (canonical commit flow) OU git plain commit + push gate humano
- Zero npm, zero pytest (smoke E2E shell + dogfood real contra plan F4 wave-3)
- Stdlib parsing: regex + text (sem PyYAML; registry regenera via `_tools/render-registry.py` que tem dep própria)

**Specs canônicas:**
- Wave-1 (esta): `bevox-knowledge/35_specs/2026-04-19-e10-scrum-master-agent.md` (commit `2ac8527` em main local)
- Dependência F4 wave-3: `bevox-knowledge/35_specs/2026-04-19-e5-f4-kanban-dev-lifecycle.md` (commit `2483df0`)
- PRD raiz: "OpenClaw Task-Orchestrated Development for Claude Code" (histórico planejamento 2026-04-19)

**Plans pares (pattern reference):**
- Plan F4 wave-3: `~/.openclaw/docs/superpowers/plans/2026-04-19-e5-f4-kanban-dev-lifecycle-plan.md`

**Constraint operacional:**
- Zero pip install em módulos host-local. stdlib-puro.
- F4 wave-3 delivered e em `main` (MC branch `feat/e5-f4-kanban-dev-lifecycle` ainda aguarda push — não bloqueante pra este plan; kanban-tasks host-local já funcional).
- Canonical commit em `bevox-knowledge/main` local aguarda push gate humano (precedente F4 wave-3).
- `~/.openclaw/` não é git repo — kanban-tasks e scrum-master-agent são host-local SoT operacional.

---

## File Structure

### Host-local novo módulo (`~/.openclaw/scrum-master-agent/`)

```
~/.openclaw/scrum-master-agent/
├── cli.sh                          # entrypoint bash (espelha kanban-tasks/cli.sh)
├── lib/
│   ├── __init__.py                 # vazio
│   ├── store.py                    # I/O atomico do proposal file
│   ├── parser.py                   # parser do implementation plan (regex + text)
│   ├── proposer.py                 # build do proposal JSON
│   ├── materializer.py             # accept → invoca kanban CLI + set-dispatch-payload
│   └── api.py                      # argparse dispatcher
├── proposals/                      # proposals JSON files (gerados em runtime)
├── playbook.md                     # copia sync'd do canonical (manual ou via knowledge-sync)
└── README.md                       # operação + troubleshooting
```

### Host-local delta (`~/.openclaw/kanban-tasks/` — enabling delta wave-3+)

```
~/.openclaw/kanban-tasks/
├── lib/
│   ├── task.py                     # MODIFICA: adiciona set_dispatch_payload()
│   └── api.py                      # MODIFICA: argparse task set-dispatch-payload + cmd + event handler
├── smoke_e2e.sh                    # ESTENDE: cenario set-dispatch-payload
└── README.md                       # MODIFICA: doc novo cmd
```

### Canonical (`bevox-knowledge/`)

```
bevox-knowledge/
├── 20_architecture/agents/
│   ├── scrum-master-agent.md       # NOVO: playbook canonical
│   ├── registry.yml                # MODIFICA: adiciona entry scrum-master-agent
│   └── registry.md                 # REGENERADO via _tools/render-registry.py
└── 40_roadmap/
    └── delivery-tracker.yml        # MODIFICA: adiciona wave E10/scrum-master-agent
```

---

## Phase 0: Pre-flight + defensive backups

### Task 0.1: Verificar ambos repos limpos no escopo desta wave

**Files:** none (read-only)

- [ ] **Step 1: Confirmar spec canonizada**

```bash
git -C ~/bevox-knowledge log --oneline -1 -- 35_specs/2026-04-19-e10-scrum-master-agent.md
```

Expected: commit `2ac8527` (ou equivalente SHA do commit da spec).

- [ ] **Step 2: Confirmar playbook ainda não existe**

```bash
ls ~/bevox-knowledge/20_architecture/agents/scrum-master-agent.md 2>/dev/null && echo "WARN: playbook ja existe" || echo "OK: nao criado ainda"
```

Expected: `OK: nao criado ainda`.

- [ ] **Step 3: Confirmar módulo host-local ainda não existe**

```bash
ls ~/.openclaw/scrum-master-agent/ 2>/dev/null && echo "WARN: modulo ja existe" || echo "OK: nao criado"
```

Expected: `OK: nao criado`.

- [ ] **Step 4: Confirmar F4 wave-3 set_dispatch_payload ainda não existe**

```bash
grep -q "def set_dispatch_payload" ~/.openclaw/kanban-tasks/lib/task.py && echo "WARN: set_dispatch_payload ja existe" || echo "OK: enabling delta pendente"
```

Expected: `OK: enabling delta pendente`.

### Task 0.2: Backup state kanban-tasks

**Files:** snapshot defensivo

- [ ] **Step 1: Backup state.json + events.jsonl**

```bash
mkdir -p ~/.openclaw/backups/kanban-tasks
TS=$(date -Iseconds)
cp ~/.openclaw/kanban-tasks/state.json ~/.openclaw/backups/kanban-tasks/state.json.pre-scrum-master.$TS
cp ~/.openclaw/kanban-tasks/events.jsonl ~/.openclaw/backups/kanban-tasks/events.jsonl.pre-scrum-master.$TS
ls -la ~/.openclaw/backups/kanban-tasks/ | tail -4
```

Expected: 2 arquivos backup com timestamp atual.

### Task 0.3: Verificar plan F4 wave-3 disponível pra dogfood

**Files:** none (read-only)

- [ ] **Step 1: Plan F4 wave-3 existe em ~/.openclaw/docs/superpowers/plans/**

```bash
ls -la ~/.openclaw/docs/superpowers/plans/2026-04-19-e5-f4-kanban-dev-lifecycle-plan.md
wc -l ~/.openclaw/docs/superpowers/plans/2026-04-19-e5-f4-kanban-dev-lifecycle-plan.md
```

Expected: arquivo existe, ~800+ linhas.

- [ ] **Step 2: Verificar header tem Epico (scrum-master vai precisar)**

```bash
head -20 ~/.openclaw/docs/superpowers/plans/2026-04-19-e5-f4-kanban-dev-lifecycle-plan.md | grep -iE "epico|epic"
```

Expected: 0 linhas (plan wave-3 não tem header `**Epico:**` explícito — dogfood vai exigir Bernard adicionar linha ou usar `--project-override`).

Essa informação é insumo pra Phase 9 (dogfood) — se plan não tiver `**Epico:**`, Bernard precisa editar plan pra adicionar linha antes do accept, ou scrum-master vai falhar com `PLAN_MISSING_EPIC`. Documentado no smoke.

---

## Phase 1: Kanban enabling delta (`task set-dispatch-payload`)

### Task 1.1: Adicionar `set_dispatch_payload` em `lib/task.py`

**Files:**
- Modify: `~/.openclaw/kanban-tasks/lib/task.py`

- [ ] **Step 1: Adicionar método depois de `reopen()` (antes de `# ============ Project management ============`)**

Procurar a linha `# ============ Project management ============` e inserir ANTES dela:

```python
def set_dispatch_payload(
    task_id: str,
    payload: Dict[str, Any],
    merge: bool = False,
    actor: str = "bernard",
) -> Dict[str, Any]:
    """Set task.dispatch_payload. replace (default) ou merge shallow.

    Rejeita em status='archived'. Emite event task_dispatch_payload_set.
    """
    if not isinstance(payload, dict):
        raise ValueError(f"payload must be dict, got {type(payload).__name__}")
    with store.mutate_state() as state:
        t = find_task(state, task_id)
        if t is None:
            raise ValueError(f"task not found: {task_id}")
        if t["status"] == "archived":
            raise ValueError("task is archived; unarchive first")
        existing = t.get("dispatch_payload") or {}
        if merge:
            new_payload = {**existing, **payload}
        else:
            new_payload = payload
        keys_set = sorted(payload.keys())
        t["dispatch_payload"] = new_payload
        t["updated_at"] = store.now_iso()
        seq = store.next_seq(state)
        store.append_event({
            "seq": seq, "ts": store.now_iso(), "type": "task_dispatch_payload_set",
            "actor": actor, "task_id": task_id,
            "keys_set": keys_set, "merge": merge,
        })
        state["last_event_seq"] = seq
        return {"ok": True, "noop": False, "task": t}
```

- [ ] **Step 2: Sanity import**

```bash
PYTHONPATH=~/.openclaw/kanban-tasks python3 -c "
from lib import task as task_lib
assert hasattr(task_lib, 'set_dispatch_payload')
print('OK')
"
```

Expected: `OK`.

### Task 1.2: Adicionar argparse + cmd handler em `lib/api.py`

**Files:**
- Modify: `~/.openclaw/kanban-tasks/lib/api.py`

- [ ] **Step 1: Adicionar cmd handler depois de `cmd_task_reopen`**

Localizar `def cmd_task_reopen(args: argparse.Namespace) -> int:` e adicionar EM SEGUIDA:

```python
def cmd_task_set_dispatch_payload(args: argparse.Namespace) -> int:
    try:
        payload = json.loads(args.payload)
    except json.JSONDecodeError as e:
        return _err(
            f"invalid JSON payload: {e}", "invalid_input", args.json,
        )
    res = task_lib.set_dispatch_payload(
        args.task_id, payload, merge=args.merge, actor=args.actor,
    )
    _print(
        res, args.json,
        f"dispatch_payload {'merged' if args.merge else 'set'}: {res['task']['id']}",
    )
    return EXIT_OK
```

- [ ] **Step 2: Adicionar subparser em `build_parser()`**

Localizar o bloco do `rp = leaf(tk_sub, "reopen")` e adicionar DEPOIS do `rp.set_defaults(func=cmd_task_reopen)`:

```python
    sp = leaf(tk_sub, "set-dispatch-payload")
    sp.add_argument("task_id")
    sp.add_argument(
        "--payload", required=True,
        help="JSON string com o dispatch_payload",
    )
    sp.add_argument(
        "--merge", action="store_true",
        help="shallow merge (default: replace)",
    )
    sp.set_defaults(func=cmd_task_set_dispatch_payload)
```

- [ ] **Step 3: Sanity parser**

```bash
cd ~/.openclaw/kanban-tasks && PYTHONPATH=. python3 -c "
from lib.api import build_parser
p = build_parser()
ns = p.parse_args(['task', 'set-dispatch-payload', 'T-0001',
                   '--payload', '{\"goal\": \"x\"}'])
assert ns.func.__name__ == 'cmd_task_set_dispatch_payload'
assert ns.task_id == 'T-0001'
assert ns.payload == '{\"goal\": \"x\"}'
assert ns.merge is False
ns = p.parse_args(['task', 'set-dispatch-payload', 'T-0002',
                   '--payload', '{}', '--merge'])
assert ns.merge is True
print('OK')
"
```

Expected: `OK`.

### Task 1.3: Adicionar event handler em `apply_event`

**Files:**
- Modify: `~/.openclaw/kanban-tasks/lib/api.py`

- [ ] **Step 1: Adicionar clause depois do handler `task_reopened`**

Localizar `elif t in ("task_entered_testing", "task_rejected_with_reason"):` (linha próxima do final de `_apply_event`). Inserir ANTES dessa clause:

```python
    elif t == "task_dispatch_payload_set":
        for tk in state["tasks"]:
            if tk["id"] == ev["task_id"]:
                # apply_event nao tem acesso ao payload real (nao e
                # emitido no evento). Preserva dispatch_payload existente
                # no state ja projetado; se state vier de rebuild puro
                # (sem payload material), fica null e precisa re-apply
                # do comando set-dispatch-payload.
                tk["updated_at"] = ts
```

**Nota importante:** O evento registra `keys_set` como audit trail mas NÃO carrega o valor real do payload. Motivo: payloads podem ser grandes e inflar `events.jsonl`. Trade-off: rebuild puro não reconstrói `dispatch_payload`, mas o estado persiste via `mutate_state` que escreve `state.json` atômico. Se rebuild rodar em um momento que perdeu state.json, os payloads precisariam ser re-aplicados. Documentado §9.2 da spec.

- [ ] **Step 2: Sanity apply_event aceita o novo type sem erro**

```bash
cd ~/.openclaw/kanban-tasks && PYTHONPATH=. python3 -c "
from lib.api import _apply_event
state = {'tasks': [{'id': 'T-0001', 'updated_at': ''}], 'sprints': [], 'projects': []}
ev = {'type': 'task_dispatch_payload_set', 'task_id': 'T-0001',
      'actor': 'vox', 'ts': '2026-04-19T00:00:00Z', 'seq': 99,
      'keys_set': ['goal'], 'merge': False}
_apply_event(state, ev)
assert state['tasks'][0]['updated_at'] == '2026-04-19T00:00:00Z'
print('OK')
"
```

Expected: `OK`.

### Task 1.4: Testar E2E CLI num sandbox isolado

**Files:** none (sandbox manual)

- [ ] **Step 1: Setup sandbox e testar flow**

```bash
set -e
cd ~/.openclaw/kanban-tasks
# Backup live state
cp state.json /tmp/state.scrum1.json
cp events.jsonl /tmp/events.scrum1.jsonl
rm state.json events.jsonl
./cli.sh sprint init >/dev/null
./cli.sh task add "dispatch payload test" --project openclaw --sprint current >/dev/null
./cli.sh task move T-0001 ready
echo "==> set dispatch_payload (replace)"
./cli.sh task set-dispatch-payload T-0001 --payload '{"goal": "testar", "spec_refs": ["x.md"]}'
echo "==> verificar payload persisted"
./cli.sh task show T-0001 --json | python3 -c "
import json, sys
t = json.load(sys.stdin)['task']
dp = t['dispatch_payload']
assert dp == {'goal': 'testar', 'spec_refs': ['x.md']}, dp
print('OK replace')
"
echo "==> merge: adicionar campo novo"
./cli.sh task set-dispatch-payload T-0001 --payload '{"acceptance_criteria": ["y"]}' --merge
./cli.sh task show T-0001 --json | python3 -c "
import json, sys
t = json.load(sys.stdin)['task']
dp = t['dispatch_payload']
assert dp.get('goal') == 'testar'
assert dp.get('acceptance_criteria') == ['y']
print('OK merge')
"
echo "==> event trail"
./cli.sh events tail --n 3 --type task_dispatch_payload_set --json | python3 -c "
import json, sys
events = json.load(sys.stdin)['events']
assert len(events) == 2
assert events[0]['merge'] is True
assert events[1]['merge'] is False
print('OK events')
"
# Restore
cp /tmp/state.scrum1.json state.json
cp /tmp/events.scrum1.jsonl events.jsonl
./cli.sh rebuild >/dev/null
echo "==> state real restaurado"
```

Expected: `OK replace`, `OK merge`, `OK events`, e `state real restaurado`.

### Task 1.5: Estender `smoke_e2e.sh` com cenário set-dispatch-payload

**Files:**
- Modify: `~/.openclaw/kanban-tasks/smoke_e2e.sh`

- [ ] **Step 1: Adicionar bloco depois de `archive auto-unblock` (no bloco WAVE-3)**

Localizar `echo "==> archive auto-unblock"` e seu bloco. Depois do `assert 'task_archived' in types` + print, ANTES de `==> rebuild idempotente`, inserir:

```bash

echo "==> set-dispatch-payload (replace + merge)"
$KT task add "dispatch test" --project openclaw --sprint current >/dev/null
DP_ID=$($KT task list --json | python3 -c "import json,sys; print(json.load(sys.stdin)['tasks'][-1]['id'])")
$KT task set-dispatch-payload $DP_ID --payload '{"goal": "x"}'
$KT task set-dispatch-payload $DP_ID --payload '{"spec_refs": ["y.md"]}' --merge
$KT task show $DP_ID --json | python3 -c "
import json, sys
t = json.load(sys.stdin)['task']
dp = t['dispatch_payload']
assert dp.get('goal') == 'x' and dp.get('spec_refs') == ['y.md'], dp
print('dispatch_payload OK')
"
$KT task archive $DP_ID >/dev/null
```

- [ ] **Step 2: Rodar smoke**

```bash
cd ~/.openclaw/kanban-tasks
cp state.json /tmp/state.scrum1b.json
cp events.jsonl /tmp/events.scrum1b.jsonl
bash smoke_e2e.sh 2>&1 | tail -15
# Restore
cp /tmp/state.scrum1b.json state.json
cp /tmp/events.scrum1b.jsonl events.jsonl
./cli.sh rebuild >/dev/null
```

Expected: `WAVE-3 smoke PASSED` + `ALL E2E PASSED` + `dispatch_payload OK` no output.

### Task 1.6: Atualizar README kanban-tasks

**Files:**
- Modify: `~/.openclaw/kanban-tasks/README.md`

- [ ] **Step 1: Adicionar seção de cmd `set-dispatch-payload` na seção "Cmds wave-3"**

Localizar `## Cmds wave-3` e o bloco de código bash. Adicionar ao final do bloco (antes do closing ` ``` `):

```bash

# Set dispatch_payload (reservado pra dispatcher/scrum-master agents)
cli.sh task set-dispatch-payload T-0042 --payload '{"goal": "x", "spec_refs": [...]}'
cli.sh task set-dispatch-payload T-0042 --payload '{"dispatched_at": "..."}' --merge
```

---

## Phase 2: scrum-master-agent — skeleton

### Task 2.1: Criar estrutura de diretórios

**Files:**
- Create: `~/.openclaw/scrum-master-agent/` (dir)
- Create: `~/.openclaw/scrum-master-agent/lib/` (dir)
- Create: `~/.openclaw/scrum-master-agent/proposals/` (dir)
- Create: `~/.openclaw/scrum-master-agent/lib/__init__.py`
- Create: `~/.openclaw/scrum-master-agent/README.md`

- [ ] **Step 1: Criar dirs + `__init__.py` vazio**

```bash
mkdir -p ~/.openclaw/scrum-master-agent/lib
mkdir -p ~/.openclaw/scrum-master-agent/proposals
touch ~/.openclaw/scrum-master-agent/lib/__init__.py
```

- [ ] **Step 2: README esqueleto**

```bash
cat > ~/.openclaw/scrum-master-agent/README.md <<'EOF'
# scrum-master-agent

> HOST-LOCAL, NUNCA COMMITADO. Modulo Hub-dispatch que projeta
> implementation plans em tasks do kanban-tasks.

Spec canonica:
`bevox-knowledge/35_specs/2026-04-19-e10-scrum-master-agent.md`

Playbook canonico:
`bevox-knowledge/20_architecture/agents/scrum-master-agent.md`
(cópia sync'd em `./playbook.md`).

## Operação básica

```bash
# Propor — gera proposta JSON em proposals/
vox scrum-master propose --plan 2026-04-19-e5-f4-kanban-dev-lifecycle-plan

# Listar pending
vox scrum-master list

# Inspecionar
vox scrum-master show <proposal-id>
vox scrum-master diff <proposal-id>

# Aceitar (all-or-nothing)
vox scrum-master accept <proposal-id>
vox scrum-master accept <proposal-id> --ready

# Rejeitar
vox scrum-master reject <proposal-id> --reason "..."
```

## Troubleshooting

**`PLAN_MISSING_EPIC`:** adicione `**Epico:** <ep>/<wave>` no header do plan.

**`AMBIGUOUS_PROJECT`:** adicione `**Project:** <nome>` no header do plan OU use `--project-override <nome>` na invocação.

**`PROPOSAL_ALREADY_ACCEPTED`:** proposta já foi consumida. Para refazer, propose novamente (produz proposal_id novo).

**`PLAN_DRIFT`:** plan editado após propose. Use `--force-plan-drift` ou re-proponha.

## Spec canônica

- `bevox-knowledge/35_specs/2026-04-19-e10-scrum-master-agent.md`
- Plan wave-1: `~/.openclaw/docs/superpowers/plans/2026-04-19-e10-scrum-master-agent-plan.md`
EOF
```

- [ ] **Step 3: Verificar estrutura**

```bash
ls -la ~/.openclaw/scrum-master-agent/
```

Expected: `lib/`, `proposals/`, `README.md` presentes.

### Task 2.2: Criar `lib/store.py` — I/O atômico para proposal files

**Files:**
- Create: `~/.openclaw/scrum-master-agent/lib/store.py`

- [ ] **Step 1: Escrever store.py**

```python
"""Storage para proposal files: atomic write, glob, load, update state."""

import json
import os
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

ROOT = Path(os.path.expanduser("~/.openclaw/scrum-master-agent"))
PROPOSALS_DIR = ROOT / "proposals"


def now_iso() -> str:
    """UTC ISO8601 com Z suffix, segundos precision (match kanban convention)."""
    return datetime.now(tz=timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _atomic_write(path: Path, content: str) -> None:
    """tmpfile + os.rename (atomic on POSIX)."""
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(
        prefix=path.name + ".",
        suffix=".tmp",
        dir=str(path.parent),
    )
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(content)
        os.rename(tmp, path)
    except Exception:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise


def write_proposal(proposal: Dict[str, Any]) -> Path:
    """Escreve proposal JSON atomic. Retorna path absoluto."""
    pid = proposal["proposal_id"]
    path = PROPOSALS_DIR / f"{pid}.json"
    content = json.dumps(proposal, ensure_ascii=False, indent=2)
    _atomic_write(path, content)
    return path


def read_proposal(proposal_id: str) -> Dict[str, Any]:
    """Lê proposal JSON. Raises FileNotFoundError se ausente."""
    path = PROPOSALS_DIR / f"{proposal_id}.json"
    if not path.exists():
        raise FileNotFoundError(f"PROPOSAL_NOT_FOUND: {proposal_id}")
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def update_proposal(proposal: Dict[str, Any]) -> Path:
    """Reescreve proposal (atomic). Proposal_id inalterado."""
    return write_proposal(proposal)


def list_proposals(
    status_filter: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """Lista proposals. status_filter: pending|accepted|rejected|None."""
    if not PROPOSALS_DIR.exists():
        return []
    out: List[Dict[str, Any]] = []
    for path in sorted(PROPOSALS_DIR.glob("*.json")):
        try:
            with open(path, "r", encoding="utf-8") as f:
                p = json.load(f)
        except (OSError, json.JSONDecodeError):
            continue
        state = p.get("state", {})
        if state.get("accepted_at"):
            p_status = "accepted"
        elif state.get("rejected_at"):
            p_status = "rejected"
        else:
            p_status = "pending"
        if status_filter and status_filter != "all" and p_status != status_filter:
            continue
        p["_computed_status"] = p_status
        out.append(p)
    return out


def proposal_exists(proposal_id: str) -> bool:
    return (PROPOSALS_DIR / f"{proposal_id}.json").exists()
```

- [ ] **Step 2: Sanity**

```bash
cd ~/.openclaw/scrum-master-agent && PYTHONPATH=. python3 -c "
from lib.store import (
    write_proposal, read_proposal, list_proposals, proposal_exists, now_iso,
)
p = {'proposal_id': 'test-1', 'total_tasks': 0, 'state': {}}
write_proposal(p)
assert proposal_exists('test-1')
got = read_proposal('test-1')
assert got['proposal_id'] == 'test-1'
props = list_proposals()
assert any(x['proposal_id'] == 'test-1' for x in props)
# Cleanup
import os
os.unlink(f'~/.openclaw/scrum-master-agent/proposals/test-1.json')
print('OK')
"
```

Expected: `OK`.

### Task 2.3: Criar `cli.sh` entrypoint

**Files:**
- Create: `~/.openclaw/scrum-master-agent/cli.sh`

- [ ] **Step 1: Escrever wrapper bash**

```bash
cat > ~/.openclaw/scrum-master-agent/cli.sh <<'EOF'
#!/usr/bin/env bash
# scrum-master-agent CLI entrypoint.
# Invoca lib.api via python3 stdlib.
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"
exec python3 -m lib.api "$@"
EOF
chmod +x ~/.openclaw/scrum-master-agent/cli.sh
```

- [ ] **Step 2: Verificar**

```bash
ls -la ~/.openclaw/scrum-master-agent/cli.sh
```

Expected: arquivo existe, executável.

---

## Phase 3: Plan parser (`lib/parser.py`)

### Task 3.1: Parser header (Epico, Project, Projects, Goal)

**Files:**
- Create: `~/.openclaw/scrum-master-agent/lib/parser.py`

- [ ] **Step 1: Criar parser.py com header parsing**

```python
"""Parser do implementation plan (convencao superpowers:writing-plans).

Extrai:
- Header: Goal, Epico (obrigatorio), Project/Projects (opcional)
- Phases: `^## Phase N: Name`
- Tasks: `^### Task N.M: Subject`
- Files blocks (Create/Modify/Test)
- Expected: lines (acceptance criteria)
- Out of scope blocks (opcional)

Regex + text parsing puro. Zero deps externas.
"""

import re
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple


# -- Regex patterns ------------------------------------------------------

RE_HEADER_GOAL = re.compile(r"^\*\*Goal:\*\*\s*(.+?)$", re.MULTILINE)
RE_HEADER_EPICO = re.compile(r"^\*\*Epico:\*\*\s*(\S+)\s*$", re.MULTILINE)
RE_HEADER_PROJECT = re.compile(r"^\*\*Project:\*\*\s*(\S+)\s*$", re.MULTILINE)
RE_HEADER_PROJECTS = re.compile(r"^\*\*Projects:\*\*\s*(.+?)$", re.MULTILINE)

RE_PHASE = re.compile(r"^##\s+Phase\s+(\d+):\s*(.+?)\s*$", re.MULTILINE)
RE_TASK = re.compile(r"^###\s+Task\s+(\d+)\.(\d+):\s*(.+?)\s*$", re.MULTILINE)

RE_FILES_BLOCK = re.compile(
    r"^\*\*Files:\*\*\s*\n((?:^-\s+.+\n)+)",
    re.MULTILINE,
)
RE_FILE_LINE = re.compile(
    r"^-\s+(Create|Modify|Test):\s*`([^`]+)`",
    re.MULTILINE,
)

RE_EXPECTED = re.compile(r"^Expected:\s*(.+?)$", re.MULTILINE)


# -- Data shapes ---------------------------------------------------------

class ParseError(Exception):
    """Plan malformado ou missing header obrigatorio."""

    def __init__(self, code: str, detail: str):
        self.code = code
        self.detail = detail
        super().__init__(f"{code}: {detail}")


def parse_header(text: str) -> Dict[str, Any]:
    """Parse header. Raises ParseError se Epico ausente.

    Returns: {'goal': str, 'epic_id': str, 'wave_slug': str,
              'wave_ref_root': str, 'project': str | None,
              'projects': [str] | None}
    """
    out: Dict[str, Any] = {
        "goal": None, "epic_id": None, "wave_slug": None,
        "wave_ref_root": None, "project": None, "projects": None,
    }
    m = RE_HEADER_GOAL.search(text)
    if m:
        out["goal"] = m.group(1).strip()
    m = RE_HEADER_EPICO.search(text)
    if not m:
        raise ParseError(
            "PLAN_MISSING_EPIC",
            "plan header deve ter `**Epico:** <epic-id>/<wave-slug>` "
            "(ex: `**Epico:** E5/F4-kanban-dev-lifecycle`)",
        )
    epico_raw = m.group(1).strip()
    if "/" not in epico_raw:
        raise ParseError(
            "PLAN_MISSING_EPIC",
            f"`**Epico:**` value '{epico_raw}' deve ter forma "
            f"`<epic-id>/<wave-slug>` (ex: `E5/F4-kanban-dev-lifecycle`)",
        )
    epic_id, wave_slug = epico_raw.split("/", 1)
    out["epic_id"] = epic_id
    out["wave_slug"] = wave_slug
    out["wave_ref_root"] = epico_raw
    m = RE_HEADER_PROJECT.search(text)
    if m:
        out["project"] = m.group(1).strip()
    else:
        m = RE_HEADER_PROJECTS.search(text)
        if m:
            projs = [p.strip() for p in m.group(1).split(",") if p.strip()]
            out["projects"] = projs
    return out
```

- [ ] **Step 2: Sanity com fixture inline**

```bash
cd ~/.openclaw/scrum-master-agent && PYTHONPATH=. python3 -c "
from lib.parser import parse_header, ParseError
t1 = '''
# Plan
**Goal:** entregar X
**Epico:** E5/F4-kanban-dev-lifecycle
**Project:** openclaw
'''
h = parse_header(t1)
assert h['goal'] == 'entregar X'
assert h['epic_id'] == 'E5'
assert h['wave_slug'] == 'F4-kanban-dev-lifecycle'
assert h['wave_ref_root'] == 'E5/F4-kanban-dev-lifecycle'
assert h['project'] == 'openclaw'
assert h['projects'] is None
print('OK single project')

t2 = '''**Goal:** x
**Epico:** E10/scrum-master-agent
**Projects:** openclaw, bevox-knowledge
'''
h = parse_header(t2)
assert h['projects'] == ['openclaw', 'bevox-knowledge']
assert h['project'] is None
print('OK multi projects')

t3 = '**Goal:** x'  # sem Epico
try:
    parse_header(t3)
    assert False, 'deveria ter falhado'
except ParseError as e:
    assert e.code == 'PLAN_MISSING_EPIC'
print('OK missing epic raises')

t4 = '**Epico:** E5_missing_slash'
try:
    parse_header(t4)
    assert False
except ParseError as e:
    assert e.code == 'PLAN_MISSING_EPIC'
print('OK missing slash raises')
"
```

Expected: 4 OKs.

### Task 3.2: Parse Phases + Tasks

**Files:**
- Modify: `~/.openclaw/scrum-master-agent/lib/parser.py`

- [ ] **Step 1: Adicionar `parse_phases_and_tasks` ao final de parser.py**

```python
def parse_phases_and_tasks(text: str) -> List[Dict[str, Any]]:
    """Extrai Phases + Tasks do plan.

    Returns: lista de tasks, cada uma com:
      {'phase_num': int, 'phase_name': str,
       'task_num': str (ex '1.1'), 'task_subject': str,
       'body': str (texto completo da task ate proxima task/phase)}
    """
    # Coleta offsets de Phase headings pra identificar boundaries
    phase_positions: List[Tuple[int, int, str]] = []  # (offset, phase_num, phase_name)
    for m in RE_PHASE.finditer(text):
        phase_positions.append((m.start(), int(m.group(1)), m.group(2).strip()))
    if not phase_positions:
        raise ParseError(
            "NO_PHASES_FOUND",
            "plan nao tem headings `^## Phase N:`; verifique convencao",
        )

    # Coleta task headings
    task_positions: List[Tuple[int, int, int, str]] = []
    # (offset, phase_num_decl, task_num_decl, subject)
    for m in RE_TASK.finditer(text):
        task_positions.append(
            (m.start(), int(m.group(1)), int(m.group(2)), m.group(3).strip()),
        )
    if not task_positions:
        raise ParseError(
            "NO_TASKS_FOUND",
            "plan nao tem headings `^### Task N.M:`; verifique convencao",
        )

    # Build tasks com body
    all_boundaries = sorted(
        [p[0] for p in phase_positions] + [t[0] for t in task_positions] + [len(text)]
    )
    out: List[Dict[str, Any]] = []
    for offset, phase_n_decl, task_n_sub, subject in task_positions:
        # Encontra offset da proxima boundary (phase ou task ou EOF)
        next_offset = len(text)
        for b in all_boundaries:
            if b > offset:
                next_offset = b
                break
        # Busca phase name correspondente (maior offset de phase <= offset)
        phase_name = ""
        phase_num_actual = phase_n_decl
        for p_off, p_num, p_name in phase_positions:
            if p_off < offset and p_num == phase_n_decl:
                phase_name = p_name
                phase_num_actual = p_num
        body = text[offset:next_offset].rstrip()
        out.append({
            "phase_num": phase_num_actual,
            "phase_name": phase_name,
            "task_num": f"{phase_n_decl}.{task_n_sub}",
            "task_subject": subject,
            "body": body,
            "offset": offset,
        })
    return out
```

- [ ] **Step 2: Sanity contra plan F4 wave-3**

```bash
cd ~/.openclaw/scrum-master-agent && PYTHONPATH=. python3 -c "
from lib.parser import parse_phases_and_tasks
text = open('~/.openclaw/docs/superpowers/plans/2026-04-19-e5-f4-kanban-dev-lifecycle-plan.md').read()
tasks = parse_phases_and_tasks(text)
print(f'total tasks: {len(tasks)}')
print('first 3:')
for t in tasks[:3]:
    print(f'  Phase {t[\"phase_num\"]} \"{t[\"phase_name\"][:30]}\" Task {t[\"task_num\"]} \"{t[\"task_subject\"][:40]}\"')
assert len(tasks) >= 25, f'esperava 25+ tasks, achei {len(tasks)}'
print('OK')
"
```

Expected: `total tasks: 30+`, listagem das primeiras 3 (Phase 0 tasks), `OK`.

### Task 3.3: Extrair Files blocks per task

**Files:**
- Modify: `~/.openclaw/scrum-master-agent/lib/parser.py`

- [ ] **Step 1: Adicionar `extract_files_from_task` ao final de parser.py**

```python
def extract_files_from_task(task_body: str) -> List[Dict[str, str]]:
    """Extrai `**Files:**` block da task body.

    Returns: lista de {'op': 'Create'|'Modify'|'Test', 'path': str}
    """
    m = RE_FILES_BLOCK.search(task_body)
    if not m:
        return []
    block = m.group(1)
    out: List[Dict[str, str]] = []
    for fm in RE_FILE_LINE.finditer(block):
        out.append({"op": fm.group(1), "path": fm.group(2).strip()})
    return out


def extract_expected_lines(task_body: str) -> List[str]:
    """Extrai todas as linhas `Expected: X` da task body (acceptance criteria)."""
    return [m.group(1).strip() for m in RE_EXPECTED.finditer(task_body)]
```

- [ ] **Step 2: Sanity contra plan F4 wave-3 (Task 1.1)**

```bash
cd ~/.openclaw/scrum-master-agent && PYTHONPATH=. python3 -c "
from lib.parser import parse_phases_and_tasks, extract_files_from_task, extract_expected_lines
text = open('~/.openclaw/docs/superpowers/plans/2026-04-19-e5-f4-kanban-dev-lifecycle-plan.md').read()
tasks = parse_phases_and_tasks(text)
# Task 1.1 = 'Criar lib/transitions.py com whitelist'
t11 = next(t for t in tasks if t['task_num'] == '1.1')
files = extract_files_from_task(t11['body'])
print(f'files em 1.1: {files}')
assert any('transitions.py' in f['path'] for f in files), files
expected = extract_expected_lines(t11['body'])
print(f'expected count 1.1: {len(expected)}')
assert len(expected) >= 1, expected
print('OK')
"
```

Expected: lista com pelo menos `lib/transitions.py`, >=1 Expected line, `OK`.

---

## Phase 4: Project derivation

### Task 4.1: Path-to-project map + rule 2

**Files:**
- Create: `~/.openclaw/scrum-master-agent/lib/projects.py`

- [ ] **Step 1: Criar projects.py**

```python
"""Project derivation rules. Deterministico, error-on-ambiguity."""

from pathlib import Path
from typing import List, Optional, Set, Tuple

# Mapa canonico path prefix -> project name.
# Ordem matters: mais especifico antes.
PATH_MAP: List[Tuple[str, str]] = [
    ("~/.openclaw/", "openclaw"),
    ("~/.openclaw/", "openclaw"),
    ("~/.openclaw", "openclaw"),
    ("~/bevox-knowledge/", "bevox-knowledge"),
    ("~/code/mission-control/", "mission-control"),
    ("~/code/vox/", "vox"),
    ("~/code/bevox-console/", "bevox-console"),
    ("~/code/bevox-harness/", "bevox-harness"),
    ("~/code/bevox-mobile/", "bevox-mobile"),
    ("~/code/bevox-web/", "bevox-web"),
]


def project_from_path(path: str) -> Optional[str]:
    """Normaliza path e retorna project ou None se nao mapeado."""
    p = path.strip()
    # Handle ~ expansion
    if p.startswith("~"):
        expanded = str(Path(p).expanduser())
    else:
        expanded = p
    for prefix, proj in PATH_MAP:
        if p.startswith(prefix) or expanded.startswith(prefix.replace("~", "~")):
            return proj
    return None


def projects_from_task_paths(task_files: List[dict]) -> Set[str]:
    """Retorna set de projects resolvidos dos paths da task.

    Paths nao mapeados sao ignorados (nao adicionam ao set, mas nao erram).
    """
    out: Set[str] = set()
    for f in task_files:
        proj = project_from_path(f.get("path", ""))
        if proj is not None:
            out.add(proj)
    return out
```

- [ ] **Step 2: Sanity**

```bash
cd ~/.openclaw/scrum-master-agent && PYTHONPATH=. python3 -c "
from lib.projects import project_from_path, projects_from_task_paths
assert project_from_path('~/.openclaw/kanban-tasks/lib/task.py') == 'openclaw'
assert project_from_path('~/.openclaw/kanban-tasks/lib/task.py') == 'openclaw'
assert project_from_path('~/code/mission-control/src/app/x.tsx') == 'mission-control'
assert project_from_path('~/bevox-knowledge/35_specs/x.md') == 'bevox-knowledge'
assert project_from_path('/random/path') is None
files = [
    {'op': 'Create', 'path': '~/.openclaw/a.py'},
    {'op': 'Modify', 'path': '~/code/mission-control/b.tsx'},
]
projs = projects_from_task_paths(files)
assert projs == {'openclaw', 'mission-control'}
print('OK')
"
```

Expected: `OK`.

### Task 4.2: Rules 1+3 (plan-level explicit + override/error)

**Files:**
- Modify: `~/.openclaw/scrum-master-agent/lib/projects.py`

- [ ] **Step 1: Adicionar `resolve_task_project`**

```python
def resolve_task_project(
    task_files: List[dict],
    plan_project: Optional[str],
    plan_projects: Optional[List[str]],
    cli_override: Optional[str],
) -> Tuple[Optional[str], List[str]]:
    """Resolve project de UMA task. Retorna (project | None, warnings).

    Rules (1ª que bate vence):
    1. plan-level `Project: X` (single) → todas tasks = X.
    2. plan-level `Projects: a,b` OU ausente → per-task path resolution.
    3. Se nao resolveu e cli_override setado → cli_override + warning.
    4. Se nao resolveu → (None, []) → caller dispara AMBIGUOUS_PROJECT.
    """
    warnings: List[str] = []
    # Rule 1: plan-level single
    if plan_project is not None:
        return plan_project, warnings
    # Rule 2: path resolution per-task
    projs = projects_from_task_paths(task_files)
    if len(projs) == 1:
        return projs.pop(), warnings
    # Rule 3: cli override escape hatch
    if cli_override is not None:
        warnings.append(
            f"project_override_applied: resolved={sorted(projs)} "
            f"-> override='{cli_override}'"
        )
        return cli_override, warnings
    # Fall through: nao resolveu
    return None, warnings


def known_projects() -> Set[str]:
    """Le projects.yml do kanban-tasks (stdlib parser simples)."""
    path = Path("~/.openclaw/kanban-tasks/projects.yml")
    if not path.exists():
        return set()
    out: Set[str] = set()
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or line.startswith("projects:"):
            continue
        if line.startswith("- "):
            out.add(line[2:].strip().strip('"').strip("'"))
    return out
```

- [ ] **Step 2: Sanity**

```bash
cd ~/.openclaw/scrum-master-agent && PYTHONPATH=. python3 -c "
from lib.projects import resolve_task_project, known_projects
files_single = [{'op': 'Create', 'path': '~/.openclaw/a.py'}]
files_multi = [{'op': 'Create', 'path': '~/.openclaw/a.py'},
               {'op': 'Modify', 'path': '~/code/mission-control/b.tsx'}]
files_none = [{'op': 'Create', 'path': '/random/x'}]

# Rule 1: plan-level
p, w = resolve_task_project(files_multi, 'vox', None, None)
assert p == 'vox' and w == []

# Rule 2: path resolution single
p, w = resolve_task_project(files_single, None, None, None)
assert p == 'openclaw' and w == []

# Rule 2 multi → fall through
p, w = resolve_task_project(files_multi, None, None, None)
assert p is None

# Rule 3: override aplicado
p, w = resolve_task_project(files_multi, None, None, 'mission-control')
assert p == 'mission-control'
assert len(w) == 1 and 'override_applied' in w[0]

# Rule 3: nao resolveu, no override → None
p, w = resolve_task_project(files_none, None, None, None)
assert p is None

# known_projects lista da projects.yml
kp = known_projects()
assert 'openclaw' in kp
print('OK')
"
```

Expected: `OK`.

---

## Phase 5: Proposer (build proposal JSON)

### Task 5.1: `lib/proposer.py` — monta top-level + per-task

**Files:**
- Create: `~/.openclaw/scrum-master-agent/lib/proposer.py`

- [ ] **Step 1: Criar proposer.py**

```python
"""Monta proposal JSON a partir do plan parseado."""

import subprocess
from pathlib import Path
from typing import Any, Dict, List, Optional

from . import parser as parser_lib
from . import projects as projects_lib
from . import store


def _plan_sha(plan_path: Path) -> Optional[str]:
    """Retorna git SHA do plan se tiver versao em repo; None caso contrario."""
    try:
        result = subprocess.run(
            ["git", "log", "-1", "--format=%H", "--", str(plan_path)],
            capture_output=True, text=True, check=False,
            cwd=str(plan_path.parent),
            timeout=5,
        )
        if result.returncode != 0:
            return None
        sha = result.stdout.strip()
        return sha if sha else None
    except (OSError, subprocess.TimeoutExpired):
        return None


def _make_proposal_id(plan_path: Path) -> str:
    """Timestamp + plan slug (sem .md)."""
    ts = store.now_iso().replace(":", "").replace("-", "")
    slug = plan_path.stem.replace(".", "-")
    return f"{ts}-{slug}"


def _build_task_from_plan(
    parsed_task: Dict[str, Any],
    header: Dict[str, Any],
    provisional_id: str,
    plan_path: Path,
    plan_ref_display: str,
    cli_project_override: Optional[str],
    cli_target_sprint: str,
    spec_refs: List[str],
) -> Dict[str, Any]:
    files = parser_lib.extract_files_from_task(parsed_task["body"])
    ac = parser_lib.extract_expected_lines(parsed_task["body"])
    project, warnings = projects_lib.resolve_task_project(
        files, header.get("project"), header.get("projects"),
        cli_project_override,
    )

    # wave_ref completo (AJUSTE #1: aponta pra wave do trabalho)
    wave_ref = f"{header['wave_ref_root']}/Phase-{parsed_task['phase_num']}"

    # Anchor no plan (github-style slug)
    task_anchor = f"task-{parsed_task['task_num'].replace('.', '-')}"

    # Description: primeiro paragrafo do body (apos o heading)
    body_lines = parsed_task["body"].split("\n")
    body_lines = [l for l in body_lines[1:] if l.strip() and not l.startswith("**Files:**")][:3]
    description = " ".join(body_lines).strip()

    # files_relevant: paths do Files block
    files_relevant = [f["path"] for f in files]

    dispatch_payload: Dict[str, Any] = {
        "goal": description or parsed_task["task_subject"],
        "spec_refs": spec_refs,
        "plan_ref": plan_ref_display,
        "plan_anchor": task_anchor,
        "acceptance_criteria": ac,
        "files_relevant": files_relevant,
    }
    # Omit optional empty keys pra enxuto
    if not dispatch_payload["spec_refs"]:
        del dispatch_payload["spec_refs"]
    if not dispatch_payload["acceptance_criteria"]:
        del dispatch_payload["acceptance_criteria"]
    if not dispatch_payload["files_relevant"]:
        del dispatch_payload["files_relevant"]

    task_obj = {
        "provisional_id": provisional_id,
        "title": parsed_task["task_subject"],
        "description": description or parsed_task["task_subject"],
        "status_on_create": "backlog",
        "project": project,
        "epic_id": header["epic_id"],
        "wave_ref": wave_ref,
        "sprint_target": cli_target_sprint,
        "dispatch_payload": dispatch_payload,
        "_warnings": warnings,  # consumido pelo caller no summary
    }
    return task_obj


def build_proposal(
    plan_path: Path,
    cli_project_override: Optional[str],
    cli_target_sprint: str,
    actor: str = "bernard",
) -> Dict[str, Any]:
    """Entry-point: le plan, parseia, monta proposal. Raises ParseError se plan invalido."""
    if not plan_path.exists():
        raise parser_lib.ParseError(
            "PLAN_NOT_FOUND",
            f"plan path '{plan_path}' nao encontrado",
        )
    text = plan_path.read_text(encoding="utf-8")
    header = parser_lib.parse_header(text)
    parsed_tasks = parser_lib.parse_phases_and_tasks(text)

    # Spec refs (explicit na header "Specs canonicas:" linha)
    spec_refs: List[str] = []
    import re as _re
    m = _re.search(r"^\*\*Spec canonica:\*\*\s*(.+?)$", text, _re.MULTILINE)
    if m:
        spec_refs.append(m.group(1).strip().strip("`"))
    for m2 in _re.finditer(
        r"^- (?:Wave-\d+[^:]*|Spec[^:]*|Plan[^:]*):\s*`([^`]+)`", text, _re.MULTILINE,
    ):
        spec_refs.append(m2.group(1))
    # Dedup preservando ordem
    seen = set()
    spec_refs = [r for r in spec_refs if not (r in seen or seen.add(r))]

    plan_ref_display = str(plan_path).replace("~/", "~/")
    proposal_id = _make_proposal_id(plan_path)

    tasks: List[Dict[str, Any]] = []
    for i, pt in enumerate(parsed_tasks, start=1):
        provisional = f"P-{i:03d}"
        tasks.append(_build_task_from_plan(
            pt, header, provisional, plan_path, plan_ref_display,
            cli_project_override, cli_target_sprint, spec_refs,
        ))

    # Detecta projects-canonical ausente → valida
    known = projects_lib.known_projects()
    unknown_projs = set()
    for t in tasks:
        if t["project"] and t["project"] not in known:
            unknown_projs.add(t["project"])
    if unknown_projs:
        raise parser_lib.ParseError(
            "UNKNOWN_PROJECT",
            f"projects nao listados em ~/.openclaw/kanban-tasks/projects.yml: "
            f"{sorted(unknown_projs)}. Rode `cli.sh project add <nome>`.",
        )

    # Detecta tasks sem project resolvido
    ambiguous = [t["provisional_id"] for t in tasks if t["project"] is None]
    if ambiguous:
        raise parser_lib.ParseError(
            "AMBIGUOUS_PROJECT",
            f"{len(ambiguous)} tasks sem project resolvido: {ambiguous[:5]}"
            f"{'...' if len(ambiguous) > 5 else ''}. Adicione `**Project:**` ou "
            f"`**Projects:**` no header do plan, ou use --project-override <nome>.",
        )

    proposal = {
        "schema_version": 1,
        "proposal_id": proposal_id,
        "plan_ref": plan_ref_display,
        "plan_sha": _plan_sha(plan_path),
        "sprint_goal": header.get("goal") or "",
        "target_sprint": cli_target_sprint,
        "target_project": header.get("project"),
        "epic_id": header["epic_id"],
        "wave_ref_root": header["wave_ref_root"],
        "total_tasks": len(tasks),
        "total_phases": len({t["wave_ref"].rsplit("/", 1)[-1] for t in tasks}),
        "tasks": tasks,
        "state": {
            "proposed_at": store.now_iso(),
            "proposed_by": actor,
            "accepted_at": None,
            "accepted_by": None,
            "rejected_at": None,
            "rejected_reason": None,
            "materialized_task_ids": None,
        },
    }
    # Strip _warnings dos tasks, agregar no top-level pra summary
    all_warnings: List[str] = []
    for t in tasks:
        all_warnings.extend(t.pop("_warnings", []))
    if all_warnings:
        proposal["_warnings"] = all_warnings
    return proposal
```

- [ ] **Step 2: Sanity contra plan F4 wave-3 (ADICIONAR header Epico temporariamente)**

Plan F4 wave-3 atual não tem `**Epico:**`. Pra smoke, vou testar após Bernard adicionar na Phase 9 OU com um fixture mock:

```bash
cd ~/.openclaw/scrum-master-agent && PYTHONPATH=. python3 -c "
import tempfile, json
from pathlib import Path
from lib.proposer import build_proposal

# Fixture plan curto inline
plan_text = '''# Teste
**Goal:** smoke test
**Epico:** E10/scrum-master-agent
**Project:** openclaw

## Phase 0: Setup

### Task 0.1: Criar arquivo

**Files:**
- Create: \`~/.openclaw/scrum-master-agent/x.py\`

- [ ] **Step 1: criar**

Run: \`ls\`
Expected: arquivo existe

### Task 0.2: Outra

**Files:**
- Modify: \`~/.openclaw/scrum-master-agent/y.py\`

- [ ] **Step 1: stub**

Expected: ok
'''

with tempfile.NamedTemporaryFile(mode='w', suffix='.md', delete=False) as f:
    f.write(plan_text)
    fpath = Path(f.name)

p = build_proposal(fpath, cli_project_override=None, cli_target_sprint='next')
print('proposal_id:', p['proposal_id'])
print('total_tasks:', p['total_tasks'])
print('epic_id:', p['epic_id'])
print('wave_ref_root:', p['wave_ref_root'])
print('task[0] wave_ref:', p['tasks'][0]['wave_ref'])
print('task[0] project:', p['tasks'][0]['project'])
print('task[0] ac:', p['tasks'][0]['dispatch_payload'].get('acceptance_criteria'))

assert p['epic_id'] == 'E10'
assert p['wave_ref_root'] == 'E10/scrum-master-agent'
assert p['tasks'][0]['wave_ref'] == 'E10/scrum-master-agent/Phase-0'
assert p['tasks'][0]['project'] == 'openclaw'
assert p['total_tasks'] == 2
print('OK')
"
```

Expected: `OK` + campos corretos impressos.

---

## Phase 6: CLI commands — propose, list, show, diff, reject

### Task 6.1: `lib/api.py` skeleton + `cmd_propose`

**Files:**
- Create: `~/.openclaw/scrum-master-agent/lib/api.py`

- [ ] **Step 1: Criar api.py**

```python
"""CLI dispatcher: parses argv, invoca proposer/materializer, imprime output."""

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Dict, Optional

from . import proposer as proposer_lib
from . import parser as parser_lib
from . import store

EXIT_OK = 0
EXIT_INPUT = 1
EXIT_STATE = 2
EXIT_LOCK = 3

PLANS_DIR = Path("~/.openclaw/docs/superpowers/plans")


def _print(payload: Any, json_mode: bool, human: Optional[str] = None) -> None:
    if json_mode:
        print(json.dumps(payload, ensure_ascii=False, indent=2))
    else:
        if human is not None:
            print(human)
        else:
            print(json.dumps(payload, ensure_ascii=False, indent=2))


def _err(msg: str, code: str, json_mode: bool) -> int:
    if json_mode:
        print(json.dumps({"ok": False, "error": msg, "code": code}))
    else:
        print(f"ERROR ({code}): {msg}", file=sys.stderr)
    if code == "invalid_input" or code.startswith("PLAN_") or code.startswith("AMBIGUOUS") or code == "UNKNOWN_PROJECT":
        return EXIT_INPUT
    return EXIT_STATE


def _resolve_plan_path(plan_arg: str) -> Path:
    """Slug ou path absoluto → Path.

    Slug: tenta plans_dir/<slug>.md.
    Path absoluto: usa direto.
    """
    p = Path(plan_arg).expanduser()
    if p.is_absolute() and p.exists():
        return p
    # Slug
    candidate = PLANS_DIR / f"{plan_arg}.md"
    if candidate.exists():
        return candidate
    candidate2 = PLANS_DIR / plan_arg
    if candidate2.exists():
        return candidate2
    raise parser_lib.ParseError(
        "PLAN_NOT_FOUND",
        f"plan '{plan_arg}' nao resolve. Tente path absoluto ou slug "
        f"existente em {PLANS_DIR}",
    )


def cmd_propose(args: argparse.Namespace) -> int:
    try:
        plan_path = _resolve_plan_path(args.plan)
        proposal = proposer_lib.build_proposal(
            plan_path=plan_path,
            cli_project_override=args.project_override,
            cli_target_sprint=args.target_sprint,
            actor=args.actor,
        )
    except parser_lib.ParseError as e:
        return _err(e.detail, e.code, args.json)
    except Exception as e:
        return _err(str(e), "proposer_failed", args.json)
    path = store.write_proposal(proposal)
    summary = {
        "ok": True,
        "proposal_id": proposal["proposal_id"],
        "path": str(path).replace("~/", "~/"),
        "total_tasks": proposal["total_tasks"],
        "total_phases": proposal["total_phases"],
        "epic_id": proposal["epic_id"],
        "wave_ref_root": proposal["wave_ref_root"],
        "warnings_count": len(proposal.get("_warnings", [])),
    }
    _print(
        summary, args.json,
        f"proposal created: {proposal['proposal_id']}\n"
        f"  path: {summary['path']}\n"
        f"  tasks: {proposal['total_tasks']} across {proposal['total_phases']} phases\n"
        f"  epic: {proposal['epic_id']} / {proposal['wave_ref_root']}\n"
        f"  warnings: {summary['warnings_count']}",
    )
    return EXIT_OK
```

- [ ] **Step 2: Sanity invocation via python3 -m (shortcut antes do parser)**

```bash
cd ~/.openclaw/scrum-master-agent && PYTHONPATH=. python3 -c "
from lib.api import _resolve_plan_path
p = _resolve_plan_path('2026-04-19-e5-f4-kanban-dev-lifecycle-plan')
assert p.exists()
print('OK resolves slug:', p.name)
"
```

Expected: `OK resolves slug: 2026-04-19-e5-f4-kanban-dev-lifecycle-plan.md`.

### Task 6.2: `cmd_list`, `cmd_show`, `cmd_reject`

**Files:**
- Modify: `~/.openclaw/scrum-master-agent/lib/api.py`

- [ ] **Step 1: Adicionar handlers em api.py**

```python
def cmd_list(args: argparse.Namespace) -> int:
    proposals = store.list_proposals(status_filter=args.status)
    if args.json:
        _print({"proposals": proposals}, True)
        return EXIT_OK
    if not proposals:
        print("(nenhum proposal)")
        return EXIT_OK
    print(f"{'ID':60s} {'STATUS':10s} TASKS EPIC/WAVE")
    for p in proposals:
        print(
            f"{p['proposal_id'][:60]:60s} {p['_computed_status']:10s} "
            f"{p['total_tasks']:5d} {p['wave_ref_root']}"
        )
    return EXIT_OK


def cmd_show(args: argparse.Namespace) -> int:
    try:
        proposal = store.read_proposal(args.proposal_id)
    except FileNotFoundError as e:
        return _err(str(e), "PROPOSAL_NOT_FOUND", args.json)
    _print(proposal, args.json)
    return EXIT_OK


def cmd_reject(args: argparse.Namespace) -> int:
    try:
        proposal = store.read_proposal(args.proposal_id)
    except FileNotFoundError as e:
        return _err(str(e), "PROPOSAL_NOT_FOUND", args.json)
    state = proposal["state"]
    if state.get("accepted_at"):
        return _err(
            f"proposal {args.proposal_id} ja aceita em {state['accepted_at']}",
            "PROPOSAL_ALREADY_ACCEPTED", args.json,
        )
    if state.get("rejected_at"):
        return _err(
            f"proposal {args.proposal_id} ja rejeitada em {state['rejected_at']}",
            "PROPOSAL_ALREADY_REJECTED", args.json,
        )
    state["rejected_at"] = store.now_iso()
    state["rejected_reason"] = args.reason
    store.update_proposal(proposal)
    _print(
        {"ok": True, "proposal_id": args.proposal_id}, args.json,
        f"rejected: {args.proposal_id}\n  reason: {args.reason}",
    )
    return EXIT_OK
```

- [ ] **Step 2: Sanity list/show/reject**

```bash
cd ~/.openclaw/scrum-master-agent && PYTHONPATH=. python3 -c "
from lib import store, api
import argparse
# Fixture: create proposal
p = {'schema_version': 1, 'proposal_id': 'test-show-1',
     'plan_ref': 'x', 'total_tasks': 3, 'total_phases': 1,
     'epic_id': 'E0', 'wave_ref_root': 'E0/test',
     'tasks': [], 'state': {'proposed_at': '2026-01-01T00:00:00Z',
                            'accepted_at': None, 'rejected_at': None}}
store.write_proposal(p)

# list
ns = argparse.Namespace(status='pending', json=False, actor='bernard')
api.cmd_list(ns)

# show
ns = argparse.Namespace(proposal_id='test-show-1', json=True, actor='bernard')
api.cmd_show(ns)

# reject
ns = argparse.Namespace(proposal_id='test-show-1', reason='teste',
                         json=False, actor='bernard')
api.cmd_reject(ns)

# verify rejected
p2 = store.read_proposal('test-show-1')
assert p2['state']['rejected_reason'] == 'teste'
print('OK')

# cleanup
import os
os.unlink('~/.openclaw/scrum-master-agent/proposals/test-show-1.json')
"
```

Expected: listagem do proposal, JSON dump, `rejected: ...`, `OK`.

### Task 6.3: `cmd_diff` (preview)

**Files:**
- Modify: `~/.openclaw/scrum-master-agent/lib/api.py`

- [ ] **Step 1: Adicionar `cmd_diff`**

```python
def cmd_diff(args: argparse.Namespace) -> int:
    try:
        proposal = store.read_proposal(args.proposal_id)
    except FileNotFoundError as e:
        return _err(str(e), "PROPOSAL_NOT_FOUND", args.json)
    tasks = proposal["tasks"]
    if args.json:
        _print({
            "proposal_id": proposal["proposal_id"],
            "target_sprint": proposal["target_sprint"],
            "total_tasks": proposal["total_tasks"],
            "preview_cli": [
                f"cli.sh task add \"{t['title']}\" --sprint {t['sprint_target']} "
                f"--project {t['project']} --epic {t['epic_id']} "
                f"--wave {t['wave_ref']}"
                for t in tasks
            ],
        }, True)
        return EXIT_OK
    print(f"proposal: {proposal['proposal_id']}")
    print(f"  target_sprint: {proposal['target_sprint']}")
    print(f"  epic: {proposal['epic_id']} / {proposal['wave_ref_root']}")
    print(f"  total: {proposal['total_tasks']} tasks")
    print()
    print("Materialization preview (cli.sh invocations):")
    for t in tasks:
        print(
            f"  task add \"{t['title'][:60]}\" "
            f"--sprint {t['sprint_target']} --project {t['project']} "
            f"--epic {t['epic_id']} --wave {t['wave_ref']}"
        )
    return EXIT_OK
```

### Task 6.4: argparse wiring

**Files:**
- Modify: `~/.openclaw/scrum-master-agent/lib/api.py`

- [ ] **Step 1: Adicionar `build_parser` + `main` ao final**

```python
def build_parser() -> argparse.ArgumentParser:
    common = argparse.ArgumentParser(add_help=False)
    common.add_argument("--json", action="store_true", help="JSON output")
    common.add_argument("--actor", default="bernard", help="actor identity")

    p = argparse.ArgumentParser(prog="scrum-master-agent")
    sub = p.add_subparsers(dest="cmd", required=True)

    def leaf(psub, name):
        return psub.add_parser(name, parents=[common])

    # propose
    prop = leaf(sub, "propose")
    prop.add_argument("--plan", required=True, help="plan slug ou path absoluto")
    prop.add_argument("--target-sprint", default="next",
                      help="sprint alvo (current|next|<sprint-id>); default next")
    prop.add_argument("--project-override", default=None,
                      help="escape pra AMBIGUOUS_PROJECT")
    prop.set_defaults(func=cmd_propose)

    # list
    ls = leaf(sub, "list")
    ls.add_argument("--status", default="pending",
                    choices=["pending", "accepted", "rejected", "all"])
    ls.set_defaults(func=cmd_list)

    # show
    sh = leaf(sub, "show")
    sh.add_argument("proposal_id")
    sh.set_defaults(func=cmd_show)

    # diff
    df = leaf(sub, "diff")
    df.add_argument("proposal_id")
    df.set_defaults(func=cmd_diff)

    # reject
    rj = leaf(sub, "reject")
    rj.add_argument("proposal_id")
    rj.add_argument("--reason", required=True, help="motivo da rejeicao")
    rj.set_defaults(func=cmd_reject)

    # accept (stub; materializer na Phase 7)
    acc = leaf(sub, "accept")
    acc.add_argument("proposal_id")
    acc.add_argument("--ready", action="store_true",
                     help="cria tasks diretamente como ready (default backlog)")
    acc.add_argument("--force-plan-drift", action="store_true")
    acc.set_defaults(func=cmd_accept_stub)

    return p


def cmd_accept_stub(args: argparse.Namespace) -> int:
    """Placeholder até Phase 7. Erra explícito."""
    return _err(
        "accept not yet wired (Phase 7 of plan)", "NOT_IMPLEMENTED", args.json,
    )


def main(argv=None) -> int:
    p = build_parser()
    args = p.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 2: Sanity invoking via cli.sh**

```bash
~/.openclaw/scrum-master-agent/cli.sh list
echo "---"
~/.openclaw/scrum-master-agent/cli.sh list --json
```

Expected: `(nenhum proposal)` + `{"proposals": []}` (se proposals/ vazio).

---

## Phase 7: Materializer (accept all-or-nothing)

### Task 7.1: `lib/materializer.py` — validate + drift check

**Files:**
- Create: `~/.openclaw/scrum-master-agent/lib/materializer.py`

- [ ] **Step 1: Criar materializer.py**

```python
"""Accept = materializa proposal no kanban-tasks via CLI existente."""

import json
import subprocess
from pathlib import Path
from typing import Any, Dict, List, Optional

from . import store
from . import proposer as proposer_lib


KANBAN_CLI = Path("~/.openclaw/kanban-tasks/cli.sh")


class MaterializerError(Exception):
    def __init__(self, code: str, detail: str):
        self.code = code
        self.detail = detail
        super().__init__(f"{code}: {detail}")


def _run_kanban(args: List[str], actor: str) -> Dict[str, Any]:
    """Invoca cli.sh kanban-tasks com --json --actor; devolve payload parseado."""
    cmd = [str(KANBAN_CLI)] + args + ["--json", "--actor", actor]
    result = subprocess.run(
        cmd, capture_output=True, text=True, check=False, timeout=30,
    )
    if result.returncode != 0:
        raise MaterializerError(
            "KANBAN_CLI_FAILED",
            f"cmd {' '.join(cmd)} exit={result.returncode}; "
            f"stderr={result.stderr[:200]}",
        )
    try:
        return json.loads(result.stdout)
    except json.JSONDecodeError as e:
        raise MaterializerError(
            "KANBAN_CLI_BAD_JSON",
            f"stdout nao eh JSON: {result.stdout[:200]} err={e}",
        )


def _validate_and_drift_check(
    proposal: Dict[str, Any],
    force_plan_drift: bool,
) -> List[str]:
    """Retorna lista de warnings. Raises em erros fatais."""
    warnings: List[str] = []
    state = proposal["state"]
    if state.get("accepted_at"):
        raise MaterializerError(
            "PROPOSAL_ALREADY_ACCEPTED",
            f"ja aceita em {state['accepted_at']}",
        )
    if state.get("rejected_at"):
        raise MaterializerError(
            "PROPOSAL_ALREADY_REJECTED",
            f"ja rejeitada em {state['rejected_at']}",
        )
    # Drift check
    plan_ref = proposal["plan_ref"].replace("~/", "~/")
    plan_path = Path(plan_ref).expanduser()
    recomputed_sha = proposer_lib._plan_sha(plan_path)
    saved_sha = proposal.get("plan_sha")
    if saved_sha is None:
        warnings.append("plan_sha=null (plan not under git); drift check skipped")
    elif recomputed_sha != saved_sha:
        if not force_plan_drift:
            raise MaterializerError(
                "PLAN_DRIFT",
                f"plan sha mudou: saved={saved_sha} atual={recomputed_sha}. "
                f"Use --force-plan-drift ou re-proponha.",
            )
        warnings.append(
            f"plan_drift_forced: saved={saved_sha} atual={recomputed_sha}"
        )
    return warnings


def _materialize_single(
    task: Dict[str, Any],
    prov_to_real: Dict[str, str],
    make_ready: bool,
    actor: str,
) -> str:
    """Materializa 1 task: cli.sh task add + set-dispatch-payload + optional move.

    Retorna task_id real criado. Atualiza prov_to_real mapping in-place.
    """
    add_args = [
        "task", "add", task["title"],
        "--sprint", task["sprint_target"],
        "--project", task["project"],
        "--epic", task["epic_id"],
        "--wave", task["wave_ref"],
    ]
    if task.get("description"):
        add_args += ["--description", task["description"]]
    result = _run_kanban(add_args, actor=actor)
    real_id = result["task"]["id"]
    prov_to_real[task["provisional_id"]] = real_id

    # Resolve depends_on (se presente) provisional → real
    payload = dict(task.get("dispatch_payload", {}))
    if "depends_on" in payload and isinstance(payload["depends_on"], list):
        resolved_deps: List[str] = []
        for d in payload["depends_on"]:
            if d in prov_to_real:
                resolved_deps.append(prov_to_real[d])
            else:
                # Dep aponta pra task ainda nao materializada ou ID real externo
                resolved_deps.append(d)
        payload["depends_on"] = resolved_deps

    # set-dispatch-payload
    _run_kanban(
        ["task", "set-dispatch-payload", real_id,
         "--payload", json.dumps(payload)],
        actor=actor,
    )

    if make_ready:
        _run_kanban(
            ["task", "move", real_id, "ready"],
            actor=actor,
        )

    return real_id


def materialize(
    proposal: Dict[str, Any],
    make_ready: bool,
    force_plan_drift: bool,
    actor: str,
) -> Dict[str, Any]:
    """Roda accept flow completo. Retorna summary com warnings + task_ids."""
    warnings = _validate_and_drift_check(proposal, force_plan_drift)

    prov_to_real: Dict[str, str] = {}
    created: List[str] = []
    failed_at: Optional[Dict[str, Any]] = None

    try:
        for idx, task in enumerate(proposal["tasks"], start=1):
            try:
                real_id = _materialize_single(
                    task, prov_to_real, make_ready, actor,
                )
                created.append(real_id)
            except Exception as e:
                failed_at = {
                    "index": idx,
                    "provisional_id": task.get("provisional_id"),
                    "error": str(e),
                }
                break
    finally:
        # Update proposal state regardless (partial ou full)
        proposal["state"]["materialized_task_ids"] = created
        if failed_at is None:
            proposal["state"]["accepted_at"] = store.now_iso()
            proposal["state"]["accepted_by"] = actor
        store.update_proposal(proposal)

    if failed_at is not None:
        raise MaterializerError(
            "PARTIAL_MATERIALIZATION",
            f"falhou na task {failed_at['index']} "
            f"({failed_at['provisional_id']}): {failed_at['error']}. "
            f"Criadas antes: {created}. "
            f"Proposal NAO marcada accepted. Manualmente arquive "
            f"ou re-proponha plan ajustado.",
        )

    return {
        "ok": True,
        "proposal_id": proposal["proposal_id"],
        "materialized_task_ids": created,
        "total_materialized": len(created),
        "warnings": warnings,
    }
```

- [ ] **Step 2: Sanity import + wire no api.py**

Substituir `cmd_accept_stub` em `lib/api.py` por:

```python
def cmd_accept(args: argparse.Namespace) -> int:
    try:
        proposal = store.read_proposal(args.proposal_id)
    except FileNotFoundError as e:
        return _err(str(e), "PROPOSAL_NOT_FOUND", args.json)
    from . import materializer as mlib
    try:
        result = mlib.materialize(
            proposal,
            make_ready=args.ready,
            force_plan_drift=args.force_plan_drift,
            actor=args.actor,
        )
    except mlib.MaterializerError as e:
        return _err(e.detail, e.code, args.json)
    _print(
        result, args.json,
        f"accepted: {args.proposal_id}\n"
        f"  materialized: {result['total_materialized']} tasks\n"
        f"  ids: {', '.join(result['materialized_task_ids'][:5])}"
        f"{'...' if result['total_materialized'] > 5 else ''}\n"
        f"  warnings: {len(result['warnings'])}",
    )
    return EXIT_OK
```

E mude `acc.set_defaults(func=cmd_accept_stub)` pra `acc.set_defaults(func=cmd_accept)`. Remova `cmd_accept_stub`.

- [ ] **Step 3: Sanity import**

```bash
cd ~/.openclaw/scrum-master-agent && PYTHONPATH=. python3 -c "
from lib import api, materializer
assert hasattr(materializer, 'materialize')
p = api.build_parser()
ns = p.parse_args(['accept', 'test-1'])
assert ns.func.__name__ == 'cmd_accept'
print('OK')
"
```

Expected: `OK`.

---

## Phase 8: Canonical artifacts (`bevox-knowledge/`)

### Task 8.1: Playbook canonical

**Files:**
- Create: `~/bevox-knowledge/20_architecture/agents/scrum-master-agent.md`

- [ ] **Step 1: Escrever playbook espelhando `delivery-status-agent.md`**

```markdown
<!-- Agent file do Scrum Master Agent — primeira wave do PRD
     "OpenClaw Task-Orchestrated Development for Claude Code".
     Criado a partir de _template.md (E3) + pattern Hub-dispatch
     estabelecido por delivery-status-agent (2026-04-17).

     Modo operacional: Hub-dispatch (ver CREATING.md §7.3).
     Spec canonica: 35_specs/2026-04-19-e10-scrum-master-agent.md.
     Design canonico: 30_adr/ADR-003-agent-governance.md.
     Policy canonica: 30_adr/ADR-006-autonomy-permissions-approval.md.

     Identidade canonica: scrum-master-agent.
     Agente entrando em L1 novo.
     Zero TBDs pendentes.
-->

# Agent: scrum-master-agent

> Runbook canonico do Scrum Master Agent. Spec:
> `35_specs/2026-04-19-e10-scrum-master-agent.md`. Design:
> `30_adr/ADR-003-agent-governance.md`. Policy de autonomia:
> `30_adr/ADR-006-autonomy-permissions-approval.md`. Source of truth
> dos campos de metadata: `20_architecture/agents/registry.yml`.

- **Owner:** <!-- DERIVED: registry.yml -> agents.scrum-master-agent.owner --> Bernard
- **Status:** <!-- DERIVED: registry.yml -> agents.scrum-master-agent.status --> ativo
- **Level:** <!-- DERIVED: registry.yml -> agents.scrum-master-agent.level --> L1
- **Modelo padrao:** <!-- DERIVED: registry.yml -> agents.scrum-master-agent.model.primary --> stdlib-python/no-model
- **Modelo fallback:** <!-- DERIVED: registry.yml -> agents.scrum-master-agent.model.fallback --> none
- **Criado em:** <!-- DERIVED: registry.yml -> agents.scrum-master-agent.since --> 2026-04-19

## Missao

Projetar implementation plans (produto de `superpowers:writing-plans`)
em tasks operacionais do kanban-tasks, preservando metadata via
`dispatch_payload` estruturado. Agente eh **coordenador**; NAO escreve
codigo, NAO executa tasks.

## Inputs

- **Invocacao explicita do Bernard**: `vox scrum-master propose --plan
  <slug-ou-path>` via Hub-dispatch (CLI host-local direto ou via Vox
  carregando o playbook como working context).
- **Plan file obrigatorio** em `~/.openclaw/docs/superpowers/plans/`.
  Plans sem header `**Epico:**` sao recusados com
  `PLAN_MISSING_EPIC`.

## Outputs

- **Proposal JSON estruturada** em
  `~/.openclaw/scrum-master-agent/proposals/<timestamp>-<slug>.json`,
  com schema conforme spec §7.
- **Nenhuma mutacao direta** em bevox-knowledge, delivery-tracker,
  ou qualquer arquivo canonico.
- **Apos accept humano**, materializacao no kanban-tasks via CLI
  existente + novo subcmd `task set-dispatch-payload`.
- **Linha de dispatch** em `~/.openclaw/workspace/shared/outputs/
  agent-dispatch.jsonl` por OPERATING_RULES §Log.

## Skills

- Leitura de plan + spec + tracker + registry.
- Shell tool para invocar `cli.sh` do kanban-tasks.
- `git` read (log, show) no clone de bevox-knowledge pra capturar
  plan_sha e validar epic/wave.
- Nenhuma skill externa nova.

## Limites

1. **UMA proposta por invocacao.** Proposal_id unico por timestamp + slug;
   reinvocacao com mesmo plan gera ID diferente.
2. **Accept all-or-nothing.** Sem partial accept. Rejeicao + reproposta
   eh o caminho pra ajustar.
3. **Escrita estritamente local.** Proposals em host-local, tasks
   materializadas no kanban host-local. NAO muta canonico.
4. **Input plan obrigatorio.** NAO aceita spec direto (skill
   `superpowers:writing-plans` eh pre-requisito).
5. **NUNCA inventa acceptance_criteria.** Extrai de `Expected:` lines
   do plan. Ausencia vira AC vazia (warning no summary).
6. **NUNCA reexecuta propose idempotente.** Cada invocacao cria novo
   proposal_id. Bernard eh responsavel por rejeitar proposals antigos
   se repropos.
7. Hard limits gerais (ADR-006) aplicam.

## Approvals

Modo Hub-dispatch; sem sessao runtime propria, sem entry em
`exec-approvals.json`. Gate eh `vox scrum-master accept <id>` (CLI
explicito do Bernard). Nao usa knowledge-sync canonical flow
(proposal eh host-local, NAO muta canonico; materializacao eh
operacional via kanban CLI).

Hard limits gerais do Vox aplicam em cima deste playbook.
Dispatch registrado em
`~/.openclaw/workspace/shared/outputs/agent-dispatch.jsonl`.

## KPIs

- **Proposals geradas por semana**: contagem de arquivos em `proposals/`
  com `proposed_at` em janela de 7 dias.
- **Taxa de acceptance**: `accepted_at != null` / total proposals.
- **Time-to-accept**: mediana de (accepted_at - proposed_at).
- **AMBIGUOUS_PROJECT rate**: quantas invocacoes de `propose` falham
  com esse erro — sinal de plan headers incompletos.
- **--project-override usage**: >30% sustentado = review do playbook
  ou dos plans producers.
- **Frequencia de revisao**: mensal. Primeira revisao 2026-05-19.

## Playbook operacional

Quando Bernard invoca `vox scrum-master propose --plan <slug>`:

### Passo 1 — Registrar dispatch

Append em `~/.openclaw/workspace/shared/outputs/agent-dispatch.jsonl`:

```json
{
  "ts": "<ISO8601 UTC>",
  "playbook": "scrum-master-agent",
  "source": "explicit",
  "request_summary": "propose from plan <slug>",
  "session_id": "<canal ou null>"
}
```

### Passo 2 — Resolver plan

Aceita slug ou path absoluto. Slug = `<slug>.md` em
`~/.openclaw/docs/superpowers/plans/`. Falhar com `PLAN_NOT_FOUND`
se nao resolver.

### Passo 3 — Parsear plan

- Header obrigatorio: `**Epico:** <epic>/<wave>`. Sem, `PLAN_MISSING_EPIC`.
- Opcional: `**Project:**` ou `**Projects:**`. Sem, derive per-task.
- Phases: `^## Phase N: Name`. Sem nenhuma, `NO_PHASES_FOUND`.
- Tasks: `^### Task N.M: Subject`. Sem, `NO_TASKS_FOUND`.

### Passo 4 — Derivar project (per task)

Rules deterministicas (spec §5.3):
1. plan-level `Project:` → todas tasks.
2. per-task `**Files:**` paths → mapa canonico (§5.3 spec).
3. `--project-override` escape.
4. None resolvido → `AMBIGUOUS_PROJECT`.

### Passo 5 — Montar proposal

Schema §7 da spec. Populado:
- `epic_id`, `wave_ref_root` do header.
- `task.wave_ref = <wave_ref_root>/Phase-<N>` (AJUSTE #1).
- `task.dispatch_payload` com AC, files_relevant, spec_refs, goal.
- `plan_sha` via `git log -1 <plan>` (null se nao sob git).

### Passo 6 — Escrever proposal

`~/.openclaw/scrum-master-agent/proposals/<proposal_id>.json`,
atomic write.

### Passo 7 — Retornar summary

Mostrar: proposal_id, total_tasks, total_phases, epic_id,
warnings_count.

### Accept flow (invocado separado por Bernard)

1. Validate: `accepted_at`/`rejected_at` must be null.
2. Plan drift check: re-compute plan_sha; comparar com
   `proposal.plan_sha`. Se diverge e sem `--force-plan-drift`, erro.
3. Per task, em ordem:
   a. `cli.sh task add ... --actor scrum-master`
   b. `cli.sh task set-dispatch-payload <id> --payload <json>`
   c. Se `--ready`, `cli.sh task move <id> ready`
4. Se qualquer step falha: marca proposal com `materialized_task_ids`
   parcial, NAO seta `accepted_at`. Erro `PARTIAL_MATERIALIZATION`.
5. Se sucesso: `accepted_at = now`, `materialized_task_ids` completo.

## Boundary com outros agentes

| Identidade | Dominio | Modo |
|---|---|---|
| `delivery-agent` (E5) | propor work items das specs ativas | runtime L1 (systemd timer) |
| `delivery-status-agent` (E10) | flip status no delivery-tracker.yml | Hub-dispatch + knowledge-sync |
| `scrum-master-agent` (E10) | projetar plan → kanban tasks | Hub-dispatch + kanban CLI |

Os 3 operam em paralelo, sem acoplamento.
`scrum-master-agent` NAO consome outputs do `delivery-agent` ou do
`delivery-status-agent`.

## Volume minimo

Volume minimo para manter L1: **pelo menos 1 proposal por mes**
(natural ou sintetico). Abaixo, revisar.

Promocao L1→L2 (ADR-003 §Fase 4): **pelo menos 2 proposals por
semana por 4 semanas consecutivas**, taxa accept ≥ 75%, zero
`PARTIAL_MATERIALIZATION` em 10 accepts consecutivos.

## Historico de levels

- L1 desde 2026-04-19
```

### Task 8.2: Registry entry + re-render

**Files:**
- Modify: `~/bevox-knowledge/20_architecture/agents/registry.yml`
- Regenerate: `~/bevox-knowledge/20_architecture/agents/registry.md`

- [ ] **Step 1: Adicionar entry em `registry.yml`**

Localizar a linha `  product-agent:` (ordem alfabética — `scrum-master-agent` vai entre `product-agent` e `documentation-agent` no alfabeto, mas a regra é ordem alfabética por chave). Verificar `render-registry.py` re-ordena. Adicionar em qualquer posição razoável, ex: após `product-agent`:

```yaml
  product-agent:
    status: ativo
    level: L1
    owner: Bernard
    model:
      primary: openai-codex/gpt-5.4
      fallback: openrouter/healer-alpha
    since: 2026-04-11
    file: product-agent.md
  scrum-master-agent:
    status: ativo
    level: L1
    owner: Bernard
    model:
      primary: stdlib-python/no-model
      fallback: none
    since: 2026-04-19
    file: scrum-master-agent.md
```

- [ ] **Step 2: Re-render registry.md**

```bash
cd ~/bevox-knowledge
./20_architecture/agents/_tools/render-registry.py
git status -s 20_architecture/agents/registry.md
```

Expected: `registry.md` modificado, `registry.yml` staged.

- [ ] **Step 3: Sanity check — entry aparece em registry.md**

```bash
grep -A 2 "scrum-master-agent" ~/bevox-knowledge/20_architecture/agents/registry.md | head -10
```

Expected: linha com `scrum-master-agent` presente.

### Task 8.3: Delivery-tracker entry

**Files:**
- Modify: `~/bevox-knowledge/40_roadmap/delivery-tracker.yml`

- [ ] **Step 1: Adicionar wave em E10**

Localizar o bloco E10 (grep `^  - id: E10`). Dentro do `waves:`, após `- id: delivery-status-agent` (que vem pós `wave-2`), adicionar:

```yaml
      - id: scrum-master-agent
        status: delivered
        delivered_at: 2026-04-XX  # preencher data real no final
        features:
          - "Hub-dispatch supervisionado que le implementation plan (produto de superpowers:writing-plans) e propoe materializacao 1:1 como tasks do kanban-tasks"
          - "projecao 1 plan Task = 1 kanban task; phases viram wave_ref suffix (<plan.epic>/<plan.wave>/Phase-N) apontando pra wave do trabalho (nao pra wave do agente)"
          - "project derivation deterministica: plan-level `**Project:**` -> per-task path map -> `--project-override` -> erro AMBIGUOUS_PROJECT"
          - "proposal persistida em ~/.openclaw/scrum-master-agent/proposals/<id>.json; atomic write; imutavel apos escrita"
          - "accept all-or-nothing (sem partial accept); rejeicao + repropose = ajuste"
          - "plan drift check via git SHA comparado com plan_sha na proposta; --force-plan-drift explicit"
          - "enabling delta minimo no kanban-tasks: novo cmd `task set-dispatch-payload` (write-path pra slot reservado wave-3), novo event task_dispatch_payload_set"
          - "default status=backlog; flag --ready materializa ja como ready"
        spec: 35_specs/2026-04-19-e10-scrum-master-agent.md
```

### Task 8.4: Commit canonical (playbook + registry + tracker)

**Files:**
- Stage: 4 files em bevox-knowledge
- Commit

- [ ] **Step 1: Stage + commit**

```bash
cd ~/bevox-knowledge
git add 20_architecture/agents/scrum-master-agent.md \
        20_architecture/agents/registry.yml \
        20_architecture/agents/registry.md \
        40_roadmap/delivery-tracker.yml
git status -s
```

Expected: 4 files staged. READMEs e outras modificações prévias ficam fora do stage.

- [ ] **Step 2: Commit**

```bash
git commit -m "$(cat <<'EOF'
feat(E10): scrum-master-agent wave delivered

Primeira wave do PRD "OpenClaw Task-Orchestrated Development for
Claude Code". Hub-dispatch supervisionado que lê implementation plan
e propõe materialização 1:1 como tasks do kanban-tasks.

- Playbook canonical: 20_architecture/agents/scrum-master-agent.md
- Registry: nova entry L1 (stdlib-python/no-model)
- Tracker: E10/scrum-master-agent delivered

Módulo operacional em ~/.openclaw/scrum-master-agent/ (host-local,
fora do git). Enabling delta mínimo no kanban-tasks (cmd
set-dispatch-payload + event type) também host-local.

Spec: 35_specs/2026-04-19-e10-scrum-master-agent.md (commit 2ac8527)
Plan: ~/.openclaw/docs/superpowers/plans/2026-04-19-e10-scrum-master-agent-plan.md

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
git log --oneline -3
```

---

## Phase 9: Smoke E2E dogfood — scrum-master contra plan F4 wave-3

### Task 9.1: Adicionar `**Epico:**` no plan F4 wave-3 (one-line fix)

**Files:**
- Modify: `~/.openclaw/docs/superpowers/plans/2026-04-19-e5-f4-kanban-dev-lifecycle-plan.md`

- [ ] **Step 1: Adicionar linha de Epico após `**Tech Stack:**`**

Localizar `**Tech Stack:**` no header. Adicionar em linha subsequente (antes do `**Specs canonicas:**`):

```markdown
**Epico:** E5/F4-kanban-dev-lifecycle
```

Se o plan já tem `**Projects:**` multi-repo (scope F4 wave-3 cruza openclaw + mission-control), confirma com grep. Senão adicionar:

```bash
grep -E "\*\*(Epico|Project|Projects):\*\*" ~/.openclaw/docs/superpowers/plans/2026-04-19-e5-f4-kanban-dev-lifecycle-plan.md
```

Expected: `**Epico:** E5/F4-kanban-dev-lifecycle` listado.

Se `Projects:` ainda não estiver, Bernard pode adicionar manualmente OU usar `--project-override` (tarefas cruzadas viriam todas com mesmo project — não ideal, mas funcional pra dogfood).

### Task 9.2: `propose` contra plan F4 wave-3

**Files:** none (invocação)

- [ ] **Step 1: Propose**

```bash
~/.openclaw/scrum-master-agent/cli.sh propose \
  --plan 2026-04-19-e5-f4-kanban-dev-lifecycle-plan \
  --target-sprint next
```

Expected: `proposal created: <timestamp>-...`, `tasks: 30+ across 8+ phases`, `epic: E5 / E5/F4-kanban-dev-lifecycle`.

Se der `AMBIGUOUS_PROJECT`: plan cruza múltiplos repos e não tem `**Project:**` single. Re-invocar com:

```bash
~/.openclaw/scrum-master-agent/cli.sh propose \
  --plan 2026-04-19-e5-f4-kanban-dev-lifecycle-plan \
  --project-override openclaw
```

(Tasks mission-control nascerão com project=openclaw erroneamente — dogfood apenas; não aceitar.)

### Task 9.3: Inspect proposta

- [ ] **Step 1: List + show + diff**

```bash
~/.openclaw/scrum-master-agent/cli.sh list
PID=$(~/.openclaw/scrum-master-agent/cli.sh list --json | python3 -c "import json,sys; print(json.load(sys.stdin)['proposals'][0]['proposal_id'])")
echo "proposal_id: $PID"
~/.openclaw/scrum-master-agent/cli.sh show $PID --json | python3 -c "
import json, sys
p = json.load(sys.stdin)
print(f'total_tasks: {p[\"total_tasks\"]}')
print(f'wave_ref_root: {p[\"wave_ref_root\"]}')
t0 = p['tasks'][0]
print(f'task[0] title: {t0[\"title\"]}')
print(f'task[0] wave_ref: {t0[\"wave_ref\"]}')
print(f'task[0] project: {t0[\"project\"]}')
print(f'task[0] dispatch_payload keys: {list(t0[\"dispatch_payload\"].keys())}')
assert t0['wave_ref'].startswith('E5/F4-kanban-dev-lifecycle/Phase-')
"
~/.openclaw/scrum-master-agent/cli.sh diff $PID | head -10
```

Expected: proposal_id impresso, task[0] inspeciona com wave_ref correto (`E5/F4-kanban-dev-lifecycle/Phase-0`), diff mostra preview das invocações `cli.sh task add`.

### Task 9.4: `reject` (dogfood; não aceitar de verdade)

- [ ] **Step 1: Reject pra limpar**

Se Bernard quer testar o fluxo completo mas **não** materializar (plan F4 wave-3 já está feito — não queremos duplicar tasks):

```bash
~/.openclaw/scrum-master-agent/cli.sh reject $PID --reason "dogfood: plan ja entregue, nao materializar"
~/.openclaw/scrum-master-agent/cli.sh list --status rejected
```

Expected: proposal marcada como rejected na listagem.

Se Bernard **quer** materializar (ex: criar tasks representando o próprio work já feito, pra ter audit trail do dogfood):

```bash
~/.openclaw/scrum-master-agent/cli.sh accept $PID
```

Expected: `accepted: ...`, `materialized: 30+ tasks`, IDs criados.

Decisão: **reject** pra não poluir o sprint. Bernard valida o fluxo sem side-effects.

### Task 9.5: Sanity final

- [ ] **Step 1: Verificar artefatos criados**

```bash
ls ~/.openclaw/scrum-master-agent/proposals/
ls ~/.openclaw/scrum-master-agent/lib/
~/.openclaw/scrum-master-agent/cli.sh --help 2>&1 | head
```

Expected: proposal JSON presente (status rejected), lib files todos presentes, help text visível.

- [ ] **Step 2: Verificar kanban rebuild ainda determinístico (wave-3 F4)**

```bash
cd ~/.openclaw/kanban-tasks
cp state.json /tmp/state.scrum9.json
./cli.sh rebuild
diff <(python3 -c "import json; s=json.load(open('/tmp/state.scrum9.json')); s.pop('generated_at',None); print(json.dumps(s, sort_keys=True, indent=2))") \
     <(python3 -c "import json; s=json.load(open('state.json')); s.pop('generated_at',None); print(json.dumps(s, sort_keys=True, indent=2))") \
  && echo REPLAY_OK
```

Expected: `REPLAY_OK`.

---

## Phase 10: Push gate humano

### Task 10.1: Mostrar o que está pronto pra push

**Files:** none (informativo)

- [ ] **Step 1: Summary bevox-knowledge**

```bash
echo '=== bevox-knowledge (main local) ==='
cd ~/bevox-knowledge
git log --oneline origin/main..HEAD
echo ''
echo '=== READMEs + specs untracked (NAO staged) ==='
git status -s | head -20
```

Expected:
- 2 commits ahead: `2ac8527 spec(E10): scrum-master-agent wave` + `<novo-sha> feat(E10): scrum-master-agent wave delivered` (+ possivelmente commits de F4 wave-3 anterior ainda não pushados: `4d955d8`, `2483df0`)
- READMEs + specs pre-existentes permanecem untracked/unstaged.

- [ ] **Step 2: Instruções para push**

```
Bernard decide:

Push agora:
  cd ~/bevox-knowledge && git push origin main

Pause e revisa:
  git diff origin/main..HEAD   # diff completo
  git show HEAD~1               # spec commit
  git show HEAD                 # feat commit

Rollback se algo estiver errado:
  git reset --soft HEAD~1       # desfaz último commit mantendo staged
```

### Task 10.2: Backfill `delivered_at` no tracker

**Files:**
- Modify: `~/bevox-knowledge/40_roadmap/delivery-tracker.yml`

- [ ] **Step 1: Substituir `2026-04-XX` pela data real do delivery**

Após Bernard decidir que delivery está completo:

```bash
cd ~/bevox-knowledge
sed -i "s/delivered_at: 2026-04-XX  # preencher data real no final/delivered_at: $(date +%Y-%m-%d)/" \
    40_roadmap/delivery-tracker.yml
git diff 40_roadmap/delivery-tracker.yml | head -5
git add 40_roadmap/delivery-tracker.yml
git commit --amend --no-edit
```

Expected: commit HEAD amend'd com data real; 1 line changed.

### Task 10.3: Atualizar memory projeto scrum-master

**Files:**
- Create: `~/.claude/projects/-home-you--openclaw/memory/e10_scrum_master_agent_state.md`

- [ ] **Step 1: Criar memory entry**

```bash
cat > ~/.claude/projects/-home-you--openclaw/memory/e10_scrum_master_agent_state.md <<'EOF'
---
name: E10/scrum-master-agent — execution state
description: Status wave scrum-master-agent (Hub-dispatch + materialização plan→kanban)
type: project
---

## Checkpoint (2026-04-XX)

**Entregue localmente**. Push gate humano pendente pra bevox-knowledge.

- Spec canonizada: `35_specs/2026-04-19-e10-scrum-master-agent.md` (commit `2ac8527`)
- Playbook canonical: `20_architecture/agents/scrum-master-agent.md` (commit `<feat-sha>`)
- Registry entry + re-render
- Delivery-tracker: E10/scrum-master-agent delivered

## Módulo host-local (`~/.openclaw/scrum-master-agent/`)

- cli.sh entrypoint
- lib/ (parser, projects, proposer, materializer, store, api) — stdlib puro
- proposals/ dir (atomic write JSON files)
- playbook.md sync'd com canonical

## Enabling delta kanban-tasks

- `lib/task.py`: `set_dispatch_payload(task_id, payload, merge, actor)`
- `lib/api.py`: argparse `task set-dispatch-payload` + cmd handler + event `task_dispatch_payload_set`
- smoke_e2e.sh estendido

## Decisões travadas

- Projection: 1 plan Task = 1 kanban task
- wave_ref aponta pra wave do trabalho (`<plan.epic>/<plan.wave>/Phase-N`), não pra wave do agente
- Project derivation: plan-level → path map → --project-override → AMBIGUOUS_PROJECT
- Accept all-or-nothing
- Default status: backlog (flag --ready como escape)
- Enabling delta kanban na mesma wave (não separada)

## Dogfood validado

- `propose` contra plan F4 wave-3 (com `**Epico:**` adicionado no plan)
- proposal JSON gerada com wave_ref correto, dispatch_payload populado
- `reject` testado (não materializar — plan já entregue)
- rebuild idempotente preservado

## Próximas waves do PRD (fora desta spec)

- E10/dispatcher-agent (wave-2 PRD): próxima ready → handoff Claude Code
- E10/tester-agent (wave-3 PRD): testing → done/rejected
- E10/cron-scrum-master (wave-4 PRD): auto-propose restrito

## Push gate

Local `bevox-knowledge/main` tem 2 commits ahead de origin/main
(spec + feat). Bernard decide push quando satisfeito.
`~/.openclaw/scrum-master-agent/` é host-local, não git.
EOF
```

- [ ] **Step 2: Adicionar ao MEMORY.md index**

```bash
grep -q "e10_scrum_master_agent" ~/.claude/projects/-home-you--openclaw/memory/MEMORY.md && echo "WARN: ja no index" || \
  echo "- [E10/scrum-master-agent — execution state](e10_scrum_master_agent_state.md) — Hub-dispatch wave-1 PRD orchestration; push gate pendente" >> \
  ~/.claude/projects/-home-you--openclaw/memory/MEMORY.md
```

---

## Self-review (executado durante writing)

### Spec coverage
- §2 identidade (Hub-dispatch, L1, canonical doc, registry, módulo host-local): Phase 8 + 2 ✓
- §3 boundary + 3 canais mutação: Phase 2 (host-local) + Phase 8 (canonical) ✓
- §4 input (plan): Phase 3 parser + Phase 6 _resolve_plan_path ✓
- §5 derivation rules (wave_ref §5.2, project §5.3, dispatch_payload §5.4): Phase 3 + 4 + 5 ✓
- §6 CLI surface (propose/list/show/diff/accept/reject): Phase 6 + Phase 7 (accept) ✓
- §7 proposal JSON schema: Phase 5.1 _build_proposal shape ✓
- §8 accept flow all-or-nothing + partial handling: Phase 7.1 materializer ✓
- §9 enabling delta kanban: Phase 1 (task.py, api.py, event, smoke) ✓
- §10 playbook canonical content: Phase 8.1 ✓
- §11 registry entry: Phase 8.2 ✓
- §12 boundary com delivery-agent/delivery-status-agent: Phase 8.1 playbook + spec text ✓
- §13 DoD: Phase 9 dogfood + Phase 10 gate ✓
- §14 risks: all covered (drift check Phase 7.1, ambiguous project error Phase 4+5, partial materialization Phase 7.1) ✓

### Placeholder scan
- `2026-04-XX` em tracker + memory: explicitly marked as "preencher data real"; Phase 10.2 tem step pra fazer backfill ✓
- Nenhum TBD/TODO técnico não-resolvido

### Type consistency
- `set_dispatch_payload(task_id, payload, merge, actor)` consistente em Phase 1.1 lib + 1.2 api + 7.1 materializer ✓
- `proposal` shape: schema_version, proposal_id, plan_ref, plan_sha, state.{proposed_at,accepted_at,rejected_at,materialized_task_ids} consistente entre Phase 5.1, 6.1, 7.1 ✓
- `wave_ref` formula `<wave_ref_root>/Phase-<N>` consistente Phase 5.1 + playbook Phase 8.1 + spec §5.2 ✓
- `_plan_sha` helper consistente Phase 5.1 (proposer) + 7.1 (materializer) ✓
- CLI subcmd nome `task set-dispatch-payload` consistente Phase 1.2 + 7.1 `_materialize_single` ✓

Nenhum drift identificado.

---

## Notas operacionais

- **Push gate humano (Phase 10)**: Bernard decide. Não automatizar.
- **Module host-local**: `~/.openclaw/scrum-master-agent/` NÃO é git repo. Não há commits pra código Python.
- **Playbook sync**: canonical em `bevox-knowledge/20_architecture/agents/scrum-master-agent.md` é SoT. Cópia host-local em `~/.openclaw/scrum-master-agent/playbook.md` — precisa sync manual ou via knowledge-sync (out of scope desta wave; Bernard copia manualmente após canonical commit).
- **Dogfood reject**: Phase 9.4 rejeita a proposta em vez de aceitar, evitando materializar 30+ tasks duplicadas no sprint atual.
- **Plan F4 wave-3 edit** (Phase 9.1): adiciona `**Epico:**` line no plan existente. Não altera funcionalidade, só torna plan consumível pelo scrum-master.
