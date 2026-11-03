# E10 OH Wave-8 Fixes Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Fix 3 bugs discovered by wave-7 self-test (dispatcher cgroup-kill, empty-log false-success, scrum-master blocked_by_labels rejection + missing set-blocked-by CLI call), re-run wave-7 to PASS, close OH block.

**Architecture:** 5 phases. Phase 1+2 swap runner.py's Popen/setsid detach for `systemd-run --user` transient service (subprocess lifecycle independent of cron-dispatcher.service cgroup) + replace log-parser exit-code with `systemctl show` query. Phase 3 scrum-master materializer TDD (allowed_keys + set-blocked-by CLI call). Phase 4 rewrite synthetic spec AC-only. Phase 5 Bernard re-runs wave-7 via Telegram dogfood; I observe + report PASS/FAIL. Closure tasks (release note + tracker + push) only if PASS.

**Tech Stack:** Python 3 stdlib (subprocess, unittest.mock), systemd-run user instance, bash. Zero new pip deps.

**Spec canônica:** `bevox-knowledge/35_specs/2026-04-22-e10-oh-wave-8-fixes.md` (commit 9e39bc2)
**ADR governante:** ADR-009
**Bloco:** Operational Loop Hardening 2026-04-21 (wave-8 de 8, FINAL)
**Branch draft:** `draft/adr-009-clarification-daemon`
**Evidence wave-7 FAIL:** `~/.openclaw/self-test-evidence/evidence/fail-2026-04-22T13-50-06Z/`

---

## File Structure

**Runtime (NÃO git-tracked):**
- `~/.openclaw/dispatcher-agent/lib/runner.py` — Phase 1+2 (launch_detached + reap_finished)
- `~/.openclaw/dispatcher-agent/lib/runner.py.pre-wave8.bak` — rollback
- `~/.openclaw/scrum-master-agent/lib/materializer.py` — Phase 3 (allowed_keys + set-blocked-by call)
- `~/.openclaw/scrum-master-agent/lib/materializer.py.pre-wave8.bak` — rollback
- `~/.openclaw/scrum-master-agent/tests/test_materializer_wave8.py` — Phase 3 (4 tests novos, arquivo próprio pra não poluir test_materializer_v2.py)
- `~/.openclaw/self-test-evidence/specs/2026-04-22-self-test-sidecar.md` — Phase 4 (AC-only rewrite)
- `~/.openclaw/self-test-evidence/specs/2026-04-22-self-test-sidecar.md.pre-wave8.bak` — rollback

**Canonico (bevox-knowledge, draft branch, PÓS-PASS):**
- `50_releases/2026-04-22-operational-loop-hardening-closed.md` — NEW
- `40_roadmap/delivery-tracker.yml` — MODIFY (add wave-8 + OH-closure entries)
- `40_roadmap/2026-04-09-openclaw-company-os-roadmap.md` — MODIFY (OH CLOSED section)
- `35_specs/2026-04-22-e10-oh-wave-8-fixes.md` — MODIFY (status draft → delivered)
- `35_specs/2026-04-21-e10-scrum-master-self-test.md` — MODIFY (status delivered)

**Git push PÓS-PASS (explícito Bernard go-ahead):**
- `bevox-knowledge/draft/adr-009-clarification-daemon` → `main`
- `knowledge-sync/feat/e10-clarification-commands-plugin` → `main`
- `mission-control/feat/e10-payload-completeness-gate` → `main`
- `mission-control/feat/e5-f4-kanban-blocked-by-schema` → `main`

---

## Phase 0 — Cleanup state

### Task 0.1: Archive residual + reset artifacts

**Files:**
- Archive: T-0015, T-0016 em kanban-tasks `test-project`
- Move: `~/.openclaw/scrum-master-agent/proposals/20260422T135631Z-2026-04-22-self-test-sidecar.json` → `/tmp/`
- Remove: `~/.openclaw/self-test-evidence/artifacts/_a-*.md` (manual test leftover)

- [ ] **Step 1: Archive tasks T-0015 + T-0016 no kanban**

```bash
for tid in T-0015 T-0016; do
  ~/.openclaw/kanban-tasks/cli.sh task archive "$tid" \
    --reason "wave-7 self-test FAIL — archived pre-wave-8 cleanup" \
    --actor self-test-cleanup --json | python3 -m json.tool | head -5
done
~/.openclaw/kanban-tasks/cli.sh task list --project test-project --json | python3 -c "import sys,json; d=json.load(sys.stdin); print('active tasks:', len([t for t in d['tasks'] if t.get('status') != 'archived']))"
```

Expected: ambas archived; 0 active tasks em test-project.

- [ ] **Step 2: Move proposal residual**

```bash
mv ~/.openclaw/scrum-master-agent/proposals/20260422T135631Z-2026-04-22-self-test-sidecar.json /tmp/wave7-repro-proposal.json 2>/dev/null || echo "(já movido)"
ls ~/.openclaw/scrum-master-agent/proposals/ | grep self-test && echo "ALERT: ainda existe proposal self-test" || echo "OK: proposals/ limpo de self-test"
```

Expected: "OK: proposals/ limpo de self-test".

- [ ] **Step 3: Limpa artifacts/**

```bash
rm -f ~/.openclaw/self-test-evidence/artifacts/_a-*.md
rm -f ~/.openclaw/self-test-evidence/artifacts/_b-*.md
ls ~/.openclaw/self-test-evidence/artifacts/
```

Expected: dir vazio.

- [ ] **Step 4: Nenhum commit** (runtime cleanup).

---

## Phase 1 — Fix Bug #1 (runner systemd-run)

### Task 1.1: Backup runner.py + audit shape

**Files:**
- Backup: `~/.openclaw/dispatcher-agent/lib/runner.py.pre-wave8.bak`

- [ ] **Step 1: Backup**

```bash
cp ~/.openclaw/dispatcher-agent/lib/runner.py ~/.openclaw/dispatcher-agent/lib/runner.py.pre-wave8.bak
ls -la ~/.openclaw/dispatcher-agent/lib/runner.py.pre-wave8.bak
```

Expected: backup criado, mtime agora.

- [ ] **Step 2: Confirma shape atual do launch_detached**

```bash
grep -n 'def launch_detached\|def reap_finished\|def _parse_exit_code_from_log\|def is_session_alive' ~/.openclaw/dispatcher-agent/lib/runner.py
```

Expected: 4 funções listadas nas linhas ~37, 111, 142, 172.

- [ ] **Step 3: Nenhum commit**.

### Task 1.2: Modify `launch_detached` → systemd-run transient service

**Files:**
- Modify: `~/.openclaw/dispatcher-agent/lib/runner.py:37-63`

- [ ] **Step 1: Substituir `launch_detached`**

Substituir o bloco inteiro da função `launch_detached` (linhas 37-63) por:

```python
def launch_detached(
    task_id: str, briefing_path: Path, allowed_tools: str,
    model: Optional[str] = None,
) -> Dict[str, Any]:
    """Spawn `claude -p` como transient systemd-run user service.

    Wave-8 fix: evita cgroup-kill da cron-dispatcher.service quando
    cron-tick --once exita. Transient service vive no cgroup próprio
    user-level; `--collect` remove unit auto ao terminar.
    """
    session_id = _build_session_id(task_id)
    log_path = store.execution_log_path(task_id)
    log_path.parent.mkdir(parents=True, exist_ok=True)

    unit_name = f"claude-task-{task_id}-{session_id.split('-', 1)[1]}.service"
    briefing_content = briefing_path.read_text(encoding="utf-8")

    sd_cmd = [
        "systemd-run", "--user",
        f"--unit={unit_name}",
        "--collect",
        "--property=Type=exec",
        f"--property=StandardOutput=truncate:{log_path}",
        "--property=StandardError=inherit",
        "--",
        "claude", "-p", briefing_content,
        "--allowedTools", allowed_tools,
    ]
    if model:
        sd_cmd += ["--model", model]

    try:
        result = subprocess.run(
            sd_cmd, capture_output=True, text=True, timeout=15, check=False,
        )
    except subprocess.TimeoutExpired:
        raise RunnerError(
            "SYSTEMD_RUN_TIMEOUT",
            f"systemd-run --user excedeu 15s pra spawnar claude-task {task_id}",
        )
    if result.returncode != 0:
        raise RunnerError(
            "SYSTEMD_RUN_FAILED",
            f"systemd-run exit={result.returncode}: {result.stderr.strip()[:300]}",
        )

    status = {
        "task_id": task_id, "session_id": session_id,
        "unit_name": unit_name, "pid": None,
        "run_mode": "detach", "started_at": store.now_iso(),
        "briefing_path": str(briefing_path), "log_path": str(log_path),
        "finished_at": None, "exit_code": None,
        "model": model or "default",
    }
    store.write_execution_status(task_id, status)
    return status
```

**Nota:** remove `pid` como source of truth (systemd gerencia). Adiciona `unit_name` ao status.json pra reap query.

- [ ] **Step 2: Verificar py_compile**

```bash
python3 -m py_compile ~/.openclaw/dispatcher-agent/lib/runner.py && echo "OK"
```

Expected: "OK" sem erros de sintaxe.

- [ ] **Step 3: Nenhum commit ainda** (Phase 2 depende, commit conjunto).

### Task 1.3: Smoke manual — task single dispatch

**Files:** (nenhum modificado; só verificação runtime)

- [ ] **Step 1: Criar task de teste + dispatch foreground**

```bash
# Criar 1 task em test-project com payload mínimo
~/.openclaw/kanban-tasks/cli.sh task add "wave-8 smoke task" \
  --sprint next --project test-project \
  --epic E10 --wave E10/OH/wave-8-smoke \
  --payload '{"spec_ref":"~/.openclaw/docs/superpowers/plans/2026-04-22-e10-oh-wave-8-fixes-plan.md","acceptance_criteria":["smoke task"],"goal":"smoke only","plan_ref":"none","plan_anchor":"smoke","files_relevant":[]}' \
  --json | python3 -c "import sys,json; d=json.load(sys.stdin); print('task:', d['task']['id'])"
```

Expected: task criada, ID retornado (ex: T-0017).

- [ ] **Step 2: Capturar ID + mover para ready + dispatch detached via runner direto**

```bash
TID=$(~/.openclaw/kanban-tasks/cli.sh task list --project test-project --json | python3 -c "import sys,json; d=json.load(sys.stdin); print([t['id'] for t in d['tasks'] if t.get('status')=='backlog' and not t.get('archived_at')][-1])")
echo "smoke TID=$TID"
~/.openclaw/kanban-tasks/cli.sh task move "$TID" ready --actor smoke-wave8
```

Expected: task move para ready OK.

- [ ] **Step 3: Rodar cron-tick manualmente + verificar transient unit**

```bash
~/.openclaw/dispatcher-agent/cli.sh cron-tick --once 2>&1 | tail -5
sleep 2
systemctl --user list-units 'claude-task-*' --no-pager 2>&1 | head -5
```

Expected: cron-tick reporta `dispatched: 1`; `systemctl list-units` mostra unit `claude-task-T-NNNN-*.service` em estado `active` ou recém finalizado.

- [ ] **Step 4: Commit (consolidado Phase 1+2)** será feito em Task 2.3.

### Task 1.4: Validar log populado

**Files:** (verificação runtime)

- [ ] **Step 1: Aguardar + verificar log não-vazio**

```bash
TID=$(ls -t ~/.openclaw/dispatcher-agent/executions/*.log | head -1 | sed 's|.*/||' | sed 's|\.log$||')
echo "TID=$TID"
# Aguardar até 120s pro claude terminar (poll)
for i in $(seq 1 24); do
  sz=$(stat -c %s ~/.openclaw/dispatcher-agent/executions/${TID}.log 2>/dev/null || echo 0)
  echo "  [${i}] log_size=${sz}B"
  if [ "$sz" -gt 100 ]; then break; fi
  sleep 5
done
head -20 ~/.openclaw/dispatcher-agent/executions/${TID}.log
```

Expected: log > 100 bytes com output real do claude (algo como "Smoke task completed" ou similar).

**Critério crítico:** log **NÃO 0 bytes**. Se 0 bytes, Bug #1 NÃO resolvido — revisar Task 1.2.

- [ ] **Step 2: Nenhum commit** (Phase 2 valida reap).

---

## Phase 2 — Fix Bug #2 (reap via systemd query)

### Task 2.1: Substituir `reap_finished` para systemctl show

**Files:**
- Modify: `~/.openclaw/dispatcher-agent/lib/runner.py:142-169`

- [ ] **Step 1: Substituir `reap_finished`**

Substituir o bloco inteiro de `reap_finished` (linhas 142-169) por:

```python
def reap_finished(task_id: str) -> Optional[Dict[str, Any]]:
    """Checa se transient service terminou (wave-8 via systemctl show).

    Fluxo:
      1. Le status.json; se ja finished → return
      2. Query `systemctl --user show UNIT --property=ActiveState,ExecMainStatus`
      3. ActiveState in {"activating","active","deactivating"} → still running
      4. ActiveState == "inactive" (ou "failed") → marca finished +
         exit_code = ExecMainStatus (systemd canonical)
      5. Unit nao-existente → treat como completed (--collect removeu)
         com exit_code 0 (best-effort; log inspecionavel manualmente)
    """
    status = store.read_execution_status(task_id)
    if status is None or status.get("finished_at") is not None:
        return status
    unit_name = status.get("unit_name")
    if not unit_name:
        # Status pre-wave-8 sem unit_name (task criada antes do upgrade)
        return status
    try:
        result = subprocess.run(
            ["systemctl", "--user", "show", unit_name,
             "--property=ActiveState,ExecMainStatus,Result"],
            capture_output=True, text=True, timeout=5, check=False,
        )
    except subprocess.TimeoutExpired:
        return status
    props: Dict[str, str] = {}
    for line in result.stdout.splitlines():
        if "=" in line:
            k, _, v = line.partition("=")
            props[k] = v
    active_state = props.get("ActiveState", "")
    if active_state in ("activating", "active", "deactivating", "reloading"):
        return status
    # Finished state: inactive | failed | gone (post --collect cleanup)
    exit_code_s = props.get("ExecMainStatus", "")
    try:
        exit_code = int(exit_code_s) if exit_code_s else -1
    except ValueError:
        exit_code = -1
    status["finished_at"] = store.now_iso()
    status["exit_code"] = exit_code
    status["systemd_result"] = props.get("Result", "")
    status["unit_final_state"] = active_state or "gone"
    store.write_execution_status(task_id, status)
    return status
```

- [ ] **Step 2: py_compile check**

```bash
python3 -m py_compile ~/.openclaw/dispatcher-agent/lib/runner.py && echo "OK"
```

Expected: "OK".

- [ ] **Step 3: Nenhum commit** (Task 2.2 remove dead code).

### Task 2.2: Remover `_parse_exit_code_from_log` (dead code)

**Files:**
- Modify: `~/.openclaw/dispatcher-agent/lib/runner.py:172-184` (DELETE)

- [ ] **Step 1: Remover função**

Abrir `~/.openclaw/dispatcher-agent/lib/runner.py`, deletar linhas 172-184 inteiras (função `_parse_exit_code_from_log`).

- [ ] **Step 2: Verificar nenhum caller residual**

```bash
grep -n '_parse_exit_code_from_log' ~/.openclaw/dispatcher-agent/lib/runner.py
```

Expected: sem resultados (função removida + ninguém a chama mais dentro de runner.py).

```bash
grep -rn '_parse_exit_code_from_log' ~/.openclaw/dispatcher-agent/lib/ | grep -v .pyc | grep -v .bak
```

Expected: sem resultados.

- [ ] **Step 3: py_compile + run existing smoke_e2e.sh (se aplicável)**

```bash
python3 -m py_compile ~/.openclaw/dispatcher-agent/lib/runner.py && echo "OK compile"
```

Expected: "OK compile".

- [ ] **Step 4: Nenhum commit** (Task 2.3 valida + commita).

### Task 2.3: Smoke + commit consolidado Phase 1+2

**Files:** (validation + commit)

- [ ] **Step 1: Aguardar smoke task finalizar + reap**

```bash
# Pick smoke task ID
TID=$(ls -t ~/.openclaw/dispatcher-agent/executions/*.status.json | head -1 | sed 's|.*/||' | sed 's|\.status\.json$||')
echo "smoke TID=$TID"
# Verify status antes de reap
cat ~/.openclaw/dispatcher-agent/executions/${TID}.status.json | python3 -m json.tool | head -20
# Aguardar claude terminar (systemctl show mostra inactive)
for i in $(seq 1 24); do
  state=$(systemctl --user show claude-task-${TID}-* --property=ActiveState 2>/dev/null | head -1 | cut -d= -f2)
  echo "  [${i}] ActiveState=${state:-gone}"
  if [ "$state" = "inactive" ] || [ -z "$state" ]; then break; fi
  sleep 5
done
```

Expected: state → inactive em <120s (claude terminou).

- [ ] **Step 2: Invocar reap via CLI + verificar status.json atualizado**

```bash
~/.openclaw/dispatcher-agent/cli.sh reap "$TID" --json 2>&1 | python3 -m json.tool | head -30
cat ~/.openclaw/dispatcher-agent/executions/${TID}.status.json | python3 -m json.tool | grep -E '(finished_at|exit_code|systemd_result|unit_gc)'
```

Expected: `finished_at` populado; `exit_code` = 0 (smoke task succeeded) ou outro número real (não 0 mascarado).

- [ ] **Step 3: Confirmar artefato criado (log > 0 bytes + content)**

```bash
LOG=~/.openclaw/dispatcher-agent/executions/${TID}.log
ls -la "$LOG"
head -30 "$LOG"
```

Expected: log > 0 bytes; content real.

- [ ] **Step 4: Cleanup smoke task (archive)**

```bash
~/.openclaw/kanban-tasks/cli.sh task archive "$TID" \
  --reason "wave-8 smoke task cleanup" \
  --actor wave-8 --json >/dev/null && echo "smoke task $TID archived"
```

Expected: archived.

- [ ] **Step 5: Nenhum commit ainda** (Phase 3 consolidará commit único; runtime não-git, mas convenção).

---

## Phase 3 — Fix Bug #3a + #3b (scrum-master materializer)

### Task 3.1: Backup + add `blocked_by_labels` ao ALLOWED set

**Files:**
- Backup: `~/.openclaw/scrum-master-agent/lib/materializer.py.pre-wave8.bak`
- Modify: `~/.openclaw/scrum-master-agent/lib/materializer.py:47-50`

- [ ] **Step 1: Backup**

```bash
cp ~/.openclaw/scrum-master-agent/lib/materializer.py ~/.openclaw/scrum-master-agent/lib/materializer.py.pre-wave8.bak
ls -la ~/.openclaw/scrum-master-agent/lib/materializer.py.pre-wave8.bak
```

Expected: backup criado.

- [ ] **Step 2: Editar `_DISPATCH_PAYLOAD_ALLOWED`**

Em `~/.openclaw/scrum-master-agent/lib/materializer.py`, localizar linhas 47-50:

```python
_DISPATCH_PAYLOAD_ALLOWED = _DISPATCH_PAYLOAD_REQUIRED | {
    "acceptance_criteria", "out_of_scope", "files_relevant",
    "guardrails", "depends_on",
}
```

Substituir por:

```python
_DISPATCH_PAYLOAD_ALLOWED = _DISPATCH_PAYLOAD_REQUIRED | {
    "acceptance_criteria", "out_of_scope", "files_relevant",
    "guardrails", "depends_on", "blocked_by_labels",
}
```

- [ ] **Step 3: Verificar**

```bash
grep -A 4 '_DISPATCH_PAYLOAD_ALLOWED = _DISPATCH_PAYLOAD_REQUIRED' ~/.openclaw/scrum-master-agent/lib/materializer.py | head -5
```

Expected: shows `blocked_by_labels` na última linha do set.

- [ ] **Step 4: py_compile + rodar suite wave-6 existente (sanity)**

```bash
cd ~/.openclaw/scrum-master-agent && python3 -m py_compile lib/materializer.py && echo "OK compile"
cd ~/.openclaw/scrum-master-agent && python3 -m unittest tests.test_materializer_v2 -v 2>&1 | tail -15
```

Expected: compile OK; test suite continua passando (~6-8 tests em test_materializer_v2).

### Task 3.2: Write failing test — `_materialize_one` calls `task set-blocked-by`

**Files:**
- Create: `~/.openclaw/scrum-master-agent/tests/test_materializer_wave8.py`

- [ ] **Step 1: Criar arquivo de teste novo**

Criar `~/.openclaw/scrum-master-agent/tests/test_materializer_wave8.py` com conteúdo:

```python
"""Wave-8 fixes for materializer: Bug #3a (allowed_keys) + #3b (set-blocked-by CLI call)."""
import importlib
import json
import unittest
from unittest.mock import patch


def _reload_mat():
    from lib import materializer
    importlib.reload(materializer)
    return materializer


WAVE8_PROPOSAL_FIXTURE = {
    "schema_version": 2,
    "proposal_id": "wave-8-test-proposal",
    "dependency_mode": "hybrid",
    "target_sprint": "current",
    "computed_deps": {
        "Task 1.1": [],
        "Task 2.1": ["Task 1.1"],
    },
    "tasks": [
        {
            "provisional_id": "prov-1", "label": "Task 1.1",
            "title": "A", "project": "test-project", "epic_id": "E10",
            "wave_ref": "E10/OH/wave-8-fixture/Phase-1",
            "dispatch_payload": {
                "spec_refs": ["x.md"], "acceptance_criteria": ["AC1"],
                "goal": "create A", "plan_ref": "p.md", "plan_anchor": "a",
                "blocked_by_labels": [],
            },
            "description": "",
        },
        {
            "provisional_id": "prov-2", "label": "Task 2.1",
            "title": "B", "project": "test-project", "epic_id": "E10",
            "wave_ref": "E10/OH/wave-8-fixture/Phase-2",
            "dispatch_payload": {
                "spec_refs": ["x.md"], "acceptance_criteria": ["AC2"],
                "goal": "create B", "plan_ref": "p.md", "plan_anchor": "a",
                "blocked_by_labels": ["Task 1.1"],
            },
            "description": "",
        },
    ],
}


class TestWave8AllowedKeys(unittest.TestCase):
    """Bug #3a: _DISPATCH_PAYLOAD_ALLOWED inclui blocked_by_labels."""

    def test_blocked_by_labels_in_allowed_set(self):
        materializer = _reload_mat()
        self.assertIn("blocked_by_labels", materializer._DISPATCH_PAYLOAD_ALLOWED)

    def test_materialize_accepts_blocked_by_labels(self):
        """Sanity: proposal com blocked_by_labels nao raise INVALID_PAYLOAD."""
        materializer = _reload_mat()
        calls = []

        def fake_run_kanban(args, actor=None):
            calls.append(tuple(args))
            if args[0] == "task" and args[1] == "add":
                idx = sum(1 for c in calls if c[:2] == ("task", "add"))
                return {"ok": True, "task": {"id": f"T-99{idx:02d}"}}
            return {"ok": True}

        with patch.object(materializer, "_run_kanban", side_effect=fake_run_kanban):
            result = materializer.materialize_proposal(
                WAVE8_PROPOSAL_FIXTURE, target_sprint="current",
                make_ready=False, actor="test-wave8",
            )

        self.assertEqual(len(result), 2)
        self.assertEqual(result[0]["task_id"], "T-9901")
        self.assertEqual(result[1]["task_id"], "T-9902")
        self.assertEqual(result[1]["preds"], ["T-9901"])


class TestWave8SetBlockedByCall(unittest.TestCase):
    """Bug #3b: materializer chama `task set-blocked-by` quando preds nao-vazio."""

    def test_set_blocked_by_called_for_task_with_preds(self):
        materializer = _reload_mat()
        calls = []

        def fake_run_kanban(args, actor=None):
            calls.append(tuple(args))
            if args[0] == "task" and args[1] == "add":
                idx = sum(1 for c in calls if c[:2] == ("task", "add"))
                return {"ok": True, "task": {"id": f"T-55{idx:02d}"}}
            return {"ok": True}

        with patch.object(materializer, "_run_kanban", side_effect=fake_run_kanban):
            materializer.materialize_proposal(
                WAVE8_PROPOSAL_FIXTURE, target_sprint="current",
                make_ready=False, actor="test-wave8",
            )

        set_blocked_by_calls = [
            c for c in calls
            if len(c) >= 2 and c[0] == "task" and c[1] == "set-blocked-by"
        ]
        # Task 1.1 (preds vazios) -> 0 calls; Task 2.1 (preds=['Task 1.1']) -> 1 call
        self.assertEqual(len(set_blocked_by_calls), 1,
                         f"esperava 1 call set-blocked-by, calls={calls}")
        call = set_blocked_by_calls[0]
        self.assertEqual(call[2], "T-5502",
                         f"set-blocked-by deve ser no Task 2.1 (T-5502), call={call}")
        # Format esperado: ("task", "set-blocked-by", task_id, "--preds", *preds)
        preds_start = list(call).index("--preds") + 1
        self.assertEqual(call[preds_start:], ("T-5501",),
                         f"--preds deve apontar pra T-5501, call={call}")

    def test_set_blocked_by_NOT_called_when_preds_empty(self):
        """Task 1.1 (sem preds) nao deve disparar set-blocked-by call."""
        materializer = _reload_mat()
        proposal_single = {
            "schema_version": 2,
            "proposal_id": "single",
            "dependency_mode": "hybrid",
            "target_sprint": "current",
            "computed_deps": {"Task 1.1": []},
            "tasks": [
                {
                    "provisional_id": "prov-1", "label": "Task 1.1",
                    "title": "Solo", "project": "test-project", "epic_id": "E10",
                    "wave_ref": "E10/OH/solo/Phase-1",
                    "dispatch_payload": {
                        "spec_refs": ["x.md"], "acceptance_criteria": ["AC"],
                        "goal": "g", "plan_ref": "p", "plan_anchor": "a",
                        "blocked_by_labels": [],
                    },
                    "description": "",
                },
            ],
        }
        calls = []

        def fake_run_kanban(args, actor=None):
            calls.append(tuple(args))
            if args[0] == "task" and args[1] == "add":
                return {"ok": True, "task": {"id": "T-7701"}}
            return {"ok": True}

        with patch.object(materializer, "_run_kanban", side_effect=fake_run_kanban):
            materializer.materialize_proposal(
                proposal_single, target_sprint="current",
                make_ready=False, actor="test-wave8",
            )

        set_blocked_by_calls = [
            c for c in calls
            if len(c) >= 2 and c[0] == "task" and c[1] == "set-blocked-by"
        ]
        self.assertEqual(len(set_blocked_by_calls), 0,
                         f"0 calls set-blocked-by pra task sem preds, calls={calls}")


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Rodar testes — TestWave8AllowedKeys deve PASSAR (fix já aplicado Task 3.1), TestWave8SetBlockedByCall deve FALHAR**

```bash
cd ~/.openclaw/scrum-master-agent && python3 -m unittest tests.test_materializer_wave8 -v 2>&1 | tail -25
```

Expected: `test_blocked_by_labels_in_allowed_set` PASSA. `test_materialize_accepts_blocked_by_labels` PASSA. `test_set_blocked_by_called_for_task_with_preds` **FALHA** (assertEqual len == 1 fails; 0 calls set-blocked-by). `test_set_blocked_by_NOT_called_when_preds_empty` PASSA (trivialmente — 0 calls quando não há implementação).

Esta é a falha intencional TDD que Task 3.3 vai passar.

### Task 3.3: Implementar `task set-blocked-by` CLI call em `_materialize_one`

**Files:**
- Modify: `~/.openclaw/scrum-master-agent/lib/materializer.py:449-465`

- [ ] **Step 1: Localizar bloco atual**

Linhas ~449-465 da função `_materialize_one`:

```python
        # Resolve blocked_by_labels -> task_ids reais
        resolved_blocked_by = [
            label_to_real[pl] for pl in pred_labels if pl in label_to_real
        ]
        full_dp["blocked_by"] = resolved_blocked_by

        # Legacy depends_on resolution preserved
        if isinstance(full_dp.get("depends_on"), list):
            full_dp["depends_on"] = [
                prov_to_real.get(d, d) for d in full_dp["depends_on"]
            ]

        _run_kanban(
            ["task", "set-dispatch-payload", real_id,
             "--payload", json.dumps(full_dp, ensure_ascii=False)],
            actor=actor,
        )
```

- [ ] **Step 2: Inserir CLI call `task set-blocked-by` logo após `full_dp["blocked_by"] = resolved_blocked_by`**

Substituir o bloco por:

```python
        # Resolve blocked_by_labels -> task_ids reais
        resolved_blocked_by = [
            label_to_real[pl] for pl in pred_labels if pl in label_to_real
        ]
        full_dp["blocked_by"] = resolved_blocked_by

        # Wave-8 fix: popula wave-5 task-record blocked_by via CLI
        # (source of truth pra gate de move-to-ready + auto-release hooks)
        if resolved_blocked_by:
            _run_kanban(
                ["task", "set-blocked-by", real_id,
                 "--preds", *resolved_blocked_by],
                actor=actor,
            )

        # Legacy depends_on resolution preserved
        if isinstance(full_dp.get("depends_on"), list):
            full_dp["depends_on"] = [
                prov_to_real.get(d, d) for d in full_dp["depends_on"]
            ]

        _run_kanban(
            ["task", "set-dispatch-payload", real_id,
             "--payload", json.dumps(full_dp, ensure_ascii=False)],
            actor=actor,
        )
```

- [ ] **Step 3: py_compile**

```bash
python3 -m py_compile ~/.openclaw/scrum-master-agent/lib/materializer.py && echo "OK"
```

Expected: OK.

- [ ] **Step 4: Rodar testes wave-8 — todos devem passar**

```bash
cd ~/.openclaw/scrum-master-agent && python3 -m unittest tests.test_materializer_wave8 -v 2>&1 | tail -15
```

Expected: **4/4 tests PASS**.

### Task 3.4: Run full test suite + commit

**Files:** (validation + commit)

- [ ] **Step 1: Full scrum-master test suite**

```bash
cd ~/.openclaw/scrum-master-agent && python3 -m unittest discover tests -v 2>&1 | tail -10
```

Expected: `Ran N tests in Ms` com `OK`. Total esperado: ~38 (34 existing wave-6 + 4 wave-8 novos).

- [ ] **Step 2: Commit (scrum-master é runtime-only, não git-tracked; "commit" = apenas confirmação nenhum rollback necessário)**

```bash
# Verifica estado final (backup + novo arquivo + modificações):
ls -la ~/.openclaw/scrum-master-agent/lib/materializer.py.pre-wave8.bak
ls -la ~/.openclaw/scrum-master-agent/tests/test_materializer_wave8.py
echo ""
grep -c 'set-blocked-by' ~/.openclaw/scrum-master-agent/lib/materializer.py
grep -c 'blocked_by_labels' ~/.openclaw/scrum-master-agent/lib/materializer.py
```

Expected: backup existe; novo test file existe; pelo menos 1 ocorrência de `set-blocked-by` em materializer.py; pelo menos 2 ocorrências de `blocked_by_labels`.

- [ ] **Step 3: Nenhum commit git** (scrum-master runtime NÃO git-tracked).

---

## Phase 4 — Rewrite synthetic spec AC-only

### Task 4.1: Backup + rewrite spec sem bash blocks

**Files:**
- Backup: `~/.openclaw/self-test-evidence/specs/2026-04-22-self-test-sidecar.md.pre-wave8.bak`
- Modify: `~/.openclaw/self-test-evidence/specs/2026-04-22-self-test-sidecar.md`

- [ ] **Step 1: Backup spec atual**

```bash
cp ~/.openclaw/self-test-evidence/specs/2026-04-22-self-test-sidecar.md ~/.openclaw/self-test-evidence/specs/2026-04-22-self-test-sidecar.md.pre-wave8.bak
ls -la ~/.openclaw/self-test-evidence/specs/2026-04-22-self-test-sidecar.md.pre-wave8.bak
```

Expected: backup criado.

- [ ] **Step 2: Substituir spec inteira por versão AC-only**

Escrever conteúdo completo no arquivo `~/.openclaw/self-test-evidence/specs/2026-04-22-self-test-sidecar.md`:

```markdown
# Self-Test Evidence Sidecar Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Exercitar end-to-end o bloco OH (scrum-master-v2 → kanban gate+blocked_by → dispatcher → clarification-agent → tester) criando 2 arquivos evidenciais em `~/.openclaw/self-test-evidence/artifacts/` com dependência explícita entre eles.

**Architecture:** 2 tasks atômicas em 2 phases. Task 1.1 cria arquivo A com timestamp ISO. Task 2.1 (`**Depends:** Task 1.1`) cria arquivo B contendo conteúdo de A + linha `depends_resolved=true`. Exercita: scrum-master-v2 popula blocked_by via override; wave-4 gate aceita payload com spec_ref + AC; wave-5 mantém B blocked até A done + auto-release após A done; tester valida AC e transita done.

**Tech Stack:** Claude executor escolhe tools (Write direto é mais provável; Bash via tools permitidos também OK).

**Epico:** E10/OH/wave-7-self-test

**Project:** test-project

**Specs:** `~/.openclaw/self-test-evidence/specs/2026-04-22-self-test-sidecar.md`, `bevox-knowledge/20_architecture/agents/dispatcher-agent.md`

---

## File Structure

**Arquivos a criar:**
- `~/.openclaw/self-test-evidence/artifacts/_a-<timestamp>.md` — evidência task 1.1
- `~/.openclaw/self-test-evidence/artifacts/_b-<timestamp>.md` — evidência task 2.1 (depende de _a)

**Formato timestamp:** ISO 8601 UTC com Z (ex: `2026-04-22T12:00:00Z`).

---

## Phase 1: Evidence sidecar A

### Task 1.1: Criar arquivo A com timestamp

**Files:**
- Create: `~/.openclaw/self-test-evidence/artifacts/_a-<timestamp>.md`

- [ ] **Step 1: Criar arquivo A em `~/.openclaw/self-test-evidence/artifacts/`**

Criar arquivo no path `~/.openclaw/self-test-evidence/artifacts/_a-<TIMESTAMP>.md` onde `<TIMESTAMP>` é a hora UTC atual formatada ISO 8601 com Z (exemplo: `2026-04-22T13:45:00Z`). Conteúdo do arquivo:

```
# Self-test evidence A

timestamp=<TIMESTAMP>
source_task=Task 1.1 Self-Test Sidecar
```

Substituir `<TIMESTAMP>` pela hora UTC real no momento da execução, no formato ISO 8601 com Z (ex: `2026-04-22T13:45:00Z`).

Expected: 1 arquivo criado tipo `_a-2026-04-22T13:45:00Z.md` contendo header, linha `timestamp=<iso>` e linha `source_task=Task 1.1 Self-Test Sidecar`.

## Phase 2: Evidence sidecar B (herda A)

### Task 2.1: Criar arquivo B herdando A

**Files:**
- Create: `~/.openclaw/self-test-evidence/artifacts/_b-<timestamp>.md`

**Depends:** Task 1.1

- [ ] **Step 1: Ler arquivo A mais recente + criar arquivo B**

Identificar o arquivo mais recente em `~/.openclaw/self-test-evidence/artifacts/_a-*.md` (gerado pela Task 1.1). Ler todo o conteúdo dele. Gerar novo timestamp UTC ISO 8601 com Z. Criar arquivo `~/.openclaw/self-test-evidence/artifacts/_b-<NOVO_TIMESTAMP>.md` com conteúdo:

```
# Self-test evidence B

<conteúdo completo do arquivo A>

---

depends_resolved=true
timestamp_b=<NOVO_TIMESTAMP>
source_task=Task 2.1 Self-Test Sidecar
depends_from=<caminho absoluto do arquivo A lido>
```

Expected: 1 arquivo `_b-<ts>.md` criado contendo:
- Conteúdo de A replicado inteiramente
- Separador `---`
- Linha `depends_resolved=true`
- Linha `timestamp_b=<iso>`
- Linha `source_task=Task 2.1 Self-Test Sidecar`
- Linha `depends_from=<path>`
```

- [ ] **Step 3: Verificar tamanho spec reduziu**

```bash
wc -l ~/.openclaw/self-test-evidence/specs/2026-04-22-self-test-sidecar.md
```

Expected: ~60-70 linhas (reduzido de ~100 linhas originais pre-wave-8; sem ```bash``` blocks).

### Task 4.2: Parser sanity check

**Files:** (validation only)

- [ ] **Step 1: Rodar parser + verificar output shape**

```bash
python3 -c "
import sys
sys.path.insert(0, '~/.openclaw/scrum-master-agent')
from lib import parser, dependency_resolver
text = open('~/.openclaw/self-test-evidence/specs/2026-04-22-self-test-sidecar.md').read()
summary = parser.parse_plan_summary(text)
for t in summary['tasks']:
    print(f'phase_num={t[\"phase_num\"]} task_num={t[\"task_num\"]!r} subject={t[\"task_subject\"]!r}')
    deps = parser.extract_depends(t['body'])
    print(f'  depends={deps}')
    ac = t.get('expected') or []
    print(f'  acceptance_criteria count={len(ac)}')
    print(f'  first AC: {ac[0][:80] if ac else \"(none)\"}')
resolver_input = [{'label': f'Task {t[\"task_num\"]}', 'phase_num': t['phase_num'], 'depends': parser.extract_depends(t['body'])} for t in summary['tasks']]
computed = dependency_resolver.resolve(resolver_input, mode='hybrid')
print('computed_deps:', computed)
print('spec_refs found:', summary['header'].get('specs_canonicas'))
"
```

Expected:
- 2 tasks parsed: `Task 1.1` (phase 1), `Task 2.1` (phase 2)
- `Task 2.1` depends = `['Task 1.1']`
- Each task has `acceptance_criteria` count ≥ 1 (Expected bullet items extracted)
- `computed_deps` = `{'Task 1.1': [], 'Task 2.1': ['Task 1.1']}`
- `spec_refs` contém `bevox-knowledge/20_architecture/agents/dispatcher-agent.md`

- [ ] **Step 2: Nenhum commit** (runtime não-git).

---

## Phase 5 — Re-run wave-7

### Task 5.1: Preflight + confirmação ready

**Files:** (runtime check)

- [ ] **Step 1: Rodar preflight.sh**

```bash
~/.openclaw/self-test-evidence/preflight.sh 2>&1; echo "---EXIT=$?"
```

Expected: **13/13 PASS + EXIT=0**. Se algum FAIL, investigar antes de Bernard disparar.

**Provável FAIL:** `artifacts/ NAO esta vazio` se Phase 0 Task 0.1 Step 3 não foi rodado. Re-rodar `rm -f ~/.openclaw/self-test-evidence/artifacts/_*.md`.

### Task 5.2: Bernard dispara via Telegram + aguardar

**Files:** (ação Bernard)

- [ ] **Step 1: Bernard envia mensagem no topic `bevox-mobile` (Telegram grupo -100XXXXXXXXXX, topic 7)**

Mensagem sugerida:

> Dispara o self-test wave-7 re-run do bloco Operational Loop Hardening (pós-wave-8 fixes): invoca `~/.openclaw/scrum-master-agent/cli.sh propose --plan ~/.openclaw/self-test-evidence/specs/2026-04-22-self-test-sidecar.md --project-override test-project --dependency-mode hybrid`. Captura o `proposal_id` retornado. Em seguida invoca `~/.openclaw/scrum-master-agent/cli.sh accept <proposal_id>`. Depois deixa cron-dispatcher pegar e executar. Me avisa quando ambas tasks fecharem `done`.

Expected: agent retorna propose OK + accept OK + 2 task IDs criados (ex: T-0017, T-0018).

### Task 5.3: Observe + report PASS/FAIL

**Files:** (observação + report)

- [ ] **Step 1: Observar progressão (watch kanban)**

```bash
watch -n 10 '~/.openclaw/kanban-tasks/cli.sh task list --project test-project --json | python3 -c "
import sys, json
d = json.load(sys.stdin)
for t in d[\"tasks\"]:
    if t.get(\"archived_at\"): continue
    blocked_by = t.get(\"blocked_by\") or []
    print(f\"{t[\\\"id\\\"]:<8} status={t[\\\"status\\\"]:<12} blocked={str(t[\\\"blocked\\\"])[:5]:<5} blocked_by={blocked_by}\")"'
```

Observar progressão esperada (~15-25 min total):
1. Pós-accept: 2 tasks em `backlog` (T-0017, T-0018). T-0018 tem `blocked_by=[T-0017]` (wave-5 populated).
2. Pós-accept `make_ready`: T-0017 move pra `ready` (sem preds); T-0018 fica `backlog` + `blocked=true` (wave-5 gate bloqueia move-to-ready).
3. Cron-tick (~5min): T-0017 pega pra `in_progress`, dispatcher detach claude via systemd-run.
4. Claude executa, cria `_a-<ts>.md`; systemctl show marca inactive; reap popula exit_code=0.
5. T-0017 auto-move `in_progress` → `testing` → `done` (tester valida AC).
6. Hook auto-release: T-0018 `blocked=false` → movível pra `ready`.
7. Cron-tick: T-0018 pega, dispatcher, Claude cria `_b-<ts>.md` com conteúdo de A + `depends_resolved=true`.
8. T-0018 `done`.

- [ ] **Step 2: Validar PASS criteria**

```bash
# Artifacts check
ls -la ~/.openclaw/self-test-evidence/artifacts/ | head -10
cat ~/.openclaw/self-test-evidence/artifacts/_a-*.md 2>&1 | head -10
cat ~/.openclaw/self-test-evidence/artifacts/_b-*.md 2>&1 | head -15

# Status check
~/.openclaw/kanban-tasks/cli.sh task list --project test-project --json | python3 -c "
import sys, json
d = json.load(sys.stdin)
wave8 = [t for t in d['tasks'] if t.get('wave_ref','').startswith('E10/OH/wave-7-self-test')]
for t in wave8:
    print(t['id'], t['status'], 'blocked_by=', t.get('blocked_by'))
"

# Escalations check
grep 'drafter_escalated_to_cloud\|unsafe' ~/.openclaw/clarification-agent/poll.jsonl 2>&1 | tail -5 || echo "no escalations unsafe — OK"
```

Expected (PASS):
- `_a-*.md` existe com `timestamp=<iso>`, `source_task=Task 1.1 Self-Test Sidecar`
- `_b-*.md` existe com `depends_resolved=true`, timestamp herdado de A, `source_task=Task 2.1 Self-Test Sidecar`
- Ambas tasks T-NNNN wave-7-self-test em status `done`
- T-0018 tem `blocked_by=[T-0017]`
- Zero eventos unsafe OR drafter_escalated em slice

- [ ] **Step 3: Reportar PASS (seguir closure) OU FAIL (snapshot + investigar)**

**Se PASS:** seguir para Phase 6 (closure).

**Se FAIL:** rodar:

```bash
FAIL_DIR=~/.openclaw/self-test-evidence/evidence/fail-$(date -u +%Y-%m-%dT%H-%M-%SZ)-wave8
mkdir -p "$FAIL_DIR"
cp ~/.openclaw/kanban-tasks/state.json "$FAIL_DIR/"
tail -300 ~/.openclaw/kanban-tasks/events.jsonl > "$FAIL_DIR/kanban-events-tail.jsonl"
tail -100 ~/.openclaw/clarification-agent/poll.jsonl > "$FAIL_DIR/clarification-poll-tail.jsonl"
ls ~/.openclaw/dispatcher-agent/executions/*.log 2>/dev/null | xargs -I{} cp {} "$FAIL_DIR/" 2>/dev/null || true
ls ~/.openclaw/dispatcher-agent/executions/*.status.json 2>/dev/null | xargs -I{} cp {} "$FAIL_DIR/" 2>/dev/null || true
cp -r ~/.openclaw/self-test-evidence/artifacts "$FAIL_DIR/artifacts-copy"
echo "FAIL snapshot: $FAIL_DIR"
```

Reportar ao Claude: cenário exato + path snapshot + hypothesis.

---

## Phase 6 — Closure (condicional PASS)

### Task 6.1: Release note

**Files:**
- Create: `bevox-knowledge/50_releases/2026-04-22-operational-loop-hardening-closed.md`

- [ ] **Step 1: Criar release note**

```bash
cd ~/bevox-knowledge
cat > 50_releases/2026-04-22-operational-loop-hardening-closed.md <<'EOF'
# Release — Operational Loop Hardening CLOSED (2026-04-22)

**Bloco:** Operational Loop Hardening 2026-04-21
**Waves:** 0 (noise reset) + 1 (clarification daemon) + 2 (telegram push) + 3 (telegram reply) + 4 (payload gate) + 5 (kanban blocked_by) + 6 (scrum-master-v2) + 7 (self-test) + 8 (fixes) = 8 waves fechadas em 2 dias (2026-04-21 → 2026-04-22).

## Waves entregues

| Wave | Tests | Delivered |
|---|---|---|
| 0 noise-reset-prereq | N/A (data-only archive) | 2026-04-21 |
| 1 clarification-daemon-local-first | 24/24 | 2026-04-22 |
| 2 telegram-push-escalations | 35/35 | 2026-04-22 (LIVE 09:58Z) |
| 3 telegram-reply-handler | 37/37 | 2026-04-22 (gateway LIVE) |
| 4 payload-completeness-gate | 32/32 | 2026-04-22 |
| 5 kanban-blocked-by-schema | 42/42 | 2026-04-22 (state v2→v3) |
| 6 scrum-master-v2 | 34/34 | 2026-04-22 |
| 7 scrum-master-self-test | dogfood E2E | 2026-04-22 FAIL → re-run PASS pós-wave-8 |
| 8 oh-fixes | 4 + 34 existing | 2026-04-22 |

## Bugs fechados pelo wave-8

- Bug #1 dispatcher cgroup-kill: runner usa `systemd-run --user` transient service.
- Bug #2 empty-log false-success: `reap_finished` consulta `systemctl show ExecMainStatus`.
- Bug #3a scrum-master accept: `_DISPATCH_PAYLOAD_ALLOWED` inclui `blocked_by_labels`.
- Bug #3b materializer: chama `task set-blocked-by` CLI para popular wave-5 task-record.

## Closure criteria

Wave-7 self-test re-run PASS 2026-04-22T<HH:MM>Z:
- Ambas tasks `done` autonomamente
- `_a-*.md` + `_b-*.md` com AC completos
- Wave-5 blocked_by enforcement funcionando
- Zero unsafe escalations

## Branches merged

- `bevox-knowledge/draft/adr-009-clarification-daemon` → `main`
- `knowledge-sync/feat/e10-clarification-commands-plugin` → `main`
- `mission-control/feat/e10-payload-completeness-gate` → `main`
- `mission-control/feat/e5-f4-kanban-blocked-by-schema` → `main`

## Próximos passos operacionais

- Monitorar: `openclaw-clarification-daemon.timer` + `openclaw-clarification-notifier.timer` LIVE produzindo telemetria em `poll.jsonl` e `notifier.jsonl`.
- Wave-4.1 UI follow-up pendente (MC `/kanban` new-task form gates).
- Bevox-mobile agent context-overflow em prompts ambíguos (wave-7 finding) — follow-up separado.

## Stakeholder

Bernard — founder, Company OS operation.
EOF
ls -la 50_releases/2026-04-22-operational-loop-hardening-closed.md
```

Expected: arquivo criado ~80-100 linhas.

### Task 6.2: Update tracker

**Files:**
- Modify: `bevox-knowledge/40_roadmap/delivery-tracker.yml`

- [ ] **Step 1: Ler estrutura atual**

```bash
grep -A 3 'wave-6-scrum-master-v2\|wave-1-clarification' ~/bevox-knowledge/40_roadmap/delivery-tracker.yml | head -20
```

Expected: vê formato YAML das entries existentes.

- [ ] **Step 2: Adicionar entries wave-7 + wave-8 + OH-closure**

Adicionar ao final do array apropriado (provavelmente dentro de `E10` features), following existing style. Estrutura a acrescentar (adapte ao YAML real):

```yaml
      - id: wave-7-self-test
        status: delivered
        delivered_at: "2026-04-22"
        evidence: "self-test dogfood E2E via Telegram bevox-mobile (wave-7 FAIL expôs 3 bugs + wave-8 fixes + re-run PASS)"
        notes: "closes wave-7; re-run pós-wave-8 PASS"
      - id: wave-8-oh-fixes
        status: delivered
        delivered_at: "2026-04-22"
        evidence: "Bug #1 cgroup-kill, #2 empty-log, #3a+3b blocked_by_labels. 4 tests novos + 34 wave-6 preserved. Wave-7 re-run PASS."
        notes: "final wave do bloco OH"
      - id: oh-closure
        status: delivered
        delivered_at: "2026-04-22"
        evidence: "release note 50_releases/2026-04-22-operational-loop-hardening-closed.md + 4 branches merged to main"
        notes: "bloco de 8 waves fechado em 2 dias"
```

- [ ] **Step 3: Validar YAML**

```bash
python3 -c "import yaml; yaml.safe_load(open('~/bevox-knowledge/40_roadmap/delivery-tracker.yml'))" && echo "OK YAML"
```

Expected: "OK YAML".

### Task 6.3: Update roadmap narrative + spec statuses

**Files:**
- Modify: `bevox-knowledge/40_roadmap/2026-04-09-openclaw-company-os-roadmap.md`
- Modify: `bevox-knowledge/35_specs/2026-04-22-e10-oh-wave-8-fixes.md` (status delivered)
- Modify: `bevox-knowledge/35_specs/2026-04-21-e10-scrum-master-self-test.md` (status delivered)

- [ ] **Step 1: Adicionar seção "Operational Loop Hardening CLOSED" no roadmap narrative**

Localizar seção de E10 no roadmap (`2026-04-09-openclaw-company-os-roadmap.md`). Adicionar bloco:

```markdown
### Operational Loop Hardening — CLOSED (2026-04-22)

Bloco de 8 waves entregue em 2 dias (2026-04-21 → 2026-04-22). Loop operacional fechado end-to-end: escalation → Telegram push → Bernard responde `/clr_*` → daemon resolve → kanban gate exige payload → blocked_by orquestra ordem → scrum-master gera tasks compliant → dispatcher usa systemd-run → tester valida.

Detalhes: `50_releases/2026-04-22-operational-loop-hardening-closed.md`.
```

- [ ] **Step 2: Update spec statuses**

Em `bevox-knowledge/35_specs/2026-04-22-e10-oh-wave-8-fixes.md`, localizar `**Status:** draft → em execucao (2026-04-22)` e substituir por `**Status:** delivered (2026-04-22)`.

Em `bevox-knowledge/35_specs/2026-04-21-e10-scrum-master-self-test.md`, localizar `**Status:** ...` e substituir por `**Status:** delivered (2026-04-22, via wave-8 re-run)`.

### Task 6.4: Commit closure em draft branch

**Files:** (commit)

- [ ] **Step 1: Git add + commit**

```bash
cd ~/bevox-knowledge
git status -s
git add 50_releases/2026-04-22-operational-loop-hardening-closed.md \
        40_roadmap/delivery-tracker.yml \
        40_roadmap/2026-04-09-openclaw-company-os-roadmap.md \
        35_specs/2026-04-22-e10-oh-wave-8-fixes.md \
        35_specs/2026-04-21-e10-scrum-master-self-test.md
git status -s
git commit -m "$(cat <<'EOF'
delivery(E10/OH): bloco Operational Loop Hardening CLOSED

Waves 0-8 entregues 2026-04-21→2026-04-22. Wave-7 self-test re-run
PASS pós-wave-8 fixes (dispatcher systemd-run, reap systemctl query,
scrum-master blocked_by_labels + set-blocked-by CLI).

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
git log --oneline -3
```

Expected: commit criado; branch aponta pra novo commit.

### Task 6.5: Push 4 branches to main (Bernard go-ahead explícito)

**Files:** (git push — sensitive per CLAUDE.md §8)

- [ ] **Step 1: Bernard confirma push autorizado**

Antes de qualquer push, Bernard precisa confirmar explicitamente. Claude NÃO push sem OK verbal.

- [ ] **Step 2: Merge + push bevox-knowledge**

```bash
cd ~/bevox-knowledge
git checkout main
git merge --no-ff draft/adr-009-clarification-daemon -m "merge(E10/OH): Operational Loop Hardening 8 waves"
git push origin main
git log --oneline -5
```

Expected: fast-forward merge ou merge commit criado + pushed.

- [ ] **Step 3: Merge + push knowledge-sync**

```bash
cd ~/code/knowledge-sync
git checkout main
git pull --ff-only origin main
git merge --no-ff feat/e10-clarification-commands-plugin -m "merge(E10/OH wave-3): clarification-commands plugin"
git push origin main
```

Expected: merge + push.

- [ ] **Step 4: Merge + push mission-control branches (2 branches)**

```bash
cd ~/code/mission-control
git checkout main
git pull --ff-only origin main

git merge --no-ff feat/e10-payload-completeness-gate -m "merge(E10/OH wave-4): payload completeness gate"
git merge --no-ff feat/e5-f4-kanban-blocked-by-schema -m "merge(E10/OH wave-5): kanban blocked_by schema"
git push origin main
```

Expected: 2 merges + push único.

- [ ] **Step 5: Sanity check — listar branches ativas**

```bash
for repo in bevox-knowledge code/knowledge-sync code/mission-control; do
  echo "=== $repo ==="
  cd ~/$repo
  git branch -a | head -10
  echo ""
done
```

Expected: main sincronizado com origin em todos.

- [ ] **Step 6: Criar teardown final (archive self-test-evidence → bevox-knowledge)**

```bash
# Runtime artifacts stay in .openclaw runtime (non-git). Não há commit.
~/.openclaw/self-test-evidence/teardown.sh 2>&1 | tail -10
```

Expected: teardown roda (archive tasks, snapshot events, remove opt-in cron-projects.txt).

---

## Rollback procedures

**Phase 1+2 rollback (runner.py):**

```bash
mv ~/.openclaw/dispatcher-agent/lib/runner.py.pre-wave8.bak ~/.openclaw/dispatcher-agent/lib/runner.py
systemctl --user restart openclaw-cron-dispatcher.timer
echo "rollback runner.py complete"
```

**Phase 3 rollback (materializer.py):**

```bash
mv ~/.openclaw/scrum-master-agent/lib/materializer.py.pre-wave8.bak ~/.openclaw/scrum-master-agent/lib/materializer.py
rm ~/.openclaw/scrum-master-agent/tests/test_materializer_wave8.py
echo "rollback materializer.py complete"
```

**Phase 4 rollback (spec):**

```bash
mv ~/.openclaw/self-test-evidence/specs/2026-04-22-self-test-sidecar.md.pre-wave8.bak ~/.openclaw/self-test-evidence/specs/2026-04-22-self-test-sidecar.md
```

**Transient units lingering (edge):**

```bash
systemctl --user stop 'claude-task-*' 2>/dev/null
systemctl --user reset-failed 'claude-task-*' 2>/dev/null
```

---

## Self-review checklist (antes de executar)

- [ ] Cada Phase tem entrega independente testável
- [ ] Tests TDD em Phase 3 seguem fail-first → implement → pass cycle
- [ ] Phase 0 cleanup NÃO perde evidência de wave-7 FAIL (snapshot existe em `evidence/fail-2026-04-22T13-50-06Z/`)
- [ ] Phase 6 push é condicional a PASS explícito do Bernard
- [ ] Rollback disponível para cada phase

---

## Model selection (subagent-driven-development)

| Task | Complexity | Recommended model |
|---|---|---|
| Phase 0 Task 0.1 | mecânico (shell cleanup) | haiku |
| Phase 1 Task 1.1-1.4 | integração (systemd + subprocess) | opus |
| Phase 2 Task 2.1-2.3 | integração (systemctl show parsing) | opus |
| Phase 3 Task 3.1-3.4 | mecânico (TDD padrão wave-6) | haiku |
| Phase 4 Task 4.1-4.2 | mecânico (rewrite markdown) | haiku |
| Phase 5 Task 5.1-5.3 | observação (Bernard + Claude observa) | opus (eu direto) |
| Phase 6 Task 6.1-6.5 | integração (doc + git) | opus (eu direto, sensitive) |
