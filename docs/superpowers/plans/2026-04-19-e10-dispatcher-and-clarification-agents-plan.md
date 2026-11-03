# E10 Dispatcher + Clarification Agents Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use `superpowers:subagent-driven-development` (recommended) or `superpowers:executing-plans` to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Entregar 2 agents Hub-dispatch L1 (dispatcher-agent + clarification-agent) que fecham o loop spec → execução com Bernard-zero-touch no happy path. Dispatcher invoca Claude Code em background detached; clarification responde dúvidas durante execução com confidence gate + auto-resolve safe.

**Architecture:** Dois módulos host-local em `~/.openclaw/dispatcher-agent/` e `~/.openclaw/clarification-agent/` (Python 3 stdlib + bash entrypoints, herda convenção F4). Subprocess `claude -p` como executor (dispatcher) e drafter (clarification). Comunicação cross-agent via `dispatch_payload` shallow merge no kanban + signal files. Zero novo backend (consume apenas hooks F4 wave-3 + scrum-master wave-1).

**Tech Stack:**
- Python 3 stdlib puro (zero pip install; decisão arquitetural §4.1 da spec)
- Bash entrypoints (`cli.sh`)
- `claude` CLI local (executor dispatcher + drafter clarification)
- `setsid + nohup` para detached subprocess
- JSON/jsonl para state
- Kanban CLI consumption (subprocess invocations)

**Specs canônicas:**
- Wave-2 (esta): `bevox-knowledge/35_specs/2026-04-19-e10-dispatcher-and-clarification-agents.md` (commit `85d4c04`)
- Dependência wave-1 PRD: `bevox-knowledge/35_specs/2026-04-19-e10-scrum-master-agent.md`
- Dependência F4 wave-3: `bevox-knowledge/35_specs/2026-04-19-e5-f4-kanban-dev-lifecycle.md`

**Plans pares (pattern reference):**
- Plan scrum-master: `~/.openclaw/docs/superpowers/plans/2026-04-19-e10-scrum-master-agent-plan.md`

**Constraint operacional:**
- **Zero pip install** em módulos host-local
- Zero novo backend (MC, kanban-tasks host-local inalterados)
- Tester-agent (wave-3 PRD), cron (wave-4 PRD), auto-close **EXPLICITAMENTE fora**
- Push canonical single-gate ao final (pattern scrum-master)
- Spike results (6 spikes 2026-04-19) são base técnica — não re-executar no plano

---

## File Structure

### Host-local — dispatcher-agent (novo)

```
~/.openclaw/dispatcher-agent/
├── cli.sh                          # entrypoint bash
├── lib/
│   ├── __init__.py                 # vazio
│   ├── store.py                    # I/O atômico (sessions, status.json, logs)
│   ├── selector.py                 # consome /next-ready + 1-task-per-project guard
│   ├── briefing.py                 # gera briefing.md a partir de dispatch_payload
│   ├── runner.py                   # subprocess detached/foreground `claude -p`
│   ├── lifecycle.py                # transitions + auto-move testing + execution_failed
│   └── api.py                      # argparse dispatcher
├── briefings/                      # runtime: briefings/<task-id>.md
├── executions/                     # runtime: executions/<task-id>.log + .status.json
├── playbook.md                     # cópia sync'd do canonical (Phase 12)
└── README.md
```

### Host-local — clarification-agent (novo)

```
~/.openclaw/clarification-agent/
├── cli.sh                          # entrypoint bash
├── lib/
│   ├── __init__.py
│   ├── store.py                    # I/O questions/, answers/, escalations/, signals/
│   ├── context_loader.py           # le spec_refs + plan_ref + ADRs citadas
│   ├── drafter.py                  # subprocess claude -p com prompt estruturado
│   ├── safety.py                   # confidence binary + escalation_reason + path validator
│   ├── lifecycle.py                # ask/draft/resolve cycle + block/unblock wiring
│   └── api.py                      # argparse
├── questions/                      # questions/<task-id>-clr-<seq>.md
├── answers/                        # answers/<task-id>-clr-<seq>.md (header confidence)
├── escalations/                    # escalations/<task-id>-clr-<seq>.md (symlinks)
├── signals/                        # signals/<clarification-id>.signal (file vazio quando answer ready)
├── playbook.md                     # cópia sync'd do canonical (Phase 12)
└── README.md
```

### Host-local — delta mínimo em kanban-tasks (inalterado)

Nenhum. Wave-2 consome apenas APIs existentes da F4 wave-3.

### Canonical (bevox-knowledge)

```
bevox-knowledge/
├── 20_architecture/agents/
│   ├── dispatcher-agent.md         # NOVO: playbook canonical
│   ├── clarification-agent.md      # NOVO: playbook canonical
│   ├── registry.yml                # MODIFICA: 2 entries L1
│   └── registry.md                 # REGENERADO via _tools/render-registry.py
└── 40_roadmap/
    └── delivery-tracker.yml        # MODIFICA: wave delivered em E10
```

---

## Phase 0: Pre-flight + defensive backup

### Task 0.1: Verificar escopo novo não existe

**Files:** none (read-only)

- [ ] **Step 1: Confirmar spec canonizada**

```bash
git -C ~/bevox-knowledge log --oneline -1 -- 35_specs/2026-04-19-e10-dispatcher-and-clarification-agents.md
```

Expected: commit `85d4c04` listado.

- [ ] **Step 2: Confirmar módulos host-local ainda não existem**

```bash
ls ~/.openclaw/dispatcher-agent 2>/dev/null && echo "WARN existe" || echo "OK dispatcher: pendente"
ls ~/.openclaw/clarification-agent 2>/dev/null && echo "WARN existe" || echo "OK clarification: pendente"
```

Expected: ambos "OK ... pendente".

- [ ] **Step 3: Confirmar dependências presentes**

```bash
ls ~/.openclaw/scrum-master-agent/cli.sh
ls ~/.openclaw/kanban-tasks/cli.sh
which claude
claude --version 2>&1 | head -2
```

Expected: scrum-master cli.sh existe, kanban cli.sh existe, `claude` CLI disponível, version listada.

- [ ] **Step 4: Confirmar hooks F4 wave-3 disponíveis**

```bash
~/.openclaw/kanban-tasks/cli.sh task set-dispatch-payload --help 2>&1 | head -3 || true
~/.openclaw/kanban-tasks/cli.sh task block --help 2>&1 | head -3 || true
```

Expected: help text sem erro (cmds existem).

### Task 0.2: Backup state kanban-tasks

**Files:** snapshot defensivo

- [ ] **Step 1: Backup state**

```bash
mkdir -p ~/.openclaw/backups/kanban-tasks
TS=$(date -Iseconds)
cp ~/.openclaw/kanban-tasks/state.json ~/.openclaw/backups/kanban-tasks/state.json.pre-wave2-prd.$TS
cp ~/.openclaw/kanban-tasks/events.jsonl ~/.openclaw/backups/kanban-tasks/events.jsonl.pre-wave2-prd.$TS
ls -la ~/.openclaw/backups/kanban-tasks/ | tail -4
```

Expected: 2 backup files criados.

---

## Phase 1: dispatcher-agent — skeleton

### Task 1.1: Criar dirs + README

**Files:**
- Create: `~/.openclaw/dispatcher-agent/` (dir)
- Create: `~/.openclaw/dispatcher-agent/lib/` (dir)
- Create: `~/.openclaw/dispatcher-agent/briefings/` (dir)
- Create: `~/.openclaw/dispatcher-agent/executions/` (dir)
- Create: `~/.openclaw/dispatcher-agent/lib/__init__.py`
- Create: `~/.openclaw/dispatcher-agent/README.md`

- [ ] **Step 1: Criar estrutura**

```bash
mkdir -p ~/.openclaw/dispatcher-agent/{lib,briefings,executions}
touch ~/.openclaw/dispatcher-agent/lib/__init__.py
```

- [ ] **Step 2: README esqueleto**

```bash
cat > ~/.openclaw/dispatcher-agent/README.md <<'EOF'
# dispatcher-agent

> HOST-LOCAL, NUNCA COMMITADO. Hub-dispatch L1 que seleciona proxima task
> ready, gera briefing, invoca Claude Code em background detached,
> auto-move in_progress -> testing no exit 0.

Spec: `bevox-knowledge/35_specs/2026-04-19-e10-dispatcher-and-clarification-agents.md`
Playbook: `bevox-knowledge/20_architecture/agents/dispatcher-agent.md`

## Operacao basica

```bash
vox dispatcher next [--project X]            # dry-run
vox dispatcher next --launch [--project X]   # default detach; cmd retorna imediato
vox dispatcher next --launch --foreground    # debug: bloqueia ate Claude Code terminar
vox dispatcher status                        # lista sessions ativas
vox dispatcher show <task-id>                # detail + log path
vox dispatcher tail <task-id>                # tail -f no log
vox dispatcher relaunch <task-id>            # apos fix de execution_failed
vox dispatcher kill <task-id>                # SIGTERM session
```

## Troubleshooting

**`NO_READY_TASK`**: scrum-master precisa ter produzido tasks ready
OU mover manual via `kanban-tasks/cli.sh task move <id> ready`.

**`WORK_IN_PROGRESS_LIMIT`**: ja existe task do projeto em in_progress.
Conclui ela primeiro, ou rode `vox dispatcher kill <id>`.

**`execution_failed`**: Claude Code terminou exit != 0. Chequa log:
`vox dispatcher tail <task-id>`. Decide `relaunch` ou rejection manual.

## Spec canonica

- `bevox-knowledge/35_specs/2026-04-19-e10-dispatcher-and-clarification-agents.md`
EOF
```

- [ ] **Step 3: Verificar**

```bash
ls -la ~/.openclaw/dispatcher-agent/
```

Expected: `lib/`, `briefings/`, `executions/`, `README.md` presentes.

### Task 1.2: lib/store.py (I/O atômico)

**Files:**
- Create: `~/.openclaw/dispatcher-agent/lib/store.py`

- [ ] **Step 1: Escrever store.py**

```python
"""Storage para session state: briefings, logs, status.json atomicos.

Responsabilidade unica: I/O dos arquivos em ~/.openclaw/dispatcher-agent/.
NAO invoca Claude Code, NAO chama kanban, NAO resolve contexto.
"""

import json
import os
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Optional

ROOT = Path(os.path.expanduser("~/.openclaw/dispatcher-agent"))
BRIEFINGS_DIR = ROOT / "briefings"
EXECUTIONS_DIR = ROOT / "executions"


def now_iso() -> str:
    """UTC ISO8601 com Z suffix, match kanban convention."""
    return datetime.now(tz=timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _atomic_write(path: Path, content: str) -> None:
    """tmpfile + os.rename (atomic em POSIX)."""
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(
        prefix=path.name + ".", suffix=".tmp", dir=str(path.parent),
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


def write_briefing(task_id: str, content: str) -> Path:
    """Escreve briefing em briefings/<task-id>.md (atomic)."""
    path = BRIEFINGS_DIR / f"{task_id}.md"
    _atomic_write(path, content)
    return path


def briefing_path(task_id: str) -> Path:
    return BRIEFINGS_DIR / f"{task_id}.md"


def execution_log_path(task_id: str) -> Path:
    return EXECUTIONS_DIR / f"{task_id}.log"


def execution_status_path(task_id: str) -> Path:
    return EXECUTIONS_DIR / f"{task_id}.status.json"


def write_execution_status(task_id: str, status: Dict[str, Any]) -> Path:
    """Escreve status.json atomico."""
    path = execution_status_path(task_id)
    _atomic_write(path, json.dumps(status, ensure_ascii=False, indent=2))
    return path


def read_execution_status(task_id: str) -> Optional[Dict[str, Any]]:
    """Le status.json ou retorna None se nao existe."""
    path = execution_status_path(task_id)
    if not path.exists():
        return None
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except (OSError, json.JSONDecodeError):
        return None


def list_executions() -> list:
    """Lista todas as executions conhecidas (status.json files)."""
    if not EXECUTIONS_DIR.exists():
        return []
    out = []
    for p in sorted(EXECUTIONS_DIR.glob("*.status.json")):
        try:
            with open(p, "r", encoding="utf-8") as f:
                out.append(json.load(f))
        except (OSError, json.JSONDecodeError):
            continue
    return out
```

- [ ] **Step 2: Sanity import**

```bash
cd ~/.openclaw/dispatcher-agent && PYTHONPATH=. python3 -c "
from lib.store import now_iso, write_briefing, read_execution_status, list_executions
assert now_iso().endswith('Z')
p = write_briefing('test-fixture', '# test')
assert p.exists()
assert read_execution_status('nonexistent') is None
import os; os.unlink(p)
print('OK')
"
```

Expected: `OK`.

### Task 1.3: cli.sh entrypoint

**Files:**
- Create: `~/.openclaw/dispatcher-agent/cli.sh`

- [ ] **Step 1: Criar wrapper**

```bash
cat > ~/.openclaw/dispatcher-agent/cli.sh <<'EOF'
#!/usr/bin/env bash
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"
exec python3 -m lib.api "$@"
EOF
chmod +x ~/.openclaw/dispatcher-agent/cli.sh
```

- [ ] **Step 2: Verificar**

```bash
ls -la ~/.openclaw/dispatcher-agent/cli.sh
```

Expected: executável.

---

## Phase 2: dispatcher-agent — selector + briefing

### Task 2.1: lib/selector.py (next-ready + project guard)

**Files:**
- Create: `~/.openclaw/dispatcher-agent/lib/selector.py`

- [ ] **Step 1: Escrever selector.py**

```python
"""Selector: escolhe proxima task ready via hook HTTP + 1-task-per-project guard.

HTTP route consumida: GET /api/kanban/tasks/next-ready?project=X (F4 wave-3).
Como o MC roda em :4310 atras de Cloudflare Access, usamos subprocess
curl com Cf-Access header local, OU chamada direto ao state.json (stdlib).

Escolha: usar state.json direto (mesmo pattern do scrum-master
materializer). Evita dep em HTTP/auth, e MC eh projecao do mesmo state.
"""

import json
import subprocess
from pathlib import Path
from typing import Any, Dict, List, Optional

KANBAN_CLI = Path("~/.openclaw/kanban-tasks/cli.sh")
KANBAN_STATE = Path("~/.openclaw/kanban-tasks/state.json")


class SelectorError(Exception):
    def __init__(self, code: str, detail: str):
        self.code = code
        self.detail = detail
        super().__init__(f"{code}: {detail}")


def _read_state() -> Dict[str, Any]:
    if not KANBAN_STATE.exists():
        raise SelectorError(
            "KANBAN_STATE_MISSING",
            f"{KANBAN_STATE} nao existe. Rode `kanban-tasks/cli.sh sprint init`",
        )
    try:
        return json.loads(KANBAN_STATE.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as e:
        raise SelectorError(
            "KANBAN_STATE_INVALID",
            f"falha lendo {KANBAN_STATE}: {e}",
        )


def _in_progress_tasks_for_project(state: Dict[str, Any],
                                    project: Optional[str]) -> List[Dict[str, Any]]:
    """Lista tasks in_progress no projeto alvo (ou qualquer se project=None)."""
    result = []
    for t in state.get("tasks", []):
        if t.get("status") != "in_progress":
            continue
        if project is not None and t.get("project") != project:
            continue
        result.append(t)
    return result


def check_one_task_per_project_guard(project: Optional[str]) -> None:
    """Valida que zero tasks in_progress no scope. Raise WORK_IN_PROGRESS_LIMIT."""
    state = _read_state()
    in_progress = _in_progress_tasks_for_project(state, project)
    if in_progress:
        detail = f"{len(in_progress)} task(s) em in_progress"
        if project:
            detail += f" no projeto '{project}'"
        detail += ": " + ", ".join(f"{t['id']}({t.get('title', '')[:30]})" for t in in_progress[:3])
        raise SelectorError("WORK_IN_PROGRESS_LIMIT", detail)


def select_next_ready(project: Optional[str]) -> Dict[str, Any]:
    """Retorna primeira task ready nao-blocked do projeto (ou qualquer).

    Ordena por created_at ascendente (mesma heuristica do /next-ready).
    Raise NO_READY_TASK se ausente.
    """
    state = _read_state()
    candidates = []
    for t in state.get("tasks", []):
        if t.get("status") != "ready":
            continue
        if t.get("blocked"):
            continue
        if project is not None and t.get("project") != project:
            continue
        candidates.append(t)
    if not candidates:
        msg = "nenhuma task ready nao-blocked"
        if project:
            msg += f" no projeto '{project}'"
        msg += ". Rode `vox scrum-master` OU `kanban-tasks/cli.sh task move <id> ready`"
        raise SelectorError("NO_READY_TASK", msg)
    candidates.sort(key=lambda t: t.get("created_at", ""))
    return candidates[0]
```

- [ ] **Step 2: Sanity**

```bash
cd ~/.openclaw/dispatcher-agent && PYTHONPATH=. python3 -c "
from lib.selector import select_next_ready, check_one_task_per_project_guard, SelectorError
try:
    t = select_next_ready(None)
    print(f'next-ready: {t[\"id\"]} project={t.get(\"project\")}')
except SelectorError as e:
    print(f'selector: {e.code} = OK esperado se state nao tem ready')
print('OK')
"
```

Expected: ou `next-ready: T-NNNN` ou `selector: NO_READY_TASK`. Ambos OK.

### Task 2.2: lib/briefing.py (template gerador)

**Files:**
- Create: `~/.openclaw/dispatcher-agent/lib/briefing.py`

- [ ] **Step 1: Escrever briefing.py**

```python
"""Gera briefing.md estruturado a partir de dispatch_payload.

Shape segue convention §10.1 da spec. Embute instruction forte pra
Claude Code cooperar com `vox clarification ask --and-wait`.
"""

from typing import Any, Dict, List, Optional

VOX_CLARIFICATION_CLI = "~/.openclaw/clarification-agent/cli.sh"


def _fmt_bullets(items: List[str], empty_msg: str = "(nenhum)") -> str:
    if not items:
        return empty_msg
    return "\n".join(f"- {i}" for i in items)


def _fmt_specs(refs: List[str]) -> str:
    if not refs:
        return "(nenhuma spec referenciada)"
    return "\n".join(f"- `{r}`" for r in refs)


def render_briefing(task: Dict[str, Any], allowed_tools: str) -> str:
    """Renderiza briefing.md a partir de task + flag allowed_tools literal.

    task precisa ter: id, title, status, epic_id, wave_ref, dispatch_payload
    (ao menos goal; outros campos opcionais).
    """
    task_id = task["id"]
    title = task.get("title", "")
    payload = task.get("dispatch_payload") or {}
    goal = payload.get("goal") or task.get("description") or title
    spec_refs = payload.get("spec_refs") or []
    plan_ref = payload.get("plan_ref") or ""
    plan_anchor = payload.get("plan_anchor") or ""
    ac = payload.get("acceptance_criteria") or []
    files_relevant = payload.get("files_relevant") or []
    out_of_scope = payload.get("out_of_scope") or []
    guardrails = payload.get("guardrails") or []

    ac_block = "\n".join(f"- [ ] {c}" for c in ac) if ac else "(nenhum AC explicito; infira dos spec_refs)"
    files_block = _fmt_bullets(files_relevant, "(nenhum file explicito; explore conforme necessario)")
    oos_block = _fmt_bullets(out_of_scope, "(nada declarado fora de escopo)")
    guards_block = _fmt_bullets(guardrails, "(nenhum guardrail explicito; siga ADRs padrao)")

    plan_line = f"**Plan:** `{plan_ref}`" + (f" (anchor: {plan_anchor})" if plan_anchor else "")

    return f"""# Task {task_id} — {title}

{goal}

## Contexto canonico

**Spec(s):**
{_fmt_specs(spec_refs)}

{plan_line}

**Epic/Wave:** {task.get("epic_id", "?")} / {task.get("wave_ref", "?")}

## Objetivo

{goal}

## Acceptance criteria

{ac_block}

## Files relevantes

{files_block}

## Out of scope

{oos_block}

## Guardrails

{guards_block}

---

## INSTRUCOES OPERACIONAIS — LEIA ANTES DE EXECUTAR

Voce esta sendo invocado pelo dispatcher-agent do OpenClaw como executor
de uma task operacional. Convention OBRIGATORIA:

### Se encontrar duvida bloqueante

Se durante a execucao voce precisar de informacao que NAO esta neste
briefing nem nos spec_refs/plan_ref citados, e que NAO consegue inferir
com seguranca a partir do codigo existente, NAO INVENTE. Execute via
Bash:

```
{VOX_CLARIFICATION_CLI} ask {task_id} \\
    --question "<sua pergunta especifica>" \\
    --and-wait
```

O comando vai bloquear ate a resposta chegar. A resposta virá no stdout.
Use ela e continue.

### Se a resposta retornar com exit code 4 (CLARIFICATION_REJECTED_TASK)

Significa que Bernard decidiu rejeitar esta task. Encerre execucao
imediatamente; NAO commite mudancas parciais.

### Se concluir com sucesso

Encerre limpamente (exit 0). O dispatcher detecta seu exit code e move
a task pra `testing` automaticamente. NAO tente mover a task voce mesmo.

### Tools permitidas nesta sessao

{allowed_tools}
"""
```

- [ ] **Step 2: Sanity com fixture**

```bash
cd ~/.openclaw/dispatcher-agent && PYTHONPATH=. python3 -c "
from lib.briefing import render_briefing
task = {
    'id': 'T-0042', 'title': 'criar lib X',
    'status': 'ready', 'epic_id': 'E5', 'wave_ref': 'E5/F4-demo/Phase-1',
    'dispatch_payload': {
        'goal': 'criar modulo X com shape Y',
        'spec_refs': ['bevox-knowledge/35_specs/X.md'],
        'plan_ref': '~/.openclaw/docs/superpowers/plans/p.md',
        'plan_anchor': 'task-1-1',
        'acceptance_criteria': ['X.py importavel', 'smoke passa'],
        'files_relevant': ['~/.openclaw/X/lib/x.py'],
        'guardrails': ['zero pip install'],
        'out_of_scope': ['refactor Y'],
    },
}
out = render_briefing(task, 'Read,Write,Bash(vox:*)')
assert 'T-0042' in out
assert 'ask T-0042' in out
assert 'Bash(vox:*)' in out
assert 'criar modulo X' in out
print('OK briefing render')
"
```

Expected: `OK briefing render`.

---

## Phase 3: dispatcher-agent — runner (subprocess)

### Task 3.1: lib/runner.py (detached + foreground)

**Files:**
- Create: `~/.openclaw/dispatcher-agent/lib/runner.py`

- [ ] **Step 1: Escrever runner.py**

```python
"""Runner: invoca claude -p como subprocess (detached ou foreground).

Detached (default): setsid + nohup + redirect stdout/stderr -> log file.
Cmd retorna imediato com pid + session_id. Claude Code sobrevive fechamento
de TTY do invocador.

Foreground (debug): subprocess.run blocking ate terminar.
"""

import json
import os
import subprocess
from pathlib import Path
from typing import Any, Dict, List, Optional

from . import store


class RunnerError(Exception):
    def __init__(self, code: str, detail: str):
        self.code = code
        self.detail = detail
        super().__init__(f"{code}: {detail}")


def _build_session_id(task_id: str) -> str:
    """<task>-<ts-compact>."""
    ts = store.now_iso().replace(":", "").replace("-", "")
    return f"{task_id}-{ts}"


def _claude_cmd(briefing_path: Path, allowed_tools: str, model: Optional[str] = None) -> List[str]:
    """Monta argv pra `claude -p` lendo briefing via shell (cat)."""
    # Ler briefing conteudo; passa direto como -p argument (mais robusto que stdin redirect)
    briefing_content = briefing_path.read_text(encoding="utf-8")
    cmd = ["claude", "-p", briefing_content]
    if model:
        cmd += ["--model", model]
    cmd += ["--allowedTools", allowed_tools]
    return cmd


def launch_detached(
    task_id: str,
    briefing_path: Path,
    allowed_tools: str,
    model: Optional[str] = None,
) -> Dict[str, Any]:
    """Spawn `claude -p` em background detached. Retorna status metadata.

    Usa setsid + nohup. Redirect stdout/stderr combinado pro log file.
    """
    session_id = _build_session_id(task_id)
    log_path = store.execution_log_path(task_id)
    log_path.parent.mkdir(parents=True, exist_ok=True)
    log_f = open(log_path, "w", encoding="utf-8")
    try:
        cmd = _claude_cmd(briefing_path, allowed_tools, model)
        proc = subprocess.Popen(
            cmd,
            stdin=subprocess.DEVNULL,
            stdout=log_f,
            stderr=subprocess.STDOUT,
            start_new_session=True,  # equivalente a setsid
            close_fds=True,
        )
    finally:
        log_f.close()
    status = {
        "task_id": task_id,
        "session_id": session_id,
        "pid": proc.pid,
        "run_mode": "detach",
        "started_at": store.now_iso(),
        "briefing_path": str(briefing_path),
        "log_path": str(log_path),
        "finished_at": None,
        "exit_code": None,
        "model": model or "default",
    }
    store.write_execution_status(task_id, status)
    return status


def launch_foreground(
    task_id: str,
    briefing_path: Path,
    allowed_tools: str,
    model: Optional[str] = None,
    timeout_seconds: int = 3600,
) -> Dict[str, Any]:
    """Spawn `claude -p` em foreground (debug). Bloqueia ate terminar.

    Output streamed pra terminal E pro log file.
    """
    session_id = _build_session_id(task_id)
    log_path = store.execution_log_path(task_id)
    status_initial = {
        "task_id": task_id,
        "session_id": session_id,
        "pid": None,
        "run_mode": "foreground",
        "started_at": store.now_iso(),
        "briefing_path": str(briefing_path),
        "log_path": str(log_path),
        "finished_at": None,
        "exit_code": None,
        "model": model or "default",
    }
    store.write_execution_status(task_id, status_initial)

    cmd = _claude_cmd(briefing_path, allowed_tools, model)
    try:
        # tee-like: pipe stdout, duplicar pra terminal + log
        with open(log_path, "w", encoding="utf-8") as log_f:
            proc = subprocess.Popen(
                cmd, stdin=subprocess.DEVNULL,
                stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                text=True,
            )
            status_initial["pid"] = proc.pid
            store.write_execution_status(task_id, status_initial)
            assert proc.stdout is not None
            for line in proc.stdout:
                print(line, end="")
                log_f.write(line)
                log_f.flush()
            exit_code = proc.wait(timeout=timeout_seconds)
    except subprocess.TimeoutExpired:
        proc.kill()
        raise RunnerError(
            "FOREGROUND_TIMEOUT",
            f"claude -p excedeu {timeout_seconds}s em foreground mode",
        )

    status_initial["exit_code"] = exit_code
    status_initial["finished_at"] = store.now_iso()
    store.write_execution_status(task_id, status_initial)
    return status_initial


def is_session_alive(status: Dict[str, Any]) -> bool:
    """Checa se PID do status.json ainda esta vivo."""
    pid = status.get("pid")
    if not pid:
        return False
    if status.get("finished_at") is not None:
        return False
    try:
        os.kill(pid, 0)  # signal 0 = check existence
        return True
    except (OSError, ProcessLookupError):
        return False


def kill_session(task_id: str, sig: int = 15) -> Dict[str, Any]:
    """Envia SIGTERM (ou custom) pra session. Atualiza status."""
    status = store.read_execution_status(task_id)
    if status is None:
        raise RunnerError("SESSION_NOT_FOUND", f"{task_id}: sem status.json")
    pid = status.get("pid")
    if not pid:
        raise RunnerError("SESSION_NO_PID", f"{task_id}: pid ausente no status")
    try:
        os.kill(pid, sig)
    except (OSError, ProcessLookupError) as e:
        raise RunnerError("KILL_FAILED", f"{task_id}: {e}")
    status["finished_at"] = store.now_iso()
    status["exit_code"] = -sig
    status["canceled"] = True
    store.write_execution_status(task_id, status)
    return status


def reap_finished(task_id: str) -> Optional[Dict[str, Any]]:
    """Checa se subprocess detached terminou. Se sim, atualiza status.json
    com exit_code capturado via wait sem block (waitpid WNOHANG)."""
    status = store.read_execution_status(task_id)
    if status is None or status.get("finished_at") is not None:
        return status
    pid = status.get("pid")
    if not pid:
        return status
    try:
        wait_pid, exit_code_raw = os.waitpid(pid, os.WNOHANG)
    except ChildProcessError:
        # Process ja reaped pelo sistema (detached via setsid nao eh filho direto)
        # Checar via kill -0 + inferir
        if not is_session_alive(status):
            status["finished_at"] = store.now_iso()
            # exit_code desconhecido — tentar parse do log final
            status["exit_code"] = _parse_exit_code_from_log(task_id)
            store.write_execution_status(task_id, status)
        return status
    if wait_pid == 0:
        # Ainda rodando
        return status
    # Terminou
    if os.WIFEXITED(exit_code_raw):
        status["exit_code"] = os.WEXITSTATUS(exit_code_raw)
    elif os.WIFSIGNALED(exit_code_raw):
        status["exit_code"] = -os.WTERMSIG(exit_code_raw)
    else:
        status["exit_code"] = -1
    status["finished_at"] = store.now_iso()
    store.write_execution_status(task_id, status)
    return status


def _parse_exit_code_from_log(task_id: str) -> int:
    """Fallback heuristica: infere exit code do final do log. Conservador: 1
    se ha sinais de erro, 0 caso contrario."""
    log_path = store.execution_log_path(task_id)
    if not log_path.exists():
        return -1
    try:
        tail = log_path.read_text(encoding="utf-8", errors="replace")[-2000:]
    except OSError:
        return -1
    low = tail.lower()
    for marker in ("error:", "traceback", "failed", "abort"):
        if marker in low:
            return 1
    return 0
```

- [ ] **Step 2: Sanity (import + session id)**

```bash
cd ~/.openclaw/dispatcher-agent && PYTHONPATH=. python3 -c "
from lib.runner import _build_session_id, is_session_alive
sid = _build_session_id('T-0042')
assert sid.startswith('T-0042-')
assert is_session_alive({'pid': None}) is False
print('OK runner sanity')
"
```

Expected: `OK runner sanity`.

---

## Phase 4: dispatcher-agent — lifecycle

### Task 4.1: lib/lifecycle.py (transitions + auto-move testing)

**Files:**
- Create: `~/.openclaw/dispatcher-agent/lib/lifecycle.py`

- [ ] **Step 1: Escrever lifecycle.py**

```python
"""Lifecycle: transitions de status no kanban + dispatch metadata merge.

Usa cli.sh kanban-tasks como API. Single-call por transicao.
"""

import json
import subprocess
from pathlib import Path
from typing import Any, Dict, Optional

from . import store

KANBAN_CLI = Path("~/.openclaw/kanban-tasks/cli.sh")


class LifecycleError(Exception):
    def __init__(self, code: str, detail: str):
        self.code = code
        self.detail = detail
        super().__init__(f"{code}: {detail}")


def _run_kanban(args: list, actor: str = "dispatcher") -> Dict[str, Any]:
    """Invoca cli.sh kanban-tasks --json. Retorna payload parseado."""
    cmd = [str(KANBAN_CLI)] + args + ["--json", "--actor", actor]
    try:
        result = subprocess.run(
            cmd, capture_output=True, text=True, check=False, timeout=30,
        )
    except (OSError, subprocess.TimeoutExpired) as e:
        raise LifecycleError(
            "KANBAN_CLI_TIMEOUT", f"{' '.join(cmd[:4])}: {e}",
        )
    if result.returncode != 0:
        raise LifecycleError(
            "KANBAN_CLI_FAILED",
            f"exit={result.returncode} stderr={result.stderr.strip()[:200]}",
        )
    try:
        return json.loads(result.stdout)
    except json.JSONDecodeError as e:
        raise LifecycleError(
            "KANBAN_CLI_BAD_JSON", f"{e}: {result.stdout[:200]}",
        )


def move_to_in_progress(task_id: str) -> None:
    """ready -> in_progress via kanban CLI."""
    _run_kanban(["task", "move", task_id, "in_progress"], actor="dispatcher")


def merge_dispatch_payload(task_id: str, merge_fields: Dict[str, Any]) -> None:
    """Merge shallow top-level dispatch_payload fields."""
    _run_kanban(
        ["task", "set-dispatch-payload", task_id,
         "--payload", json.dumps(merge_fields, ensure_ascii=False),
         "--merge"],
        actor="dispatcher",
    )


def auto_move_to_testing(task_id: str) -> None:
    """Exit 0 handler: in_progress -> testing."""
    _run_kanban(["task", "move", task_id, "testing"], actor="dispatcher")


def mark_execution_failed(task_id: str, reason_summary: str) -> None:
    """Exit != 0 handler: seta blocked flag com reason='execution_failed: ...'.

    Trunca reason em 80 char pra caber em UI/event summary.
    """
    reason = f"execution_failed: {reason_summary[:80]}"
    _run_kanban(
        ["task", "block", task_id, "--reason", reason],
        actor="dispatcher",
    )


def unblock_for_relaunch(task_id: str) -> None:
    """Relaunch: limpa blocked flag antes de novo launch."""
    _run_kanban(["task", "unblock", task_id], actor="dispatcher")


def process_finished_session(task_id: str) -> Dict[str, Any]:
    """Dado status.json com finished_at + exit_code, aplica kanban transition.

    Exit 0 -> auto-move testing.
    Exit != 0 -> block execution_failed.
    Retorna status atualizado com post_action field.
    """
    status = store.read_execution_status(task_id)
    if status is None:
        raise LifecycleError(
            "SESSION_NOT_FOUND", f"{task_id}: sem status.json",
        )
    if status.get("finished_at") is None:
        raise LifecycleError(
            "SESSION_NOT_FINISHED", f"{task_id}: ainda em execucao",
        )
    if status.get("post_action_applied"):
        return status  # ja processado
    exit_code = status.get("exit_code")
    ts = store.now_iso()
    if exit_code == 0:
        auto_move_to_testing(task_id)
        merge_dispatch_payload(task_id, {
            "execution_finished_at": status["finished_at"],
            "execution_exit_code": 0,
            "auto_moved_to_testing_at": ts,
        })
        status["post_action"] = "auto_moved_to_testing"
    else:
        # Parse stderr tail do log pra reason
        log_path = Path(status.get("log_path", ""))
        stderr_tail = "(sem log)"
        if log_path.exists():
            try:
                content = log_path.read_text(encoding="utf-8", errors="replace")
                stderr_tail = content[-300:].replace("\n", " ").strip()[:150]
            except OSError:
                pass
        mark_execution_failed(task_id, stderr_tail)
        merge_dispatch_payload(task_id, {
            "execution_finished_at": status["finished_at"],
            "execution_exit_code": exit_code,
            "execution_failed_marked_at": ts,
        })
        status["post_action"] = f"blocked_execution_failed_exit_{exit_code}"
    status["post_action_applied"] = True
    status["post_action_at"] = ts
    store.write_execution_status(task_id, status)
    return status
```

- [ ] **Step 2: Sanity**

```bash
cd ~/.openclaw/dispatcher-agent && PYTHONPATH=. python3 -c "
from lib.lifecycle import _run_kanban, LifecycleError
try:
    res = _run_kanban(['task', 'list', '--status', 'ready'], actor='dispatcher')
    print(f'kanban reached: {len(res.get(\"tasks\", []))} ready tasks')
except LifecycleError as e:
    print(f'expected if kanban empty: {e.code}')
print('OK lifecycle sanity')
"
```

Expected: print de listagem + `OK lifecycle sanity`.

---

## Phase 5: dispatcher-agent — CLI wiring

### Task 5.1: lib/api.py skeleton + argparse

**Files:**
- Create: `~/.openclaw/dispatcher-agent/lib/api.py`

- [ ] **Step 1: Criar api.py completo**

```python
"""CLI dispatcher: argparse + cmd handlers."""

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Optional

from . import briefing as briefing_lib
from . import lifecycle as lifecycle_lib
from . import runner as runner_lib
from . import selector as selector_lib
from . import store

EXIT_OK = 0
EXIT_INPUT = 1
EXIT_STATE = 2

DEFAULT_ALLOWED_TOOLS = (
    "Read,Write,Edit,Glob,Grep,"
    "Bash(git:*),Bash(npm:*),Bash(python3:*),Bash(pytest:*),"
    "Bash(ls:*),Bash(cat:*),Bash(echo:*),Bash(mkdir:*),Bash(touch:*),"
    "Bash(vox clarification:*),Bash(~/.openclaw/clarification-agent/cli.sh:*),"
    "Bash(rm:*)"
)

_EXIT_BY_CODE = {
    "NO_READY_TASK": EXIT_INPUT,
    "WORK_IN_PROGRESS_LIMIT": EXIT_INPUT,
    "KANBAN_STATE_MISSING": EXIT_STATE,
    "KANBAN_STATE_INVALID": EXIT_STATE,
    "KANBAN_CLI_TIMEOUT": EXIT_STATE,
    "KANBAN_CLI_FAILED": EXIT_STATE,
    "KANBAN_CLI_BAD_JSON": EXIT_STATE,
    "SESSION_NOT_FOUND": EXIT_INPUT,
    "SESSION_NO_PID": EXIT_STATE,
    "SESSION_NOT_FINISHED": EXIT_STATE,
    "KILL_FAILED": EXIT_STATE,
    "FOREGROUND_TIMEOUT": EXIT_STATE,
    "NOT_IMPLEMENTED": EXIT_STATE,
}


def _err(msg: str, code: str, json_mode: bool) -> int:
    if json_mode:
        print(json.dumps({"ok": False, "error": msg, "code": code}))
    else:
        print(f"ERROR ({code}): {msg}", file=sys.stderr)
    return _EXIT_BY_CODE.get(code, EXIT_STATE)


def _print(payload: Any, json_mode: bool, human: Optional[str] = None) -> None:
    if json_mode:
        print(json.dumps(payload, ensure_ascii=False, indent=2))
    else:
        if human is not None:
            print(human)
        else:
            print(json.dumps(payload, ensure_ascii=False, indent=2))


# ============ cmd_next: dry-run + --launch ============

def cmd_next(args: argparse.Namespace) -> int:
    # 1. Select next ready + 1-task-per-project guard
    try:
        if args.launch:
            selector_lib.check_one_task_per_project_guard(args.project)
        task = selector_lib.select_next_ready(args.project)
    except selector_lib.SelectorError as e:
        return _err(e.detail, e.code, args.json)

    # 2. Gerar briefing
    allowed_tools = args.allowed_tools or DEFAULT_ALLOWED_TOOLS
    briefing_content = briefing_lib.render_briefing(task, allowed_tools)
    if args.briefing_only or not args.launch:
        # Dry-run: escreve briefing mas NAO move status nem invoca Claude
        bpath = store.write_briefing(task["id"], briefing_content)
        _print({
            "ok": True, "mode": "dry_run",
            "task_id": task["id"], "title": task.get("title"),
            "project": task.get("project"),
            "briefing_path": str(bpath),
        }, args.json, f"selected (dry-run): {task['id']} project={task.get('project')}\n"
                      f"briefing: {bpath}\n"
                      f"[use --launch pra mover status + invocar Claude Code]")
        return EXIT_OK

    # 3. Launch path
    bpath = store.write_briefing(task["id"], briefing_content)
    try:
        lifecycle_lib.move_to_in_progress(task["id"])
    except lifecycle_lib.LifecycleError as e:
        return _err(e.detail, e.code, args.json)

    # 4. Merge metadata
    ts = store.now_iso()
    metadata = {
        "dispatched_at": ts,
        "dispatcher_actor": "dispatcher",
        "briefing_path": str(bpath),
        "dispatch_mode": "foreground" if args.foreground else "detach",
    }
    try:
        lifecycle_lib.merge_dispatch_payload(task["id"], metadata)
    except lifecycle_lib.LifecycleError as e:
        return _err(e.detail, e.code, args.json)

    # 5. Spawn Claude Code
    try:
        if args.foreground:
            status = runner_lib.launch_foreground(
                task["id"], bpath, allowed_tools, model=args.model,
            )
            # Foreground: processa finished inline
            lifecycle_lib.process_finished_session(task["id"])
        else:
            status = runner_lib.launch_detached(
                task["id"], bpath, allowed_tools, model=args.model,
            )
    except runner_lib.RunnerError as e:
        return _err(e.detail, e.code, args.json)

    # 6. Merge execution start metadata
    lifecycle_lib.merge_dispatch_payload(task["id"], {
        "execution_session_id": status["session_id"],
        "execution_log_path": status["log_path"],
        "execution_started_at": status["started_at"],
    })

    _print(status, args.json,
           f"launched: {task['id']} ({status['run_mode']})\n"
           f"  session_id: {status['session_id']}\n"
           f"  pid:        {status['pid']}\n"
           f"  log:        {status['log_path']}\n"
           f"  briefing:   {status['briefing_path']}")
    return EXIT_OK


# ============ cmd_status / cmd_show / cmd_tail ============

def cmd_status(args: argparse.Namespace) -> int:
    executions = store.list_executions()
    if args.json:
        # Enriquecer com is_alive
        for e in executions:
            e["alive"] = runner_lib.is_session_alive(e)
        _print({"executions": executions}, True)
        return EXIT_OK
    if not executions:
        print("(nenhuma session)")
        return EXIT_OK
    print(f"{'TASK':8s} {'MODE':10s} {'PID':6s} {'ALIVE':6s} STARTED_AT             FINISHED_AT            EXIT")
    for e in executions:
        alive = "yes" if runner_lib.is_session_alive(e) else "no "
        pid = str(e.get("pid") or "?")
        started = e.get("started_at", "?")
        finished = e.get("finished_at") or "-"
        exit_code = e.get("exit_code")
        exit_str = str(exit_code) if exit_code is not None else "-"
        print(f"{e['task_id']:8s} {e.get('run_mode', '?'):10s} {pid:6s} {alive:6s} {started:22s} {finished:22s} {exit_str}")
    return EXIT_OK


def cmd_show(args: argparse.Namespace) -> int:
    status = store.read_execution_status(args.task_id)
    if status is None:
        return _err(f"{args.task_id}: sem status.json", "SESSION_NOT_FOUND", args.json)
    status["alive"] = runner_lib.is_session_alive(status)
    _print(status, args.json)
    return EXIT_OK


def cmd_tail(args: argparse.Namespace) -> int:
    path = store.execution_log_path(args.task_id)
    if not path.exists():
        return _err(f"{args.task_id}: log nao existe em {path}", "SESSION_NOT_FOUND", args.json)
    # tail -f bloqueante. User sai com Ctrl-C.
    import subprocess as sp
    try:
        sp.run(["tail", "-f", str(path)], check=False)
    except KeyboardInterrupt:
        pass
    return EXIT_OK


# ============ cmd_kill / cmd_relaunch ============

def cmd_kill(args: argparse.Namespace) -> int:
    try:
        status = runner_lib.kill_session(args.task_id)
    except runner_lib.RunnerError as e:
        return _err(e.detail, e.code, args.json)
    # Unblock (task volta pra in_progress nao-blocked; Bernard decide)
    _print({"ok": True, "killed": args.task_id, "status": status}, args.json,
           f"killed: {args.task_id} (session ended)")
    return EXIT_OK


def cmd_relaunch(args: argparse.Namespace) -> int:
    # Valida task esta em execution_failed
    # Simplificado: chama unblock + re-run cmd_next launch-only
    try:
        lifecycle_lib.unblock_for_relaunch(args.task_id)
    except lifecycle_lib.LifecycleError as e:
        return _err(e.detail, e.code, args.json)
    # Re-select task pelo id (nao via selector proximo)
    import json as _json
    KANBAN_CLI = "~/.openclaw/kanban-tasks/cli.sh"
    import subprocess as sp
    out = sp.run([KANBAN_CLI, "task", "show", args.task_id, "--json"],
                 capture_output=True, text=True, check=False, timeout=10)
    if out.returncode != 0:
        return _err(f"task show {args.task_id}: {out.stderr}", "KANBAN_CLI_FAILED", args.json)
    task_data = _json.loads(out.stdout).get("task")
    if task_data is None:
        return _err(f"{args.task_id} nao encontrada", "SESSION_NOT_FOUND", args.json)

    allowed_tools = args.allowed_tools or DEFAULT_ALLOWED_TOOLS
    content = briefing_lib.render_briefing(task_data, allowed_tools)
    bpath = store.write_briefing(args.task_id, content)
    try:
        status = runner_lib.launch_detached(
            args.task_id, bpath, allowed_tools, model=args.model,
        )
    except runner_lib.RunnerError as e:
        return _err(e.detail, e.code, args.json)
    _print(status, args.json, f"relaunched: {args.task_id} (pid {status['pid']})")
    return EXIT_OK


# ============ Parser ============

def build_parser() -> argparse.ArgumentParser:
    common = argparse.ArgumentParser(add_help=False)
    common.add_argument("--json", action="store_true")
    common.add_argument("--actor", default="dispatcher")

    p = argparse.ArgumentParser(prog="dispatcher-agent")
    sub = p.add_subparsers(dest="cmd", required=True)

    def leaf(psub, name):
        return psub.add_parser(name, parents=[common])

    nx = leaf(sub, "next")
    nx.add_argument("--project", default=None)
    nx.add_argument("--launch", action="store_true",
                    help="move status + invoca Claude; default dry-run")
    nx.add_argument("--foreground", action="store_true",
                    help="debug: bloqueia ate Claude Code terminar")
    nx.add_argument("--briefing-only", action="store_true",
                    help="gera briefing + NAO move status")
    nx.add_argument("--allowed-tools", default=None,
                    help=f"override do default (ver help)")
    nx.add_argument("--model", default="claude-opus-4-7",
                    help="model passado ao claude -p (default: claude-opus-4-7)")
    nx.set_defaults(func=cmd_next)

    st = leaf(sub, "status")
    st.set_defaults(func=cmd_status)

    sh = leaf(sub, "show")
    sh.add_argument("task_id")
    sh.set_defaults(func=cmd_show)

    tl = leaf(sub, "tail")
    tl.add_argument("task_id")
    tl.set_defaults(func=cmd_tail)

    kl = leaf(sub, "kill")
    kl.add_argument("task_id")
    kl.set_defaults(func=cmd_kill)

    rl = leaf(sub, "relaunch")
    rl.add_argument("task_id")
    rl.add_argument("--allowed-tools", default=None)
    rl.add_argument("--model", default="claude-opus-4-7")
    rl.set_defaults(func=cmd_relaunch)

    return p


def main(argv=None) -> int:
    p = build_parser()
    args = p.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 2: Sanity CLI help**

```bash
~/.openclaw/dispatcher-agent/cli.sh --help 2>&1 | head -10
echo '---'
~/.openclaw/dispatcher-agent/cli.sh next --help 2>&1 | head -10
echo '---'
~/.openclaw/dispatcher-agent/cli.sh status
```

Expected: help text renderiza + `status` retorna `(nenhuma session)`.

### Task 5.2: Sandbox E2E dispatcher (sem Claude real)

- [ ] **Step 1: Dry-run contra kanban real**

```bash
# Criar task fixture em ready pra dry-run pegar
cd ~/.openclaw/kanban-tasks
cp state.json /tmp/state.disp-sandbox.json
cp events.jsonl /tmp/events.disp-sandbox.jsonl

./cli.sh task add "dispatcher sandbox task" --project openclaw --sprint current >/dev/null
TID=$(./cli.sh task list --status backlog --json | python3 -c "
import json,sys; tks=json.load(sys.stdin)['tasks']
for t in reversed(tks):
  if t.get('title')=='dispatcher sandbox task':
    print(t['id']); break
")
./cli.sh task move $TID ready --actor bernard
# dispatch_payload minimal pra briefing nao ficar vazio
./cli.sh task set-dispatch-payload $TID --payload '{"goal":"sandbox test","spec_refs":["none.md"],"plan_ref":"/tmp/p.md","plan_anchor":"task-0-0","acceptance_criteria":["sanity"],"files_relevant":["/tmp/x.py"]}'
echo "fixture task: $TID"
echo '---'

echo '=== dispatcher next (dry-run) ==='
~/.openclaw/dispatcher-agent/cli.sh next --project openclaw
echo '---'
ls -la ~/.openclaw/dispatcher-agent/briefings/

echo '=== cleanup fixture sandbox ==='
cp /tmp/state.disp-sandbox.json ~/.openclaw/kanban-tasks/state.json
cp /tmp/events.disp-sandbox.jsonl ~/.openclaw/kanban-tasks/events.jsonl
~/.openclaw/kanban-tasks/cli.sh rebuild >/dev/null
rm -f ~/.openclaw/dispatcher-agent/briefings/$TID.md
echo 'OK'
```

Expected: briefing gerado, cleanup OK.

---

## Phase 6: clarification-agent — skeleton

### Task 6.1: Criar dirs + README

**Files:**
- Create: `~/.openclaw/clarification-agent/` (dir)
- Create: `~/.openclaw/clarification-agent/lib/` (dir)
- Create: `~/.openclaw/clarification-agent/{questions,answers,escalations,signals}/` (dirs)
- Create: `~/.openclaw/clarification-agent/lib/__init__.py`
- Create: `~/.openclaw/clarification-agent/README.md`

- [ ] **Step 1: Criar estrutura**

```bash
mkdir -p ~/.openclaw/clarification-agent/{lib,questions,answers,escalations,signals}
touch ~/.openclaw/clarification-agent/lib/__init__.py
```

- [ ] **Step 2: README**

```bash
cat > ~/.openclaw/clarification-agent/README.md <<'EOF'
# clarification-agent

> HOST-LOCAL. Hub-dispatch L1 invocado pelo Claude Code (via Bash tool)
> quando ha duvida bloqueante. Le contexto canonico, gera answer com
> confidence flag. Safe -> auto-unblock + retorna answer. Unsafe -> escala.

Spec: `bevox-knowledge/35_specs/2026-04-19-e10-dispatcher-and-clarification-agents.md`

## Invocado pelo Claude Code

```bash
vox clarification ask T-0042 --question "..." --and-wait
```

## Operacao manual (Bernard)

```bash
vox clarification escalations               # lista pending
vox clarification show <task-id>            # detail
vox clarification override <task-id> --answer "..." --commit   # Bernard manual
vox clarification reject-task <task-id> --reason "<cat>: ..." --commit
vox clarification redraft <task-id>         # regenera apos edit de spec/plan
```

## Categorias validas de rejection

- `task_malformed`
- `spec_inconsistent`
- `requires_re_decomposition`
- `inexecutable`
- `manual`

## Exit codes

- 0: safe auto-resolve OK
- 2: cancelado durante --and-wait (SIGTERM)
- 3: CLARIFICATION_PROPOSES_REJECTION (drafter sugeriu reject)
- 4: CLARIFICATION_REJECTED_TASK (Bernard rejeitou durante --and-wait)
EOF
```

- [ ] **Step 3: Verificar**

```bash
ls -la ~/.openclaw/clarification-agent/
```

Expected: todos dirs + README.

### Task 6.2: lib/store.py (artifacts I/O)

**Files:**
- Create: `~/.openclaw/clarification-agent/lib/store.py`

- [ ] **Step 1: Escrever store.py**

```python
"""Storage pra questions, answers, escalations, signals.

Responsabilidade unica: I/O atomico + ids sequencial per task.
"""

import json
import os
import re
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

ROOT = Path(os.path.expanduser("~/.openclaw/clarification-agent"))
QUESTIONS_DIR = ROOT / "questions"
ANSWERS_DIR = ROOT / "answers"
ESCALATIONS_DIR = ROOT / "escalations"
SIGNALS_DIR = ROOT / "signals"


def now_iso() -> str:
    return datetime.now(tz=timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _atomic_write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(prefix=path.name + ".", suffix=".tmp", dir=str(path.parent))
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


def next_clarification_seq(task_id: str) -> int:
    """Retorna proximo seq numerico sequencial pra task, baseado em files existentes."""
    QUESTIONS_DIR.mkdir(parents=True, exist_ok=True)
    pattern = re.compile(re.escape(task_id) + r"-clr-(\d+)\.md$")
    max_seq = 0
    for p in QUESTIONS_DIR.iterdir():
        m = pattern.match(p.name)
        if m:
            max_seq = max(max_seq, int(m.group(1)))
    return max_seq + 1


def make_clarification_id(task_id: str, seq: int) -> str:
    return f"{task_id}-clr-{seq}"


def write_question(clarification_id: str, question_text: str) -> Path:
    path = QUESTIONS_DIR / f"{clarification_id}.md"
    header = (f"# Clarification question — {clarification_id}\n"
              f"\n**Received at:** {now_iso()}\n\n---\n\n")
    _atomic_write(path, header + question_text + "\n")
    return path


def write_answer(
    clarification_id: str,
    question_path: Path,
    answer_text: str,
    confidence: str,
    sources: List[str],
    drafter: str = "clarification-agent (claude-haiku-4-5)",
    escalation_reason: Optional[str] = None,
) -> Path:
    path = ANSWERS_DIR / f"{clarification_id}.md"
    sources_block = "\n".join(f"- {s}" for s in sources) if sources else "(nenhuma)"
    body = f"""# Clarification answer — {clarification_id}

**Question file:** {question_path}
**Generated at:** {now_iso()}
**Drafter:** {drafter}
**Confidence:** {confidence}
**Sources used:**
{sources_block}

---

## Answer

{answer_text}
"""
    if escalation_reason and confidence == "unsafe":
        body += f"\n---\n\n## Escalation reason\n\n{escalation_reason}\n"
    _atomic_write(path, body)
    return path


def write_escalation_symlink(clarification_id: str) -> Path:
    """Symlink de escalations/<id>.md -> answers/<id>.md."""
    target = ANSWERS_DIR / f"{clarification_id}.md"
    link = ESCALATIONS_DIR / f"{clarification_id}.md"
    ESCALATIONS_DIR.mkdir(parents=True, exist_ok=True)
    if link.exists() or link.is_symlink():
        link.unlink()
    os.symlink(str(target), str(link))
    return link


def clear_escalation_symlink(clarification_id: str) -> None:
    link = ESCALATIONS_DIR / f"{clarification_id}.md"
    if link.exists() or link.is_symlink():
        link.unlink()


def signal_path(clarification_id: str) -> Path:
    return SIGNALS_DIR / f"{clarification_id}.signal"


def emit_signal(clarification_id: str, outcome: str) -> Path:
    """Cria signal file com outcome ('safe'|'override'|'rejected')."""
    SIGNALS_DIR.mkdir(parents=True, exist_ok=True)
    path = signal_path(clarification_id)
    _atomic_write(path, json.dumps({
        "clarification_id": clarification_id,
        "outcome": outcome,
        "emitted_at": now_iso(),
    }, indent=2))
    return path


def read_signal(clarification_id: str) -> Optional[Dict[str, Any]]:
    path = signal_path(clarification_id)
    if not path.exists():
        return None
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except (OSError, json.JSONDecodeError):
        return None


def list_escalations() -> List[Dict[str, Any]]:
    """Lista escalations pending (symlinks vivos em escalations/)."""
    if not ESCALATIONS_DIR.exists():
        return []
    out = []
    for p in sorted(ESCALATIONS_DIR.iterdir()):
        if not (p.is_symlink() or p.is_file()):
            continue
        out.append({"clarification_id": p.stem, "escalation_path": str(p)})
    return out
```

- [ ] **Step 2: Sanity**

```bash
cd ~/.openclaw/clarification-agent && PYTHONPATH=. python3 -c "
from lib.store import next_clarification_seq, write_question, write_answer, emit_signal, read_signal
seq = next_clarification_seq('T-TEST')
assert seq == 1
cid = f'T-TEST-clr-{seq}'
qp = write_question(cid, 'sample question?')
ap = write_answer(cid, qp, 'sample answer', 'safe', ['ref1', 'ref2'])
sp = emit_signal(cid, 'safe')
sig = read_signal(cid)
assert sig['outcome'] == 'safe'
# cleanup
import os
os.unlink(qp); os.unlink(ap); os.unlink(sp)
print('OK store')
"
```

Expected: `OK store`.

### Task 6.3: cli.sh entrypoint

**Files:**
- Create: `~/.openclaw/clarification-agent/cli.sh`

- [ ] **Step 1:**

```bash
cat > ~/.openclaw/clarification-agent/cli.sh <<'EOF'
#!/usr/bin/env bash
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"
exec python3 -m lib.api "$@"
EOF
chmod +x ~/.openclaw/clarification-agent/cli.sh
```

---

## Phase 7: clarification-agent — context loader + safety

### Task 7.1: lib/context_loader.py

**Files:**
- Create: `~/.openclaw/clarification-agent/lib/context_loader.py`

- [ ] **Step 1: Escrever context_loader.py**

```python
"""Context loader: le dispatch_payload + spec_refs + plan_ref + ADRs.

Retorna bundle de contexto pra drafter incluir no prompt do claude -p.
Zero escrita — read-only em filesystem.
"""

import json
import subprocess
from pathlib import Path
from typing import Any, Dict, List, Optional

BEVOX_KNOWLEDGE = Path("~/bevox-knowledge")
OPENCLAW_PLANS = Path("~/.openclaw/docs/superpowers/plans")
KANBAN_CLI = Path("~/.openclaw/kanban-tasks/cli.sh")


class ContextError(Exception):
    def __init__(self, code: str, detail: str):
        self.code = code
        self.detail = detail
        super().__init__(f"{code}: {detail}")


def load_task_via_kanban(task_id: str) -> Dict[str, Any]:
    """Le task completa via kanban cli.sh task show --json."""
    try:
        r = subprocess.run(
            [str(KANBAN_CLI), "task", "show", task_id, "--json"],
            capture_output=True, text=True, check=False, timeout=10,
        )
    except (OSError, subprocess.TimeoutExpired) as e:
        raise ContextError("KANBAN_CLI_TIMEOUT", f"{e}")
    if r.returncode != 0:
        raise ContextError(
            "TASK_NOT_FOUND",
            f"{task_id}: exit={r.returncode} stderr={r.stderr.strip()[:200]}",
        )
    data = json.loads(r.stdout)
    return data.get("task") or {}


def resolve_ref_path(ref: str) -> Optional[Path]:
    """Resolve ref string pra path absoluto. Retorna None se nao encontrar."""
    # Normaliza: remove ~ ou ./ prefix; resolve relativa a bevox-knowledge ou openclaw
    r = ref.strip().strip("`")
    if r.startswith("~/"):
        p = Path(r).expanduser()
        return p if p.exists() else None
    if r.startswith("/"):
        p = Path(r)
        return p if p.exists() else None
    # Relative: tentar bevox-knowledge + openclaw
    for base in (BEVOX_KNOWLEDGE, OPENCLAW_PLANS, Path.home() / ".openclaw"):
        cand = base / r
        if cand.exists():
            return cand
    return None


def read_ref(ref: str, max_bytes: int = 20_000) -> Optional[Dict[str, Any]]:
    """Le ref file truncado em max_bytes. Retorna {'path', 'content'} ou None."""
    path = resolve_ref_path(ref)
    if path is None or not path.is_file():
        return None
    try:
        content = path.read_text(encoding="utf-8", errors="replace")[:max_bytes]
    except OSError:
        return None
    return {
        "ref": ref, "path": str(path), "content": content,
        "truncated": len(content) >= max_bytes,
    }


def extract_adrs_from_content(content: str) -> List[str]:
    """Extrai refs ADR-XXX mencionadas no content."""
    import re
    pat = re.compile(r"(bevox-knowledge/30_adr/ADR-\d+-[\w-]+\.md)")
    refs = list(dict.fromkeys(pat.findall(content)))  # dedup preservando ordem
    return refs


def build_context_bundle(task_id: str) -> Dict[str, Any]:
    """Monta bundle completo de contexto pra drafter."""
    task = load_task_via_kanban(task_id)
    payload = task.get("dispatch_payload") or {}
    spec_refs = payload.get("spec_refs") or []
    plan_ref = payload.get("plan_ref")

    read_refs: List[Dict[str, Any]] = []
    for r in spec_refs:
        result = read_ref(r)
        if result:
            read_refs.append(result)
    if plan_ref:
        result = read_ref(plan_ref)
        if result:
            read_refs.append(result)

    # Extrair ADRs citadas no conteudo e carregar
    adr_refs_seen: List[str] = []
    for r in read_refs:
        for adr in extract_adrs_from_content(r["content"]):
            if adr not in adr_refs_seen:
                adr_refs_seen.append(adr)
    for adr_ref in adr_refs_seen:
        result = read_ref(adr_ref)
        if result:
            read_refs.append(result)

    return {
        "task": task,
        "dispatch_payload": payload,
        "read_refs": read_refs,
        "resolved_count": len(read_refs),
        "unresolved_refs": [
            r for r in spec_refs + ([plan_ref] if plan_ref else [])
            if resolve_ref_path(r) is None
        ],
    }
```

- [ ] **Step 2: Sanity**

```bash
cd ~/.openclaw/clarification-agent && PYTHONPATH=. python3 -c "
from lib.context_loader import resolve_ref_path, extract_adrs_from_content, read_ref
p = resolve_ref_path('bevox-knowledge/35_specs/2026-04-19-e10-scrum-master-agent.md')
assert p is not None and p.exists(), f'expected to resolve, got {p}'
adrs = extract_adrs_from_content('see bevox-knowledge/30_adr/ADR-006-autonomy-permissions-approval.md for more')
assert 'bevox-knowledge/30_adr/ADR-006-autonomy-permissions-approval.md' in adrs
print('OK context_loader')
"
```

Expected: `OK context_loader`.

### Task 7.2: lib/safety.py

**Files:**
- Create: `~/.openclaw/clarification-agent/lib/safety.py`

- [ ] **Step 1: Escrever safety.py**

```python
"""Safety: valida answer estrutural + binary confidence (safe|unsafe).

Checks aplicados:
- Sources citadas existem no filesystem (senao force unsafe; hallucination guard)
- Presence de escalation_reason quando unsafe
- Confidence eh um dos dois valores canonicos
"""

from pathlib import Path
from typing import Any, Dict, List, Tuple

from . import context_loader


VALID_CONFIDENCE = {"safe", "unsafe"}


class SafetyError(Exception):
    def __init__(self, code: str, detail: str):
        self.code = code
        self.detail = detail
        super().__init__(f"{code}: {detail}")


def validate_confidence(value: str) -> None:
    if value not in VALID_CONFIDENCE:
        raise SafetyError(
            "INVALID_CONFIDENCE",
            f"confidence='{value}' nao e 'safe'|'unsafe'",
        )


def validate_sources(sources: List[str]) -> Tuple[List[str], List[str]]:
    """Resolve cada source path. Retorna (valid, invalid)."""
    valid, invalid = [], []
    for s in sources:
        # Strip eventuais anotacoes tipo ' (lines 45-67)' ou '#section'
        path_part = s.split(" ")[0].split("#")[0].strip("`")
        p = context_loader.resolve_ref_path(path_part)
        if p is not None and p.exists():
            valid.append(s)
        else:
            invalid.append(s)
    return valid, invalid


def enforce_safety(
    confidence: str,
    sources: List[str],
    escalation_reason: str,
) -> Tuple[str, str]:
    """Aplica safety rules. Retorna (effective_confidence, effective_reason).

    Rules:
    1. Se confidence=safe mas sources invalidas → force unsafe + reason.
    2. Se confidence=safe mas sources vazias → force unsafe + reason (no grounding).
    3. Se confidence=unsafe sem reason → injetar default reason.
    """
    validate_confidence(confidence)
    valid_sources, invalid_sources = validate_sources(sources)

    if confidence == "safe":
        if not valid_sources:
            return "unsafe", (
                "forced_unsafe: confidence=safe declarada mas zero sources "
                "validas. Drafter pode estar alucinando; escalation obrigatoria."
            )
        if invalid_sources:
            return "unsafe", (
                f"forced_unsafe: sources invalidas detectadas (hallucination guard): "
                f"{invalid_sources[:3]}. valid={valid_sources[:3]}"
            )
        return "safe", ""

    # confidence == unsafe
    reason = escalation_reason.strip() or "unspecified: drafter did not provide escalation_reason"
    return "unsafe", reason
```

- [ ] **Step 2: Sanity**

```bash
cd ~/.openclaw/clarification-agent && PYTHONPATH=. python3 -c "
from lib.safety import enforce_safety, validate_confidence, validate_sources, SafetyError
c, r = enforce_safety('safe', ['bevox-knowledge/35_specs/2026-04-19-e10-scrum-master-agent.md'], '')
assert c == 'safe', (c, r)
c, r = enforce_safety('safe', ['nonexistent/path.md'], '')
assert c == 'unsafe'
assert 'hallucination' in r
c, r = enforce_safety('safe', [], '')
assert c == 'unsafe'
c, r = enforce_safety('unsafe', [], 'need architecture decision')
assert c == 'unsafe' and r == 'need architecture decision'
try:
    validate_confidence('medium'); assert False
except SafetyError as e:
    assert e.code == 'INVALID_CONFIDENCE'
print('OK safety')
"
```

Expected: `OK safety`.

---

## Phase 8: clarification-agent — drafter

### Task 8.1: lib/drafter.py (claude -p subprocess)

**Files:**
- Create: `~/.openclaw/clarification-agent/lib/drafter.py`

- [ ] **Step 1: Escrever drafter.py**

```python
"""Drafter: invoca subprocess claude -p com prompt estruturado + parseia response.

Plano B Spike-5 aplicado: zero Anthropic SDK; usa claude CLI.
Model default: claude-haiku-4-5 (barato + rapido para QA).
"""

import json
import re
import subprocess
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from . import context_loader
from . import safety


DRAFTER_MODEL = "claude-haiku-4-5"
DRAFTER_TIMEOUT_SECONDS = 120


class DrafterError(Exception):
    def __init__(self, code: str, detail: str):
        self.code = code
        self.detail = detail
        super().__init__(f"{code}: {detail}")


def _build_prompt(
    task_id: str, question: str, ctx_bundle: Dict[str, Any],
) -> str:
    """Monta prompt estruturado com contexto + pergunta + instrucoes de output."""
    task = ctx_bundle.get("task") or {}
    payload = ctx_bundle.get("dispatch_payload") or {}
    refs = ctx_bundle.get("read_refs") or []

    refs_block = ""
    for r in refs[:10]:  # limita a 10 pra nao estourar context
        content = r["content"][:8000]  # limita por ref
        refs_block += f"\n### {r['ref']} (path: {r['path']})\n\n```\n{content}\n```\n"

    unresolved = ctx_bundle.get("unresolved_refs") or []
    unresolved_block = ""
    if unresolved:
        unresolved_block = "\n### Unresolved refs (informative)\n" + "\n".join(f"- {r}" for r in unresolved)

    prompt = f"""Voce e um agente de clarification do OpenClaw. Responda a duvida operacional
de outra sessao Claude Code (executor) estritamente com base no contexto fornecido.

NAO invente informacao. Se nao houver base no contexto, declare unsafe.

## Task alvo

- id: {task_id}
- title: {task.get("title", "")}
- epic_id: {task.get("epic_id", "")}
- wave_ref: {task.get("wave_ref", "")}

## Dispatch payload

- goal: {payload.get("goal", "")[:300]}
- acceptance_criteria: {payload.get("acceptance_criteria", [])}
- files_relevant: {payload.get("files_relevant", [])}
- guardrails: {payload.get("guardrails", [])}
- out_of_scope: {payload.get("out_of_scope", [])}

## Contexto canonico

{refs_block}

{unresolved_block}

## Pergunta do executor

{question}

## Formato OBRIGATORIO da resposta

Responda EXATAMENTE neste formato JSON (e nada alem disso; zero prose fora do JSON):

```json
{{
  "answer": "<texto da resposta, markdown permitido>",
  "sources": ["<ref>", "<ref com linhas ou secao>"],
  "confidence": "safe" | "unsafe",
  "escalation_reason": "<motivo se unsafe; string vazia se safe>"
}}
```

Regras:
- `confidence=safe`: resposta esta ancorada em trechos concretos dos refs fornecidos.
  Lista sources minimo 1 path que EXISTE no contexto acima.
- `confidence=unsafe`: resposta exigiria decisao arquitetural nao documentada
  OU contradicao entre refs OU source insuficiente. Escreve escalation_reason claro.
- NUNCA invente paths de sources que nao estao no contexto acima.
- Se pergunta pede "qual e a decisao X", mas decisao nao esta nos refs, escreva
  unsafe + reason="no supporting source for <topic>".
"""
    return prompt


def _parse_response(raw: str) -> Dict[str, Any]:
    """Extrai JSON block do output do claude -p. Tolera ```json fences."""
    # Tenta achar bloco ```json ... ``` primeiro
    m = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", raw, re.DOTALL)
    if m:
        block = m.group(1)
    else:
        # Fallback: primeiro { ... } balanceado
        start = raw.find("{")
        if start == -1:
            raise DrafterError("PARSE_NO_JSON", f"output sem JSON: {raw[:300]}")
        # Heurística: assume JSON ate ultimo }
        end = raw.rfind("}")
        if end == -1 or end <= start:
            raise DrafterError("PARSE_NO_JSON", f"JSON malformado: {raw[:300]}")
        block = raw[start : end + 1]
    try:
        parsed = json.loads(block)
    except json.JSONDecodeError as e:
        raise DrafterError("PARSE_JSON_INVALID", f"{e}: {block[:300]}")
    for field in ("answer", "sources", "confidence"):
        if field not in parsed:
            raise DrafterError("PARSE_MISSING_FIELD", f"field '{field}' ausente")
    if not isinstance(parsed["sources"], list):
        parsed["sources"] = [str(parsed["sources"])]
    parsed.setdefault("escalation_reason", "")
    return parsed


def draft_answer(
    task_id: str, question: str,
    ctx_bundle: Optional[Dict[str, Any]] = None,
    model: str = DRAFTER_MODEL,
) -> Dict[str, Any]:
    """Executa draft: monta prompt + subprocess claude -p + parseia + enforce safety.

    Retorna dict: {'answer', 'sources', 'confidence' (effective), 'escalation_reason'
    (effective), 'raw_response', 'drafter_model'}.

    Campo `confidence` eh o EFFECTIVE pos-safety enforcement (pode ser downgraded
    de safe pra unsafe se sources invalidas).
    """
    if ctx_bundle is None:
        ctx_bundle = context_loader.build_context_bundle(task_id)
    prompt = _build_prompt(task_id, question, ctx_bundle)
    try:
        result = subprocess.run(
            ["claude", "-p", prompt, "--model", model, "--allowedTools", ""],
            capture_output=True, text=True, check=False,
            timeout=DRAFTER_TIMEOUT_SECONDS,
        )
    except (OSError, subprocess.TimeoutExpired) as e:
        raise DrafterError("CLAUDE_SUBPROCESS_FAILED", f"{type(e).__name__}: {e}")
    if result.returncode != 0:
        raise DrafterError(
            "CLAUDE_EXIT_NONZERO",
            f"exit={result.returncode} stderr={result.stderr[:200]}",
        )
    parsed = _parse_response(result.stdout)
    effective_confidence, effective_reason = safety.enforce_safety(
        parsed["confidence"], parsed["sources"], parsed.get("escalation_reason", ""),
    )
    return {
        "answer": parsed["answer"],
        "sources": parsed["sources"],
        "confidence": effective_confidence,
        "escalation_reason": effective_reason,
        "raw_response": result.stdout[:5000],
        "drafter_model": model,
    }
```

- [ ] **Step 2: Sanity parse**

```bash
cd ~/.openclaw/clarification-agent && PYTHONPATH=. python3 -c "
from lib.drafter import _parse_response, DrafterError
raw = '''Here is my answer:
\`\`\`json
{\"answer\": \"use X\", \"sources\": [\"bevox-knowledge/35_specs/a.md\"], \"confidence\": \"safe\", \"escalation_reason\": \"\"}
\`\`\`
'''
p = _parse_response(raw)
assert p['answer'] == 'use X'
assert p['confidence'] == 'safe'
print('OK drafter parse')

# Fallback sem fence
raw2 = '{\"answer\": \"z\", \"sources\": [], \"confidence\": \"unsafe\", \"escalation_reason\": \"no source\"}'
p2 = _parse_response(raw2)
assert p2['confidence'] == 'unsafe'
print('OK drafter fallback')
"
```

Expected: 2 OKs.

---

## Phase 9: clarification-agent — lifecycle

### Task 9.1: lib/lifecycle.py (ask cycle + block flag + auto-resolve)

**Files:**
- Create: `~/.openclaw/clarification-agent/lib/lifecycle.py`

- [ ] **Step 1: Escrever lifecycle.py**

```python
"""Clarification lifecycle: orquestra ask->draft->resolve.

Integra com kanban-tasks CLI pra block/unblock + set-dispatch-payload.
"""

import json
import subprocess
from pathlib import Path
from typing import Any, Dict, Optional

from . import store
from . import drafter as drafter_lib
from . import context_loader

KANBAN_CLI = Path("~/.openclaw/kanban-tasks/cli.sh")


class LifecycleError(Exception):
    def __init__(self, code: str, detail: str):
        self.code = code
        self.detail = detail
        super().__init__(f"{code}: {detail}")


def _run_kanban(args: list, actor: str = "clarification") -> Dict[str, Any]:
    cmd = [str(KANBAN_CLI)] + args + ["--json", "--actor", actor]
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, check=False, timeout=30)
    except (OSError, subprocess.TimeoutExpired) as e:
        raise LifecycleError("KANBAN_CLI_TIMEOUT", str(e))
    if r.returncode != 0:
        raise LifecycleError("KANBAN_CLI_FAILED",
                             f"exit={r.returncode} stderr={r.stderr.strip()[:200]}")
    try:
        return json.loads(r.stdout)
    except json.JSONDecodeError as e:
        raise LifecycleError("KANBAN_CLI_BAD_JSON", str(e))


def block_for_clarification(task_id: str, question_summary: str) -> None:
    """task.blocked=true, reason='clarification_required: <summary>'."""
    reason = f"clarification_required: {question_summary[:80]}"
    _run_kanban(["task", "block", task_id, "--reason", reason])


def mark_escalation(task_id: str, escalation_reason: str) -> None:
    """Muda blocked_reason pra clarification_escalation_required.

    kanban-tasks nao tem 'update-blocked-reason'; estrategia: unblock + re-block
    com novo reason. Risco: race janela pequena. Aceitavel.
    """
    _run_kanban(["task", "unblock", task_id])
    reason = f"clarification_escalation_required: {escalation_reason[:80]}"
    _run_kanban(["task", "block", task_id, "--reason", reason])


def unblock(task_id: str) -> None:
    _run_kanban(["task", "unblock", task_id])


def reject_task(task_id: str, reason: str) -> None:
    """Move pra rejected com reason."""
    _run_kanban(["task", "move", task_id, "rejected", "--reason", reason])


def merge_dispatch_payload(task_id: str, fields: Dict[str, Any]) -> None:
    _run_kanban([
        "task", "set-dispatch-payload", task_id,
        "--payload", json.dumps(fields, ensure_ascii=False), "--merge",
    ])


def ask_and_draft(
    task_id: str, question_text: str, model: Optional[str] = None,
) -> Dict[str, Any]:
    """Cycle completo de ask (sem --and-wait):

    1. gera clarification_id sequencial
    2. escreve questions/<id>.md
    3. block kanban task com reason=clarification_required
    4. merge dispatch metadata (last_clarification_id, etc)
    5. invoca drafter (pode demorar ~30s-2min)
    6. escreve answers/<id>.md
    7. safe: unblock + merge resolved metadata + emit_signal(safe)
    8. unsafe: re-block com escalation reason + write_escalation_symlink +
       merge escalated metadata + DO NOT emit signal (aguarda humano)

    Retorna: {'clarification_id', 'confidence' (effective), 'answer_path',
    'question_path', 'escalation_reason'|None, 'outcome': 'safe'|'escalated'}
    """
    seq = store.next_clarification_seq(task_id)
    clarification_id = store.make_clarification_id(task_id, seq)

    question_path = store.write_question(clarification_id, question_text)
    q_summary = question_text.strip().split("\n")[0][:80]
    block_for_clarification(task_id, q_summary)
    merge_dispatch_payload(task_id, {
        "last_clarification_id": clarification_id,
        "last_clarification_question_path": str(question_path),
        "clarification_count": seq,
    })

    drafter_kwargs = {}
    if model:
        drafter_kwargs["model"] = model
    draft_result = drafter_lib.draft_answer(task_id, question_text, **drafter_kwargs)

    answer_path = store.write_answer(
        clarification_id,
        question_path,
        draft_result["answer"],
        draft_result["confidence"],
        draft_result["sources"],
        drafter=f"clarification-agent ({draft_result['drafter_model']})",
        escalation_reason=draft_result.get("escalation_reason") or None,
    )

    if draft_result["confidence"] == "safe":
        unblock(task_id)
        merge_dispatch_payload(task_id, {
            "last_clarification_answer_path": str(answer_path),
            "last_clarification_confidence": "safe",
            "last_clarification_resolved_at": store.now_iso(),
        })
        store.emit_signal(clarification_id, "safe")
        return {
            "clarification_id": clarification_id,
            "confidence": "safe",
            "answer_path": str(answer_path),
            "question_path": str(question_path),
            "outcome": "safe",
            "answer_text": draft_result["answer"],
        }
    # Unsafe -> escalation
    store.write_escalation_symlink(clarification_id)
    mark_escalation(task_id, draft_result["escalation_reason"])
    merge_dispatch_payload(task_id, {
        "last_clarification_answer_path": str(answer_path),
        "last_clarification_confidence": "unsafe",
        "last_clarification_escalated_at": store.now_iso(),
    })
    return {
        "clarification_id": clarification_id,
        "confidence": "unsafe",
        "answer_path": str(answer_path),
        "question_path": str(question_path),
        "escalation_reason": draft_result["escalation_reason"],
        "outcome": "escalated",
    }
```

- [ ] **Step 2: Sanity import + signatures**

```bash
cd ~/.openclaw/clarification-agent && PYTHONPATH=. python3 -c "
from lib.lifecycle import (
    block_for_clarification, unblock, reject_task, mark_escalation,
    merge_dispatch_payload, ask_and_draft, LifecycleError,
)
print('OK lifecycle imports')
"
```

Expected: `OK lifecycle imports`.

---

## Phase 10: clarification-agent — CLI

### Task 10.1: lib/api.py completo

**Files:**
- Create: `~/.openclaw/clarification-agent/lib/api.py`

- [ ] **Step 1: Escrever api.py**

```python
"""CLI clarification-agent."""

import argparse
import json
import sys
import time
from pathlib import Path
from typing import Any, Optional

from . import context_loader
from . import drafter as drafter_lib
from . import lifecycle as lifecycle_lib
from . import safety
from . import store

EXIT_OK = 0
EXIT_INPUT = 1
EXIT_STATE = 2
EXIT_PROPOSES_REJECTION = 3
EXIT_REJECTED_TASK = 4
EXIT_SIGTERM_CANCELED = 130

VALID_REJECT_CATEGORIES = {
    "task_malformed", "spec_inconsistent", "requires_re_decomposition",
    "inexecutable", "manual",
}

_EXIT_BY_CODE = {
    "KANBAN_CLI_TIMEOUT": EXIT_STATE,
    "KANBAN_CLI_FAILED": EXIT_STATE,
    "KANBAN_CLI_BAD_JSON": EXIT_STATE,
    "TASK_NOT_FOUND": EXIT_INPUT,
    "CLAUDE_SUBPROCESS_FAILED": EXIT_STATE,
    "CLAUDE_EXIT_NONZERO": EXIT_STATE,
    "PARSE_NO_JSON": EXIT_STATE,
    "PARSE_JSON_INVALID": EXIT_STATE,
    "PARSE_MISSING_FIELD": EXIT_STATE,
    "INVALID_REJECT_CATEGORY": EXIT_INPUT,
    "CLARIFICATION_NOT_FOUND": EXIT_INPUT,
}


def _err(msg: str, code: str, json_mode: bool) -> int:
    if json_mode:
        print(json.dumps({"ok": False, "error": msg, "code": code}))
    else:
        print(f"ERROR ({code}): {msg}", file=sys.stderr)
    return _EXIT_BY_CODE.get(code, EXIT_STATE)


def _print(payload: Any, json_mode: bool, human: Optional[str] = None) -> None:
    if json_mode:
        print(json.dumps(payload, ensure_ascii=False, indent=2))
    else:
        if human is not None:
            print(human)
        else:
            print(json.dumps(payload, ensure_ascii=False, indent=2))


# ============ cmd_ask ============

def cmd_ask(args: argparse.Namespace) -> int:
    """ask cycle: ler question + draft + resolve ou escalate.

    --and-wait: se safe, retorna answer no stdout. Se unsafe, poll-block
    esperando signal humano.
    """
    if args.question_file:
        try:
            with open(args.question_file, "r", encoding="utf-8") as f:
                question = f.read().strip()
        except OSError as e:
            return _err(str(e), "QUESTION_FILE_READ_FAILED", args.json)
    else:
        question = args.question or ""
        if not question.strip():
            return _err("--question ou --question-file obrigatorio", "invalid_input", args.json)

    try:
        result = lifecycle_lib.ask_and_draft(args.task_id, question, model=args.model)
    except (lifecycle_lib.LifecycleError, drafter_lib.DrafterError) as e:
        return _err(e.detail, e.code, args.json)

    outcome = result["outcome"]
    cid = result["clarification_id"]

    # Sem --and-wait: retorna imediato
    if not args.and_wait:
        _print(result, args.json,
               f"clarification {cid}: {outcome}\n"
               f"  question: {result['question_path']}\n"
               f"  answer:   {result['answer_path']}")
        return EXIT_OK

    # Com --and-wait:
    if outcome == "safe":
        # Safe já resolvido: print answer pro executor (Claude Code) ler
        _print({"answer": result["answer_text"], "confidence": "safe",
                "sources_path": result["answer_path"]}, args.json,
               result["answer_text"])
        return EXIT_OK

    # Unsafe: poll loop ate signal aparecer
    try:
        while True:
            sig = store.read_signal(cid)
            if sig:
                break
            time.sleep(5)
    except KeyboardInterrupt:
        return _err("canceled by SIGTERM/SIGINT during --and-wait", "SIGTERM", args.json)

    if sig.get("outcome") == "safe" or sig.get("outcome") == "override":
        # Ler answer final (override escreveu answer manual)
        import os
        ans_path = store.ANSWERS_DIR / f"{cid}.md"
        if sig.get("outcome") == "override":
            # Prefer override answer path se existir
            ov = store.ANSWERS_DIR / f"{cid}-override.md"
            if ov.exists():
                ans_path = ov
        try:
            content = ans_path.read_text(encoding="utf-8")
        except OSError:
            content = "(answer file unavailable)"
        _print({"answer_file_content": content, "outcome": sig["outcome"]},
               args.json, content)
        return EXIT_OK
    if sig.get("outcome") == "rejected":
        _print({"outcome": "rejected",
                "message": "Task foi rejeitada pelo operador. Encerre sem commitar."},
               args.json,
               "CLARIFICATION_REJECTED_TASK: task foi movida para rejected")
        return EXIT_REJECTED_TASK
    return _err(f"outcome desconhecido: {sig}", "INVALID_SIGNAL", args.json)


# ============ cmd_escalations / cmd_show ============

def cmd_escalations(args: argparse.Namespace) -> int:
    escalations = store.list_escalations()
    if args.json:
        _print({"escalations": escalations}, True)
        return EXIT_OK
    if not escalations:
        print("(nenhuma escalation pending)")
        return EXIT_OK
    print("CLARIFICATION_ID                      ESCALATION_PATH")
    for e in escalations:
        print(f"{e['clarification_id']:38s} {e['escalation_path']}")
    return EXIT_OK


def cmd_show(args: argparse.Namespace) -> int:
    """Mostra question + answer pra <task-id> OU <clarification-id>."""
    target = args.target
    # Se parece task-id sem -clr-: lista todas clarifications da task
    if "-clr-" not in target:
        import re
        pat = re.compile(re.escape(target) + r"-clr-\d+\.md$")
        if not store.QUESTIONS_DIR.exists():
            return _err(f"nenhuma clarification pra {target}", "CLARIFICATION_NOT_FOUND", args.json)
        matches = sorted([p.stem for p in store.QUESTIONS_DIR.iterdir() if pat.match(p.name)])
        if not matches:
            return _err(f"nenhuma clarification pra {target}", "CLARIFICATION_NOT_FOUND", args.json)
        if args.json:
            _print({"clarification_ids": matches}, True)
            return EXIT_OK
        print(f"clarifications for {target}:")
        for cid in matches:
            print(f"  {cid}")
        return EXIT_OK

    cid = target
    qpath = store.QUESTIONS_DIR / f"{cid}.md"
    apath = store.ANSWERS_DIR / f"{cid}.md"
    if not qpath.exists():
        return _err(f"question {cid} nao existe", "CLARIFICATION_NOT_FOUND", args.json)
    q_content = qpath.read_text(encoding="utf-8")
    a_content = apath.read_text(encoding="utf-8") if apath.exists() else "(answer pending)"
    if args.json:
        _print({"clarification_id": cid, "question": q_content, "answer": a_content}, True)
        return EXIT_OK
    print(f"=== {cid} — QUESTION ===\n{q_content}\n")
    print(f"=== {cid} — ANSWER ===\n{a_content}")
    return EXIT_OK


# ============ cmd_override / cmd_reject_task / cmd_redraft ============

def cmd_override(args: argparse.Namespace) -> int:
    # Encontra clarification_id mais recente da task
    import re
    pat = re.compile(re.escape(args.task_id) + r"-clr-(\d+)\.md$")
    max_seq = 0
    latest_cid = None
    if store.QUESTIONS_DIR.exists():
        for p in store.QUESTIONS_DIR.iterdir():
            m = pat.match(p.name)
            if m and int(m.group(1)) > max_seq:
                max_seq = int(m.group(1))
                latest_cid = p.stem
    if latest_cid is None:
        return _err(f"nenhuma clarification pending pra {args.task_id}", "CLARIFICATION_NOT_FOUND", args.json)

    # Escreve answer override
    override_path = store.ANSWERS_DIR / f"{latest_cid}-override.md"
    body = f"""# Clarification override — {latest_cid}

**Overridden by:** bernard
**Overridden at:** {store.now_iso()}
**Confidence:** manual_override (human-authored)

---

## Answer

{args.answer}
"""
    store._atomic_write(override_path, body)

    # Kanban ops
    try:
        lifecycle_lib.unblock(args.task_id)
        lifecycle_lib.merge_dispatch_payload(args.task_id, {
            "last_clarification_confidence": "manual_override",
            "last_clarification_override_path": str(override_path),
            "last_clarification_resolved_at": store.now_iso(),
        })
    except lifecycle_lib.LifecycleError as e:
        return _err(e.detail, e.code, args.json)

    # Emit signal + clear escalation
    store.emit_signal(latest_cid, "override")
    store.clear_escalation_symlink(latest_cid)

    _print({"ok": True, "clarification_id": latest_cid, "override_path": str(override_path)},
           args.json,
           f"override committed: {latest_cid}\n  unblocked {args.task_id}")
    return EXIT_OK


def cmd_reject_task(args: argparse.Namespace) -> int:
    # Valida categoria
    parts = args.reason.split(":", 1)
    if not parts or parts[0].strip() not in VALID_REJECT_CATEGORIES:
        return _err(
            f"categoria invalida. Use '<cat>: <detail>' com cat em "
            f"{sorted(VALID_REJECT_CATEGORIES)}",
            "INVALID_REJECT_CATEGORY", args.json,
        )
    try:
        lifecycle_lib.reject_task(args.task_id, args.reason)
    except lifecycle_lib.LifecycleError as e:
        return _err(e.detail, e.code, args.json)

    # Emit signal pra --and-wait pendente
    import re
    pat = re.compile(re.escape(args.task_id) + r"-clr-(\d+)\.md$")
    latest_cid = None
    max_seq = 0
    if store.QUESTIONS_DIR.exists():
        for p in store.QUESTIONS_DIR.iterdir():
            m = pat.match(p.name)
            if m and int(m.group(1)) > max_seq:
                max_seq = int(m.group(1))
                latest_cid = p.stem
    if latest_cid:
        store.emit_signal(latest_cid, "rejected")
        store.clear_escalation_symlink(latest_cid)

    _print({"ok": True, "task_id": args.task_id, "reason": args.reason}, args.json,
           f"rejected: {args.task_id} (reason: {args.reason})")
    return EXIT_OK


def cmd_redraft(args: argparse.Namespace) -> int:
    # Re-invoca ask_and_draft com same question, novo clarification_id
    import re
    pat = re.compile(re.escape(args.task_id) + r"-clr-(\d+)\.md$")
    max_seq = 0
    latest_cid = None
    for p in store.QUESTIONS_DIR.iterdir():
        m = pat.match(p.name)
        if m and int(m.group(1)) > max_seq:
            max_seq = int(m.group(1))
            latest_cid = p.stem
    if latest_cid is None:
        return _err(f"nenhuma clarification pra {args.task_id}", "CLARIFICATION_NOT_FOUND", args.json)
    # Le pergunta original
    qpath = store.QUESTIONS_DIR / f"{latest_cid}.md"
    content = qpath.read_text(encoding="utf-8")
    # Extrai question text (remove header ate primeiro '---\n\n')
    idx = content.find("\n---\n\n")
    question = content[idx + 6:].strip() if idx >= 0 else content
    # clear escalation symlink atual (será regerado se novamente unsafe)
    store.clear_escalation_symlink(latest_cid)
    try:
        result = lifecycle_lib.ask_and_draft(args.task_id, question, model=args.model)
    except (lifecycle_lib.LifecycleError, drafter_lib.DrafterError) as e:
        return _err(e.detail, e.code, args.json)
    _print(result, args.json,
           f"redraft {result['clarification_id']}: {result['outcome']}")
    return EXIT_OK


# ============ Parser ============

def build_parser() -> argparse.ArgumentParser:
    common = argparse.ArgumentParser(add_help=False)
    common.add_argument("--json", action="store_true")
    common.add_argument("--actor", default="clarification")

    p = argparse.ArgumentParser(prog="clarification-agent")
    sub = p.add_subparsers(dest="cmd", required=True)
    def leaf(psub, name):
        return psub.add_parser(name, parents=[common])

    ak = leaf(sub, "ask")
    ak.add_argument("task_id")
    ak.add_argument("--question", default=None)
    ak.add_argument("--question-file", default=None)
    ak.add_argument("--and-wait", action="store_true")
    ak.add_argument("--model", default="claude-haiku-4-5")
    ak.set_defaults(func=cmd_ask)

    es = leaf(sub, "escalations")
    es.set_defaults(func=cmd_escalations)

    sh = leaf(sub, "show")
    sh.add_argument("target", help="task-id ou clarification-id")
    sh.set_defaults(func=cmd_show)

    ov = leaf(sub, "override")
    ov.add_argument("task_id")
    ov.add_argument("--answer", required=True)
    ov.add_argument("--commit", action="store_true",
                    help="obrigatorio pra aplicar; sem --commit faz dry-run")
    ov.set_defaults(func=cmd_override)

    rj = leaf(sub, "reject-task")
    rj.add_argument("task_id")
    rj.add_argument("--reason", required=True, help="<categoria>: <detail>")
    rj.add_argument("--commit", action="store_true",
                    help="obrigatorio pra aplicar")
    rj.set_defaults(func=cmd_reject_task)

    rd = leaf(sub, "redraft")
    rd.add_argument("task_id")
    rd.add_argument("--model", default="claude-haiku-4-5")
    rd.set_defaults(func=cmd_redraft)

    return p


def main(argv=None) -> int:
    p = build_parser()
    args = p.parse_args(argv)
    # cmd_override e cmd_reject_task exigem --commit explicito
    if args.cmd in ("override", "reject-task") and not getattr(args, "commit", False):
        print("ERROR: --commit obrigatorio pra aplicar (gate humano)", file=sys.stderr)
        return EXIT_INPUT
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 2: Sanity CLI**

```bash
~/.openclaw/clarification-agent/cli.sh --help 2>&1 | head -10
~/.openclaw/clarification-agent/cli.sh escalations
~/.openclaw/clarification-agent/cli.sh reject-task T-9999 --reason "invalid_cat: test" 2>&1 | head -3
~/.openclaw/clarification-agent/cli.sh reject-task T-9999 --reason "manual: test"
```

Expected:
- help renderiza
- `(nenhuma escalation pending)`
- Primeira reject-task: erro `--commit obrigatorio`
- Segunda (sem --commit): erro `--commit obrigatorio`

### Task 10.2: Sandbox clarification (sem claude real)

- [ ] **Step 1: Sanity isolado (sem invocar claude)**

```bash
cd ~/.openclaw/clarification-agent && PYTHONPATH=. python3 -c "
from lib.store import next_clarification_seq, list_escalations
# apenas validar paths + seq logic
seq = next_clarification_seq('T-ISOLATED')
assert seq == 1
escs = list_escalations()
assert isinstance(escs, list)
print('OK clarification isolation')
"
```

Expected: `OK clarification isolation`.

---

## Phase 11: Integration E2E smoke

### Task 11.1: Baseline + fixture setup

**Files:** none (prep)

- [ ] **Step 1: Baseline snapshot**

```bash
cd ~/.openclaw/kanban-tasks
BASELINE_EVENTS=$(wc -l < events.jsonl)
cp state.json /tmp/state.ph11-baseline.json
cp events.jsonl /tmp/events.ph11-baseline.jsonl
echo "baseline events: $BASELINE_EVENTS"
```

- [ ] **Step 2: Criar fixture plan + accept via scrum-master**

```bash
cat > /tmp/ph11-plan.md <<'EOF'
# Phase 11 dogfood plan

**Goal:** validar dispatcher + clarification E2E

**Epico:** E10/dispatcher-clarification-dogfood

**Project:** openclaw

**Specs canonicas:**
- `bevox-knowledge/35_specs/2026-04-19-e10-dispatcher-and-clarification-agents.md`

## Phase 0: trivial

### Task 0.1: Escrever hello world

Tarefa minima: escrever string hello no filesystem.

**Files:**
- Create: `/tmp/ph11-output.txt`

- [ ] **Step 1: escrever**

Run: bash comando
Expected: arquivo criado com "hello"
EOF

# tracker precisa ter entry pra "E10/dispatcher-clarification-dogfood" senão scrum-master rejeita
# atalho: usar wave-ref existente E10/scrum-master-agent
sed -i 's|E10/dispatcher-clarification-dogfood|E10/scrum-master-agent|' /tmp/ph11-plan.md

~/.openclaw/scrum-master-agent/cli.sh propose --plan /tmp/ph11-plan.md --target-sprint current
PID=$(~/.openclaw/scrum-master-agent/cli.sh list --status pending --json | python3 -c "import json,sys; print(json.load(sys.stdin)['proposals'][-1]['proposal_id'])")
~/.openclaw/scrum-master-agent/cli.sh accept $PID --ready
TID=$(~/.openclaw/scrum-master-agent/cli.sh show $PID --json | python3 -c "import json,sys; print(json.load(sys.stdin)['state']['materialized_task_ids'][0])")
echo "fixture task (ready): $TID"
```

Expected: task in `ready`, T-NNNN id.

### Task 11.2: Dispatcher happy path dry-run

- [ ] **Step 1: Dry-run dispatcher next**

```bash
~/.openclaw/dispatcher-agent/cli.sh next --project openclaw
ls -la ~/.openclaw/dispatcher-agent/briefings/
echo '---briefing first 30 lines---'
BPATH=$(~/.openclaw/dispatcher-agent/cli.sh next --project openclaw --json | python3 -c "import json,sys; print(json.load(sys.stdin)['briefing_path'])")
head -30 $BPATH
```

Expected: briefing gerado, primeiras 30 linhas mostram header + contexto canônico + INSTRUCOES OPERACIONAIS.

### Task 11.3: Dispatcher launch detached (foreground pra debug)

- [ ] **Step 1: Launch foreground (debug, blocking)**

Foreground em vez de detached pra smoke ter output imediato. Timeout conservador.

```bash
timeout 120 ~/.openclaw/dispatcher-agent/cli.sh next --project openclaw --launch --foreground --model claude-haiku-4-5 2>&1 | tail -20
```

Expected: Claude Code executa, escreve `/tmp/ph11-output.txt`, dispatcher detecta exit 0, auto-move pra testing. Kanban task state pós: `testing` + blocked=false.

- [ ] **Step 2: Verificar state kanban**

```bash
~/.openclaw/kanban-tasks/cli.sh task show $TID --json | python3 -c "
import json,sys
t = json.load(sys.stdin)['task']
print(f'status={t[\"status\"]}  blocked={t.get(\"blocked\")}')
dp = t.get('dispatch_payload') or {}
print(f'auto_moved_to_testing_at: {dp.get(\"auto_moved_to_testing_at\")}')
print(f'execution_exit_code: {dp.get(\"execution_exit_code\")}')
assert t['status'] == 'testing'
assert t.get('blocked') is False
assert dp.get('execution_exit_code') == 0
print('OK happy path')
"
cat /tmp/ph11-output.txt 2>/dev/null | head -3
```

Expected: `OK happy path` + output file existe com conteúdo "hello".

### Task 11.4: Cleanup cenário 1 + re-setup cenário 2

- [ ] **Step 1: Archive + reset pro próximo smoke**

```bash
~/.openclaw/kanban-tasks/cli.sh task archive $TID >/dev/null
rm -f /tmp/ph11-output.txt
```

### Task 11.5: Clarification safe path (simulação manual)

Como depende de Claude Code cooperar com a convention, smoke manual simula
via invocação direta do `ask`.

- [ ] **Step 1: Criar nova task + ready**

```bash
cat > /tmp/ph11-plan-2.md <<'EOF'
# Plan 2

**Goal:** testar clarification safe

**Epico:** E10/scrum-master-agent

**Project:** openclaw

**Specs canonicas:**
- `bevox-knowledge/35_specs/2026-04-19-e10-dispatcher-and-clarification-agents.md`

## Phase 0: setup

### Task 0.1: clar safe

Pergunta esperada: "Qual e o nome canonico do agent da wave-2?"
Resposta vem dos spec_refs (clarification-agent).

**Files:**
- Create: `/tmp/ph11-clar.txt`

- [ ] **Step 1: stub**

Expected: arquivo criado
EOF

~/.openclaw/scrum-master-agent/cli.sh propose --plan /tmp/ph11-plan-2.md --target-sprint current
PID=$(~/.openclaw/scrum-master-agent/cli.sh list --status pending --json | python3 -c "import json,sys; print(json.load(sys.stdin)['proposals'][-1]['proposal_id'])")
~/.openclaw/scrum-master-agent/cli.sh accept $PID --ready
TID2=$(~/.openclaw/scrum-master-agent/cli.sh show $PID --json | python3 -c "import json,sys; print(json.load(sys.stdin)['state']['materialized_task_ids'][0])")
~/.openclaw/kanban-tasks/cli.sh task move $TID2 in_progress --actor bernard
echo "task in_progress: $TID2"
```

- [ ] **Step 2: Invocar clarification ask (sem --and-wait pra não poll)**

```bash
~/.openclaw/clarification-agent/cli.sh ask $TID2 \
  --question "Qual o nome canonico do agent que responde perguntas durante execucao do dispatcher?" \
  --model claude-haiku-4-5
```

Expected: output JSON-ish ou human. Outcome `safe` ou `escalated` depende do que o drafter decidir. Sources esperadas apontam pra spec citada.

- [ ] **Step 3: Verificar artifacts + kanban state**

```bash
ls ~/.openclaw/clarification-agent/questions/ | tail -3
ls ~/.openclaw/clarification-agent/answers/ | tail -3
~/.openclaw/kanban-tasks/cli.sh task show $TID2 --json | python3 -c "
import json,sys
t = json.load(sys.stdin)['task']
dp = t.get('dispatch_payload') or {}
print(f'blocked={t.get(\"blocked\")}  clarification_count={dp.get(\"clarification_count\")}')
print(f'last_confidence: {dp.get(\"last_clarification_confidence\")}')
"
```

Expected: arquivos criados; kanban mostra `clarification_count=1` + confidence=safe (ou unsafe se draft escapou).

- [ ] **Step 4: Cleanup cenário 2**

```bash
~/.openclaw/kanban-tasks/cli.sh task unblock $TID2 2>/dev/null || true
~/.openclaw/kanban-tasks/cli.sh task archive $TID2 >/dev/null
```

### Task 11.6: Escalation flow + override + reject

- [ ] **Step 1: Task + ask com pergunta deliberadamente sem base**

```bash
cat > /tmp/ph11-plan-3.md <<'EOF'
# Plan 3

**Goal:** testar escalation

**Epico:** E10/scrum-master-agent

**Project:** openclaw

**Specs canonicas:**
- `bevox-knowledge/35_specs/2026-04-19-e10-scrum-master-agent.md`

## Phase 0: x

### Task 0.1: escalation test

Teste de escalation.

**Files:**
- Create: `/tmp/ph11-esc.txt`

- [ ] **Step 1: stub**

Expected: arquivo
EOF

~/.openclaw/scrum-master-agent/cli.sh propose --plan /tmp/ph11-plan-3.md --target-sprint current
PID=$(~/.openclaw/scrum-master-agent/cli.sh list --status pending --json | python3 -c "import json,sys; print(json.load(sys.stdin)['proposals'][-1]['proposal_id'])")
~/.openclaw/scrum-master-agent/cli.sh accept $PID --ready
TID3=$(~/.openclaw/scrum-master-agent/cli.sh show $PID --json | python3 -c "import json,sys; print(json.load(sys.stdin)['state']['materialized_task_ids'][0])")
~/.openclaw/kanban-tasks/cli.sh task move $TID3 in_progress --actor bernard

~/.openclaw/clarification-agent/cli.sh ask $TID3 \
  --question "Qual o melhor sabor de sorvete do mundo? Justifique com citacoes de ADR." \
  --model claude-haiku-4-5
```

Expected: outcome `escalated` (drafter deve reconhecer que sorvete não é topic dos refs).

- [ ] **Step 2: Verificar escalation pending**

```bash
~/.openclaw/clarification-agent/cli.sh escalations
~/.openclaw/clarification-agent/cli.sh show $TID3
```

Expected: escalation listada; show mostra question + unsafe answer.

- [ ] **Step 3: Override manual do Bernard**

```bash
~/.openclaw/clarification-agent/cli.sh override $TID3 \
  --answer "Baunilha. Decidido manualmente." \
  --commit
```

Expected: override committed; task unblock; signal file `override`.

- [ ] **Step 4: Verificar state pós-override**

```bash
~/.openclaw/kanban-tasks/cli.sh task show $TID3 --json | python3 -c "
import json,sys
t = json.load(sys.stdin)['task']
dp = t.get('dispatch_payload') or {}
assert t.get('blocked') is False
assert dp.get('last_clarification_confidence') == 'manual_override'
print('OK override flow')
"
~/.openclaw/clarification-agent/cli.sh escalations  # should be empty
```

Expected: OK override flow + `(nenhuma escalation pending)`.

- [ ] **Step 5: Cleanup + smoke reject-task numa task nova**

```bash
~/.openclaw/kanban-tasks/cli.sh task archive $TID3 >/dev/null

cat > /tmp/ph11-plan-4.md <<'EOF'
# Plan 4 — reject smoke
**Goal:** testar reject-task
**Epico:** E10/scrum-master-agent
**Project:** openclaw
**Specs canonicas:**
- `bevox-knowledge/35_specs/2026-04-19-e10-scrum-master-agent.md`

## Phase 0: x
### Task 0.1: reject test
Teste reject.
**Files:**
- Create: `/tmp/ph11-rej.txt`
- [ ] **Step 1: stub**
Expected: x
EOF
~/.openclaw/scrum-master-agent/cli.sh propose --plan /tmp/ph11-plan-4.md --target-sprint current
PID=$(~/.openclaw/scrum-master-agent/cli.sh list --status pending --json | python3 -c "import json,sys; print(json.load(sys.stdin)['proposals'][-1]['proposal_id'])")
~/.openclaw/scrum-master-agent/cli.sh accept $PID --ready
TID4=$(~/.openclaw/scrum-master-agent/cli.sh show $PID --json | python3 -c "import json,sys; print(json.load(sys.stdin)['state']['materialized_task_ids'][0])")
~/.openclaw/kanban-tasks/cli.sh task move $TID4 in_progress --actor bernard

# Reject
~/.openclaw/clarification-agent/cli.sh reject-task $TID4 --reason "spec_inconsistent: smoke test" --commit
~/.openclaw/kanban-tasks/cli.sh task show $TID4 --json | python3 -c "
import json,sys
t=json.load(sys.stdin)['task']
assert t['status'] == 'rejected', t['status']
print(f'OK rejected: {t.get(\"rejected_reason\")}')"
```

Expected: `OK rejected: spec_inconsistent: smoke test`.

### Task 11.7: Restore baseline

- [ ] **Step 1: Restaurar kanban**

```bash
cd ~/.openclaw/kanban-tasks
cp /tmp/state.ph11-baseline.json state.json
cp /tmp/events.ph11-baseline.jsonl events.jsonl
./cli.sh rebuild >/dev/null
FINAL_EVENTS=$(wc -l < events.jsonl)
test "$FINAL_EVENTS" = "$BASELINE_EVENTS" && echo "OK kanban restored ($FINAL_EVENTS == baseline)"
```

Expected: `OK kanban restored ...`.

- [ ] **Step 2: Cleanup fixtures temp**

```bash
rm -f /tmp/ph11-plan*.md /tmp/ph11-output.txt /tmp/ph11-clar.txt /tmp/ph11-esc.txt /tmp/ph11-rej.txt
# Proposals do scrum-master: accepted, preservam no filesystem como audit
# (não removemos; são parte do histórico)
```

---

## Phase 12: Canonical artifacts

### Task 12.1: Playbook dispatcher-agent.md

**Files:**
- Create: `~/bevox-knowledge/20_architecture/agents/dispatcher-agent.md`

- [ ] **Step 1: Escrever playbook**

```markdown
<!-- Agent file do Dispatcher Agent — wave-2 do PRD orchestration.
     Modo: Hub-dispatch L1 supervisionado. Invoca Claude Code em
     background detached como executor.
     Spec canonica: 35_specs/2026-04-19-e10-dispatcher-and-clarification-agents.md
-->

# Agent: dispatcher-agent

> Runbook canonico. Spec:
> `35_specs/2026-04-19-e10-dispatcher-and-clarification-agents.md`.
> Design: `30_adr/ADR-003-agent-governance.md`. Policy:
> `30_adr/ADR-006-autonomy-permissions-approval.md`. Metadata:
> `20_architecture/agents/registry.yml`.

- **Owner:** <!-- DERIVED --> Bernard
- **Status:** <!-- DERIVED --> ativo
- **Level:** <!-- DERIVED --> L1
- **Modelo padrao:** <!-- DERIVED --> stdlib-python/no-model (invoca claude CLI)
- **Modelo fallback:** <!-- DERIVED --> none
- **Criado em:** <!-- DERIVED --> 2026-04-19

## Missao

Selecionar próxima task `ready`, gerar briefing a partir de
`dispatch_payload`, invocar Claude Code como subprocess detached
(foreground debug disponivel), capturar output em log, detectar exit
code, auto-mover `in_progress → testing` em exit 0, marcar blocked com
`execution_failed` em exit != 0.

Agente coordena; NAO escreve codigo. Claude Code continua sendo
executor unico.

## Inputs

- Invocacao manual: `vox dispatcher next --launch [--project X]`.
- Task `ready` nao-blocked no kanban-tasks (via scrum-master ou manual).
- `dispatch_payload` com `goal` no minimo.

## Outputs

- `~/.openclaw/dispatcher-agent/briefings/<task-id>.md`
- `~/.openclaw/dispatcher-agent/executions/<task-id>.log` +
  `.status.json`
- Kanban mutations: ready→in_progress, set-dispatch-payload --merge,
  auto in_progress→testing (exit 0) OU block execution_failed (exit != 0)

## Skills

- Subprocess `claude -p` (executor real).
- Subprocess `kanban-tasks/cli.sh task` (state machine).
- `setsid + nohup` via Python `start_new_session=True`.

## Limites

1. UMA task por invocacao. `--project` enforce: zero in_progress
   no mesmo projeto.
2. Auto-move apenas `in_progress → testing`. Nunca `→ done` nem `→ rejected`.
3. `--allowed-tools` restritivo por default (baseline em §10.2 da spec).
4. NAO invoca clarification-agent diretamente; Claude Code invoca se
   precisar (via Bash tool + convention do briefing).

## Approvals

Modo Hub-dispatch supervisionado. Gate unico: `vox dispatcher next
--launch` (CLI explicit Bernard). Hard limits ADR-006 aplicam.

## Playbook operacional

### 1. Registrar dispatch
Append em `~/.openclaw/workspace/shared/outputs/agent-dispatch.jsonl`.

### 2. Select next ready
Consome kanban `state.json` direto (MC eh projecao; pattern scrum-master).
Guard: check_one_task_per_project_guard.

### 3. Gerar briefing
Template §10.1 da spec. Embute convention pra `vox clarification ask
--and-wait`.

### 4. Move kanban + metadata
`cli.sh task move ready→in_progress --actor dispatcher`.
Merge dispatch_payload: dispatched_at, dispatcher_actor, briefing_path,
dispatch_mode.

### 5. Spawn subprocess
Detach (default): `start_new_session=True` + redirect stdout/stderr pro log.
Foreground (debug): blocking com output streamed pro TTY.

### 6. Capture + lifecycle (background)
`reap_finished` periodicamente OR caller cmd reaped sync.
Exit 0: auto-move testing + merge execution_* metadata.
Exit != 0: mark execution_failed + log path.

## Boundary

Ver §9 da spec. Dispatcher NAO registra perguntas nem faz draft. Essa
responsabilidade eh do clarification-agent (invocado pelo Claude Code
executor via Bash tool quando necessario).

## Volume minimo

Pelo menos 1 invocacao/mes em L1. Promocao L2: 5/sem por 4 sem, zero
execution_failed inesperado em 10 runs consecutivos.

## Historico de levels

- L1 desde 2026-04-19.
```

### Task 12.2: Playbook clarification-agent.md

**Files:**
- Create: `~/bevox-knowledge/20_architecture/agents/clarification-agent.md`

- [ ] **Step 1: Escrever playbook**

```markdown
<!-- Agent file do Clarification Agent — wave-2 do PRD orchestration.
     Invocado pelo Claude Code (via Bash tool) durante execucao do
     dispatcher. Gera answer com confidence; auto-resolve safe; escala
     unsafe.
-->

# Agent: clarification-agent

> Runbook canonico. Spec:
> `35_specs/2026-04-19-e10-dispatcher-and-clarification-agents.md`.

- **Owner:** <!-- DERIVED --> Bernard
- **Status:** <!-- DERIVED --> ativo
- **Level:** <!-- DERIVED --> L1
- **Modelo padrao:** <!-- DERIVED --> stdlib-python/no-model (invoca claude -p)
- **Modelo fallback:** <!-- DERIVED --> none
- **Criado em:** <!-- DERIVED --> 2026-04-19

## Missao

Responder duvidas operacionais levantadas pelo executor (Claude Code
invocado via dispatcher) estritamente com base em contexto canonico
(spec_refs, plan_ref, ADRs citadas). Confidence binary: safe → auto-unblock +
retorna answer; unsafe → escalation + aguarda Bernard.

## Inputs

- Invocacao tipica: `vox clarification ask <task-id> --question "..."
  --and-wait` executado pelo Claude Code via Bash tool.
- Task em `in_progress`, blocked=false.

## Outputs

- `~/.openclaw/clarification-agent/questions/<task-id>-clr-<seq>.md`
- `~/.openclaw/clarification-agent/answers/<task-id>-clr-<seq>.md`
- `~/.openclaw/clarification-agent/escalations/<task-id>-clr-<seq>.md`
  (symlink pra answer)
- `~/.openclaw/clarification-agent/signals/<clarification-id>.signal`
  (file vazio quando answer ready + unblock feito)
- Kanban: task block/unblock, set-dispatch-payload --merge, eventual
  task move rejected (via Bernard commit explicit).

## Skills

- Subprocess `claude -p` (drafter, Plano B Spike-5).
- Read de `bevox-knowledge/` e `~/.openclaw/docs/superpowers/plans/`.
- Subprocess `kanban-tasks/cli.sh task block/unblock/move/set-dispatch-payload`.

## Limites

1. NUNCA inventa source. Safety enforcement valida paths existem.
2. Safe → auto-unblock permitido. Unsafe → sempre Bernard decide
   (override | reject-task | redraft | edit+relaunch).
3. Reject-task SEMPRE exige `--commit` humano. Agent nunca move
   `→ rejected` autonomamente; apenas propoe exit code 3.
4. Categorias rejection fechadas: task_malformed, spec_inconsistent,
   requires_re_decomposition, inexecutable, manual.
5. NUNCA modifica dispatch_payload autoral do scrum-master.

## Approvals

- Auto-resolve safe: sem approval (gate humano dispensado pq source
  guard validou).
- Override/reject-task: EXIGE `--commit` humano.
- Hard limits ADR-006 aplicam.

## Playbook operacional

### 1. Registrar dispatch
Append em `~/.openclaw/workspace/shared/outputs/agent-dispatch.jsonl`.

### 2. Ask cycle
- Gera seq + clarification_id.
- Escreve question artifact.
- `task block --reason "clarification_required: <summary>"`.
- Merge metadata: last_clarification_id, question_path, count.

### 3. Draft
- `context_loader.build_context_bundle`: task + spec_refs + plan_ref + ADRs.
- `drafter.draft_answer`: subprocess `claude -p` com prompt estruturado.
- Parse JSON response (answer, sources, confidence, escalation_reason).
- `safety.enforce_safety`: valida sources existem; downgrade se
  hallucination.

### 4. Resolve
- **Safe**: unblock; merge resolved_at + confidence; emit signal; return
  answer no stdout (se `--and-wait`).
- **Unsafe**: write escalation symlink; `task block` com novo reason
  `clarification_escalation_required`; merge escalated_at + unsafe; se
  `--and-wait`: poll loop ate signal humano.

### 5. Human intervention (escalation)
- `override --commit`: write override answer + unblock + signal `override`.
- `reject-task --reason "<cat>: ..."  --commit`: valida categoria +
  `task move rejected` + signal `rejected`.
- `redraft`: re-invoca draft com mesma pergunta, novo clarification_id.

## Boundary

Ver §9 da spec. Clarification NAO seleciona task nem gera briefing
inicial. NAO move pra testing/done. Cada clarification isolada (sem
multi-round chain numa mesma pergunta — Claude Code pode fazer
sequenciais via novo ask).

## Volume minimo

1 clarification/mes em L1. Promocao L2: 5/sem por 4 sem, taxa
auto-resolve safe ≥ 70%, zero rejection autonoma (sempre via Bernard
--commit).

## Historico de levels

- L1 desde 2026-04-19.
```

### Task 12.3: Registry entries + render

**Files:**
- Modify: `bevox-knowledge/20_architecture/agents/registry.yml`

- [ ] **Step 1: Adicionar 2 entries**

```bash
cd ~/bevox-knowledge
# Adicionar entries alfabetico: clarification-agent vem entre 'agent-creator' e 'delivery-agent';
# dispatcher-agent vem entre 'delivery-status-agent' e 'documentation-agent'
```

Edit registry.yml, adicionar:

```yaml
  clarification-agent:
    status: ativo
    level: L1
    owner: Bernard
    model:
      primary: stdlib-python/no-model
      fallback: none
    since: 2026-04-19
    file: clarification-agent.md
```

Inserir logo após `agent-creator-agent`.

E:

```yaml
  dispatcher-agent:
    status: ativo
    level: L1
    owner: Bernard
    model:
      primary: stdlib-python/no-model
      fallback: none
    since: 2026-04-19
    file: dispatcher-agent.md
```

Inserir após `delivery-status-agent`.

- [ ] **Step 2: Re-render registry.md**

```bash
cd ~/bevox-knowledge
./20_architecture/agents/_tools/render-registry.py
git diff --stat 20_architecture/agents/registry.md
```

Expected: registry.md modificado.

### Task 12.4: Delivery tracker entry

**Files:**
- Modify: `bevox-knowledge/40_roadmap/delivery-tracker.yml`

- [ ] **Step 1: Adicionar wave em E10 (após scrum-master-agent)**

```yaml
      - id: dispatcher-and-clarification-agents
        status: delivered
        delivered_at: 2026-04-XX  # preencher no push gate
        features:
          - "Bernard-zero-touch operacional: 2 touch points no happy path (vox dispatcher next --launch + validar testing→done)"
          - "dispatcher-agent L1 (Hub-dispatch): consome /next-ready, gera briefing, move ready→in_progress, spawn claude -p subprocess detached, captura log, auto-move in_progress→testing no exit 0, mark execution_failed no exit != 0"
          - "clarification-agent L1 (Hub-dispatch): invocado pelo Claude Code via Bash tool; le contexto canonico (spec_refs, plan_ref, ADRs); drafter via claude -p (Plano B Spike-5, zero-pip-install); confidence binary safe|unsafe com hallucination guard; auto-resolve safe; escalation unsafe pra Bernard"
          - "state machine: in_progress ↔ blocked (clarification_required|clarification_escalation_required|execution_failed) via flag ortogonal F4 wave-3; rejected terminal apenas via Bernard --commit com categoria valida"
          - "Bernard-zero-touch escalation path: override --commit (answer manual) OR reject-task --commit (terminal com categoria) OR redraft (nova tentativa apos edit)"
          - "zero pip install (stdlib + claude CLI); 6 spikes tecnicos validados pre-spec (recursao, Bash tool longo block, headless, allowedTools restritivo, detached background; Plano B Spike-5 SDK → claude -p aceito como decisao arquitetural)"
          - "hooks F4 wave-3 consumidos (zero novo backend): GET /next-ready, task block/unblock, set-dispatch-payload --merge com replay deterministico"
        spec: 35_specs/2026-04-19-e10-dispatcher-and-clarification-agents.md
```

### Task 12.5: Sync playbook canonical → host-local

- [ ] **Step 1: cp canonical → host-local**

```bash
cp ~/bevox-knowledge/20_architecture/agents/dispatcher-agent.md \
   ~/.openclaw/dispatcher-agent/playbook.md
cp ~/bevox-knowledge/20_architecture/agents/clarification-agent.md \
   ~/.openclaw/clarification-agent/playbook.md
diff ~/bevox-knowledge/20_architecture/agents/dispatcher-agent.md \
     ~/.openclaw/dispatcher-agent/playbook.md && echo "dispatcher sync OK"
diff ~/bevox-knowledge/20_architecture/agents/clarification-agent.md \
     ~/.openclaw/clarification-agent/playbook.md && echo "clarification sync OK"
```

Expected: 2 OKs.

### Task 12.6: Canonical commit (single-gate)

- [ ] **Step 1: Stage + commit em main local**

```bash
cd ~/bevox-knowledge
git add \
  20_architecture/agents/dispatcher-agent.md \
  20_architecture/agents/clarification-agent.md \
  20_architecture/agents/registry.yml \
  20_architecture/agents/registry.md \
  40_roadmap/delivery-tracker.yml

git status -s | grep -E "(dispatcher|clarification|registry|delivery-tracker)" | head
```

Expected: 5 files staged.

- [ ] **Step 2: Commit**

```bash
cd ~/bevox-knowledge && git commit -m "$(cat <<'EOF'
feat(E10): dispatcher-agent + clarification-agent wave delivered

Wave-2 do PRD "OpenClaw Task-Orchestrated Development for Claude Code".
Entrega 2 agents Hub-dispatch L1 juntos fechando loop spec→execução
com Bernard-zero-touch operacional.

- dispatcher-agent: seleciona próxima ready, gera briefing, move
  ready→in_progress, invoca Claude Code em background detached,
  auto-move in_progress→testing no exit 0.
- clarification-agent: invocado pelo Claude Code via Bash tool;
  le contexto canônico; drafter via claude -p (Plano B Spike-5);
  confidence binary com hallucination guard; auto-resolve safe.

Módulos operacionais em ~/.openclaw/dispatcher-agent/ e
~/.openclaw/clarification-agent/ (host-local, Python stdlib puro,
zero pip install).

Spec: 35_specs/2026-04-19-e10-dispatcher-and-clarification-agents.md
Plan: ~/.openclaw/docs/superpowers/plans/2026-04-19-e10-dispatcher-and-clarification-agents-plan.md

6 spikes técnicos validados pré-spec (2026-04-19): recursão claude-em-claude,
Bash tool block ≥2min, headless Read+Write, allowedTools restritivo,
detached background via setsid+nohup. Spike-5 SDK FAIL → Plano B aceito
(claude -p subprocess para drafter, preserva zero-pip-install).

Boundary: tester-agent (wave-3 PRD), cron (wave-4 PRD),
auto-close/merge explicitamente fora.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
git log --oneline -3
```

Expected: commit criado + listagem.

---

## Phase 13: Push gate + memory

### Task 13.1: Show diff vs origin + gate humano

- [ ] **Step 1: Summary pré-push**

```bash
cd ~/bevox-knowledge
echo '=== commits ahead de origin/main ==='
git log --oneline origin/main..HEAD
echo ''
echo '=== git status fora do escopo ==='
git status -s | head -10
```

Expected: 2 commits ahead (spec + feat); pre-existentes não staged.

- [ ] **Step 2: Bernard decide push**

Instruções pro operador:

```
Push agora:
  cd ~/bevox-knowledge && git push origin main

Pause e revisa:
  git log --oneline origin/main..HEAD
  git show HEAD

Rollback (cuidado):
  git reset --soft HEAD~1
```

**Não automatizar push.** Gate humano explícito.

### Task 13.2: Backfill `delivered_at` no tracker

- [ ] **Step 1: Após Bernard aprovar, substituir data real**

```bash
cd ~/bevox-knowledge
sed -i "s|delivered_at: 2026-04-XX  # preencher no push gate|delivered_at: $(date +%Y-%m-%d)|" \
    40_roadmap/delivery-tracker.yml
git add 40_roadmap/delivery-tracker.yml
git commit --amend --no-edit
git log --oneline -1
```

### Task 13.3: Memory update

**Files:**
- Create: `~/.claude/projects/-home-you--openclaw/memory/e10_dispatcher_clarification_state.md`

- [ ] **Step 1: Write memory**

```bash
cat > ~/.claude/projects/-home-you--openclaw/memory/e10_dispatcher_clarification_state.md <<'EOF'
---
name: E10/dispatcher-and-clarification-agents — execution state
description: Status wave-2 PRD orchestration — dispatcher + clarification Hub-dispatch L1 com Bernard-zero-touch operacional. Delivered local 2026-04-XX.
type: project
---

## Checkpoint (2026-04-XX)

**DELIVERED localmente.** Push gate humano pendente.

- Spec canonizada: `35_specs/2026-04-19-e10-dispatcher-and-clarification-agents.md` (commit `85d4c04`)
- Wave commit: `<SHA>` em main local (playbooks + registry + tracker)
- Agents host-local operáveis via CLIs próprios

## Módulos host-local

- `~/.openclaw/dispatcher-agent/` — Python stdlib, subprocess `claude -p` detached
- `~/.openclaw/clarification-agent/` — Python stdlib, drafter via `claude -p` (Plano B Spike-5)

## Decisões travadas

- Bernard-zero-touch happy path: 2 touch points (kick off + testing validation)
- Stack: stdlib + claude CLI; zero pip install (decisão arquitetural)
- Clarification draft via `claude -p` subprocess (não Anthropic SDK)
- Detached default (setsid+nohup); foreground como debug
- Auto-resolve safe com hallucination guard (sources validadas no filesystem)
- Escalation humana obrigatória em unsafe (override | reject-task | redraft | edit+relaunch)
- Rejection terminal apenas via Bernard `--commit` com categoria válida
- 6 spikes técnicos validados pré-spec (2026-04-19)

## Touch model

- Happy path: `vox dispatcher next --launch` + `kanban task move testing→done`
- Clarification safe: auto (zero extra touch)
- Clarification escalation: + `override --commit` ou `reject-task --commit` ou `redraft`
- Execution failed: inspect log + `relaunch` ou reject manual

## Próximas waves PRD (fora desta spec)

- E10/tester-agent (wave-3 PRD): consome `task_entered_testing`, popula `test_result`
- E10/cron-dispatcher (wave-4 PRD): auto-dispatch periódico; depende de tester
- Possível Anthropic SDK adapter se latência/custo do claude -p virar dor

## Push gate

`bevox-knowledge/main` local tem 2 commits ahead (spec + wave delivered).
Comando: `cd ~/bevox-knowledge && git push origin main`
Módulos host-local (dispatcher + clarification) não precisam push.
EOF
```

- [ ] **Step 2: Adicionar ao MEMORY.md index**

```bash
echo '- [E10/dispatcher-and-clarification-agents — execution state](e10_dispatcher_clarification_state.md) — wave-2 PRD orchestration; Bernard-zero-touch delivered 2026-04-XX' >> ~/.claude/projects/-home-you--openclaw/memory/MEMORY.md
```

---

## Self-review (executado durante writing)

### Spec coverage

- §1-2 Visão + decisões: Phase 1-11 (implementação) + 12 (canonical)
- §3 Arquitetura: file structure + componentes cobertos Phases 1/6 (skeletons)
- §4 Spikes: não re-executar (base técnica estabelecida; referenciado em docs)
- §5.1-5.2 I/O models: Phases 2-4 (dispatcher), 7-9 (clarification)
- §6 State machine: Phases 4 (dispatcher transitions) + 9 (clarification block/unblock)
- §7 Commands surface: Phase 5 (dispatcher CLI) + 10 (clarification CLI)
- §8 Flows E2E: Phase 11 smoke cobre 4 cenários (happy, safe, escalation, reject)
- §9 Boundary entre agents: preservado via artifact dirs separados + metadata merge policy
- §10 Convention briefing: embed no briefing.py (Phase 2.2)
- §11 Touch model: validado em Phase 11 smoke
- §12 DoD: mapeado Phases 1-13
- §13 Boundary outros agents: playbooks Phase 12
- §14 Volume: playbooks
- §15 Riscos: convention strong + path validation + timeout handling documentados no código

### Placeholder scan

- `delivered_at: 2026-04-XX`: intencional, gate humano Phase 13.2
- Nenhum TBD técnico não-resolvido

### Type consistency

- `dispatch_payload` fields consistent entre Phase 2.2 briefing template + 4.1 lifecycle merge + 9.1 clarification merge
- Signal outcome values: `safe|override|rejected` consistent Phase 9.1 + 10.1 api
- Exit codes: `0,1,2,3,4,130` consistent Phase 10.1 API + README + spec §7.2
- Reject categories: 5 categorias fixas consistent 10.1 + spec §6.3 + playbook
- confidence: `safe|unsafe|manual_override` consistent 7.2 + 10.1

Nenhum drift identificado.

---

## Notas operacionais

- **Push gate humano (Phase 13.1):** Bernard decide timing.
- **Módulos host-local:** `~/.openclaw/dispatcher-agent/` e
  `~/.openclaw/clarification-agent/` são host-local; não há commits pra
  código Python.
- **Playbook sync:** canonical em bevox-knowledge é SoT; cópias
  host-local via `cp` explícito Phase 12.5. Sem auto-sync.
- **Smoke E2E (Phase 11)** toca Claude Code real — consome tokens
  (claude-haiku-4-5 ~$0.001 per invocação). Total estimado: ~$0.01 pra
  todos os cenários. Baseline kanban restaurado ao final.
- **Test hook de chaos (equivalente ao SCRUM_MASTER_FAIL_AT do
  scrum-master):** não adicionado nesta wave; se aparecer necessidade,
  follow-up.
