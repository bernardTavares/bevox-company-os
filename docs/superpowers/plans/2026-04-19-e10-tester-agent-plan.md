# E10 Tester Agent Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use `superpowers:subagent-driven-development` (recommended) or `superpowers:executing-plans` to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Entregar 1 agent Hub-dispatch L1 (`tester-agent`) que valida tasks em `testing` deterministicamente + via LLM checker (claude -p Read/Grep), aplica decisão final (`testing→done` auto OU `testing→in_progress` blocked com `test_failed`/`test_inconclusive` OU propõe `rejected` via exit 3 + Bernard `--commit`), e fecha o último gargalo do happy path **em modo foreground** (1 touch ate `done`). Modo detached (default do dispatcher) NÃO auto-invoca tester nesta wave (limitação documentada §10.2 da spec, follow-up daemon reaper §16).

**Architecture:** Módulo host-local em `~/.openclaw/tester-agent/` (Python 3 stdlib + bash entrypoint, herda convenção F4 + wave-2 PRD). Subprocess `claude -p` como drafter de checks (Plano B Spike-5, mesmo pattern do clarification-agent). Comunicação cross-agent via `dispatch_payload.test_result` shallow merge (slot reservado F4 wave-3). Delta mínimo no `dispatcher-agent`: `cmd_next` ganha flag `--no-tester` + lógica de auto-invoke condicional (`--launch --foreground` → invoca tester após `auto_move_to_testing`). Zero novo backend (consume hooks F4 wave-3 já existentes).

**Tech Stack:**
- Python 3 stdlib puro (zero pip install; decisão arquitetural §4.1 da spec, mesmo pattern wave-2)
- Bash entrypoint (`cli.sh`)
- `claude` CLI local com `--allowedTools "Read,Grep"` restritivo (drafter)
- JSON pra test_run artifacts; `dispatch_payload.test_result` shallow merge
- Kanban CLI consumption (subprocess invocations)

**Specs canônicas:**
- Wave-3 PRD (esta): `bevox-knowledge/35_specs/2026-04-19-e10-tester-agent.md` (commit `190f456`)
- Dependência wave-2 PRD: `bevox-knowledge/35_specs/2026-04-19-e10-dispatcher-and-clarification-agents.md`
- Dependência wave-1 PRD: `bevox-knowledge/35_specs/2026-04-19-e10-scrum-master-agent.md`
- Dependência F4 wave-3: `bevox-knowledge/35_specs/2026-04-19-e5-f4-kanban-dev-lifecycle.md`

**Plans pares (pattern reference):**
- Plan dispatcher+clarification: `~/.openclaw/docs/superpowers/plans/2026-04-19-e10-dispatcher-and-clarification-agents-plan.md`
- Plan scrum-master: `~/.openclaw/docs/superpowers/plans/2026-04-19-e10-scrum-master-agent-plan.md`

**Constraints operacionais:**
- **Zero pip install** (stdlib + claude CLI)
- Zero novo backend (kanban-tasks host-local + MC inalterados)
- Cron auto-poll (wave-4 PRD), daemon reaper detached, auto-merge, auto-close de spec/wave **EXPLICITAMENTE fora**
- Single canonical commit ao final cobrindo: playbook + registry + tracker + delta playbook dispatcher
- Spike results wave-2 (6 spikes, 2026-04-19) são base técnica — não re-executar

**Guardrails críticos (não regredir):**
1. Tester **NUNCA** auto-rejeita: exit code 3 (`TESTER_PROPOSES_REJECTION`) + Bernard `--commit`
2. Tester **NUNCA** auto-relaunch: dispatcher relaunch é Bernard-only
3. **5 invariantes** obrigatórios pra auto-promote `testing→done` (§2 decisão #8 da spec):
   - `task.status == "testing"`
   - `task.blocked == false`
   - execution log existe + não-vazio
   - nenhuma escalation aberta no clarification-agent
   - todas AC == "pass"
4. `inconclusive` **NUNCA** promove (sempre fica blocked + Bernard decide)
5. `dispatch_payload.test_result` isolado em shallow merge top-level (NÃO overwrite goal/spec_refs/AC autorais do scrum-master)
6. **Touch model split por modo**:
   - **Foreground** (`vox dispatcher next --launch --foreground`): 1 touch happy path (auto-invoke tester ao mover testing)
   - **Detached** (default `--launch`): 2 touches (Claude Code roda task; Bernard invoca `vox tester check <id>` depois)
7. Auto-invoke tester ao mover testing **CONDICIONAL**: só em modo foreground (default detached preserva touch atual)

---

## File Structure

### Host-local — tester-agent (novo)

```
~/.openclaw/tester-agent/
├── cli.sh                          # entrypoint bash
├── lib/
│   ├── __init__.py                 # vazio
│   ├── store.py                    # I/O atômico (test_runs/, escalations/)
│   ├── prechecks.py                # 5 invariantes deterministicos (TDD)
│   ├── context_loader.py           # le execution log + files_relevant + spec_refs
│   ├── checker.py                  # subprocess claude -p Read/Grep com prompt estruturado
│   ├── safety.py                   # pass|fail|inconclusive + sources validation + structural_concern (TDD)
│   ├── lifecycle.py                # orquestra prechecks -> checks -> decisão -> kanban transitions
│   └── api.py                      # argparse: check, recheck, results, show, reject-task
├── test_runs/                      # runtime: test_runs/<task-id>-tr-<seq>.json
├── escalations/                    # runtime: escalations/<task-id>-tr-<seq>.md (proposed_rejected only)
├── playbook.md                     # cópia sync'd do canonical (Phase 10)
└── README.md
```

### Host-local — delta mínimo em dispatcher-agent (existente)

```
~/.openclaw/dispatcher-agent/
└── lib/api.py                      # MODIFICA: cmd_next ganha flag --no-tester +
                                    # auto-invoke tester pos auto_move_to_testing
                                    # SOMENTE em modo foreground
```

### Host-local — kanban-tasks + clarification-agent + scrum-master-agent (inalterados)

Nenhuma mudança. Tester consome apenas:
- `cli.sh task move <id> done|in_progress` (whitelist permite — F4 wave-3)
- `cli.sh task block/unblock <id> --reason "..."` (flag ortogonal — F4 wave-3)
- `cli.sh task set-dispatch-payload <id> --merge --payload {...}` (shallow merge — F4 wave-3)
- `cli.sh task show <id> --json` (read state)
- Estado da escalation pending do clarification-agent: `~/.openclaw/clarification-agent/escalations/<task-id>-clr-*.md` (read-only check)

### Canonical (bevox-knowledge)

```
bevox-knowledge/
├── 20_architecture/agents/
│   ├── tester-agent.md             # NOVO: playbook canonical
│   ├── dispatcher-agent.md         # MODIFICA: documenta flag --no-tester + auto-invoke convention
│   ├── registry.yml                # MODIFICA: 1 entry L1 (tester-agent)
│   └── registry.md                 # REGENERADO via _tools/render-registry.py
└── 40_roadmap/
    └── delivery-tracker.yml        # MODIFICA: nova wave delivered em E10
```

---

## Phase 0: Pre-flight + defensive backup

### Task 0.1: Verificar escopo novo não existe

**Files:** none (read-only)

- [ ] **Step 1: Confirmar spec canonizada**

```bash
git -C ~/bevox-knowledge log --oneline -1 -- 35_specs/2026-04-19-e10-tester-agent.md
```

Expected: commit `190f456` listado.

- [ ] **Step 2: Confirmar módulo host-local ainda não existe**

```bash
ls ~/.openclaw/tester-agent 2>/dev/null && echo "WARN existe" || echo "OK tester: pendente"
```

Expected: `OK tester: pendente`.

- [ ] **Step 3: Confirmar dependências wave-2 + F4 presentes**

```bash
ls ~/.openclaw/dispatcher-agent/cli.sh
ls ~/.openclaw/clarification-agent/cli.sh
ls ~/.openclaw/scrum-master-agent/cli.sh
ls ~/.openclaw/kanban-tasks/cli.sh
which claude && claude --version 2>&1 | head -2
```

Expected: 4 cli.sh + claude CLI disponível.

- [ ] **Step 4: Confirmar hook set-dispatch-payload --merge funciona**

```bash
~/.openclaw/kanban-tasks/cli.sh task set-dispatch-payload --help 2>&1 | head -5
```

Expected: help text com `--merge` listado.

- [ ] **Step 5: Confirmar slot test_result reservado mas vazio**

Inspeciona uma task qualquer pra confirmar que `test_result` não foi populado por algo anterior (slot reservado F4 wave-3, write-path único nesta wave):

```bash
~/.openclaw/kanban-tasks/cli.sh task list --status testing --json 2>/dev/null | python3 -c "
import json, sys
data = json.load(sys.stdin)
tasks = data.get('tasks', [])
print(f'tasks em testing: {len(tasks)}')
for t in tasks:
    dp = t.get('dispatch_payload') or {}
    print(f'  {t[\"id\"]}: test_result={dp.get(\"test_result\") or dp.get(\"last_test_run_id\") or \"(none)\"}')
"
```

Expected: zero tasks em testing OU todas sem `test_result*` populado.

### Task 0.2: Backup state kanban-tasks

**Files:** snapshot defensivo

- [ ] **Step 1: Backup state**

```bash
mkdir -p ~/.openclaw/backups/kanban-tasks
TS=$(date -Iseconds)
cp ~/.openclaw/kanban-tasks/state.json ~/.openclaw/backups/kanban-tasks/state.json.pre-wave3-prd.$TS
cp ~/.openclaw/kanban-tasks/events.jsonl ~/.openclaw/backups/kanban-tasks/events.jsonl.pre-wave3-prd.$TS
ls -la ~/.openclaw/backups/kanban-tasks/ | tail -4
```

Expected: 2 backup files criados.

---

## Phase 1: tester-agent — skeleton

### Task 1.1: Criar dirs + README

**Files:**
- Create: `~/.openclaw/tester-agent/` (dir)
- Create: `~/.openclaw/tester-agent/lib/` (dir)
- Create: `~/.openclaw/tester-agent/test_runs/` (dir)
- Create: `~/.openclaw/tester-agent/escalations/` (dir)
- Create: `~/.openclaw/tester-agent/lib/__init__.py`
- Create: `~/.openclaw/tester-agent/README.md`

- [ ] **Step 1: Criar estrutura**

```bash
mkdir -p ~/.openclaw/tester-agent/{lib,test_runs,escalations}
touch ~/.openclaw/tester-agent/lib/__init__.py
```

- [ ] **Step 2: README esqueleto**

```bash
cat > ~/.openclaw/tester-agent/README.md <<'EOF'
# tester-agent

> HOST-LOCAL, NUNCA COMMITADO. Hub-dispatch L1 que valida tasks em
> `testing` (5 invariantes deterministicos + LLM checks per AC) e decide:
>
> - `testing → done` (auto, todos AC pass)
> - `testing → in_progress` blocked `test_failed: <ac>` (≥1 AC fail)
> - `testing → in_progress` blocked `test_inconclusive: <reason>` (≥1 AC sem evidencia)
> - **Propõe** `testing → rejected` via exit 3 (Bernard `--commit` apenas)

Spec: `bevox-knowledge/35_specs/2026-04-19-e10-tester-agent.md`
Playbook: `bevox-knowledge/20_architecture/agents/tester-agent.md`

## Operacao basica

```bash
vox tester check <task-id>                                  # roda prechecks + LLM checks; aplica decisao
vox tester check <task-id> --no-act                         # dry-run: gera test_run JSON, NAO move kanban
vox tester recheck <task-id>                                # re-valida apos edit manual; novo seq
vox tester results [--all|--failed|--inconclusive|--proposed-rejection]
vox tester show <task-id>                                   # ou <test-run-id>
vox tester reject-task <task-id> --reason "<categoria>: ..." --commit
```

## Exit codes

- `0`: done auto OR devolveu in_progress (blocked test_failed/inconclusive)
- `1`: input invalido (TASK_NOT_FOUND, INVALID_REJECT_CATEGORY)
- `2`: precheck infrastrutural falhou (sem log, sem AC)
- `3`: TESTER_PROPOSES_REJECTION (structural fail; Bernard --commit)

## Auto-invoke

Dispatcher invoca tester automaticamente APENAS em modo foreground:

```bash
vox dispatcher next --launch --foreground             # auto-invoca tester apos auto-move testing
vox dispatcher next --launch --foreground --no-tester # foreground SEM tester (debug)
vox dispatcher next --launch                          # detached (default): NAO invoca tester
```

Bernard em detached mode usa `vox tester check <id>` manual depois.

## Troubleshooting

**`PRECHECK_FAILED: execution_log_missing`**: dispatcher nao gerou log
OR foi limpo. Verifica `~/.openclaw/dispatcher-agent/executions/<id>.log`.

**`PRECHECK_FAILED: acceptance_criteria_empty`**: scrum-master nao
populou AC no dispatch_payload. Verifica plan original.

**`PRECHECK_FAILED: clarification_escalation_open`**: clarification
pending. Resolve override/reject-task antes do tester.

**`test_inconclusive`**: AC ambigua OR log incompleto. Bernard inspeciona;
opcoes: `tester recheck` apos edit, `dispatcher relaunch`, override
manual via `kanban task move done --actor bernard`.

**`exit 3 TESTER_PROPOSES_REJECTION`**: structural fail. Le
`escalations/<test-run-id>.md`; decide `tester reject-task --commit`.

## Spec canonica

- `bevox-knowledge/35_specs/2026-04-19-e10-tester-agent.md`
EOF
```

- [ ] **Step 3: Verificar**

```bash
ls -la ~/.openclaw/tester-agent/
```

Expected: `lib/`, `test_runs/`, `escalations/`, `README.md` presentes.

### Task 1.2: lib/store.py (I/O atômico)

**Files:**
- Create: `~/.openclaw/tester-agent/lib/store.py`

- [ ] **Step 1: Escrever store.py**

```python
"""Storage pra test_runs + escalations.

Responsabilidade unica: I/O atomico em ~/.openclaw/tester-agent/.
NAO invoca claude, NAO chama kanban, NAO valida AC.
"""

import json
import os
import re
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

ROOT = Path(os.path.expanduser("~/.openclaw/tester-agent"))
TEST_RUNS_DIR = ROOT / "test_runs"
ESCALATIONS_DIR = ROOT / "escalations"


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


def next_test_run_seq(task_id: str) -> int:
    """Acha proximo seq pra <task-id>-tr-<seq>.json."""
    TEST_RUNS_DIR.mkdir(parents=True, exist_ok=True)
    pattern = re.compile(re.escape(task_id) + r"-tr-(\d+)\.json$")
    max_seq = 0
    for p in TEST_RUNS_DIR.iterdir():
        m = pattern.match(p.name)
        if m:
            max_seq = max(max_seq, int(m.group(1)))
    return max_seq + 1


def make_test_run_id(task_id: str, seq: int) -> str:
    return f"{task_id}-tr-{seq}"


def test_run_path(test_run_id: str) -> Path:
    return TEST_RUNS_DIR / f"{test_run_id}.json"


def write_test_run(test_run_id: str, data: Dict[str, Any]) -> Path:
    """Escreve test_run JSON atomico."""
    path = test_run_path(test_run_id)
    _atomic_write(path, json.dumps(data, ensure_ascii=False, indent=2))
    return path


def read_test_run(test_run_id: str) -> Optional[Dict[str, Any]]:
    path = test_run_path(test_run_id)
    if not path.exists():
        return None
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except (OSError, json.JSONDecodeError):
        return None


def list_test_runs(task_id: Optional[str] = None) -> List[Dict[str, Any]]:
    """Lista test_runs (todos OR de uma task)."""
    if not TEST_RUNS_DIR.exists():
        return []
    out = []
    pattern = (re.compile(re.escape(task_id) + r"-tr-\d+\.json$")
               if task_id else re.compile(r".+-tr-\d+\.json$"))
    for p in sorted(TEST_RUNS_DIR.iterdir()):
        if not pattern.match(p.name):
            continue
        try:
            with open(p, "r", encoding="utf-8") as f:
                out.append(json.load(f))
        except (OSError, json.JSONDecodeError):
            continue
    return out


def write_escalation(test_run_id: str, content: str) -> Path:
    """Escreve escalation file pra structural reject proposal."""
    path = ESCALATIONS_DIR / f"{test_run_id}.md"
    _atomic_write(path, content)
    return path


def list_escalations() -> List[Dict[str, Any]]:
    """Lista escalations pending."""
    if not ESCALATIONS_DIR.exists():
        return []
    out = []
    for p in sorted(ESCALATIONS_DIR.iterdir()):
        if p.is_file() and p.suffix == ".md":
            out.append({"test_run_id": p.stem, "escalation_path": str(p)})
    return out


def clear_escalation(test_run_id: str) -> None:
    path = ESCALATIONS_DIR / f"{test_run_id}.md"
    if path.exists():
        path.unlink()
```

- [ ] **Step 2: Sanity import**

```bash
cd ~/.openclaw/tester-agent && PYTHONPATH=. python3 -c "
from lib.store import (now_iso, next_test_run_seq, make_test_run_id,
                       write_test_run, read_test_run, list_test_runs,
                       write_escalation, list_escalations, clear_escalation)
assert now_iso().endswith('Z')
seq = next_test_run_seq('T-9999')
assert seq >= 1
trid = make_test_run_id('T-9999', seq)
p = write_test_run(trid, {'task_id': 'T-9999', 'overall': 'pass'})
assert p.exists()
data = read_test_run(trid)
assert data['overall'] == 'pass'
runs = list_test_runs('T-9999')
assert len(runs) >= 1
ep = write_escalation(trid, '# escalation test')
assert ep.exists()
escs = list_escalations()
assert any(e['test_run_id'] == trid for e in escs)
clear_escalation(trid)
import os; os.unlink(p)
print('OK store')
"
```

Expected: `OK store`.

### Task 1.3: cli.sh entrypoint

**Files:**
- Create: `~/.openclaw/tester-agent/cli.sh`

- [ ] **Step 1: Criar wrapper**

```bash
cat > ~/.openclaw/tester-agent/cli.sh <<'EOF'
#!/usr/bin/env bash
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"
exec python3 -m lib.api "$@"
EOF
chmod +x ~/.openclaw/tester-agent/cli.sh
ls -la ~/.openclaw/tester-agent/cli.sh
```

Expected: executável.

---

## Phase 2: prechecks.py — 5 invariantes deterministicos (TDD)

### Task 2.1: Escrever testes pra prechecks

**Files:**
- Create: `~/.openclaw/tester-agent/lib/prechecks.py` (vai escrever no Step 3)
- Test inline (script python rodado direto, sem pytest pra preservar zero-pip).

- [ ] **Step 1: Escrever script de teste fail-first**

```bash
cat > /tmp/test_prechecks.py <<'EOF'
"""Tests prechecks.run_prechecks. Roda direto via python3."""
import sys, os, json, tempfile, shutil
from pathlib import Path

sys.path.insert(0, str(Path.home() / ".openclaw" / "tester-agent"))
from lib import prechecks


def make_task(status="testing", blocked=False, ac=None, files_relevant=None):
    return {
        "id": "T-FAKE",
        "status": status,
        "blocked": blocked,
        "dispatch_payload": {
            "acceptance_criteria": ac if ac is not None else ["AC: file X exists"],
            "files_relevant": files_relevant or [],
        },
    }


def test_all_pass(tmpdir):
    log = Path(tmpdir) / "T-FAKE.log"
    log.write_text("execution log content with stuff\n")
    task = make_task()
    result = prechecks.run_prechecks(task, log_path=log, escalation_check=lambda tid: False)
    assert result["passed"] is True, result
    assert all(result["details"][k] for k in [
        "task_in_testing", "task_not_blocked", "execution_log_exists",
        "acceptance_criteria_non_empty", "no_open_clarification_escalation"
    ]), result
    print("  OK test_all_pass")


def test_status_not_testing(tmpdir):
    log = Path(tmpdir) / "T-FAKE.log"; log.write_text("x")
    task = make_task(status="in_progress")
    r = prechecks.run_prechecks(task, log_path=log, escalation_check=lambda tid: False)
    assert r["passed"] is False
    assert r["details"]["task_in_testing"] is False
    assert "task_in_testing" in r["failure_reason"]
    print("  OK test_status_not_testing")


def test_blocked_true(tmpdir):
    log = Path(tmpdir) / "T-FAKE.log"; log.write_text("x")
    task = make_task(blocked=True)
    r = prechecks.run_prechecks(task, log_path=log, escalation_check=lambda tid: False)
    assert r["passed"] is False
    assert r["details"]["task_not_blocked"] is False
    print("  OK test_blocked_true")


def test_log_missing(tmpdir):
    log = Path(tmpdir) / "T-DOES-NOT-EXIST.log"
    task = make_task()
    r = prechecks.run_prechecks(task, log_path=log, escalation_check=lambda tid: False)
    assert r["passed"] is False
    assert r["details"]["execution_log_exists"] is False
    print("  OK test_log_missing")


def test_log_empty(tmpdir):
    log = Path(tmpdir) / "T-FAKE.log"; log.write_text("")
    task = make_task()
    r = prechecks.run_prechecks(task, log_path=log, escalation_check=lambda tid: False)
    assert r["passed"] is False
    assert r["details"]["execution_log_exists"] is False
    print("  OK test_log_empty")


def test_ac_empty(tmpdir):
    log = Path(tmpdir) / "T-FAKE.log"; log.write_text("x")
    task = make_task(ac=[])
    r = prechecks.run_prechecks(task, log_path=log, escalation_check=lambda tid: False)
    assert r["passed"] is False
    assert r["details"]["acceptance_criteria_non_empty"] is False
    print("  OK test_ac_empty")


def test_clarification_escalation_open(tmpdir):
    log = Path(tmpdir) / "T-FAKE.log"; log.write_text("x")
    task = make_task()
    r = prechecks.run_prechecks(task, log_path=log, escalation_check=lambda tid: True)
    assert r["passed"] is False
    assert r["details"]["no_open_clarification_escalation"] is False
    assert "clarification" in r["failure_reason"]
    print("  OK test_clarification_escalation_open")


def main():
    tmp = tempfile.mkdtemp()
    try:
        test_all_pass(tmp)
        test_status_not_testing(tmp)
        test_blocked_true(tmp)
        test_log_missing(tmp)
        test_log_empty(tmp)
        test_ac_empty(tmp)
        test_clarification_escalation_open(tmp)
        print("ALL OK")
    finally:
        shutil.rmtree(tmp)


if __name__ == "__main__":
    main()
EOF
```

- [ ] **Step 2: Rodar pra confirmar FAIL (modulo nao existe)**

```bash
python3 /tmp/test_prechecks.py 2>&1 | tail -5 || true
```

Expected: `ModuleNotFoundError: No module named 'lib.prechecks'` ou `ImportError`.

- [ ] **Step 3: Implementar prechecks.py**

```bash
cat > ~/.openclaw/tester-agent/lib/prechecks.py <<'EOF'
"""Prechecks deterministicos: 5 invariantes antes de invocar LLM checks.

Decisao #8 da spec: auto-promote done exige TODOS pass:
- task.status == "testing"
- task.blocked == false
- execution log existe + nao-vazio
- nenhuma escalation aberta no clarification-agent
- acceptance_criteria nao-vazio

Senao: blocked com test_failed: precheck_X.
"""

from pathlib import Path
from typing import Any, Callable, Dict, Optional


def _check_task_in_testing(task: Dict[str, Any]) -> bool:
    return task.get("status") == "testing"


def _check_task_not_blocked(task: Dict[str, Any]) -> bool:
    return task.get("blocked") is False


def _check_execution_log_exists(log_path: Path) -> bool:
    if not log_path.exists() or not log_path.is_file():
        return False
    try:
        return log_path.stat().st_size > 0
    except OSError:
        return False


def _check_acceptance_criteria_non_empty(task: Dict[str, Any]) -> bool:
    ac = (task.get("dispatch_payload") or {}).get("acceptance_criteria") or []
    return isinstance(ac, list) and len(ac) > 0


def _check_no_open_clarification_escalation(
    task_id: str, escalation_check: Callable[[str], bool],
) -> bool:
    """escalation_check(task_id) returns True if escalation pending."""
    return not escalation_check(task_id)


def run_prechecks(
    task: Dict[str, Any],
    log_path: Path,
    escalation_check: Callable[[str], bool],
) -> Dict[str, Any]:
    """Executa 5 invariantes. Retorna dict com 'passed' + 'details' + 'failure_reason'."""
    details = {
        "task_in_testing": _check_task_in_testing(task),
        "task_not_blocked": _check_task_not_blocked(task),
        "execution_log_exists": _check_execution_log_exists(log_path),
        "acceptance_criteria_non_empty": _check_acceptance_criteria_non_empty(task),
        "no_open_clarification_escalation": _check_no_open_clarification_escalation(
            task.get("id", ""), escalation_check,
        ),
    }
    failed = [k for k, v in details.items() if not v]
    return {
        "passed": len(failed) == 0,
        "details": details,
        "failure_reason": (
            f"precheck_failed: {','.join(failed)}" if failed else ""
        ),
    }


def default_escalation_check(task_id: str) -> bool:
    """Verifica se ha escalation pending no clarification-agent (filesystem)."""
    import os
    import re
    esc_dir = Path(os.path.expanduser(
        "~/.openclaw/clarification-agent/escalations",
    ))
    if not esc_dir.exists():
        return False
    pattern = re.compile(re.escape(task_id) + r"-clr-\d+\.md$")
    for p in esc_dir.iterdir():
        if (p.is_symlink() or p.is_file()) and pattern.match(p.name):
            return True
    return False
EOF
```

- [ ] **Step 4: Rodar testes — devem passar**

```bash
python3 /tmp/test_prechecks.py
```

Expected: `ALL OK` com 7 OKs listados.

- [ ] **Step 5: Cleanup test script**

```bash
rm /tmp/test_prechecks.py
```

---

## Phase 3: context_loader.py — le execution log + files_relevant + spec_refs

### Task 3.1: lib/context_loader.py

**Files:**
- Create: `~/.openclaw/tester-agent/lib/context_loader.py`

- [ ] **Step 1: Escrever context_loader**

```bash
cat > ~/.openclaw/tester-agent/lib/context_loader.py <<'EOF'
"""Context loader: le execution log (tail) + files_relevant + spec_refs.

Read-only filesystem. Mesmo pattern do clarification-agent context_loader,
mas adicionado read do execution log do dispatcher.
"""

import json
import re
import subprocess
from pathlib import Path
from typing import Any, Dict, List, Optional

BEVOX_KNOWLEDGE = Path("~/bevox-knowledge")
OPENCLAW_PLANS = Path("~/.openclaw/docs/superpowers/plans")
KANBAN_CLI = Path("~/.openclaw/kanban-tasks/cli.sh")
DISPATCHER_EXEC_DIR = Path("~/.openclaw/dispatcher-agent/executions")

LOG_TAIL_BYTES = 8000
FILE_HEAD_BYTES = 4000
SPEC_HEAD_BYTES = 2000


class ContextError(Exception):
    def __init__(self, code: str, detail: str):
        self.code = code
        self.detail = detail
        super().__init__(f"{code}: {detail}")


def load_task_via_kanban(task_id: str) -> Dict[str, Any]:
    try:
        r = subprocess.run(
            [str(KANBAN_CLI), "task", "show", task_id, "--json"],
            capture_output=True, text=True, check=False, timeout=10,
        )
    except (OSError, subprocess.TimeoutExpired) as e:
        raise ContextError("KANBAN_CLI_TIMEOUT", str(e))
    if r.returncode != 0:
        raise ContextError(
            "TASK_NOT_FOUND",
            f"{task_id}: exit={r.returncode} stderr={r.stderr.strip()[:200]}",
        )
    data = json.loads(r.stdout)
    return data.get("task") or {}


def execution_log_path(task_id: str) -> Path:
    return DISPATCHER_EXEC_DIR / f"{task_id}.log"


def read_execution_log_tail(task_id: str, max_bytes: int = LOG_TAIL_BYTES) -> str:
    """Le tail do execution log (max_bytes bytes finais)."""
    path = execution_log_path(task_id)
    if not path.exists() or not path.is_file():
        return ""
    try:
        size = path.stat().st_size
        with open(path, "rb") as f:
            if size > max_bytes:
                f.seek(size - max_bytes)
            data = f.read()
        return data.decode("utf-8", errors="replace")
    except OSError:
        return ""


def resolve_ref_path(ref: str) -> Optional[Path]:
    """Resolve path ref (absolute, ~, ou prefixed). Mesma logica clarification-agent."""
    r = ref.strip().strip("`")
    if r.startswith("~/"):
        p = Path(r).expanduser()
        return p if p.exists() else None
    if r.startswith("/"):
        p = Path(r)
        return p if p.exists() else None
    HOME = Path.home()
    if r.startswith("bevox-knowledge/"):
        p = HOME / r
        return p if p.exists() else None
    if r.startswith(".openclaw/") or r.startswith("openclaw/"):
        p = (HOME / r if r.startswith(".openclaw/")
             else HOME / ".openclaw" / r[len("openclaw/"):])
        return p if p.exists() else None
    for base in (BEVOX_KNOWLEDGE, OPENCLAW_PLANS, HOME / ".openclaw"):
        cand = base / r
        if cand.exists():
            return cand
    return None


def read_ref(ref: str, max_bytes: int = FILE_HEAD_BYTES) -> Optional[Dict[str, Any]]:
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


def build_test_context(task_id: str) -> Dict[str, Any]:
    """Bundle: task + execution log tail + files_relevant + spec_refs."""
    task = load_task_via_kanban(task_id)
    payload = task.get("dispatch_payload") or {}

    log_tail = read_execution_log_tail(task_id)

    files_relevant_resolved: List[Dict[str, Any]] = []
    files_relevant_unresolved: List[str] = []
    for f in (payload.get("files_relevant") or []):
        result = read_ref(f, max_bytes=FILE_HEAD_BYTES)
        if result:
            files_relevant_resolved.append(result)
        else:
            files_relevant_unresolved.append(f)

    spec_refs_resolved: List[Dict[str, Any]] = []
    for r in (payload.get("spec_refs") or []):
        result = read_ref(r, max_bytes=SPEC_HEAD_BYTES)
        if result:
            spec_refs_resolved.append(result)

    return {
        "task": task,
        "dispatch_payload": payload,
        "acceptance_criteria": payload.get("acceptance_criteria") or [],
        "execution_log_tail": log_tail,
        "execution_log_path": str(execution_log_path(task_id)),
        "files_relevant": files_relevant_resolved,
        "files_relevant_unresolved": files_relevant_unresolved,
        "spec_refs": spec_refs_resolved,
    }
EOF
```

- [ ] **Step 2: Sanity import**

```bash
cd ~/.openclaw/tester-agent && PYTHONPATH=. python3 -c "
from lib.context_loader import (resolve_ref_path, read_ref,
                                 read_execution_log_tail, execution_log_path)
# resolve known canonical path
p = resolve_ref_path('bevox-knowledge/35_specs/2026-04-19-e10-tester-agent.md')
assert p is not None and p.exists(), p
# read it
r = read_ref('bevox-knowledge/35_specs/2026-04-19-e10-tester-agent.md')
assert r is not None and 'tester' in r['content'].lower()
# log tail of nonexistent task
log = read_execution_log_tail('T-DOES-NOT-EXIST')
assert log == ''
print('OK context_loader')
"
```

Expected: `OK context_loader`.

---

## Phase 4: checker.py — claude -p subprocess Read/Grep

### Task 4.1: lib/checker.py

**Files:**
- Create: `~/.openclaw/tester-agent/lib/checker.py`

- [ ] **Step 1: Escrever checker.py**

```bash
cat > ~/.openclaw/tester-agent/lib/checker.py <<'EOF'
"""Checker: invoca claude -p com prompt estruturado per AC.

Plano B Spike-5: zero Anthropic SDK; usa claude CLI subprocess.
allowedTools="Read,Grep" restritivo (decisao #6 da spec).
Model default: claude-haiku-4-5 (barato + rapido).
"""

import json
import re
import subprocess
from typing import Any, Dict, List, Optional

CHECKER_MODEL = "claude-haiku-4-5"
CHECKER_TIMEOUT_SECONDS = 120
ALLOWED_TOOLS = "Read,Grep"


class CheckerError(Exception):
    def __init__(self, code: str, detail: str):
        self.code = code
        self.detail = detail
        super().__init__(f"{code}: {detail}")


def _build_prompt(ac: str, ctx: Dict[str, Any]) -> str:
    task = ctx.get("task") or {}
    payload = ctx.get("dispatch_payload") or {}
    log_tail = ctx.get("execution_log_tail") or ""

    files_block = ""
    for f in (ctx.get("files_relevant") or [])[:10]:
        files_block += f"\n### {f['ref']} (path: {f['path']})\n\n```\n{f['content'][:4000]}\n```\n"
    if not files_block:
        files_block = "(nenhum file_relevant resolvido)"

    spec_block = ""
    for r in (ctx.get("spec_refs") or [])[:5]:
        spec_block += f"\n### {r['ref']} (path: {r['path']})\n\n```\n{r['content'][:2000]}\n```\n"
    if not spec_block:
        spec_block = "(sem spec_refs)"

    prompt = f"""Voce eh tester-agent do OpenClaw. Valide se a Acceptance Criterion (AC) abaixo
foi cumprida pela execucao do dispatcher. Use APENAS evidencia do execution log,
files_relevant e spec_refs (read-only).

NAO opine sobre qualidade, elegancia, ou design. Apenas valida cumprimento
objetivo da AC.

## Task

- id: {task.get("id", "")}
- title: {task.get("title", "")}
- goal: {payload.get("goal", "")[:300]}

## AC sob avaliacao

{ac}

## Execution log (tail 8000 chars)

```
{log_tail[:8000]}
```

## Files relevant

{files_block}

## Spec refs (resumo)

{spec_block}

## Formato OBRIGATORIO da resposta

Responda EXATAMENTE neste formato JSON (e nada alem disso; zero prose fora do JSON):

```json
{{
  "status": "pass" | "fail" | "inconclusive",
  "evidence": "<excerpt curto do log/file que justifica>",
  "sources": ["<path>", "<path with line>"],
  "structural_concern": "<motivo se detectar task_malformed/spec_inconsistent/inexecutable/requires_re_decomposition; vazio se nao>"
}}
```

Regras:
- `pass`: evidencia clara no log/files que AC foi cumprida.
- `fail`: evidencia clara que AC NAO foi cumprida (ex: arquivo nao criado, exit nao-zero no log).
- `inconclusive`: log/files nao tem evidencia explicita pro AC. NAO chute.
- `structural_concern`: preencha SE perceber que AC contradiz spec_refs OR eh ambigua a ponto de
  inviabilizar checagem. Caller usara pra propor rejected.
- Sources: cada path deve EXISTIR no contexto fornecido (hallucination guard).
"""
    return prompt


def _parse_response(raw: str) -> Dict[str, Any]:
    m = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", raw, re.DOTALL)
    if m:
        block = m.group(1)
    else:
        start = raw.find("{")
        if start == -1:
            raise CheckerError("PARSE_NO_JSON", f"output sem JSON: {raw[:300]}")
        end = raw.rfind("}")
        if end == -1 or end <= start:
            raise CheckerError("PARSE_NO_JSON", f"JSON malformado: {raw[:300]}")
        block = raw[start : end + 1]
    try:
        parsed = json.loads(block)
    except json.JSONDecodeError as e:
        raise CheckerError("PARSE_JSON_INVALID", f"{e}: {block[:300]}")
    for field in ("status", "evidence", "sources"):
        if field not in parsed:
            raise CheckerError("PARSE_MISSING_FIELD", f"field '{field}' ausente")
    if not isinstance(parsed["sources"], list):
        parsed["sources"] = [str(parsed["sources"])]
    parsed.setdefault("structural_concern", "")
    return parsed


def check_ac(
    ac: str, ctx: Dict[str, Any], model: str = CHECKER_MODEL,
) -> Dict[str, Any]:
    """Invoca claude -p pro AC. Retorna dict raw (status, evidence, sources, structural_concern)."""
    prompt = _build_prompt(ac, ctx)
    try:
        result = subprocess.run(
            ["claude", "-p", prompt, "--model", model,
             "--allowedTools", ALLOWED_TOOLS],
            capture_output=True, text=True, check=False,
            timeout=CHECKER_TIMEOUT_SECONDS,
        )
    except (OSError, subprocess.TimeoutExpired) as e:
        raise CheckerError("CLAUDE_SUBPROCESS_FAILED",
                          f"{type(e).__name__}: {e}")
    if result.returncode != 0:
        raise CheckerError(
            "CLAUDE_EXIT_NONZERO",
            f"exit={result.returncode} stderr={result.stderr[:200]}",
        )
    parsed = _parse_response(result.stdout)
    parsed["raw_response"] = result.stdout[:5000]
    parsed["drafter_model"] = model
    return parsed
EOF
```

- [ ] **Step 2: Sanity import**

```bash
cd ~/.openclaw/tester-agent && PYTHONPATH=. python3 -c "
from lib.checker import check_ac, _build_prompt, _parse_response, CHECKER_MODEL
# parse valid
p = _parse_response('''
\`\`\`json
{\"status\": \"pass\", \"evidence\": \"x\", \"sources\": [\"a\"]}
\`\`\`
''')
assert p['status'] == 'pass'
assert p['structural_concern'] == ''
# parse with structural_concern
p = _parse_response('{\"status\":\"fail\",\"evidence\":\"e\",\"sources\":[],\"structural_concern\":\"task_malformed\"}')
assert p['structural_concern'] == 'task_malformed'
# parse missing field
try:
    _parse_response('{\"status\":\"pass\"}')
    assert False, 'should have raised'
except Exception as e:
    assert 'evidence' in str(e) or 'sources' in str(e)
# build prompt
prompt = _build_prompt('AC test', {'task': {'id': 'T-1'}, 'execution_log_tail': 'log content'})
assert 'AC test' in prompt and 'T-1' in prompt
print('OK checker')
"
```

Expected: `OK checker`.

---

## Phase 5: safety.py — pass/fail/inconclusive + sources validation (TDD)

### Task 5.1: Escrever testes pra safety

- [ ] **Step 1: Escrever testes fail-first**

```bash
cat > /tmp/test_safety.py <<'EOF'
"""Tests safety.enforce_safety. Roda direto via python3."""
import sys, tempfile, os
from pathlib import Path

sys.path.insert(0, str(Path.home() / ".openclaw" / "tester-agent"))
from lib import safety


def make_ctx_with_files(tmpdir):
    """Cria fake files_relevant + spec_refs files."""
    f1 = Path(tmpdir) / "real.py"; f1.write_text("x")
    f2 = Path(tmpdir) / "spec.md"; f2.write_text("y")
    return {
        "files_relevant": [{"ref": "real.py", "path": str(f1), "content": "x"}],
        "spec_refs": [{"ref": "spec.md", "path": str(f2), "content": "y"}],
        "execution_log_path": "/tmp/fake.log",
    }


def test_pass_with_valid_sources(tmpdir):
    ctx = make_ctx_with_files(tmpdir)
    r = safety.enforce_safety(
        status="pass", sources=[str(Path(tmpdir) / "real.py")],
        structural_concern="", ctx=ctx,
    )
    assert r["effective_status"] == "pass", r
    print("  OK test_pass_with_valid_sources")


def test_pass_zero_sources_downgrades(tmpdir):
    ctx = make_ctx_with_files(tmpdir)
    r = safety.enforce_safety(
        status="pass", sources=[], structural_concern="", ctx=ctx,
    )
    assert r["effective_status"] == "inconclusive", r
    assert "no_sources" in r["downgrade_reason"]
    print("  OK test_pass_zero_sources_downgrades")


def test_pass_invalid_source_downgrades(tmpdir):
    ctx = make_ctx_with_files(tmpdir)
    r = safety.enforce_safety(
        status="pass", sources=["/nonexistent/path.py"],
        structural_concern="", ctx=ctx,
    )
    assert r["effective_status"] == "inconclusive"
    assert "hallucination" in r["downgrade_reason"]
    print("  OK test_pass_invalid_source_downgrades")


def test_fail_passthrough(tmpdir):
    ctx = make_ctx_with_files(tmpdir)
    r = safety.enforce_safety(
        status="fail", sources=[str(Path(tmpdir) / "real.py")],
        structural_concern="", ctx=ctx,
    )
    assert r["effective_status"] == "fail"
    print("  OK test_fail_passthrough")


def test_inconclusive_passthrough(tmpdir):
    ctx = make_ctx_with_files(tmpdir)
    r = safety.enforce_safety(
        status="inconclusive", sources=[], structural_concern="", ctx=ctx,
    )
    assert r["effective_status"] == "inconclusive"
    print("  OK test_inconclusive_passthrough")


def test_structural_concern_valid(tmpdir):
    ctx = make_ctx_with_files(tmpdir)
    r = safety.enforce_safety(
        status="fail", sources=[], structural_concern="task_malformed",
        ctx=ctx,
    )
    assert r["effective_structural_concern"] == "task_malformed"
    print("  OK test_structural_concern_valid")


def test_structural_concern_invalid_dropped(tmpdir):
    ctx = make_ctx_with_files(tmpdir)
    r = safety.enforce_safety(
        status="fail", sources=[], structural_concern="random_garbage",
        ctx=ctx,
    )
    assert r["effective_structural_concern"] == ""
    print("  OK test_structural_concern_invalid_dropped")


def test_invalid_status_raises(tmpdir):
    ctx = make_ctx_with_files(tmpdir)
    try:
        safety.enforce_safety(status="bogus", sources=[], structural_concern="", ctx=ctx)
        assert False, "should raise"
    except safety.SafetyError as e:
        assert e.code == "INVALID_STATUS"
    print("  OK test_invalid_status_raises")


def main():
    tmp = tempfile.mkdtemp()
    try:
        test_pass_with_valid_sources(tmp)
        test_pass_zero_sources_downgrades(tmp)
        test_pass_invalid_source_downgrades(tmp)
        test_fail_passthrough(tmp)
        test_inconclusive_passthrough(tmp)
        test_structural_concern_valid(tmp)
        test_structural_concern_invalid_dropped(tmp)
        test_invalid_status_raises(tmp)
        print("ALL OK")
    finally:
        import shutil; shutil.rmtree(tmp)


if __name__ == "__main__":
    main()
EOF
```

- [ ] **Step 2: Rodar — deve FAIL (modulo nao existe)**

```bash
python3 /tmp/test_safety.py 2>&1 | tail -3 || true
```

Expected: `ImportError` ou `ModuleNotFoundError`.

- [ ] **Step 3: Implementar safety.py**

```bash
cat > ~/.openclaw/tester-agent/lib/safety.py <<'EOF'
"""Safety: valida status + sources + structural_concern.

Decisoes da spec:
- Confidence binary pass|fail|inconclusive (decisao #4 + #2c).
- Sources hallucination guard: pass exige >=1 source valida (existe no
  contexto OU no filesystem). Senao downgrade pra inconclusive.
- structural_concern: 4 categorias validas; outras dropadas.
"""

from pathlib import Path
from typing import Any, Dict, List, Tuple

VALID_STATUS = {"pass", "fail", "inconclusive"}
VALID_STRUCTURAL_CONCERNS = {
    "task_malformed", "spec_inconsistent",
    "requires_re_decomposition", "inexecutable",
}


class SafetyError(Exception):
    def __init__(self, code: str, detail: str):
        self.code = code
        self.detail = detail
        super().__init__(f"{code}: {detail}")


def _validate_sources(sources: List[str], ctx: Dict[str, Any]) -> Tuple[List[str], List[str]]:
    """Resolve cada source: precisa estar em files_relevant/spec_refs/execution_log path
    OU existir no filesystem absoluto."""
    valid, invalid = [], []
    known_paths = set()
    for f in (ctx.get("files_relevant") or []):
        known_paths.add(f.get("path"))
        known_paths.add(f.get("ref"))
    for r in (ctx.get("spec_refs") or []):
        known_paths.add(r.get("path"))
        known_paths.add(r.get("ref"))
    log_path = ctx.get("execution_log_path")
    if log_path:
        known_paths.add(log_path)
        known_paths.add("execution_log")

    for s in sources:
        if not s:
            invalid.append(s); continue
        # Strip line/column suffixes (path:line)
        bare = s.split(":")[0].strip("`")
        # Match exact known path OR check filesystem
        if bare in known_paths or s in known_paths:
            valid.append(s)
            continue
        if any(bare in kp for kp in known_paths if kp):
            valid.append(s)
            continue
        # Filesystem fallback
        try:
            p = Path(bare).expanduser()
            if p.exists() and p.is_file():
                valid.append(s)
                continue
        except (OSError, ValueError):
            pass
        invalid.append(s)
    return valid, invalid


def enforce_safety(
    status: str, sources: List[str], structural_concern: str,
    ctx: Dict[str, Any],
) -> Dict[str, Any]:
    """Aplica safety rules. Retorna effective_status + downgrade_reason +
    effective_structural_concern + sources_valid/invalid."""
    if status not in VALID_STATUS:
        raise SafetyError(
            "INVALID_STATUS",
            f"status='{status}' nao em {sorted(VALID_STATUS)}",
        )

    valid_sources, invalid_sources = _validate_sources(sources, ctx)

    effective_status = status
    downgrade_reason = ""

    if status == "pass":
        if not valid_sources:
            effective_status = "inconclusive"
            downgrade_reason = (
                "no_sources: pass declarada mas zero sources validas. "
                "Hallucination guard: downgrade pra inconclusive."
            )
        elif invalid_sources:
            effective_status = "inconclusive"
            downgrade_reason = (
                f"hallucination_guard: sources invalidas detectadas "
                f"({invalid_sources[:3]}). valid={valid_sources[:3]}"
            )

    sc = (structural_concern or "").strip()
    effective_sc = sc if sc in VALID_STRUCTURAL_CONCERNS else ""

    return {
        "effective_status": effective_status,
        "downgrade_reason": downgrade_reason,
        "effective_structural_concern": effective_sc,
        "valid_sources": valid_sources,
        "invalid_sources": invalid_sources,
    }
EOF
```

- [ ] **Step 4: Rodar testes — devem passar**

```bash
python3 /tmp/test_safety.py
```

Expected: `ALL OK` com 8 OKs.

- [ ] **Step 5: Cleanup test script**

```bash
rm /tmp/test_safety.py
```

---

## Phase 6: lifecycle.py — orquestra prechecks → checks → decisão → kanban

### Task 6.1: lib/lifecycle.py

**Files:**
- Create: `~/.openclaw/tester-agent/lib/lifecycle.py`

- [ ] **Step 1: Escrever lifecycle.py**

```bash
cat > ~/.openclaw/tester-agent/lib/lifecycle.py <<'EOF'
"""Lifecycle: orquestra check completo de uma task.

Fluxo:
1. Carrega context (task + log + files + specs)
2. Prechecks (5 invariantes)
   - Se algum falha: precheck-failure path (block test_failed: precheck_X)
3. Per AC: check_ac via LLM + safety.enforce_safety
4. Aggregate overall status:
   - All pass + zero structural_concern -> done
   - Any structural_concern detectado -> propose_rejection (exit 3, NAO move kanban)
   - Any fail (sem structural) -> in_progress + block test_failed
   - Any inconclusive (sem fail/structural) -> in_progress + block test_inconclusive
5. Apply decisao no kanban + merge test_result
"""

import json
import subprocess
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

from . import checker as checker_lib
from . import context_loader
from . import prechecks
from . import safety
from . import store

KANBAN_CLI = Path("~/.openclaw/kanban-tasks/cli.sh")


class LifecycleError(Exception):
    def __init__(self, code: str, detail: str):
        self.code = code
        self.detail = detail
        super().__init__(f"{code}: {detail}")


def _run_kanban(args: list, actor: str = "tester") -> Dict[str, Any]:
    cmd = [str(KANBAN_CLI)] + args + ["--json", "--actor", actor]
    try:
        r = subprocess.run(
            cmd, capture_output=True, text=True, check=False, timeout=30,
        )
    except (OSError, subprocess.TimeoutExpired) as e:
        raise LifecycleError("KANBAN_CLI_TIMEOUT", str(e))
    if r.returncode != 0:
        raise LifecycleError(
            "KANBAN_CLI_FAILED",
            f"exit={r.returncode} stderr={r.stderr.strip()[:200]}",
        )
    try:
        return json.loads(r.stdout)
    except json.JSONDecodeError as e:
        raise LifecycleError("KANBAN_CLI_BAD_JSON", str(e))


def move_to_done(task_id: str) -> None:
    _run_kanban(["task", "move", task_id, "done"])


def move_to_in_progress(task_id: str) -> None:
    _run_kanban(["task", "move", task_id, "in_progress"])


def block(task_id: str, reason: str) -> None:
    _run_kanban(["task", "block", task_id, "--reason", reason])


def reject_task(task_id: str, reason: str) -> None:
    """Bernard --commit only. Move pra rejected."""
    _run_kanban(["task", "move", task_id, "rejected", "--reason", reason])


def merge_test_result(task_id: str, fields: Dict[str, Any]) -> None:
    """Shallow merge top-level em dispatch_payload."""
    _run_kanban([
        "task", "set-dispatch-payload", task_id,
        "--payload", json.dumps(fields, ensure_ascii=False), "--merge",
    ])


def _aggregate(checks: List[Dict[str, Any]]) -> Dict[str, str]:
    """Decide overall + decision baseado nos per-AC effective_status + structural_concern."""
    has_structural = any(c.get("effective_structural_concern") for c in checks)
    if has_structural:
        return {"overall": "structural_reject_proposed",
                "decision": "proposed_rejected"}
    statuses = [c.get("effective_status") for c in checks]
    if any(s == "fail" for s in statuses):
        return {"overall": "fail", "decision": "in_progress_test_failed"}
    if any(s == "inconclusive" for s in statuses):
        return {"overall": "inconclusive",
                "decision": "in_progress_test_inconclusive"}
    if all(s == "pass" for s in statuses) and statuses:
        return {"overall": "pass", "decision": "done"}
    # Fallback (zero AC checks impossivel pos-precheck mas defensivo)
    return {"overall": "inconclusive", "decision": "in_progress_test_inconclusive"}


def _short_reason(text: str, limit: int = 80) -> str:
    return (text or "").replace("\n", " ").strip()[:limit]


def _write_escalation_md(test_run_id: str, task_id: str,
                         checks: List[Dict[str, Any]]) -> None:
    structural_checks = [c for c in checks if c.get("effective_structural_concern")]
    body = f"""# Tester escalation — {test_run_id}

**Task:** {task_id}
**Generated at:** {store.now_iso()}
**Suggested category:** {structural_checks[0].get("effective_structural_concern") if structural_checks else "manual"}

---

## Structural concerns detectadas

"""
    for c in structural_checks:
        body += (f"### AC: {c.get('ac', '')[:200]}\n\n"
                 f"- structural_concern: {c.get('effective_structural_concern')}\n"
                 f"- evidence: {c.get('evidence', '')[:300]}\n"
                 f"- sources: {c.get('valid_sources') or c.get('sources')}\n\n")
    body += """---

## Acoes possiveis (Bernard)

- `vox tester reject-task <task-id> --reason "<categoria>: <detail>" --commit`
- `vox tester recheck <task-id>` (apos editar AC/spec)
- Override manual: `~/.openclaw/kanban-tasks/cli.sh task move <task-id> done --actor bernard`
"""
    store.write_escalation(test_run_id, body)


def run_check(
    task_id: str,
    no_act: bool = False,
    model: Optional[str] = None,
    trigger: str = "manual",
    escalation_check: Optional[Callable[[str], bool]] = None,
) -> Dict[str, Any]:
    """Executa check completo: prechecks -> LLM checks -> decisao -> kanban (se !no_act).

    Retorna test_run dict completo.
    """
    if escalation_check is None:
        escalation_check = prechecks.default_escalation_check

    seq = store.next_test_run_seq(task_id)
    test_run_id = store.make_test_run_id(task_id, seq)
    started_at = store.now_iso()

    # Load context
    ctx = context_loader.build_test_context(task_id)
    task = ctx["task"]
    log_path = context_loader.execution_log_path(task_id)

    # Prechecks
    pc = prechecks.run_prechecks(task, log_path, escalation_check)
    test_run: Dict[str, Any] = {
        "test_run_id": test_run_id,
        "task_id": task_id,
        "started_at": started_at,
        "trigger": trigger,
        "prechecks": pc,
        "checks": [],
        "overall": None,
        "decision": None,
        "decision_reason": "",
        "kanban_actions_applied": [],
    }

    if not pc["passed"]:
        # Precheck failure path: nao roda LLM, devolve in_progress blocked
        test_run["overall"] = "fail"
        test_run["decision"] = "in_progress_test_failed_precheck"
        test_run["decision_reason"] = pc["failure_reason"]
        test_run["finished_at"] = store.now_iso()
        path = store.write_test_run(test_run_id, test_run)
        if not no_act:
            try:
                move_to_in_progress(task_id)
                block(task_id, f"test_failed: {_short_reason(pc['failure_reason'])}")
                merge_test_result(task_id, _build_merge_fields(test_run, path, seq))
                test_run["kanban_actions_applied"] = [
                    "task_move:in_progress", "task_block:test_failed",
                    "set-dispatch-payload:test_result"]
                store.write_test_run(test_run_id, test_run)
            except LifecycleError:
                raise
        return test_run

    # Per AC checks
    ac_list = ctx["acceptance_criteria"]
    model_kw = {"model": model} if model else {}
    raw_checks: List[Dict[str, Any]] = []
    for ac in ac_list:
        try:
            raw = checker_lib.check_ac(ac, ctx, **model_kw)
        except checker_lib.CheckerError as e:
            # Treat checker failure as inconclusive (operator inspect)
            raw = {"status": "inconclusive", "evidence": "", "sources": [],
                   "structural_concern": "",
                   "raw_response": f"CHECKER_ERROR: {e}",
                   "drafter_model": model or checker_lib.CHECKER_MODEL,
                   "checker_error": str(e)}
        safety_result = safety.enforce_safety(
            raw["status"], raw["sources"], raw.get("structural_concern", ""), ctx,
        )
        raw_checks.append({
            "ac": ac,
            "status": raw["status"],
            "effective_status": safety_result["effective_status"],
            "downgrade_reason": safety_result["downgrade_reason"],
            "structural_concern": raw.get("structural_concern", ""),
            "effective_structural_concern": safety_result["effective_structural_concern"],
            "evidence": raw.get("evidence", ""),
            "sources": raw.get("sources", []),
            "valid_sources": safety_result["valid_sources"],
            "invalid_sources": safety_result["invalid_sources"],
            "drafter_model": raw.get("drafter_model"),
            "raw_response": raw.get("raw_response", ""),
            "checker_error": raw.get("checker_error"),
        })

    test_run["checks"] = raw_checks

    # Aggregate decision
    agg = _aggregate(raw_checks)
    test_run["overall"] = agg["overall"]
    test_run["decision"] = agg["decision"]
    test_run["decision_reason"] = _build_decision_reason(agg, raw_checks)
    test_run["finished_at"] = store.now_iso()
    path = store.write_test_run(test_run_id, test_run)

    if no_act:
        return test_run

    # Apply kanban
    actions: List[str] = []
    decision = agg["decision"]
    if decision == "done":
        move_to_done(task_id)
        actions += ["task_move:done"]
    elif decision == "in_progress_test_failed":
        first_fail = next((c for c in raw_checks
                           if c["effective_status"] == "fail"), None)
        ac_excerpt = _short_reason(first_fail.get("ac", "") if first_fail else "")
        move_to_in_progress(task_id)
        block(task_id, f"test_failed: {ac_excerpt}")
        actions += ["task_move:in_progress", "task_block:test_failed"]
    elif decision == "in_progress_test_inconclusive":
        first_inc = next((c for c in raw_checks
                          if c["effective_status"] == "inconclusive"), None)
        reason_excerpt = _short_reason(
            (first_inc.get("downgrade_reason") or first_inc.get("evidence") or "")
            if first_inc else "",
        )
        move_to_in_progress(task_id)
        block(task_id, f"test_inconclusive: {reason_excerpt}")
        actions += ["task_move:in_progress", "task_block:test_inconclusive"]
    elif decision == "proposed_rejected":
        # NAO move kanban; escreve escalation file. Bernard --commit decide.
        _write_escalation_md(test_run_id, task_id, raw_checks)
        actions += ["escalation_written"]
    merge_test_result(task_id, _build_merge_fields(test_run, path, seq))
    actions += ["set-dispatch-payload:test_result"]

    test_run["kanban_actions_applied"] = actions
    store.write_test_run(test_run_id, test_run)
    return test_run


def _build_merge_fields(test_run: Dict[str, Any], path: Path,
                        seq: int) -> Dict[str, Any]:
    """Campos isolados em dispatch_payload (decisao #9 da spec)."""
    return {
        "test_result": {
            "last_test_run_id": test_run["test_run_id"],
            "last_test_run_path": str(path),
            "last_test_overall": test_run["overall"],
            "last_test_decision": test_run["decision"],
            "last_test_finished_at": test_run.get("finished_at"),
            "test_run_count": seq,
            "tester_actor": "tester",
        },
    }


def _build_decision_reason(agg: Dict[str, str],
                           checks: List[Dict[str, Any]]) -> str:
    decision = agg["decision"]
    if decision == "done":
        return f"all {len(checks)} AC pass"
    if decision == "in_progress_test_failed":
        fails = [c for c in checks if c["effective_status"] == "fail"]
        return f"{len(fails)}/{len(checks)} AC fail: {_short_reason(fails[0].get('ac', ''))}"
    if decision == "in_progress_test_inconclusive":
        inc = [c for c in checks if c["effective_status"] == "inconclusive"]
        return f"{len(inc)}/{len(checks)} AC inconclusive: {_short_reason(inc[0].get('downgrade_reason') or inc[0].get('evidence', ''))}"
    if decision == "proposed_rejected":
        sc = [c for c in checks if c.get("effective_structural_concern")]
        return f"structural concern detected: {sc[0].get('effective_structural_concern')}"
    return "unknown"
EOF
```

- [ ] **Step 2: Sanity import**

```bash
cd ~/.openclaw/tester-agent && PYTHONPATH=. python3 -c "
from lib.lifecycle import (run_check, _aggregate, _build_decision_reason,
                            _short_reason, LifecycleError)
# aggregate decisions
assert _aggregate([{'effective_status': 'pass', 'effective_structural_concern': ''}])['decision'] == 'done'
assert _aggregate([{'effective_status': 'fail', 'effective_structural_concern': ''},
                    {'effective_status': 'pass', 'effective_structural_concern': ''}])['decision'] == 'in_progress_test_failed'
assert _aggregate([{'effective_status': 'inconclusive', 'effective_structural_concern': ''}])['decision'] == 'in_progress_test_inconclusive'
assert _aggregate([{'effective_status': 'fail', 'effective_structural_concern': 'task_malformed'}])['decision'] == 'proposed_rejected'
# pass + structural -> propose
assert _aggregate([{'effective_status': 'pass', 'effective_structural_concern': 'spec_inconsistent'}])['decision'] == 'proposed_rejected'
assert _short_reason('a' * 200) == 'a' * 80
print('OK lifecycle aggregate')
"
```

Expected: `OK lifecycle aggregate`.

---

## Phase 7: api.py — CLI: check, recheck, results, show, reject-task

### Task 7.1: lib/api.py

**Files:**
- Create: `~/.openclaw/tester-agent/lib/api.py`

- [ ] **Step 1: Escrever api.py**

```bash
cat > ~/.openclaw/tester-agent/lib/api.py <<'EOF'
"""CLI tester-agent."""

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Optional

from . import checker as checker_lib
from . import context_loader as ctx_lib
from . import lifecycle as lifecycle_lib
from . import store

EXIT_OK = 0
EXIT_INPUT = 1
EXIT_PRECHECK_FAILED_INFRA = 2
EXIT_PROPOSES_REJECTION = 3

VALID_REJECT_CATEGORIES = {
    "task_malformed", "spec_inconsistent", "requires_re_decomposition",
    "inexecutable", "manual",
}

_EXIT_BY_CODE = {
    "TASK_NOT_FOUND": EXIT_INPUT,
    "KANBAN_CLI_TIMEOUT": EXIT_INPUT,
    "KANBAN_CLI_FAILED": EXIT_INPUT,
    "KANBAN_CLI_BAD_JSON": EXIT_INPUT,
    "INVALID_REJECT_CATEGORY": EXIT_INPUT,
    "TEST_RUN_NOT_FOUND": EXIT_INPUT,
}


def _err(msg: str, code: str, json_mode: bool) -> int:
    if json_mode:
        print(json.dumps({"ok": False, "error": msg, "code": code}))
    else:
        print(f"ERROR ({code}): {msg}", file=sys.stderr)
    return _EXIT_BY_CODE.get(code, 2)


def _print(payload: Any, json_mode: bool, human: Optional[str] = None) -> None:
    if json_mode:
        print(json.dumps(payload, ensure_ascii=False, indent=2))
    else:
        if human is not None:
            print(human)
        else:
            print(json.dumps(payload, ensure_ascii=False, indent=2))


def _decision_exit_code(decision: str) -> int:
    if decision == "proposed_rejected":
        return EXIT_PROPOSES_REJECTION
    return EXIT_OK


def cmd_check(args: argparse.Namespace) -> int:
    try:
        result = lifecycle_lib.run_check(
            args.task_id, no_act=args.no_act, model=args.model, trigger="manual",
        )
    except ctx_lib.ContextError as e:
        return _err(e.detail, e.code, args.json)
    except lifecycle_lib.LifecycleError as e:
        return _err(e.detail, e.code, args.json)

    decision = result.get("decision") or ""
    pc_passed = result.get("prechecks", {}).get("passed", False)

    if args.json:
        _print(result, True)
    else:
        print(f"test_run: {result['test_run_id']}")
        print(f"  prechecks_passed: {pc_passed}")
        if not pc_passed:
            print(f"  failure_reason: {result['prechecks']['failure_reason']}")
        else:
            n_pass = sum(1 for c in result['checks'] if c['effective_status'] == 'pass')
            n_fail = sum(1 for c in result['checks'] if c['effective_status'] == 'fail')
            n_inc = sum(1 for c in result['checks'] if c['effective_status'] == 'inconclusive')
            n_struct = sum(1 for c in result['checks'] if c.get('effective_structural_concern'))
            print(f"  ac_results: {n_pass}p / {n_fail}f / {n_inc}i ({len(result['checks'])} total)"
                  + (f" + {n_struct} structural_concern" if n_struct else ""))
        print(f"  overall: {result['overall']}")
        print(f"  decision: {decision}")
        print(f"  reason: {result['decision_reason']}")
        if result.get("kanban_actions_applied"):
            print(f"  applied: {', '.join(result['kanban_actions_applied'])}")

    if not pc_passed and not args.no_act:
        # precheck infrastrutural fail (log missing etc) — exit 2 ate Bernard fix
        infra_fails = {"execution_log_exists", "acceptance_criteria_non_empty"}
        failed_keys = {k for k, v in result["prechecks"]["details"].items() if not v}
        if failed_keys & infra_fails:
            return EXIT_PRECHECK_FAILED_INFRA

    return _decision_exit_code(decision)


def cmd_recheck(args: argparse.Namespace) -> int:
    # Recheck = mesma logica do check; novo seq sai automatico
    return cmd_check(args)


def cmd_results(args: argparse.Namespace) -> int:
    runs = store.list_test_runs(task_id=args.task_id)
    if args.failed:
        runs = [r for r in runs if r.get("decision") == "in_progress_test_failed"
                or r.get("decision") == "in_progress_test_failed_precheck"]
    elif args.inconclusive:
        runs = [r for r in runs if r.get("decision") == "in_progress_test_inconclusive"]
    elif args.proposed_rejection:
        runs = [r for r in runs if r.get("decision") == "proposed_rejected"]
    if args.json:
        _print({"test_runs": runs}, True)
        return EXIT_OK
    if not runs:
        print("(nenhum test_run)")
        return EXIT_OK
    print(f"{'TEST_RUN_ID':30s} {'TASK':10s} {'OVERALL':30s} DECISION")
    for r in runs:
        print(f"{r.get('test_run_id', '?'):30s} "
              f"{r.get('task_id', '?'):10s} "
              f"{(r.get('overall') or '?'):30s} "
              f"{r.get('decision') or '?'}")
    return EXIT_OK


def cmd_show(args: argparse.Namespace) -> int:
    target = args.target
    if "-tr-" in target:
        # test_run_id
        tr = store.read_test_run(target)
        if tr is None:
            return _err(f"test_run {target} nao existe",
                        "TEST_RUN_NOT_FOUND", args.json)
        if args.json:
            _print(tr, True)
            return EXIT_OK
        print(f"=== {target} ===")
        print(json.dumps(tr, ensure_ascii=False, indent=2))
        return EXIT_OK
    # task_id: lista test_runs dessa task
    runs = store.list_test_runs(task_id=target)
    if not runs:
        return _err(f"nenhum test_run para {target}",
                    "TEST_RUN_NOT_FOUND", args.json)
    if args.json:
        _print({"task_id": target, "test_runs": runs}, True)
        return EXIT_OK
    print(f"test_runs for {target}:")
    for r in runs:
        print(f"  {r.get('test_run_id'):30s} {r.get('decision') or '?'}")
    return EXIT_OK


def cmd_reject_task(args: argparse.Namespace) -> int:
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
    # Clear escalation (latest seq)
    runs = store.list_test_runs(task_id=args.task_id)
    if runs:
        latest = max(runs, key=lambda r: r.get("test_run_id", ""))
        store.clear_escalation(latest.get("test_run_id"))
    _print({"ok": True, "task_id": args.task_id, "reason": args.reason},
           args.json,
           f"rejected: {args.task_id} (reason: {args.reason})")
    return EXIT_OK


def cmd_escalations(args: argparse.Namespace) -> int:
    escs = store.list_escalations()
    if args.json:
        _print({"escalations": escs}, True)
        return EXIT_OK
    if not escs:
        print("(nenhuma escalation pending)")
        return EXIT_OK
    print(f"{'TEST_RUN_ID':30s} ESCALATION_PATH")
    for e in escs:
        print(f"{e['test_run_id']:30s} {e['escalation_path']}")
    return EXIT_OK


def build_parser() -> argparse.ArgumentParser:
    common = argparse.ArgumentParser(add_help=False)
    common.add_argument("--json", action="store_true")
    common.add_argument("--actor", default="tester")

    p = argparse.ArgumentParser(prog="tester-agent")
    sub = p.add_subparsers(dest="cmd", required=True)

    def leaf(psub, name):
        return psub.add_parser(name, parents=[common])

    ck = leaf(sub, "check")
    ck.add_argument("task_id")
    ck.add_argument("--no-act", action="store_true",
                    help="dry-run: gera test_run JSON, NAO move kanban")
    ck.add_argument("--model", default="claude-haiku-4-5")
    ck.set_defaults(func=cmd_check)

    rc = leaf(sub, "recheck")
    rc.add_argument("task_id")
    rc.add_argument("--no-act", action="store_true")
    rc.add_argument("--model", default="claude-haiku-4-5")
    rc.set_defaults(func=cmd_recheck)

    rs = leaf(sub, "results")
    rs.add_argument("--task-id", default=None)
    rs.add_argument("--all", action="store_true")
    rs.add_argument("--failed", action="store_true")
    rs.add_argument("--inconclusive", action="store_true")
    rs.add_argument("--proposed-rejection", action="store_true")
    rs.set_defaults(func=cmd_results)

    sh = leaf(sub, "show")
    sh.add_argument("target", help="task_id ou test_run_id")
    sh.set_defaults(func=cmd_show)

    rj = leaf(sub, "reject-task")
    rj.add_argument("task_id")
    rj.add_argument("--reason", required=True)
    rj.add_argument("--commit", action="store_true")
    rj.set_defaults(func=cmd_reject_task)

    es = leaf(sub, "escalations")
    es.set_defaults(func=cmd_escalations)

    return p


def main(argv=None) -> int:
    p = build_parser()
    args = p.parse_args(argv)
    if args.cmd == "reject-task" and not getattr(args, "commit", False):
        print("ERROR: --commit obrigatorio pra aplicar (gate humano)",
              file=sys.stderr)
        return EXIT_INPUT
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
EOF
```

- [ ] **Step 2: Sanity CLI help**

```bash
~/.openclaw/tester-agent/cli.sh --help 2>&1 | head -10
~/.openclaw/tester-agent/cli.sh check --help 2>&1 | head -8
~/.openclaw/tester-agent/cli.sh reject-task --help 2>&1 | head -8
```

Expected: usage textos sem traceback; `check` mostra `--no-act`, `--model`; `reject-task` mostra `--reason`, `--commit`.

- [ ] **Step 3: Sanity reject-task SEM --commit (deve falhar com EXIT_INPUT)**

```bash
~/.openclaw/tester-agent/cli.sh reject-task T-FAKE --reason "manual: x" 2>&1; echo "exit=$?"
```

Expected: `--commit obrigatorio` + `exit=1`.

- [ ] **Step 4: Sanity reject-task com categoria invalida**

```bash
~/.openclaw/tester-agent/cli.sh reject-task T-FAKE --reason "garbage_category: x" --commit 2>&1; echo "exit=$?"
```

Expected: `categoria invalida` + `exit=1`.

- [ ] **Step 5: Sanity escalations vazio**

```bash
~/.openclaw/tester-agent/cli.sh escalations
```

Expected: `(nenhuma escalation pending)`.

- [ ] **Step 6: Commit progresso (host-local — opcional sanity)**

Não há git tracking em `~/.openclaw/tester-agent/` (host-local). Pular commit; só verificar listing:

```bash
ls -la ~/.openclaw/tester-agent/lib/
ls -la ~/.openclaw/tester-agent/
```

Expected: 7 .py files em lib/ + cli.sh + README.md + dirs.

---

## Phase 8: dispatcher delta — flag --no-tester + auto-invoke condicional

### Task 8.1: Backup dispatcher api.py + adicionar flag

**Files:**
- Modify: `~/.openclaw/dispatcher-agent/lib/api.py`
- Backup: `~/.openclaw/dispatcher-agent/lib/api.py.pre-tester.bak`

- [ ] **Step 1: Backup**

```bash
cp ~/.openclaw/dispatcher-agent/lib/api.py ~/.openclaw/dispatcher-agent/lib/api.py.pre-tester.bak
```

- [ ] **Step 2: Adicionar TESTER_CLI constant + cmd_next ganha auto-invoke**

Edita `~/.openclaw/dispatcher-agent/lib/api.py`:

Localizar bloco `DEFAULT_ALLOWED_TOOLS` (linha ~18). Logo abaixo adicionar:

```python
TESTER_CLI = "~/.openclaw/tester-agent/cli.sh"
```

Localizar `def cmd_next(args: argparse.Namespace) -> int:` (linha ~62).
Após o bloco que faz `lifecycle_lib.process_finished_session(task["id"])`
em foreground (linha ~108), antes do `else: status = runner_lib.launch_detached(...)`,
inserir auto-invoke logic. Estrutura final do bloco:

```python
        if args.foreground:
            status = runner_lib.launch_foreground(
                task["id"], bpath, allowed_tools, model=args.model,
            )
            lifecycle_lib.process_finished_session(task["id"])
            # Auto-invoke tester (foreground only; default ON; --no-tester desativa)
            tester_invoked = False
            tester_result_summary = None
            if not args.no_tester:
                tester_invoked, tester_result_summary = _invoke_tester(
                    task["id"], json_mode=args.json,
                )
            status["tester_invoked"] = tester_invoked
            if tester_result_summary:
                status["tester_result_summary"] = tester_result_summary
        else:
            status = runner_lib.launch_detached(
                task["id"], bpath, allowed_tools, model=args.model,
            )
```

E adicionar a function helper `_invoke_tester` antes de `cmd_next`:

```python
def _invoke_tester(task_id: str, json_mode: bool) -> tuple:
    """Invoca tester-agent CLI sequencial. Retorna (invoked_bool, summary_dict).

    Foreground only — chamado dentro de cmd_next quando --foreground + sem --no-tester.
    Em modo detached, esta funcao NAO eh chamada (limitacao MVP wave-3 da spec; ver §10.2).
    """
    import subprocess as sp
    cmd = [TESTER_CLI, "check", task_id, "--json"]
    try:
        r = sp.run(cmd, capture_output=True, text=True, check=False, timeout=600)
    except (OSError, sp.TimeoutExpired) as e:
        if not json_mode:
            print(f"WARN: tester invoke failed: {e}", file=sys.stderr)
        return False, {"error": str(e)}
    if r.returncode not in (0, 3) and not json_mode:
        print(f"WARN: tester exit={r.returncode}; ver test_run", file=sys.stderr)
    summary: Dict[str, Any] = {"tester_exit_code": r.returncode}
    try:
        parsed = json.loads(r.stdout)
        summary["test_run_id"] = parsed.get("test_run_id")
        summary["overall"] = parsed.get("overall")
        summary["decision"] = parsed.get("decision")
    except (json.JSONDecodeError, ValueError):
        summary["raw_stdout_tail"] = r.stdout[-300:]
    return True, summary
```

E o argparse de `next` precisa ganhar `--no-tester`. Localizar o bloco `nx = leaf(sub, "next")` (linha ~233) e adicionar:

```python
    nx.add_argument("--no-tester", action="store_true",
                    help="Skip auto-invoke do tester (foreground only).")
```

Implementar via Edit:

```bash
# Adicionar TESTER_CLI constant
~/.openclaw/dispatcher-agent/cli.sh --help >/dev/null  # baseline confirmado
```

Use Edit tool pra fazer as 4 mudanças no `~/.openclaw/dispatcher-agent/lib/api.py`:

1. Adicionar `TESTER_CLI = "~/.openclaw/tester-agent/cli.sh"` após `DEFAULT_ALLOWED_TOOLS`.
2. Adicionar function `_invoke_tester` antes de `cmd_next`.
3. Inserir auto-invoke dentro de `if args.foreground:` block após `process_finished_session`.
4. Adicionar `nx.add_argument("--no-tester", ...)` em build_parser.

Adicionalmente importar `Dict` se não estiver:

```python
from typing import Any, Dict, Optional
```

(o existente já importa `Any, Optional`; basta adicionar `Dict`).

- [ ] **Step 3: Verificar import + parser ainda funcionam**

```bash
~/.openclaw/dispatcher-agent/cli.sh --help 2>&1 | head -5
~/.openclaw/dispatcher-agent/cli.sh next --help 2>&1 | grep -E "(no-tester|foreground|launch)"
```

Expected: help OK; `--no-tester` listado entre os args do `next`.

- [ ] **Step 4: Sanity import**

```bash
cd ~/.openclaw/dispatcher-agent && PYTHONPATH=. python3 -c "
from lib.api import _invoke_tester, TESTER_CLI, build_parser
p = build_parser()
args = p.parse_args(['next', '--help'])
" 2>&1 | head -3
```

Expected: prints help text without crash (argparse `--help` raises SystemExit which é OK).

- [ ] **Step 5: Verificar backup**

```bash
diff ~/.openclaw/dispatcher-agent/lib/api.py.pre-tester.bak ~/.openclaw/dispatcher-agent/lib/api.py | head -50
```

Expected: diff mostra adições (TESTER_CLI, _invoke_tester, --no-tester arg, auto-invoke block).

---

## Phase 9: Integration E2E smoke — cobre 8 cenários DoD §12.4

### Task 9.1: Baseline + setup helpers

**Files:** none (prep)

- [ ] **Step 1: Baseline snapshot kanban + executions + tester runs**

```bash
cd ~/.openclaw/kanban-tasks
BASELINE_EVENTS=$(wc -l < events.jsonl)
cp state.json /tmp/state.ph9-baseline.json
cp events.jsonl /tmp/events.ph9-baseline.jsonl
echo "baseline events: $BASELINE_EVENTS"

# Snapshot executions + test_runs (limpa pra evitar lixo entre cenarios)
mkdir -p /tmp/ph9-bk
cp -r ~/.openclaw/dispatcher-agent/executions /tmp/ph9-bk/executions || true
cp -r ~/.openclaw/tester-agent/test_runs /tmp/ph9-bk/test_runs || true
cp -r ~/.openclaw/tester-agent/escalations /tmp/ph9-bk/escalations || true
```

- [ ] **Step 2: Helper function pra criar fixture briefing/log/AC**

```bash
cat > /tmp/ph9-create-fixture.sh <<'BASH'
#!/usr/bin/env bash
# Cria task fixture com AC, log fake, dispatch_payload completo.
# Uso: ./ph9-create-fixture.sh <suffix> <ac_text> <log_content>
set -euo pipefail
SUFFIX="$1"; AC="$2"; LOG_CONTENT="$3"
PLAN=/tmp/ph9-plan-${SUFFIX}.md
cat > "$PLAN" <<EOF
# Plan ph9-${SUFFIX}
**Goal:** smoke ph9 ${SUFFIX}
**Epico:** E10/scrum-master-agent
**Project:** openclaw
**Specs canonicas:**
- \`bevox-knowledge/35_specs/2026-04-19-e10-tester-agent.md\`
## Phase 0: x
### Task 0.1: ph9 ${SUFFIX}
${AC}
**Files:**
- Create: \`/tmp/ph9-out-${SUFFIX}.txt\`
- [ ] **Step 1: stub**
Expected: x
EOF
~/.openclaw/scrum-master-agent/cli.sh propose --plan "$PLAN" --target-sprint current >/dev/null
PID=$(~/.openclaw/scrum-master-agent/cli.sh list --status pending --json | python3 -c "import json,sys; print(json.load(sys.stdin)['proposals'][-1]['proposal_id'])")
~/.openclaw/scrum-master-agent/cli.sh accept "$PID" --ready >/dev/null
TID=$(~/.openclaw/scrum-master-agent/cli.sh show "$PID" --json | python3 -c "import json,sys; print(json.load(sys.stdin)['state']['materialized_task_ids'][0])")
echo "$TID"
BASH
chmod +x /tmp/ph9-create-fixture.sh
```

- [ ] **Step 3: Helper pra simular execucao detached (sem invocar Claude real)**

```bash
cat > /tmp/ph9-fake-execution.sh <<'BASH'
#!/usr/bin/env bash
# Simula dispatcher execution: cria log + status.json + auto-move testing.
# Uso: ./ph9-fake-execution.sh <task-id> <log-content> [exit-code]
set -euo pipefail
TID="$1"; LOG_CONTENT="$2"; EXIT=${3:-0}
mkdir -p ~/.openclaw/dispatcher-agent/executions
echo -e "$LOG_CONTENT" > ~/.openclaw/dispatcher-agent/executions/${TID}.log
TS=$(date -u +%Y-%m-%dT%H:%M:%SZ)
cat > ~/.openclaw/dispatcher-agent/executions/${TID}.status.json <<EOF
{
  "task_id": "${TID}",
  "session_id": "fake-${TID}",
  "pid": 0,
  "log_path": "$(echo ~)/.openclaw/dispatcher-agent/executions/${TID}.log",
  "started_at": "${TS}",
  "finished_at": "${TS}",
  "exit_code": ${EXIT},
  "run_mode": "detach"
}
EOF
# Move ready -> in_progress -> testing (simula dispatcher path)
~/.openclaw/kanban-tasks/cli.sh task move "$TID" in_progress --actor dispatcher >/dev/null 2>&1 || true
~/.openclaw/kanban-tasks/cli.sh task move "$TID" testing --actor dispatcher >/dev/null
echo "fake exec done: $TID"
BASH
chmod +x /tmp/ph9-fake-execution.sh
```

### Task 9.2: Cenario 1 — Foreground happy path (auto-tester pass → done)

- [ ] **Step 1: Criar fixture com AC simples + executar dispatcher --foreground**

```bash
TID1=$(/tmp/ph9-create-fixture.sh c1 "AC: arquivo /tmp/ph9-out-c1.txt deve conter string 'hello'" "n/a")
echo "task: $TID1"

# Foreground real: claude executa de verdade (escreve hello), dispatcher auto-move testing,
# auto-invoca tester, tester valida AC contra log+arquivo, decide done.
timeout 240 ~/.openclaw/dispatcher-agent/cli.sh next --project openclaw \
  --launch --foreground --model claude-haiku-4-5 2>&1 | tail -30
```

Expected: dispatcher launched, claude exec hello escrita, auto-move testing, tester invocado, decision=done.

- [ ] **Step 2: Verificar state**

```bash
~/.openclaw/kanban-tasks/cli.sh task show $TID1 --json | python3 -c "
import json, sys
t = json.load(sys.stdin)['task']
dp = t.get('dispatch_payload') or {}
tr = dp.get('test_result') or {}
print(f'status={t[\"status\"]}  blocked={t.get(\"blocked\")}')
print(f'test_overall={tr.get(\"last_test_overall\")}  decision={tr.get(\"last_test_decision\")}')
assert t['status'] == 'done', t['status']
assert tr.get('last_test_overall') == 'pass'
assert tr.get('last_test_decision') == 'done'
print('OK cenario 1: foreground happy path')
"
cat /tmp/ph9-out-c1.txt 2>/dev/null
```

Expected: `OK cenario 1` + arquivo contém "hello".

- [ ] **Step 3: Cleanup cenário 1**

```bash
~/.openclaw/kanban-tasks/cli.sh task archive $TID1 >/dev/null
rm -f /tmp/ph9-out-c1.txt
```

### Task 9.3: Cenario 2 — Foreground fail-AC → in_progress + test_failed

Pra cenário fail rápido, simula fake execution (sem claude real burning tokens):
- log mostra falha intencional
- AC pede algo que log NÃO mostra → tester decide fail

- [ ] **Step 1: Criar fixture + fake execution falha**

```bash
TID2=$(/tmp/ph9-create-fixture.sh c2 "AC: log do executor deve mostrar 'BUILD SUCCESS' explicito." "n/a")
/tmp/ph9-fake-execution.sh "$TID2" "starting build...\nBUILD FAILED: missing dependency\nexit 0" 0

# Roda tester direto sobre task em testing
~/.openclaw/tester-agent/cli.sh check "$TID2" --model claude-haiku-4-5 2>&1 | tail -15
```

Expected: tester detecta fail (log diz FAILED, AC diz SUCCESS), decisao=in_progress_test_failed.

- [ ] **Step 2: Verificar state**

```bash
~/.openclaw/kanban-tasks/cli.sh task show $TID2 --json | python3 -c "
import json, sys
t = json.load(sys.stdin)['task']
dp = t.get('dispatch_payload') or {}
tr = dp.get('test_result') or {}
print(f'status={t[\"status\"]}  blocked={t.get(\"blocked\")}  reason={t.get(\"blocked_reason\")}')
assert t['status'] == 'in_progress'
assert t.get('blocked') is True
assert 'test_failed' in (t.get('blocked_reason') or '')
assert tr.get('last_test_decision') in ('in_progress_test_failed', 'in_progress_test_inconclusive')
print('OK cenario 2: foreground fail-AC')
"
```

Expected: `OK cenario 2`.

- [ ] **Step 3: Cleanup**

```bash
~/.openclaw/kanban-tasks/cli.sh task unblock $TID2 2>/dev/null || true
~/.openclaw/kanban-tasks/cli.sh task archive $TID2 >/dev/null
```

### Task 9.4: Cenario 3 — Foreground inconclusive (sem evidencia)

- [ ] **Step 1: Fixture + fake execution sem evidencia clara**

```bash
TID3=$(/tmp/ph9-create-fixture.sh c3 "AC: pytest da feature X deve passar com 0 erros." "n/a")
/tmp/ph9-fake-execution.sh "$TID3" "boot complete\nidle session" 0

~/.openclaw/tester-agent/cli.sh check "$TID3" --model claude-haiku-4-5 2>&1 | tail -15
```

Expected: tester identifica que log nao tem trace de pytest → inconclusive.

- [ ] **Step 2: Verificar**

```bash
~/.openclaw/kanban-tasks/cli.sh task show $TID3 --json | python3 -c "
import json, sys
t = json.load(sys.stdin)['task']
dp = t.get('dispatch_payload') or {}
tr = dp.get('test_result') or {}
print(f'status={t[\"status\"]}  blocked={t.get(\"blocked\")}  reason={t.get(\"blocked_reason\")}')
assert t['status'] == 'in_progress'
assert t.get('blocked') is True
assert tr.get('last_test_decision') == 'in_progress_test_inconclusive', tr.get('last_test_decision')
assert 'inconclusive' in (t.get('blocked_reason') or '')
print('OK cenario 3: inconclusive')
"
```

Expected: `OK cenario 3`.

- [ ] **Step 3: Cleanup**

```bash
~/.openclaw/kanban-tasks/cli.sh task unblock $TID3 2>/dev/null || true
~/.openclaw/kanban-tasks/cli.sh task archive $TID3 >/dev/null
```

### Task 9.5: Cenario 4 — Reject-propose (structural fail) + Bernard --commit

- [ ] **Step 1: Fixture com AC que contradiz spec_refs internos**

```bash
TID4=$(/tmp/ph9-create-fixture.sh c4 "AC: implementar feature de auto-merge canonico (rejeitada explicitamente em ADR-006). Spec deve provar que ADR-006 nao se aplica." "n/a")
/tmp/ph9-fake-execution.sh "$TID4" "executor saiu cedo, AC contradiz canonical" 0

# Tester deve detectar structural concern (AC contradiz canonical), exit 3
~/.openclaw/tester-agent/cli.sh check "$TID4" --model claude-haiku-4-5 2>&1 | tail -15
TESTER_EXIT=$?
echo "tester exit code: $TESTER_EXIT"
```

Expected: tester output indica `proposed_rejected`; pode OR pode não retornar exit 3 (depende do drafter detectar structural). Se não detectar:

- [ ] **Step 2: Forçar manualmente cenário reject-task --commit (gate humano funciona)**

```bash
# Reject manual (smoke do gate humano)
~/.openclaw/tester-agent/cli.sh reject-task $TID4 --reason "spec_inconsistent: smoke test cenario 4" --commit

~/.openclaw/kanban-tasks/cli.sh task show $TID4 --json | python3 -c "
import json, sys
t = json.load(sys.stdin)['task']
print(f'status={t[\"status\"]}  reason={t.get(\"rejected_reason\")}')
assert t['status'] == 'rejected'
assert 'spec_inconsistent' in (t.get('rejected_reason') or '')
print('OK cenario 4: reject-task --commit')
"
```

Expected: `OK cenario 4`.

- [ ] **Step 3: Cleanup**

```bash
# Reject sem --commit deve falhar (verifica guardrail)
~/.openclaw/tester-agent/cli.sh reject-task T-FAKE-WHATEVER --reason "manual: x" 2>&1; echo "exit=$?"
# Expected: exit=1 + ERROR: --commit obrigatorio
```

### Task 9.6: Cenario 5 — Hallucination guard (pass forced → inconclusive)

Esse cenário valida `safety.enforce_safety` no fluxo real: drafter retorna pass com source falsa → tester downgrade pra inconclusive. Como o drafter real raramente alucina path, o smoke é unit-level (já feito Phase 5) + cenário com fake execution onde só o log é fonte e drafter cita arquivo inexistente seria cara/instável. Pular real e validar via test isolado:

- [ ] **Step 1: Test isolado simulando alucinação**

```bash
cd ~/.openclaw/tester-agent && PYTHONPATH=. python3 <<'EOF'
"""Simula drafter alucinando source. Safety.enforce_safety deve downgrade."""
from lib import safety
ctx = {
    "files_relevant": [{"ref": "real.py", "path": "/tmp/real.py"}],
    "spec_refs": [],
    "execution_log_path": "/tmp/fake.log",
}
r = safety.enforce_safety(
    status="pass",
    sources=["/tmp/imaginary-not-exist-xyz.py"],
    structural_concern="",
    ctx=ctx,
)
assert r["effective_status"] == "inconclusive", r
assert "hallucination" in r["downgrade_reason"].lower() or "no_sources" in r["downgrade_reason"].lower()
print(f"OK cenario 5: hallucination guard downgrade pass->inconclusive (reason: {r['downgrade_reason'][:60]}...)")
EOF
```

Expected: `OK cenario 5`.

### Task 9.7: Cenario 6 — Manual recheck Bernard

- [ ] **Step 1: Reusa cenario 3 path: fake execution + recheck**

```bash
TID6=$(/tmp/ph9-create-fixture.sh c6 "AC: log deve conter 'CHECKPOINT'" "n/a")
/tmp/ph9-fake-execution.sh "$TID6" "starting...\nCHECKPOINT reached\ndone" 0

# Bernard recheck (= check; novo seq)
~/.openclaw/tester-agent/cli.sh recheck "$TID6" --model claude-haiku-4-5 2>&1 | tail -10

~/.openclaw/kanban-tasks/cli.sh task show $TID6 --json | python3 -c "
import json, sys
t = json.load(sys.stdin)['task']
dp = t.get('dispatch_payload') or {}
tr = dp.get('test_result') or {}
print(f'status={t[\"status\"]}  decision={tr.get(\"last_test_decision\")}')
assert t['status'] == 'done', t['status']
print('OK cenario 6: recheck manual passou')
"
```

Expected: `OK cenario 6`.

- [ ] **Step 2: Cleanup**

```bash
~/.openclaw/kanban-tasks/cli.sh task archive $TID6 >/dev/null
```

### Task 9.8: Cenario 7 — Detached default (auto-tester DESABILITADO nesta wave)

- [ ] **Step 1: Fixture + dispatcher next --launch (sem --foreground)**

```bash
TID7=$(/tmp/ph9-create-fixture.sh c7 "AC: arquivo /tmp/ph9-out-c7.txt deve conter 'detached'" "n/a")

# Detached default: dispatcher spawn + retorna imediato; tester NAO eh invocado
~/.openclaw/dispatcher-agent/cli.sh next --project openclaw --launch --model claude-haiku-4-5 2>&1 | tail -10
```

Expected: launched detach; cmd retornou rapido.

- [ ] **Step 2: Esperar Claude finalizar (poll status até finished_at)**

```bash
for i in 1 2 3 4 5 6 7 8 9 10; do
  STATUS=$(~/.openclaw/dispatcher-agent/cli.sh show $TID7 --json 2>/dev/null | python3 -c "import json,sys; print(json.load(sys.stdin).get('finished_at', '') or 'pending')" 2>/dev/null || echo pending)
  if [ "$STATUS" != "pending" ]; then echo "finished_at=$STATUS"; break; fi
  echo "wait... $i"; sleep 8
done
```

Expected: finished_at populado dentro de 80s.

- [ ] **Step 3: Verificar — task em testing, test_result NAO populado**

```bash
# Trigger lifecycle reaping (chamado por status/show no padrao wave-2)
~/.openclaw/dispatcher-agent/cli.sh show $TID7 --json >/dev/null

~/.openclaw/kanban-tasks/cli.sh task show $TID7 --json | python3 -c "
import json, sys
t = json.load(sys.stdin)['task']
dp = t.get('dispatch_payload') or {}
tr = dp.get('test_result') or None
print(f'status={t[\"status\"]}  test_result={tr}')
assert t['status'] == 'testing', t['status']
assert tr is None or not tr.get('last_test_run_id'), f'auto-tester rodou em detach: {tr}'
print('OK cenario 7: detached default, tester NAO auto-invocado')
"
```

Expected: `OK cenario 7`.

### Task 9.9: Cenario 8 — Detached + Bernard manual `vox tester check` → done

- [ ] **Step 1: Reusa task do cenario 7 + Bernard check manual**

```bash
~/.openclaw/tester-agent/cli.sh check $TID7 --model claude-haiku-4-5 2>&1 | tail -10

~/.openclaw/kanban-tasks/cli.sh task show $TID7 --json | python3 -c "
import json, sys
t = json.load(sys.stdin)['task']
dp = t.get('dispatch_payload') or {}
tr = dp.get('test_result') or {}
print(f'status={t[\"status\"]}  decision={tr.get(\"last_test_decision\")}')
assert t['status'] == 'done', t['status']
assert tr.get('last_test_decision') == 'done'
print('OK cenario 8: detached + tester manual = done (2 touches)')
"
cat /tmp/ph9-out-c7.txt 2>/dev/null
```

Expected: `OK cenario 8` + arquivo contém "detached".

- [ ] **Step 2: Cleanup**

```bash
~/.openclaw/kanban-tasks/cli.sh task archive $TID7 >/dev/null
rm -f /tmp/ph9-out-c7.txt
```

### Task 9.10: Restore baseline

- [ ] **Step 1: Restaurar kanban**

```bash
cd ~/.openclaw/kanban-tasks
cp /tmp/state.ph9-baseline.json state.json
cp /tmp/events.ph9-baseline.jsonl events.jsonl
./cli.sh rebuild >/dev/null 2>&1 || true
FINAL_EVENTS=$(wc -l < events.jsonl)
test "$FINAL_EVENTS" = "$BASELINE_EVENTS" && echo "OK kanban restored ($FINAL_EVENTS == baseline)"
```

Expected: `OK kanban restored ...`.

- [ ] **Step 2: Cleanup tester runs + executions criados no smoke**

```bash
# Tester runs gerados durante smoke ficam pra audit; opcionalmente limpa
ls ~/.openclaw/tester-agent/test_runs/ | grep -E "T-(F[0-9]|[0-9])" | head
# Se quiser limpar tudo (smoke fixtures), descomente:
# rm -f ~/.openclaw/tester-agent/test_runs/*-tr-*.json
# rm -f ~/.openclaw/tester-agent/escalations/*.md
# rm -f ~/.openclaw/dispatcher-agent/executions/T-*.{log,status.json}
rm -f /tmp/ph9-plan-*.md /tmp/ph9-out-*.txt /tmp/ph9-create-fixture.sh /tmp/ph9-fake-execution.sh
echo "smoke cleanup done"
```

- [ ] **Step 3: Sumario dos 8 cenarios**

```bash
cat <<EOF
Smoke E2E completo:
  ✓ Cenario 1: foreground happy path → done (1 touch, real claude)
  ✓ Cenario 2: foreground fail-AC → in_progress blocked test_failed
  ✓ Cenario 3: foreground inconclusive → in_progress blocked test_inconclusive
  ✓ Cenario 4: reject-propose + Bernard --commit (gate humano OK)
  ✓ Cenario 5: hallucination guard downgrade pass→inconclusive
  ✓ Cenario 6: recheck manual Bernard
  ✓ Cenario 7: detached default → tester NAO auto-invocado (limitacao MVP)
  ✓ Cenario 8: detached + tester manual = done (2 touches)
EOF
```

---

## Phase 10: Canonical artifacts

### Task 10.1: Playbook tester-agent.md

**Files:**
- Create: `~/bevox-knowledge/20_architecture/agents/tester-agent.md`

- [ ] **Step 1: Escrever playbook**

```bash
cat > ~/bevox-knowledge/20_architecture/agents/tester-agent.md <<'EOF'
<!-- Agent file do Tester Agent — wave-3 do PRD orchestration.
     Hub-dispatch L1 invocado pelo dispatcher (foreground only) OR
     manualmente por Bernard (qualquer modo).
     Spec canonica: 35_specs/2026-04-19-e10-tester-agent.md
-->

# Agent: tester-agent

> Runbook canonico. Spec: `35_specs/2026-04-19-e10-tester-agent.md`.
> Design: `30_adr/ADR-003-agent-governance.md`. Policy:
> `30_adr/ADR-006-autonomy-permissions-approval.md`. Metadata:
> `20_architecture/agents/registry.yml`.

- **Owner:** <!-- DERIVED --> Bernard
- **Status:** <!-- DERIVED --> ativo
- **Level:** <!-- DERIVED --> L1
- **Modelo padrao:** <!-- DERIVED --> stdlib-python/no-model (invoca claude -p subprocess)
- **Modelo fallback:** <!-- DERIVED --> none
- **Criado em:** <!-- DERIVED --> 2026-04-19

## Missao

Validar tasks em `testing` operacionalmente: 5 invariantes
deterministicos antes de invocar LLM, depois 1 check via `claude -p`
(allowedTools=Read,Grep) por AC; aplicar decisao final no kanban
SEM auto-rejeicao (proposes only).

Decisoes:
- All AC pass + invariantes OK → `testing → done` (auto)
- ≥1 AC fail (reparable) → `testing → in_progress` blocked
  `test_failed: <ac>`
- ≥1 AC inconclusive → `testing → in_progress` blocked
  `test_inconclusive: <reason>`
- Structural concern detectado → exit 3 + escalation file (Bernard
  `--commit` com categoria valida pra mover rejected)

Tester eh **gate de validacao operacional**, NAO juiz de produto.
Valida AC explicita determinanticamente; nunca opina sobre qualidade
subjetiva.

## Inputs

- Auto-invocacao: pelo dispatcher em modo foreground apos
  `auto_move_to_testing`. Skip via `--no-tester`.
- Manual: `vox tester check <task-id>` (qualquer momento, qualquer
  task em testing).
- Recheck: `vox tester recheck <task-id>` (apos edit; novo seq).

## Outputs

- `~/.openclaw/tester-agent/test_runs/<task-id>-tr-<seq>.json`
  (per-test-run audit; prechecks + per-AC checks + decision)
- `~/.openclaw/tester-agent/escalations/<task-id>-tr-<seq>.md`
  (apenas pra structural reject proposed)
- Kanban mutations:
  - Pass: `task move <id> done --actor tester`
  - Fail/inconclusive: `task move <id> in_progress --actor tester` +
    `task block <id> --reason "test_failed|test_inconclusive: ..."`
  - Reject (Bernard `--commit`): `task move <id> rejected --reason "<cat>: ..."`
  - Sempre: `task set-dispatch-payload <id> --merge --payload {test_result: {...}}`

## Skills

- Subprocess `claude -p --allowedTools "Read,Grep"` (drafter, Plano B
  Spike-5, herda padrao validado wave-2).
- Read filesystem (execution log + files_relevant + spec_refs).
- Subprocess `~/.openclaw/kanban-tasks/cli.sh task` (state machine).

## Limites

1. **NUNCA auto-rejeita.** Structural fail → exit 3
   (`TESTER_PROPOSES_REJECTION`); commit terminal sempre via Bernard
   `--commit` com categoria valida.
2. **NUNCA auto-relaunch.** Dispatcher relaunch eh Bernard-only.
3. **5 invariantes obrigatorios** pra auto-promote done:
   `task.status==testing` + `task.blocked==false` + execution log
   non-empty + zero clarification escalation aberta + AC nao-vazio.
4. **`inconclusive` NUNCA promove.** Sempre vira `in_progress` blocked
   `test_inconclusive: <reason>`.
5. **`dispatch_payload.test_result` isolado** em shallow merge top-level.
   Nao toca em campos autorais do scrum-master (goal,
   acceptance_criteria, files_relevant, etc.) nem do dispatcher
   (briefing_path, execution_*).
6. **Auto-invoke condicional ao modo:** apenas em foreground. Detached
   default do dispatcher NAO auto-invoca tester (limitacao MVP wave-3
   §10.2 da spec; follow-up daemon reaper §16).
7. **One-task-per-project**: respeitado quando invocado standalone
   (1 task por invocacao). Concorrencia so se Bernard invocar paralelo.
8. **Read-only allowedTools**: drafter usa apenas `Read,Grep`. Nunca
   `Edit/Write/Bash`.
9. **Categorias rejection fechadas**: `task_malformed`,
   `spec_inconsistent`, `requires_re_decomposition`, `inexecutable`,
   `manual`. Outras strings rejeitadas com `INVALID_REJECT_CATEGORY`.
10. Hard limits gerais (ADR-006) aplicam.

## Approvals

- **Auto-promote done**: sem approval card (gate dispensado pelos 5
  invariantes + hallucination guard de sources).
- **Auto-block fail/inconclusive**: sem approval card (operacao
  reversivel; Bernard pode override via kanban manual).
- **Reject-task**: EXIGE flag `--commit` humano explicit.
- Hard limits gerais (ADR-006) aplicam.

## KPIs

- Test_runs/semana.
- Taxa auto-promote done / total runs.
- Taxa test_failed / total runs (alto = sinal de executor pobre OR AC
  ralo do scrum-master).
- Taxa test_inconclusive / total runs (alto = sinal de AC mal escrita
  OR log incompleto OR drafter prompt fraco).
- Taxa proposed_rejected / total runs (alto = sinal de plan→spec
  drift; scrum-master pode estar produzindo tasks sem checagem com
  canonical).
- Taxa override Bernard kanban manual (apos test_inconclusive) /
  total inconclusive (alto = sinal que confidence binary tá calibrado
  conservador demais).

## Playbook operacional

### 1. Registrar dispatch
Append em `~/.openclaw/workspace/shared/outputs/agent-dispatch.jsonl`.

### 2. Prechecks (5 invariantes)
- task em testing + nao-blocked
- execution log existe e nao-vazio
- acceptance_criteria nao-vazio
- nenhuma clarification escalation aberta
Se algum falha: precheck-failure path (block test_failed: precheck_X).

### 3. Context loader
- Le task via `cli.sh task show <id> --json`
- Le execution log tail (8000 chars) de
  `~/.openclaw/dispatcher-agent/executions/<id>.log`
- Le files_relevant (head 4000 chars cada, max 10)
- Le spec_refs (head 2000 chars cada, max 5)

### 4. Per AC LLM check
- `claude -p` com prompt estruturado §10.3 da spec
- allowedTools="Read,Grep" (read-only)
- Model default: claude-haiku-4-5
- Parse JSON: `{status, evidence, sources, structural_concern}`

### 5. Safety enforce
- Valida sources existem (no contexto OU filesystem)
- Pass + zero sources validas → downgrade inconclusive
- Pass + sources alucinadas → downgrade inconclusive
- structural_concern fora das 4 categorias validas → drop

### 6. Aggregate decision
- All pass + zero structural → `decision=done`
- Any fail (sem structural) → `decision=in_progress_test_failed`
- Any inconclusive (sem fail/structural) →
  `decision=in_progress_test_inconclusive`
- Any structural → `decision=proposed_rejected` (NAO move kanban)

### 7. Apply kanban + merge test_result
- Done: `task move done --actor tester`
- Fail/inconclusive: `task move in_progress` + `task block --reason`
- Proposed_rejected: write escalation file + exit 3
- Sempre: `task set-dispatch-payload --merge --payload {test_result}`

### 8. Human intervention (Bernard)
- `vox tester reject-task <id> --reason "<cat>: ..." --commit`:
  valida categoria + `task move rejected` + clear escalation
- `vox tester recheck <id>`: re-roda check (novo seq)
- Override manual (override done apesar de fail/inconclusive):
  `~/.openclaw/kanban-tasks/cli.sh task unblock <id>` +
  `task move <id> done --actor bernard`

## Boundary com outros agents

Ver §9 + §13 da spec. Tester **NAO**:
- Seleciona task (responsabilidade do dispatcher).
- Gera briefing (responsabilidade do dispatcher).
- Move pra `rejected` autonomamente (sempre via Bernard `--commit`).
- Relaunch (responsabilidade do dispatcher; Bernard inicia).
- Modifica `dispatch_payload` autoral (goal, AC, files_relevant, etc.).
- Auto-invoca em modo detached (limitacao MVP wave-3; §10.2 da spec).
- Multi-round chain numa mesma testing entry (cada testing pass
  isolado; relaunch cria novo dispatcher run + novo testing).

## Touch model (resumo por modo)

| Modo dispatcher | Cenario | Touches Bernard |
|---|---|---|
| `--launch --foreground` | All pass | **1** (kick off) |
| `--launch --foreground` | Test fail/inconclusive | 2 (kick + relaunch ou reject) |
| `--launch --foreground` | Proposed rejected | 2 (kick + `reject-task --commit`) |
| `--launch` (detached default) | All pass | **2** (kick + `vox tester check`) |
| `--launch` (detached default) | Worst case | 4-5 |

Ver §11 da spec para detalhes.

## Volume minimo

- Manter L1: pelo menos 1 invocacao/mes.
- Promocao L2 (ADR-003): pelo menos 5/sem por 4 sem consecutivas, taxa
  auto-promote done ≥ 60%, zero rejection autonoma (sempre via Bernard
  `--commit`), zero overrides manuais Bernard de test_inconclusive em
  10 runs (sinal que confidence binary tá calibrado).

## Historico de levels

- L1 desde 2026-04-19.
EOF
```

- [ ] **Step 2: Verificar criado**

```bash
wc -l ~/bevox-knowledge/20_architecture/agents/tester-agent.md
head -5 ~/bevox-knowledge/20_architecture/agents/tester-agent.md
```

Expected: ~180 linhas; header com `# Agent: tester-agent`.

### Task 10.2: Atualizar playbook canonical do dispatcher (delta --no-tester + auto-invoke)

**Files:**
- Modify: `~/bevox-knowledge/20_architecture/agents/dispatcher-agent.md`

- [ ] **Step 1: Editar playbook do dispatcher pra documentar wave-3 delta**

Localizar a seção `## Limites` e adicionar item 5:

```
5. **Auto-invoke do tester-agent** apos `auto_move_to_testing`:
   APENAS em modo foreground (`--launch --foreground`). Default
   detached NAO invoca tester (limitacao MVP wave-3; §10.2 da spec
   tester-agent). Bernard usa `vox tester check <id>` manual depois.
   Flag `--no-tester` desativa auto-invoke mesmo em foreground (debug).
```

E adicionar referência cruzada na seção `## Inputs`:

```
- Flag opcional: `--foreground` (debug; auto-invoca tester se sem
  `--no-tester`). Em detached default, tester NAO eh auto-invocado.
```

E na seção `## Outputs` adicionar (apos os 3 itens existentes):

```
- Em foreground + tester auto-invocado: tambem retorna
  `tester_invoked=true` + `tester_result_summary` no status JSON
  (test_run_id, overall, decision do tester).
```

Use Edit tool no path `~/bevox-knowledge/20_architecture/agents/dispatcher-agent.md` pra fazer essas 3 inserções.

- [ ] **Step 2: Verificar diff**

```bash
cd ~/bevox-knowledge
git diff 20_architecture/agents/dispatcher-agent.md | head -40
```

Expected: 3 chunks adicionando documentação wave-3.

### Task 10.3: Registry entry + render

**Files:**
- Modify: `bevox-knowledge/20_architecture/agents/registry.yml`

- [ ] **Step 1: Adicionar entry alfabetico (entre `scrum-master-agent` e `vox`)**

Edita `~/bevox-knowledge/20_architecture/agents/registry.yml` adicionando antes da entry `vox:`:

```yaml
  tester-agent:
    status: ativo
    level: L1
    owner: Bernard
    model:
      primary: stdlib-python/no-model
      fallback: none
    since: 2026-04-19
    file: tester-agent.md
```

- [ ] **Step 2: Re-render registry.md**

```bash
cd ~/bevox-knowledge
./20_architecture/agents/_tools/render-registry.py
git diff --stat 20_architecture/agents/registry.md 20_architecture/agents/registry.yml
```

Expected: ambos modificados; registry.md mostra tester-agent.

- [ ] **Step 3: Verificar entry no YAML**

```bash
grep -A6 "tester-agent:" ~/bevox-knowledge/20_architecture/agents/registry.yml
```

Expected: 7 linhas (status, level, owner, model.primary, model.fallback, since, file).

### Task 10.4: Delivery tracker entry

**Files:**
- Modify: `bevox-knowledge/40_roadmap/delivery-tracker.yml`

- [ ] **Step 1: Adicionar wave em E10 (após `dispatcher-and-clarification-agents`)**

Localizar bloco do E10/dispatcher-and-clarification-agents em `~/bevox-knowledge/40_roadmap/delivery-tracker.yml`. Adicionar abaixo dele:

```yaml
      - id: tester-agent
        status: delivered
        delivered_at: 2026-04-XX  # preencher no push gate
        features:
          - "tester-agent L1 (Hub-dispatch): valida tasks em testing operacionalmente; 5 invariantes deterministicos antes de LLM check; per-AC drafter via claude -p (allowedTools=Read,Grep, Plano B Spike-5); confidence pass|fail|inconclusive com hallucination guard (sources validation)"
          - "Auto-decisao: testing→done (all AC pass) OU testing→in_progress blocked test_failed/test_inconclusive (≥1 AC fail/incon) OU exit 3 proposed_rejected (structural concern detectado)"
          - "NUNCA auto-rejeita: rejection terminal sempre via Bernard 'vox tester reject-task --commit' com categoria valida (5 fixas); zero auto-relaunch (Bernard decide)"
          - "Touch model split por modo dispatcher: foreground (--launch --foreground) → 1 touch happy path (tester auto-invocado); detached (default --launch) → 2 touches (Bernard 'vox tester check <id>' manual; auto-tester em detach fica como follow-up daemon reaper §16)"
          - "Delta minimo dispatcher: cmd_next ganha flag --no-tester + helper _invoke_tester (foreground only)"
          - "test_result isolado em dispatch_payload (shallow merge top-level): NAO toca campos autorais do scrum-master (goal, AC, files_relevant) nem do dispatcher (briefing_path, execution_*)"
          - "zero pip install (stdlib + claude CLI); zero novo backend (consume hooks F4 wave-3 + slot test_result reservado); zero novo spike (reusa stack validada wave-2)"
          - "Out of scope explicito: cron auto-poll (wave-4 PRD), daemon reaper detached, auto-merge, auto-close de spec/wave, multi-LLM ensemble, network calls externos"
        spec: 35_specs/2026-04-19-e10-tester-agent.md
```

- [ ] **Step 2: Verificar**

```bash
grep -A12 "id: tester-agent" ~/bevox-knowledge/40_roadmap/delivery-tracker.yml | head -15
```

Expected: bloco delivered listado.

### Task 10.5: Sync playbook canonical → host-local

- [ ] **Step 1: cp**

```bash
cp ~/bevox-knowledge/20_architecture/agents/tester-agent.md \
   ~/.openclaw/tester-agent/playbook.md
diff ~/bevox-knowledge/20_architecture/agents/tester-agent.md \
     ~/.openclaw/tester-agent/playbook.md && echo "tester sync OK"
```

Expected: `tester sync OK` (zero diff).

### Task 10.6: Canonical commit (single-gate)

- [ ] **Step 1: Stage + status**

```bash
cd ~/bevox-knowledge
git add \
  20_architecture/agents/tester-agent.md \
  20_architecture/agents/dispatcher-agent.md \
  20_architecture/agents/registry.yml \
  20_architecture/agents/registry.md \
  40_roadmap/delivery-tracker.yml

git status -s | grep -E "(tester|dispatcher|registry|delivery-tracker)"
```

Expected: 5 files staged.

- [ ] **Step 2: Commit**

```bash
cd ~/bevox-knowledge && git commit -m "$(cat <<'EOF'
feat(E10): tester-agent wave delivered

Wave-3 do PRD "OpenClaw Task-Orchestrated Development for Claude Code".
Entrega tester-agent L1 (Hub-dispatch) que valida tasks em testing
operacionalmente e fecha o ultimo gargalo do happy path em modo
foreground (1 touch ate done).

- 5 invariantes deterministicos antes de LLM check (status, blocked,
  log, AC, clarification escalation)
- Per-AC drafter via claude -p com allowedTools=Read,Grep restritivo
  (Plano B Spike-5; reusa stack wave-2)
- Confidence pass|fail|inconclusive com hallucination guard
  (sources validadas no contexto OU filesystem)
- Auto-decisao: testing→done | in_progress blocked test_failed |
  in_progress blocked test_inconclusive | exit 3 proposed_rejected
- NUNCA auto-rejeita: rejection terminal sempre via Bernard
  'vox tester reject-task --commit' com categoria valida
- Touch model split por modo do dispatcher: foreground 1 touch
  (auto-tester); detached default 2 touches (Bernard tester check
  manual; daemon reaper como follow-up §16)

Delta minimo dispatcher-agent: cmd_next ganha flag --no-tester +
helper _invoke_tester (foreground only).

Modulo operacional em ~/.openclaw/tester-agent/ (host-local, Python
stdlib puro, zero pip install).

Spec: 35_specs/2026-04-19-e10-tester-agent.md
Plan: ~/.openclaw/docs/superpowers/plans/2026-04-19-e10-tester-agent-plan.md

Boundary: cron wave-4 PRD, daemon reaper detached, auto-merge,
auto-close de spec/wave explicitamente fora.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
git log --oneline -3
```

Expected: commit criado + listagem mostra: novo commit, `190f456` spec, anterior wave-2 `faab1d4`.

---

## Phase 11: Push gate + memory

### Task 11.1: Show diff vs origin + gate humano

- [ ] **Step 1: Summary pré-push**

```bash
cd ~/bevox-knowledge
echo '=== commits ahead de origin/main ==='
git log --oneline origin/main..HEAD
echo ''
echo '=== git status fora do escopo ==='
git status -s | head -10
```

Expected: 2 commits ahead (spec `190f456` + wave delivered); pré-existentes não staged.

- [ ] **Step 2: Bernard decide push**

Instruções pro operador:

```
Push agora:
  cd ~/bevox-knowledge && git push origin main

Pause e revisa:
  git log --oneline origin/main..HEAD
  git show HEAD

Rollback (cuidado, só apos confirmar nada foi pushado):
  git reset --soft HEAD~1
```

**Não automatizar push.** Gate humano explícito.

### Task 11.2: Backfill `delivered_at` no tracker (após push aprovado)

- [ ] **Step 1: Substituir data real**

```bash
cd ~/bevox-knowledge
sed -i "s|delivered_at: 2026-04-XX  # preencher no push gate|delivered_at: $(date +%Y-%m-%d)|" \
    40_roadmap/delivery-tracker.yml
git add 40_roadmap/delivery-tracker.yml
git commit --amend --no-edit
git log --oneline -1
```

Expected: commit amended com data real.

### Task 11.3: Memory update

**Files:**
- Create: `~/.claude/projects/-home-you--openclaw/memory/e10_tester_agent_state.md`

- [ ] **Step 1: Write memory**

```bash
cat > ~/.claude/projects/-home-you--openclaw/memory/e10_tester_agent_state.md <<'EOF'
---
name: E10/tester-agent — execution state
description: Status wave-3 PRD orchestration — tester-agent Hub-dispatch L1, gate de validacao operacional, fecha happy path em foreground (1 touch). Delivered local 2026-04-XX.
type: project
---

## Checkpoint (2026-04-XX)

**DELIVERED localmente.** Push gate humano pendente.

- Spec canonizada: `35_specs/2026-04-19-e10-tester-agent.md` (commit `190f456`)
- Wave commit: `<SHA>` em main local (playbook + registry + tracker + dispatcher delta)
- Modulo host-local operavel via `~/.openclaw/tester-agent/cli.sh`

## Modulo host-local

- `~/.openclaw/tester-agent/` — Python stdlib, drafter via `claude -p` allowedTools=Read,Grep
- Delta dispatcher: `lib/api.py` ganha `--no-tester` + helper `_invoke_tester` (foreground only)
  - Backup: `lib/api.py.pre-tester.bak`

## Decisões travadas

- Tester eh **gate de validacao operacional**, NAO juiz de produto
- Auto-invoke condicional: foreground only (default detached preserva touch atual)
- 5 invariantes deterministicos antes de LLM (decisao #8 spec)
- Confidence binary pass|fail|inconclusive (decisao #4)
- Inconclusive NUNCA promove (decisao #2c)
- LLM-only checks no MVP; commands estructurados ficam pra follow-up
- Read+Grep allowedTools restritivo (decisao #6)
- NUNCA auto-rejeita: exit code 3 + Bernard --commit com categoria valida (5 fixas: task_malformed, spec_inconsistent, requires_re_decomposition, inexecutable, manual)
- Sem auto-relaunch (decisao #5)
- test_result isolado em dispatch_payload shallow merge (decisao #9)
- One-task-per-project respeitado (decisao #10)

## Touch model (happy path)

- Foreground (`--launch --foreground`): **1 touch** (kick off → done auto)
- Detached default (`--launch`): **2 touches** (kick + `vox tester check <id>` manual)

Auto-tester em detach mode = follow-up daemon reaper (§16 da spec).

## Smoke E2E validado (8 cenarios DoD §12.4)

1. Foreground happy → done (1 touch real claude)
2. Foreground fail-AC → in_progress blocked test_failed
3. Foreground inconclusive → in_progress blocked test_inconclusive
4. Reject-propose → Bernard reject-task --commit
5. Hallucination guard downgrade pass→inconclusive (unit test)
6. Recheck manual Bernard
7. Detached default → tester NAO auto-invocado (limitacao confirmada)
8. Detached + manual tester check → done (2 touches)

## Proximas waves PRD (fora desta spec)

- E10/cron-dispatcher (wave-4 PRD): auto-poll testing column; depende de tester estavel
- Daemon reaper pra detached mode: destrava zero-touch full em background
- `acceptance_checks` field estructurado (cmd + expected_exit) no dispatch_payload — schema-add F4 futura
- UI MC pra test_results dashboard
- Notificacao push (Telegram/email) de test failures/escalations

## Push gate

`bevox-knowledge/main` local tem 2 commits ahead (spec wave-3 + wave delivered).
Comando: `cd ~/bevox-knowledge && git push origin main`
Modulo host-local (tester-agent + dispatcher delta) nao precisa push.
EOF
```

- [ ] **Step 2: Adicionar ao MEMORY.md index**

```bash
echo '- [E10/tester-agent — execution state](e10_tester_agent_state.md) — wave-3 PRD orchestration; gate de validacao operacional, foreground 1-touch happy path; delivered 2026-04-XX' >> ~/.claude/projects/-home-you--openclaw/memory/MEMORY.md
```

- [ ] **Step 3: Confirmar memory escrita**

```bash
ls -la ~/.claude/projects/-home-you--openclaw/memory/e10_tester_agent_state.md
tail -5 ~/.claude/projects/-home-you--openclaw/memory/MEMORY.md
```

Expected: file existe + última linha do MEMORY.md menciona tester-agent.

---

## Self-review (executado durante writing)

### Spec coverage

- §1 Visão + objetivo (foreground vs detached): Phase 8 (delta dispatcher) + Phase 9 (smoke 8 cenarios) + Phase 10 (playbook §11 touch model)
- §2 Decisões travadas (10 itens):
  - #1 Premissa central (gate operacional, não juiz): playbook §Limites + prompt do checker §10.3
  - #2 Auto-invoke condicional foreground: Phase 8.2 + Phase 9.7 + 9.8
  - #3 LLM-only: Phase 4 (checker.py) — sem schema novo
  - #4 Inconclusive não promove: Phase 6 (lifecycle._aggregate) + Phase 9.4
  - #5 Sem auto-relaunch: documentado playbook §Limites #2
  - #6 Read+Grep allowedTools: Phase 4.1 (`ALLOWED_TOOLS = "Read,Grep"`)
  - #7 Nunca auto-rejeita: Phase 6 (decision proposed_rejected NÃO move kanban) + Phase 7.3 (--commit guard)
  - #8 5 invariantes auto-promote done: Phase 2 (prechecks.py com 5 funcs + run_prechecks)
  - #9 test_result isolado: Phase 6 (_build_merge_fields wrapping em "test_result")
  - #10 One-task-per-project: documentado playbook (não enforced agressivo no MVP)
- §3 Arquitetura (file structure): Phase 1.1 (dirs) + Phase 8 (dispatcher delta) + Phase 10 (canonical)
- §4 Spikes: não re-executar (base wave-2 estabelecida; documentado em README + plan header)
- §5 I/O models: Phase 1.2 (store) + Phase 6 (test_run JSON shape em _build_merge_fields)
- §6 State machine: Phase 6 (run_check + _aggregate cobre 4 paths) + Phase 9.2-9.5 cenarios
- §7 Commands surface: Phase 7.1 (api.py com 5 cmds: check, recheck, results, show, reject-task + escalations)
- §8 Flows E2E (5 happy/fail/incon/reject/manual): Phase 9 cenarios 1-6
- §9 Boundary com outros agents: Phase 10.1 playbook §Boundary
- §10 Convention auto-invoke: Phase 8.2 (`_invoke_tester` em foreground only) + Phase 10.2 (delta playbook dispatcher)
- §11 Touch model: Phase 10.1 playbook tabela
- §12 DoD: 12.1 canonical Phase 10 / 12.2 host-local Phase 1-7 / 12.3 delta dispatcher Phase 8 / 12.4 smoke 8 cenarios Phase 9 / 12.5 push gate Phase 11
- §13 Boundary outros agents: playbook Phase 10.1
- §14 Volume: playbook
- §15 Riscos: hallucination guard Phase 5; conservatismo inconclusive Phase 6; documentado playbook KPIs

### Placeholder scan

- `delivered_at: 2026-04-XX`: intencional; gate humano Phase 11.2 backfill
- Nenhum TBD/TODO/"implement later" técnico
- Cenário 4 (proposed_rejected) usa fallback manual reject-task se drafter não detectar structural — explicitamente documentado como "ou-ou", não placeholder

### Type consistency

- `decision` values: `done | in_progress_test_failed | in_progress_test_inconclusive | proposed_rejected | in_progress_test_failed_precheck` consistent Phase 6 (lifecycle) + Phase 7 (api.py results filter) + Phase 9 (smoke asserts) + Phase 10 (playbook + tracker)
- `effective_status` values: `pass | fail | inconclusive` consistent Phase 4 (checker) + 5 (safety) + 6 (lifecycle._aggregate)
- `effective_structural_concern` values: 4 categorias VALID_STRUCTURAL_CONCERNS (`task_malformed, spec_inconsistent, requires_re_decomposition, inexecutable`) consistent Phase 5 (safety) + Phase 6 (`_write_escalation_md` suggested category) + Phase 7 (VALID_REJECT_CATEGORIES inclui as 4 + `manual`)
- `test_result` keys: `last_test_run_id, last_test_run_path, last_test_overall, last_test_decision, last_test_finished_at, test_run_count, tester_actor` consistent Phase 6 + Phase 9 asserts + Phase 10 playbook
- Exit codes `0,1,2,3` consistent Phase 7 (api.py) + Phase 9 cenarios + Phase 10 playbook + README
- `--commit` guard: Phase 7.4 sanity test + Phase 9.5 sanity + Phase 10 playbook §Approvals

Nenhum drift identificado.

---

## Notas operacionais

- **Push gate humano (Phase 11.1):** Bernard decide timing.
- **Módulo host-local:** `~/.openclaw/tester-agent/` é host-local; não há commits pra código Python. Mesmo pattern wave-1+2.
- **Delta dispatcher:** `~/.openclaw/dispatcher-agent/lib/api.py` modificado in-place; backup `.pre-tester.bak` preservado pra rollback.
- **Playbook sync:** canonical em bevox-knowledge é SoT; cópia host-local via `cp` explícito Phase 10.5. Sem auto-sync.
- **Smoke E2E (Phase 9)** toca Claude Code real (cenarios 1, 2, 3, 6, 8) — consome tokens (claude-haiku-4-5 ~$0.001-0.005 per invocação). Total estimado: ~$0.03-0.05 pra 8 cenarios. Baseline kanban restaurado ao final.
- **Cenário 4 (proposed_rejected):** drafter pode OR pode não detectar structural concern em fixture sintética. Fallback Phase 9.5: reject-task --commit manual valida o gate humano. Em produção, structural detection vem do drafter quando AC contradiz spec_refs.
- **Limitação detached MVP:** documentada em playbook canonical (Phase 10.1 + 10.2), README host-local (Phase 1.1), spec §10.2 + §15. Follow-up daemon reaper (§16 spec) destrava auto-tester em detach mas fica fora desta wave.
- **Foreground bloqueia terminal:** trade-off documentado nas tabelas touch model (playbook + spec §11). Bernard escolhe por invocação.
