# Payload Completeness Gate Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Enforcar em código a policy wave-0 §3: toda task nova no kanban exige `dispatch_payload.spec_ref` + `dispatch_payload.acceptance_criteria` preenchidos. Gate universal (CLI + HTTP), zero bypass, audit event em rejeição.

**Architecture:** Novo módulo `lib/payload_gate.py` (Python, stdlib) em kanban-tasks runtime — validador puro + exceção + helper enforce. CLI `task add` ganha `--payload '<json>'` required e invoca gate antes de criar. `task_lib.create()` estende assinatura para aceitar + persistir payload. MC route POST `/api/kanban/tasks` aceita `dispatch_payload` no body, valida via espelho TS `src/lib/kanban/payload-gate.ts` (pre-validate → 422 direto), e forward via `--payload` pro CLI. `cli.ts::runCli` mantém mapping exit-based para outros erros; PAYLOAD_INCOMPLETE bloqueado no pre-validate TS antes de chamar CLI (dupla defesa).

**Tech Stack:** Python 3 stdlib + unittest (kanban-tasks). TypeScript ESM + vitest (MC). Zero pip/npm install runtime. Consistência com waves 1-3.

**Spec canônica:** `bevox-knowledge/35_specs/2026-04-21-e10-payload-completeness-gate.md`
**ADR governante:** `bevox-knowledge/30_adr/ADR-009-clarification-loop-unified-local-first.md`
**Bloco narrativo:** Operational Loop Hardening 2026-04-21 (wave-4 de 8)
**Runtime kanban-tasks:** `~/.openclaw/kanban-tasks/` (NÃO git-tracked)
**Source MC:** `~/code/mission-control/` (git, branch `feat/e10-payload-completeness-gate` a criar)
**Branch draft bevox-knowledge:** `draft/adr-009-clarification-daemon` (já existente com waves 1-3 commits)

**Ajustes pós-spec (validados com Bernard 2026-04-22):**
1. **Subcomando real: `task add`** (não `task new` como spec §3.3). CLI existente.
2. **`task_lib.create()` não aceita payload hoje** — assinatura estendida para `create(..., payload: Optional[Dict[str, Any]] = None, ...)`. Persiste em `dispatch_payload` (não mais None).
3. **`cmd_task_add` ganha `--payload REQUIRED`** (argparse `required=True`). JSON string válida.
4. **Estratégia A + C (Bernard escolheu):** enforcement primário no Python gate (CLI) + espelho TS em `src/lib/kanban/payload-gate.ts` com pre-validate no route POST antes de chamar CLI. Resulta em 422 direto (evita roundtrip CLI pro caso inválido). Python gate permanece como defesa final pra invocação direta CLI por Vox/Bernard.
5. **UI `/kanban` new-task button quebra temporariamente** (form não tem campo payload) — aceito por Bernard; fix em wave futura (§1.3 spec explicitly out-of-scope).

---

## File Structure

**Arquivos a criar:**
- `~/.openclaw/kanban-tasks/lib/payload_gate.py` — validator puro + exceção + enforce
- `~/.openclaw/kanban-tasks/tests/__init__.py` — init vazio
- `~/.openclaw/kanban-tasks/tests/test_payload_gate.py` — unit tests validator
- `~/.openclaw/kanban-tasks/tests/test_task_create_payload.py` — tests create() com payload
- `~/.openclaw/kanban-tasks/tests/test_cmd_task_add_gate.py` — tests CLI end-to-end
- `~/code/mission-control/src/lib/kanban/payload-gate.ts` — TS mirror validator
- `~/code/mission-control/src/lib/kanban/payload-gate.test.ts` — vitest unit tests mirror

**Arquivos a modificar (runtime kanban-tasks, NÃO git):**
- `~/.openclaw/kanban-tasks/lib/task.py` — `create()` aceita + persiste `payload`
- `~/.openclaw/kanban-tasks/lib/api.py` — `cmd_task_add` aceita `--payload` (required) + invoca gate + emit evento reject

**Arquivos a modificar (MC repo):**
- `~/code/mission-control/src/app/api/kanban/tasks/route.ts` — POST aceita `dispatch_payload`, pre-valida, forward via `--payload`

**Arquivos a modificar (bevox-knowledge draft branch):**
- `35_specs/2026-04-21-e10-payload-completeness-gate.md` — status draft → delivered + delivery notes (5 deltas)
- `40_roadmap/delivery-tracker.yml` — entry wave-4 delivered

**Runtime gerado (não versionado):**
- Backups `.pre-gate.bak` dos arquivos lib/task.py + lib/api.py pré-modificação

---

## Phase 0 — Setup + pre-reqs

### Task 1: MC feat branch + kanban-tasks tests scaffold + backups

**Files:**
- New branch em `~/code/mission-control/`: `feat/e10-payload-completeness-gate`
- Create: `~/.openclaw/kanban-tasks/tests/__init__.py` (empty)
- Backup: `lib/task.py.pre-gate.bak`, `lib/api.py.pre-gate.bak`

- [ ] **Step 1: Confirmar que MC tem mudanças não-relacionadas uncommitted e preservá-las**

```bash
cd ~/code/mission-control
git status --short
```

Expected: deve mostrar `M CLAUDE.md`, `M src/app/(dashboard)/health/page.tsx`, `?? src/app/api/hardening/`. Essas mudanças NÃO são do wave-4 — preservar como uncommitted.

- [ ] **Step 2: Criar feat branch (mudanças uncommitted viajam junto — elas ficarão fora dos commits do wave-4)**

```bash
cd ~/code/mission-control
git checkout -b feat/e10-payload-completeness-gate
git status --short
```

Expected: mesma lista de uncommitted, agora na branch nova.

- [ ] **Step 3: Sanity — MC compile + vitest passando baseline**

```bash
cd ~/code/mission-control
npm run lint 2>&1 | tail -10
npm test -- --run 2>&1 | tail -15
```

Expected: lint ok (pode ter warnings dos arquivos uncommitted; ignorar); vitest passa a baseline atual (todos os tests existentes verdes).

- [ ] **Step 4: Criar dirs + backups em kanban-tasks runtime**

```bash
mkdir -p ~/.openclaw/kanban-tasks/tests
touch ~/.openclaw/kanban-tasks/tests/__init__.py

cd ~/.openclaw/kanban-tasks/lib
cp task.py task.py.pre-gate.bak
cp api.py api.py.pre-gate.bak
ls *.bak
```

Expected: 2 `.bak` files criados; `tests/__init__.py` existe vazio.

- [ ] **Step 5: Smoke baseline — kanban-tasks CLI ainda funciona**

```bash
~/.openclaw/kanban-tasks/cli.sh task list --json 2>&1 | head -5
```

Expected: JSON válido com lista de tasks atuais.

- [ ] **Step 6: Nenhum commit ainda** — backups não são git.

---

## Phase 1 — Python gate core (TDD red→green)

### Task 2: `lib/payload_gate.py` — validate_payload + PayloadIncompleteError + enforce

**Files:**
- Create: `~/.openclaw/kanban-tasks/tests/test_payload_gate.py`
- Create: `~/.openclaw/kanban-tasks/lib/payload_gate.py`

- [ ] **Step 1: Escrever tests falhando em `tests/test_payload_gate.py`**

```python
"""Testes payload_gate — validator puro + exceção + enforce."""
import unittest

from lib import payload_gate


class TestValidatePayload(unittest.TestCase):
    def test_empty_dict_missing_both(self):
        valid, missing = payload_gate.validate_payload({})
        self.assertFalse(valid)
        self.assertIn("spec_ref", missing)
        self.assertIn("acceptance_criteria", missing)

    def test_only_spec_ref_missing_ac(self):
        valid, missing = payload_gate.validate_payload({"spec_ref": "35_specs/x.md"})
        self.assertFalse(valid)
        self.assertEqual(missing, ["acceptance_criteria"])

    def test_only_ac_missing_spec_ref(self):
        valid, missing = payload_gate.validate_payload({"acceptance_criteria": ["AC1"]})
        self.assertFalse(valid)
        self.assertEqual(missing, ["spec_ref"])

    def test_empty_spec_ref_string_counts_missing(self):
        valid, missing = payload_gate.validate_payload({
            "spec_ref": "", "acceptance_criteria": ["AC1"],
        })
        self.assertFalse(valid)
        self.assertIn("spec_ref", missing)

    def test_empty_spec_ref_list_counts_missing(self):
        valid, missing = payload_gate.validate_payload({
            "spec_ref": [], "acceptance_criteria": ["AC1"],
        })
        self.assertFalse(valid)
        self.assertIn("spec_ref", missing)

    def test_empty_ac_list_counts_missing(self):
        valid, missing = payload_gate.validate_payload({
            "spec_ref": "35_specs/x.md", "acceptance_criteria": [],
        })
        self.assertFalse(valid)
        self.assertEqual(missing, ["acceptance_criteria"])

    def test_ac_not_list_counts_missing(self):
        valid, missing = payload_gate.validate_payload({
            "spec_ref": "35_specs/x.md", "acceptance_criteria": "AC1 string",
        })
        self.assertFalse(valid)
        self.assertEqual(missing, ["acceptance_criteria"])

    def test_happy_path_string_spec_ref(self):
        valid, missing = payload_gate.validate_payload({
            "spec_ref": "35_specs/x.md",
            "acceptance_criteria": ["AC1: tests pass"],
        })
        self.assertTrue(valid)
        self.assertEqual(missing, [])

    def test_happy_path_list_spec_ref(self):
        valid, missing = payload_gate.validate_payload({
            "spec_ref": ["35_specs/a.md", "35_specs/b.md"],
            "acceptance_criteria": ["AC1", "AC2"],
        })
        self.assertTrue(valid)
        self.assertEqual(missing, [])

    def test_extra_fields_allowed(self):
        valid, missing = payload_gate.validate_payload({
            "spec_ref": "x.md", "acceptance_criteria": ["AC"],
            "extra_field": "foo", "description": "bar",
        })
        self.assertTrue(valid)


class TestEnforcePayloadGate(unittest.TestCase):
    def test_enforce_valid_no_raise(self):
        payload_gate.enforce_payload_gate({
            "spec_ref": "x.md", "acceptance_criteria": ["AC1"],
        })

    def test_enforce_invalid_raises_with_missing(self):
        with self.assertRaises(payload_gate.PayloadIncompleteError) as ctx:
            payload_gate.enforce_payload_gate({})
        self.assertIn("spec_ref", ctx.exception.missing)
        self.assertIn("acceptance_criteria", ctx.exception.missing)
        self.assertEqual(ctx.exception.code, "PAYLOAD_INCOMPLETE")

    def test_enforce_partial_raises(self):
        with self.assertRaises(payload_gate.PayloadIncompleteError) as ctx:
            payload_gate.enforce_payload_gate({"spec_ref": "x.md"})
        self.assertEqual(ctx.exception.missing, ["acceptance_criteria"])


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Rodar tests e confirmar FAIL**

```bash
cd ~/.openclaw/kanban-tasks
python3 -m unittest tests.test_payload_gate -v
```

Expected: `ModuleNotFoundError: No module named 'lib.payload_gate'`.

- [ ] **Step 3: Implementar `lib/payload_gate.py`**

```python
"""Payload completeness gate — E10/OH wave-4.

Enforce policy wave-0 §3: criacao de task no kanban exige dispatch_payload
com spec_ref + acceptance_criteria preenchidos. Modulo puro (sem side
effects); callers (CLI + HTTP) invocam enforce_payload_gate antes de criar.

Aceita formas flexiveis de spec_ref:
- string nao-vazia
- lista nao-vazia de strings

Acceptance_criteria deve ser lista nao-vazia. Conteudo de cada item nao
eh validado nesta wave (apenas presenca/tipo).
"""
from typing import Any, Dict, List, Tuple


class PayloadIncompleteError(Exception):
    """Raised quando payload falha gate. Carrega lista de campos faltantes."""

    def __init__(self, missing: List[str]):
        self.missing = list(missing)
        self.code = "PAYLOAD_INCOMPLETE"
        super().__init__(f"payload incomplete: missing {self.missing}")


def validate_payload(payload: Dict[str, Any]) -> Tuple[bool, List[str]]:
    """Retorna (valid, missing_fields).

    Campos avaliados:
    - spec_ref: string nao-vazia OU lista nao-vazia. Falso se ausente, vazio,
      ou tipo invalido.
    - acceptance_criteria: lista com >=1 item. Falso se ausente, nao-lista,
      ou lista vazia.

    Nao raise. Callers decidem politica.
    """
    missing: List[str] = []

    spec = payload.get("spec_ref") if isinstance(payload, dict) else None
    if isinstance(spec, str):
        if not spec.strip():
            missing.append("spec_ref")
    elif isinstance(spec, list):
        if len(spec) == 0:
            missing.append("spec_ref")
    else:
        missing.append("spec_ref")

    ac = payload.get("acceptance_criteria") if isinstance(payload, dict) else None
    if not isinstance(ac, list) or len(ac) == 0:
        missing.append("acceptance_criteria")

    return (len(missing) == 0, missing)


def enforce_payload_gate(payload: Dict[str, Any]) -> None:
    """Raise PayloadIncompleteError se invalido. No-op se valido."""
    valid, missing = validate_payload(payload)
    if not valid:
        raise PayloadIncompleteError(missing)
```

- [ ] **Step 4: Re-rodar tests e confirmar 13/13 PASS**

```bash
cd ~/.openclaw/kanban-tasks
python3 -m unittest tests.test_payload_gate -v
```

Expected: `Ran 13 tests` + `OK`.

- [ ] **Step 5: Nenhum commit** (runtime não é git).

---

## Phase 2 — CLI integration (TDD)

### Task 3: Estender `task_lib.create()` para aceitar + persistir `payload`

**Files:**
- Modify: `~/.openclaw/kanban-tasks/lib/task.py` (função `create`)
- Create: `~/.openclaw/kanban-tasks/tests/test_task_create_payload.py`

- [ ] **Step 1: Escrever tests em `tests/test_task_create_payload.py`**

```python
"""Testes task_lib.create() com kwarg payload novo (wave-4)."""
import json
import os
import shutil
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch


class TestTaskCreateWithPayload(unittest.TestCase):
    def setUp(self):
        # Isolated temp state dir
        self.tmp = Path(tempfile.mkdtemp(prefix="kanban-test-"))
        # Patch store.STATE_DIR (or whatever constant) to tmp
        # Copy a minimal viable state.json pra tmp
        state_seed = {
            "schema_version": 3,
            "projects": {"openclaw": {"name": "openclaw"}},
            "sprints": [{
                "id": "SP-2026-W17", "status": "current",
                "start_date": "2026-04-21", "end_date": "2026-04-27",
                "name": "test-sprint",
            }],
            "tasks": [],
            "last_event_seq": 0,
        }
        (self.tmp / "state.json").write_text(json.dumps(state_seed))
        (self.tmp / "events.jsonl").write_text("")
        # Patch env to point at tmp dir
        os.environ["KANBAN_STATE_DIR"] = str(self.tmp)

    def tearDown(self):
        os.environ.pop("KANBAN_STATE_DIR", None)
        shutil.rmtree(self.tmp)

    def _create_with_payload(self, payload):
        # Re-import to pick up patched env (fresh module state each test)
        import importlib
        from lib import store as store_mod
        from lib import task as task_mod
        importlib.reload(store_mod)
        importlib.reload(task_mod)
        return task_mod.create(
            title="test task",
            sprint="current",
            project="openclaw",
            payload=payload,
            actor="test",
        )

    def test_create_with_payload_persists_dispatch_payload(self):
        payload = {
            "spec_ref": "35_specs/x.md",
            "acceptance_criteria": ["AC1: runs"],
        }
        res = self._create_with_payload(payload)
        self.assertTrue(res["ok"])
        self.assertEqual(res["task"]["dispatch_payload"], payload)

    def test_create_without_payload_kwarg_sets_dispatch_none(self):
        """Backward compat: chamadas sem payload continuam com None.
        Gate NAO eh invocado em create() — gate eh responsabilidade do caller
        (cmd_task_add + route.ts). Separation of concerns."""
        import importlib
        from lib import store as store_mod
        from lib import task as task_mod
        importlib.reload(store_mod)
        importlib.reload(task_mod)
        res = task_mod.create(
            title="blank", sprint="current", project="openclaw", actor="test",
        )
        self.assertTrue(res["ok"])
        self.assertIsNone(res["task"]["dispatch_payload"])

    def test_create_event_task_created_includes_payload_keys(self):
        payload = {
            "spec_ref": "35_specs/y.md",
            "acceptance_criteria": ["AC1"],
        }
        self._create_with_payload(payload)
        events = (self.tmp / "events.jsonl").read_text().splitlines()
        created_evt = None
        for line in events:
            e = json.loads(line)
            if e.get("type") == "task_created":
                created_evt = e
                break
        self.assertIsNotNone(created_evt)
        # O evento task_created NAO carrega o payload inteiro (evita bloat),
        # mas inclui flag/keys pra auditoria.
        self.assertIn("payload_keys", created_evt)
        self.assertIn("spec_ref", created_evt["payload_keys"])
        self.assertIn("acceptance_criteria", created_evt["payload_keys"])


if __name__ == "__main__":
    unittest.main()
```

**NOTE:** Se `store.py` não usa var `KANBAN_STATE_DIR` mas path absoluto hardcoded, os tests falham com ModuleNotFoundError ou write em path errado. Antes de Step 2, conferir como `store.py` resolve state path. Se houver constante tipo `STATE_DIR = Path("~/.openclaw/kanban-tasks").expanduser()`, o setUp precisa monkey-patch essa constante em vez de env var. Adaptar esta section:

```python
# Alternativa: monkey-patch via import attribute
from lib import store
self._orig_state_dir = store.STATE_DIR  # ou nome real
store.STATE_DIR = self.tmp
```

Descobrir o nome real com `grep -n "STATE\|state_dir\|^STATE" ~/.openclaw/kanban-tasks/lib/store.py | head -5` antes de escrever o setUp.

- [ ] **Step 2: Rodar tests e confirmar FAIL**

```bash
cd ~/.openclaw/kanban-tasks
python3 -m unittest tests.test_task_create_payload -v
```

Expected: FAIL com `TypeError: create() got an unexpected keyword argument 'payload'` ou similar.

- [ ] **Step 3: Estender `lib/task.py::create()`**

Abrir `~/.openclaw/kanban-tasks/lib/task.py`. Localizar função `create` (linha ~40):

```python
def create(
    title: str,
    sprint: str = "current",
    project: Optional[str] = None,
    epic_id: Optional[str] = None,
    wave_ref: Optional[str] = None,
    description: Optional[str] = None,
    actor: str = "bernard",
) -> Dict[str, Any]:
```

Substituir pela versão wave-4 que aceita `payload`:

```python
def create(
    title: str,
    sprint: str = "current",
    project: Optional[str] = None,
    epic_id: Optional[str] = None,
    wave_ref: Optional[str] = None,
    description: Optional[str] = None,
    payload: Optional[Dict[str, Any]] = None,
    actor: str = "bernard",
) -> Dict[str, Any]:
    if not title or not title.strip():
        raise ValueError("title is required")
    with store.mutate_state() as state:
        sprint_id = _resolve_sprint_id(state, sprint)
        if project is not None and project not in state["projects"]:
            raise ValueError(f"unknown project: {project}")
        seq_id = _next_task_seq(state)
        tid = f"T-{seq_id:04d}"
        ts = store.now_iso()
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
            "blocked": False,
            "blocked_reason": None,
            "blocked_at": None,
            "rejected_reason": None,
            "dispatch_payload": payload if payload else None,
            "test_result": None,
        }
        state["tasks"].append(task)
        seq = store.next_seq(state)
        payload_keys = sorted(payload.keys()) if isinstance(payload, dict) else []
        store.append_event({
            "seq": seq, "ts": ts, "type": "task_created", "actor": actor,
            "task_id": tid, "sprint_id": sprint_id, "title": task["title"],
            "project": project, "epic_id": epic_id, "wave_ref": wave_ref,
            "payload_keys": payload_keys,
        })
        state["last_event_seq"] = seq
        return {"ok": True, "task": task}
```

Mudanças: (1) novo kwarg `payload: Optional[Dict[str, Any]] = None`, (2) task.dispatch_payload recebe `payload if payload else None` (não muda pra {} quando payload={}), (3) evento `task_created` ganha campo `payload_keys` (lista ordenada das keys — facilita audit sem bloat).

- [ ] **Step 4: Re-rodar tests e confirmar 3/3 PASS**

```bash
cd ~/.openclaw/kanban-tasks
python3 -m unittest tests.test_task_create_payload -v
```

Expected: `Ran 3 tests` + `OK`.

- [ ] **Step 5: Rodar suite completa pra regressão**

```bash
python3 -m unittest discover tests -v 2>&1 | tail -5
```

Expected: 16/16 (13 payload_gate + 3 task_create_payload).

### Task 4: `cmd_task_add` aceita `--payload REQUIRED` + invoca gate + evento reject

**Files:**
- Modify: `~/.openclaw/kanban-tasks/lib/api.py` (função `cmd_task_add` + argparse)
- Create: `~/.openclaw/kanban-tasks/tests/test_cmd_task_add_gate.py`

- [ ] **Step 1: Escrever tests end-to-end em `tests/test_cmd_task_add_gate.py`**

```python
"""Testes end-to-end cmd_task_add com gate ativo (wave-4)."""
import json
import os
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path


CLI = os.path.expanduser("~/.openclaw/kanban-tasks/cli.sh")


class TestCmdTaskAddGate(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="kanban-cli-test-"))
        state_seed = {
            "schema_version": 3,
            "projects": {"openclaw": {"name": "openclaw"}},
            "sprints": [{
                "id": "SP-2026-W17", "status": "current",
                "start_date": "2026-04-21", "end_date": "2026-04-27",
                "name": "test",
            }],
            "tasks": [],
            "last_event_seq": 0,
        }
        (self.tmp / "state.json").write_text(json.dumps(state_seed))
        (self.tmp / "events.jsonl").write_text("")
        self.env = {**os.environ, "KANBAN_STATE_DIR": str(self.tmp)}

    def tearDown(self):
        shutil.rmtree(self.tmp)

    def _run(self, *args):
        return subprocess.run(
            [CLI, *args], env=self.env, capture_output=True, text=True, timeout=10,
        )

    def test_add_without_payload_arg_errors(self):
        """argparse required=True → missing --payload → exit 2 ou mensagem clara."""
        r = self._run("task", "add", "x", "--project", "openclaw", "--json")
        self.assertNotEqual(r.returncode, 0)
        # argparse padrao retorna 2 pra erro de uso; aceitamos tb 1 se cmd capturar
        self.assertIn("payload", (r.stderr + r.stdout).lower())

    def test_add_with_empty_payload_rejected_by_gate(self):
        r = self._run(
            "task", "add", "x", "--project", "openclaw",
            "--payload", "{}", "--json",
        )
        self.assertEqual(r.returncode, 1)
        parsed = json.loads(r.stdout)
        self.assertFalse(parsed["ok"])
        self.assertEqual(parsed["code"], "PAYLOAD_INCOMPLETE")

    def test_add_with_invalid_json_payload_errors(self):
        r = self._run(
            "task", "add", "x", "--project", "openclaw",
            "--payload", "not json", "--json",
        )
        self.assertEqual(r.returncode, 1)
        parsed = json.loads(r.stdout)
        self.assertFalse(parsed["ok"])
        self.assertIn("json", parsed["error"].lower())

    def test_add_with_complete_payload_succeeds(self):
        payload = {
            "spec_ref": "35_specs/x.md",
            "acceptance_criteria": ["AC1: runs"],
        }
        r = self._run(
            "task", "add", "x", "--project", "openclaw",
            "--payload", json.dumps(payload), "--json",
        )
        self.assertEqual(r.returncode, 0)
        parsed = json.loads(r.stdout)
        self.assertTrue(parsed["ok"])
        self.assertEqual(parsed["task"]["dispatch_payload"], payload)

    def test_add_rejection_emits_audit_event(self):
        self._run(
            "task", "add", "x", "--project", "openclaw",
            "--payload", "{}", "--json",
        )
        events = (self.tmp / "events.jsonl").read_text().splitlines()
        reject_events = [
            json.loads(l) for l in events
            if json.loads(l).get("type") == "task_creation_rejected_payload_incomplete"
        ]
        self.assertEqual(len(reject_events), 1)
        evt = reject_events[0]
        self.assertIn("missing_fields", evt)
        self.assertIn("spec_ref", evt["missing_fields"])
        self.assertIn("acceptance_criteria", evt["missing_fields"])
        self.assertEqual(evt.get("attempted_title"), "x")
        self.assertEqual(evt.get("source"), "cli")


if __name__ == "__main__":
    unittest.main()
```

**NOTE:** Como na Task 3, depende de `KANBAN_STATE_DIR` override. Se `store.py` usa path absoluto hardcoded, ou adaptar ou documentar que tests precisam stub via monkey-patch. Step 2 abaixo inclui ver o `store.py` pra confirmar mecanismo.

- [ ] **Step 2: Confirmar mecanismo de state dir antes de Step 3**

```bash
grep -n "STATE_DIR\|state_dir\|KANBAN_STATE_DIR\|^STATE\|_KANBAN_ROOT" ~/.openclaw/kanban-tasks/lib/store.py | head -10
```

Se não houver env var override hoje, adicionar uma no store.py como Step 3 preliminar (2-3 linhas) — pequena mudança para habilitar test isolation:

```python
# Topo do store.py (se não existe):
import os
from pathlib import Path
KANBAN_ROOT = Path(os.environ.get(
    "KANBAN_STATE_DIR",
    str(Path.home() / ".openclaw" / "kanban-tasks"),
))
STATE_JSON = KANBAN_ROOT / "state.json"
EVENTS_JSONL = KANBAN_ROOT / "events.jsonl"
```

Substituir quaisquer hardcoded paths no store.py pelas constantes derivadas. Se já existe o padrão, pular.

- [ ] **Step 3: Rodar tests e confirmar FAIL**

```bash
cd ~/.openclaw/kanban-tasks
python3 -m unittest tests.test_cmd_task_add_gate -v
```

Expected: 5/5 FAIL (pelo menos `test_add_with_empty_payload_rejected_by_gate` falha — CLI sem gate cria task blank, returncode 0).

- [ ] **Step 4: Modificar `cmd_task_add` e argparse em `lib/api.py`**

Abrir `~/.openclaw/kanban-tasks/lib/api.py`. Localizar `cmd_task_add` (linha ~183):

Substituir por versão wave-4:

```python
def cmd_task_add(args: argparse.Namespace) -> int:
    # Parse --payload JSON
    try:
        payload = json.loads(args.payload)
    except json.JSONDecodeError as e:
        return _err(
            f"invalid JSON payload: {e}", "invalid_input", args.json,
        )
    if not isinstance(payload, dict):
        return _err(
            "payload must be a JSON object", "invalid_input", args.json,
        )

    # Gate: valida completeness antes de criar
    from lib import payload_gate  # lazy import evita circular em tests
    try:
        payload_gate.enforce_payload_gate(payload)
    except payload_gate.PayloadIncompleteError as e:
        # Emit audit event ANTES de retornar erro (truth record)
        try:
            seq = store.next_seq(store.read_state())
        except Exception:
            seq = 0
        store.append_event({
            "seq": seq,
            "ts": store.now_iso(),
            "type": "task_creation_rejected_payload_incomplete",
            "actor": args.actor or "unknown",
            "attempted_title": args.title,
            "attempted_project": args.project,
            "missing_fields": e.missing,
            "source": "cli",
        })
        return _err(
            f"missing fields: {e.missing}",
            "PAYLOAD_INCOMPLETE", args.json,
        )

    # Happy path
    res = task_lib.create(
        title=args.title, sprint=args.sprint, project=args.project,
        epic_id=args.epic, wave_ref=args.wave, description=args.description,
        payload=payload, actor=args.actor,
    )
    _print(res, args.json, f"created: {res['task']['id']}")
    return EXIT_OK
```

Modificar o argparse da subcommand `task add` (procurar onde `'add'` é registrado no argparse — provavelmente em `_build_parser` ou similar). Adicionar:

```python
# Onde 'task add' subparser é construído, junto com os outros flags:
add_parser.add_argument(
    "--payload",
    required=True,
    help="JSON string com dispatch_payload (spec_ref + acceptance_criteria).",
)
```

- [ ] **Step 5: Re-rodar tests e confirmar 5/5 PASS**

```bash
cd ~/.openclaw/kanban-tasks
python3 -m unittest tests.test_cmd_task_add_gate -v
```

Expected: `Ran 5 tests` + `OK`.

- [ ] **Step 6: Rodar suite inteira pra regressão**

```bash
python3 -m unittest discover tests -v 2>&1 | tail -5
```

Expected: 21/21 (13 gate + 3 create + 5 cmd). Se algum outro test existente quebrou, investigar — provavelmente é call a `task add` sem `--payload` em outro test/smoke que precisa de ajuste.

- [ ] **Step 7: Smoke manual do CLI** (sanity final do Phase 2)

```bash
# Erro explicito: missing payload arg
~/.openclaw/kanban-tasks/cli.sh task add "sanity" --project openclaw --json
# Expected: exit !=0, mensagem "required: --payload"

# Erro PAYLOAD_INCOMPLETE
~/.openclaw/kanban-tasks/cli.sh task add "sanity" --project openclaw --payload '{}' --json
# Expected: exit 1, JSON {"ok":false,"code":"PAYLOAD_INCOMPLETE","error":"..."}

# Happy path (cria real no runtime — sanity)
~/.openclaw/kanban-tasks/cli.sh task add "wave-4 smoke" --project openclaw \
  --payload '{"spec_ref":"35_specs/2026-04-21-e10-payload-completeness-gate.md","acceptance_criteria":["AC1: gate blocks empty payload"]}' \
  --actor bernard --json | head -20
# Expected: exit 0, JSON com task criada

# Limpar a task sanity criada
~/.openclaw/kanban-tasks/cli.sh task list --project openclaw --status backlog --json | grep -oP 'T-\d{4}' | tail -1
# Pegar o id retornado + arquivar
~/.openclaw/kanban-tasks/cli.sh task archive T-XXXX --reason "wave-4 smoke cleanup" --actor bernard --json
```

- [ ] **Step 8: Nenhum commit** (runtime não é git).

---

## Phase 3 — MC TS mirror + integração HTTP

### Task 5: `src/lib/kanban/payload-gate.ts` — TS mirror + vitest

**Files:**
- Create: `~/code/mission-control/src/lib/kanban/payload-gate.ts`
- Create: `~/code/mission-control/src/lib/kanban/payload-gate.test.ts`

- [ ] **Step 1: Escrever tests em `src/lib/kanban/payload-gate.test.ts`**

```typescript
import { describe, it, expect } from "vitest";
import { validatePayload, PAYLOAD_GATE_ERROR_CODE } from "./payload-gate";

describe("validatePayload", () => {
  it("empty dict returns both missing", () => {
    expect(validatePayload({})).toEqual(["spec_ref", "acceptance_criteria"]);
  });

  it("only spec_ref returns ac missing", () => {
    expect(validatePayload({ spec_ref: "x.md" })).toEqual(["acceptance_criteria"]);
  });

  it("only ac returns spec_ref missing", () => {
    expect(validatePayload({ acceptance_criteria: ["AC1"] })).toEqual(["spec_ref"]);
  });

  it("empty spec_ref string counts missing", () => {
    expect(validatePayload({ spec_ref: "", acceptance_criteria: ["AC1"] }))
      .toContain("spec_ref");
  });

  it("empty spec_ref list counts missing", () => {
    expect(validatePayload({ spec_ref: [], acceptance_criteria: ["AC1"] }))
      .toContain("spec_ref");
  });

  it("empty ac list counts missing", () => {
    expect(validatePayload({ spec_ref: "x.md", acceptance_criteria: [] }))
      .toContain("acceptance_criteria");
  });

  it("ac as string (not list) counts missing", () => {
    expect(validatePayload({ spec_ref: "x.md", acceptance_criteria: "AC1" as any }))
      .toContain("acceptance_criteria");
  });

  it("happy path returns empty array", () => {
    expect(validatePayload({
      spec_ref: "x.md",
      acceptance_criteria: ["AC1"],
    })).toEqual([]);
  });

  it("list spec_ref happy path", () => {
    expect(validatePayload({
      spec_ref: ["a.md", "b.md"],
      acceptance_criteria: ["AC1", "AC2"],
    })).toEqual([]);
  });

  it("null/undefined input returns both missing", () => {
    expect(validatePayload(null as any)).toEqual(["spec_ref", "acceptance_criteria"]);
    expect(validatePayload(undefined as any)).toEqual(["spec_ref", "acceptance_criteria"]);
  });

  it("error code constant matches Python PAYLOAD_INCOMPLETE", () => {
    expect(PAYLOAD_GATE_ERROR_CODE).toBe("PAYLOAD_INCOMPLETE");
  });
});
```

- [ ] **Step 2: Rodar vitest e confirmar FAIL**

```bash
cd ~/code/mission-control
npx vitest run src/lib/kanban/payload-gate.test.ts 2>&1 | tail -10
```

Expected: FAIL — cannot find module `./payload-gate`.

- [ ] **Step 3: Implementar `src/lib/kanban/payload-gate.ts`**

```typescript
// payload-gate.ts — TS mirror do Python lib/payload_gate.py.
//
// Espelho de validacao para uso em MC route.ts (pre-validate client-side
// antes de chamar CLI). Python gate permanece como defesa final. Mantem
// mesma semantica: spec_ref nao-vazio (string OU lista), acceptance_criteria
// lista nao-vazia. Error code consistente com Python.

export const PAYLOAD_GATE_ERROR_CODE = "PAYLOAD_INCOMPLETE" as const;

export type Payload = {
  spec_ref?: unknown;
  acceptance_criteria?: unknown;
  [key: string]: unknown;
};

export function validatePayload(payload: Payload | null | undefined): string[] {
  const missing: string[] = [];
  if (!payload || typeof payload !== "object") {
    return ["spec_ref", "acceptance_criteria"];
  }

  const spec = payload.spec_ref;
  let specOk = false;
  if (typeof spec === "string") {
    specOk = spec.trim().length > 0;
  } else if (Array.isArray(spec)) {
    specOk = spec.length > 0;
  }
  if (!specOk) missing.push("spec_ref");

  const ac = payload.acceptance_criteria;
  const acOk = Array.isArray(ac) && ac.length > 0;
  if (!acOk) missing.push("acceptance_criteria");

  return missing;
}
```

- [ ] **Step 4: Re-rodar vitest e confirmar 11/11 PASS**

```bash
cd ~/code/mission-control
npx vitest run src/lib/kanban/payload-gate.test.ts 2>&1 | tail -10
```

Expected: `Test Files  1 passed` + `Tests  11 passed`.

### Task 6: Modificar `src/app/api/kanban/tasks/route.ts` POST — pre-validate + forward

**Files:**
- Modify: `~/code/mission-control/src/app/api/kanban/tasks/route.ts`

- [ ] **Step 1: Ler o route.ts atual e identificar a função POST**

Baseline conhecida (linhas 52-77):

```typescript
export async function POST(req: NextRequest) {
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
  if (typeof bb.title !== "string" || bb.title.trim().length === 0) {
    return NextResponse.json(
      { error: "invalid_input", detail: "title (non-empty string) required" },
      { status: 400 },
    );
  }
  const args = ["task", "add", bb.title.trim()];
  if (typeof bb.sprint === "string") args.push("--sprint", bb.sprint);
  if (typeof bb.project === "string" && bb.project.length > 0) args.push("--project", bb.project);
  if (typeof bb.epic_id === "string" && bb.epic_id.length > 0) args.push("--epic", bb.epic_id);
  if (typeof bb.wave_ref === "string" && bb.wave_ref.length > 0) args.push("--wave", bb.wave_ref);
  if (typeof bb.description === "string" && bb.description.length > 0) args.push("--description", bb.description);

  return respondCli(runCli(args, resolveActor(req)));
}
```

- [ ] **Step 2: Substituir a função POST pela versão wave-4**

```typescript
export async function POST(req: NextRequest) {
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
  if (typeof bb.title !== "string" || bb.title.trim().length === 0) {
    return NextResponse.json(
      { error: "invalid_input", detail: "title (non-empty string) required" },
      { status: 400 },
    );
  }

  // Wave-4 gate: dispatch_payload obrigatorio
  const payload = (bb.dispatch_payload ?? null) as Payload | null;
  const missing = validatePayload(payload);
  if (missing.length > 0) {
    return NextResponse.json(
      {
        error: "payload_incomplete",
        code: PAYLOAD_GATE_ERROR_CODE,
        missing,
        detail: `dispatch_payload incomplete: missing ${missing.join(", ")}`,
      },
      { status: 422 },
    );
  }

  const args = ["task", "add", bb.title.trim()];
  if (typeof bb.sprint === "string") args.push("--sprint", bb.sprint);
  if (typeof bb.project === "string" && bb.project.length > 0) args.push("--project", bb.project);
  if (typeof bb.epic_id === "string" && bb.epic_id.length > 0) args.push("--epic", bb.epic_id);
  if (typeof bb.wave_ref === "string" && bb.wave_ref.length > 0) args.push("--wave", bb.wave_ref);
  if (typeof bb.description === "string" && bb.description.length > 0) args.push("--description", bb.description);
  // Payload atomico com a criacao (wave-4):
  args.push("--payload", JSON.stringify(payload));

  return respondCli(runCli(args, resolveActor(req)));
}
```

- [ ] **Step 3: Adicionar o import no topo do arquivo**

Entre os imports existentes, inserir:

```typescript
import {
  validatePayload,
  PAYLOAD_GATE_ERROR_CODE,
  type Payload,
} from "@/lib/kanban/payload-gate";
```

- [ ] **Step 4: Rodar lint + typecheck**

```bash
cd ~/code/mission-control
npx tsc --noEmit 2>&1 | tail -10
```

Expected: zero errors (novos imports resolvem corretamente).

```bash
npm run lint 2>&1 | tail -5
```

Expected: no new warnings from route.ts/payload-gate.ts.

- [ ] **Step 5: Smoke manual HTTP** (sanity — requer MC dev server)

```bash
cd ~/code/mission-control
# Se MC dev server não estiver rodando, skipar manual; ou iniciar em terminal separado
# Bernard manualmente: npm run dev

# Em outro shell, com token válido:
TOKEN=$(grep -oP '(?<="token": ")[^"]+' ~/.openclaw/openclaw.json | head -1)
MC_PORT=3000  # confirmar com Bernard

# Test 422 sem payload
curl -s -X POST http://127.0.0.1:$MC_PORT/api/kanban/tasks \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"title":"smoke","project":"openclaw"}' \
  -w "\nHTTP %{http_code}\n"
# Expected: HTTP 422 + JSON com code=PAYLOAD_INCOMPLETE

# Test 201 com payload completo
curl -s -X POST http://127.0.0.1:$MC_PORT/api/kanban/tasks \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"title":"smoke completo","project":"openclaw","dispatch_payload":{"spec_ref":"35_specs/x.md","acceptance_criteria":["AC1"]}}' \
  -w "\nHTTP %{http_code}\n"
# Expected: HTTP 200 + JSON com task criada (MC retorna 200, não 201, porque respondCli usa 200 padrão)
```

Se MC dev server não estiver online durante o deploy, este step fica manual pós-delivery; documentar e seguir.

---

## Phase 4 — Smoke E2E integrado

### Task 7: Smoke full — CLI + runtime audit + MC pre-validator

**Files:** nenhum (só execução).

- [ ] **Step 1: Backup events.jsonl real** antes de smoke real

```bash
cp ~/.openclaw/kanban-tasks/events.jsonl ~/.openclaw/kanban-tasks/events.jsonl.pre-wave4-smoke.bak
EVENTS_LINES_BEFORE=$(wc -l < ~/.openclaw/kanban-tasks/events.jsonl)
echo "Events baseline: $EVENTS_LINES_BEFORE lines"
```

- [ ] **Step 2: Smoke 1 — CLI sem --payload → erro argparse (exit 2)**

```bash
~/.openclaw/kanban-tasks/cli.sh task add "smoke1" --project openclaw --actor test-wave4 --json
echo "Exit: $?"
```

Expected: exit !=0 + stderr mencionando `required: --payload`.

- [ ] **Step 3: Smoke 2 — CLI --payload '{}' → PAYLOAD_INCOMPLETE (exit 1)**

```bash
~/.openclaw/kanban-tasks/cli.sh task add "smoke2" --project openclaw \
  --payload '{}' --actor test-wave4 --json
echo "Exit: $?"
```

Expected: exit 1 + JSON com `"code":"PAYLOAD_INCOMPLETE"` e missing `["spec_ref","acceptance_criteria"]`.

- [ ] **Step 4: Smoke 3 — CLI --payload só spec_ref → missing=[acceptance_criteria]**

```bash
~/.openclaw/kanban-tasks/cli.sh task add "smoke3" --project openclaw \
  --payload '{"spec_ref":"x.md"}' --actor test-wave4 --json
echo "Exit: $?"
```

Expected: exit 1 + missing=["acceptance_criteria"].

- [ ] **Step 5: Smoke 4 — CLI --payload completo → exit 0 + task criada**

```bash
OUT=$(~/.openclaw/kanban-tasks/cli.sh task add "smoke4 wave-4 OK" --project openclaw \
  --payload '{"spec_ref":"35_specs/2026-04-21-e10-payload-completeness-gate.md","acceptance_criteria":["AC1: gate blocks empty"]}' \
  --actor test-wave4 --json)
echo "$OUT" | head -10
TASK_ID=$(echo "$OUT" | grep -oP '"id": "T-\d{4}"' | grep -oP 'T-\d{4}')
echo "Criada: $TASK_ID"
echo "Exit: $?"
```

Expected: exit 0 + JSON task válido + TASK_ID preenchido.

- [ ] **Step 6: Verificar audit events**

```bash
tail -20 ~/.openclaw/kanban-tasks/events.jsonl
grep -c '"task_creation_rejected_payload_incomplete"' ~/.openclaw/kanban-tasks/events.jsonl
```

Expected: ≥2 eventos `task_creation_rejected_payload_incomplete` (smoke 2 + smoke 3 geraram um cada). Evento `task_created` pro smoke4.

- [ ] **Step 7: Cleanup — archive task de smoke4**

```bash
~/.openclaw/kanban-tasks/cli.sh task archive "$TASK_ID" --reason "wave-4 smoke cleanup" --actor bernard --json
```

Expected: archive ok.

- [ ] **Step 8: Validar suite Python completa pós-smoke**

```bash
cd ~/.openclaw/kanban-tasks
python3 -m unittest discover tests -v 2>&1 | tail -5
```

Expected: 21/21.

- [ ] **Step 9: Validar suite MC (vitest) pós-smoke**

```bash
cd ~/code/mission-control
npm test -- --run 2>&1 | tail -10
```

Expected: todos os tests existentes + novos 11 payload-gate tests passam. Zero regressão.

---

## Phase 5 — Delivery commits

### Task 8: Commit MC changes em feat branch

**Files:** git commit em `~/code/mission-control/`

- [ ] **Step 1: Confirmar branch + status**

```bash
cd ~/code/mission-control
git branch --show-current
git status --short
```

Expected: branch `feat/e10-payload-completeness-gate`. Status deve mostrar:
- Unmodified NOT-related uncommitted: `M CLAUDE.md`, `M src/app/(dashboard)/health/page.tsx`, `?? src/app/api/hardening/`
- Wave-4 modified: `M src/app/api/kanban/tasks/route.ts`
- Wave-4 new: `?? src/lib/kanban/payload-gate.ts`, `?? src/lib/kanban/payload-gate.test.ts`

- [ ] **Step 2: Add EXPLICITO só dos arquivos wave-4 (crítico — NÃO `git add -A`)**

```bash
cd ~/code/mission-control
git add src/app/api/kanban/tasks/route.ts \
        src/lib/kanban/payload-gate.ts \
        src/lib/kanban/payload-gate.test.ts
git diff --cached --stat
```

Expected: 3 arquivos wave-4. Arquivos não-relacionados (`CLAUDE.md`, `health/page.tsx`, `hardening/`) **NÃO aparecem** no cached.

- [ ] **Step 3: Commit**

```bash
cd ~/code/mission-control
git commit -m "$(cat <<'EOF'
feat(kanban): payload-completeness-gate on POST /api/kanban/tasks (E10 OH wave-4)

Adiciona TS mirror `src/lib/kanban/payload-gate.ts` + pre-validate no
route POST antes de chamar CLI. Valida dispatch_payload exige:
- spec_ref: string nao-vazia OU lista nao-vazia
- acceptance_criteria: lista nao-vazia

Retorna HTTP 422 com `{error: "payload_incomplete", code: "PAYLOAD_INCOMPLETE",
missing: [...]}` quando invalido. Python gate em ~/.openclaw/kanban-tasks/
lib/payload_gate.py (nao tracked) eh defesa final pra chamadas diretas CLI.

Body POST ganha campo `dispatch_payload` obrigatorio + forwarded via
`--payload '<json>'` pro CLI task add.

11 unit tests vitest. UI form pre-validation fica fora desta wave
(spec §1.3); UI form atual sem campos payload retorna 422 ate update.

Spec: bevox-knowledge/35_specs/2026-04-21-e10-payload-completeness-gate.md
ADR: bevox-knowledge/30_adr/ADR-009-clarification-loop-unified-local-first.md

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)" && git log --oneline -1
```

Expected: novo commit criado em `feat/e10-payload-completeness-gate`, stat mostra 3 arquivos (route.ts modificado + 2 novos).

- [ ] **Step 4: NÃO pushar agora.** Push condicional ao bloco OH completo (wave-7 self-test pass).

### Task 9: Commit delivery em bevox-knowledge draft branch

**Files:**
- Modify: `~/bevox-knowledge/35_specs/2026-04-21-e10-payload-completeness-gate.md`
- Modify: `~/bevox-knowledge/40_roadmap/delivery-tracker.yml`

- [ ] **Step 1: Confirmar branch draft**

```bash
cd ~/bevox-knowledge
git branch --show-current
```

Expected: `draft/adr-009-clarification-daemon`.

- [ ] **Step 2: Atualizar status da spec**

Editar `35_specs/2026-04-21-e10-payload-completeness-gate.md`. Mudar `**Status:** draft` para `**Status:** delivered (2026-04-22)`.

- [ ] **Step 3: Adicionar 5 delivery notes na spec (deltas descobertos)**

Acrescentar logo abaixo da seção `## 2. Decisoes travadas no framing (Q1)`, antes da `## 3. Arquitetura`, o bloco:

```markdown
---

## 2.1 Delivery notes (2026-04-22)

Deltas entre spec e implementação entregue:

1. **Subcomando real é `task add`** (CLI existente), não `task new` como descrito em §3.3 e §4. Função `cmd_task_add` em `lib/api.py:183`. Gate integrado nela.

2. **`task_lib.create()` não aceitava payload** antes da wave-4. Assinatura estendida com kwarg `payload: Optional[Dict[str, Any]] = None`. Persiste em `dispatch_payload` (não mais None). Evento `task_created` ganhou campo `payload_keys` pra audit sem bloat.

3. **CLI `task add` ganhou `--payload REQUIRED`** (argparse `required=True`). JSON string válida obrigatória.

4. **MC route POST** usa dupla defesa (Bernard escolheu A+C em brainstorm 2026-04-22):
   - Pre-validate TS mirror em `src/lib/kanban/payload-gate.ts` → 422 direto se inválido (evita roundtrip CLI)
   - Python gate em `lib/payload_gate.py` permanece como defesa final para chamadas diretas CLI (Vox, Bernard, scrum-master, smoke)

5. **UI `/kanban` new-task button quebra temporariamente** — form POSTa sem `dispatch_payload`, recebe 422. Fix do form fica fora do wave-4 (§1.3 explicitly out-of-scope); documentado como follow-up wave-4.1 na UI.
```

- [ ] **Step 4: Acrescentar entry em `delivery-tracker.yml`**

Localizar bloco E10 Operational Loop Hardening (após wave-3 `telegram-reply-handler`) e inserir:

```yaml
      - id: payload-completeness-gate
        status: delivered
        delivered_at: 2026-04-22
        spec: 35_specs/2026-04-21-e10-payload-completeness-gate.md
        adr: 30_adr/ADR-009-clarification-loop-unified-local-first.md
        narrative: "Operational Loop Hardening 2026-04-22 — wave-4 de 8"
        features:
          - "lib/payload_gate.py (Python, stdlib) em kanban-tasks runtime: validate_payload + PayloadIncompleteError + enforce_payload_gate"
          - "cmd_task_add CLI ganhou --payload REQUIRED + gate antes de criar + emit audit event em rejeicao"
          - "task_lib.create() estendido com kwarg payload (persiste em dispatch_payload); evento task_created ganha payload_keys"
          - "MC route POST /api/kanban/tasks aceita dispatch_payload + pre-validate TS mirror (422 direto) + forward via --payload"
          - "src/lib/kanban/payload-gate.ts TS mirror (11 vitest tests); dupla defesa (HTTP pre-validate + Python gate fallback)"
          - "21 unit tests Python (13 gate + 3 create + 5 cmd) + 11 vitest TS = 32 tests novos"
          - "audit event task_creation_rejected_payload_incomplete em events.jsonl"
          - "policy wave-0 §3 agora enforced em codigo: zero bypass, universal (CLI + HTTP)"
          - "UI new-task form sem campos payload quebra com 422 temporariamente; fix wave-4.1 follow-up out-of-scope"
      - id: finance-agent
```

(Acima da entrada `finance-agent` existente.)

- [ ] **Step 5: Validar YAML (se yaml module disponivel)**

```bash
cd ~/bevox-knowledge
python3 -c "import yaml; yaml.safe_load(open('40_roadmap/delivery-tracker.yml'))" && echo OK
```

Expected: `OK`. Se `ModuleNotFoundError`, confiar na inspeção visual via `git diff --stat` (pattern identical a wave-3).

- [ ] **Step 6: Commit draft branch**

```bash
cd ~/bevox-knowledge
git add 35_specs/2026-04-21-e10-payload-completeness-gate.md \
        40_roadmap/delivery-tracker.yml
git diff --cached --stat
git commit -m "$(cat <<'EOF'
delivery(E10): wave-4 payload-completeness-gate delivered

Operational Loop Hardening 2026-04-22 wave-4 completa. Policy wave-0
§3 agora enforced em codigo em duas camadas:

1. Python gate `lib/payload_gate.py` em ~/.openclaw/kanban-tasks/
   (runtime, nao-git): validate_payload + enforce_payload_gate, integrado
   em cmd_task_add (novo --payload REQUIRED); task_lib.create() aceita
   payload kwarg; events.jsonl recebe task_creation_rejected_payload_incomplete.
2. TS mirror `src/lib/kanban/payload-gate.ts` (MC repo, branch
   feat/e10-payload-completeness-gate): pre-valida POST body antes de
   chamar CLI; retorna HTTP 422 com code=PAYLOAD_INCOMPLETE.

21 unit tests Python (novo tests/ dir em kanban-tasks) + 11 vitest TS.
32 tests novos total. Zero regressao.

5 delivery notes inline (§2.1) cobrem deltas:
- subcomando real é task add (nao task new)
- task_lib.create() nao aceitava payload (estendido)
- --payload REQUIRED adicionado
- A+C enforcement (pre-validate TS + Python gate fallback)
- UI form sem campos payload quebra (fix wave-4.1 follow-up)

Loop operacional agora previne recorrencia do incidente que originou
o bloco: Vox/agents/UI que tentam criar task sem payload recebem
rejeicao imediata + evento auditavel, antes que a task polua o kanban.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)" && git log --oneline -5
```

Expected: novo commit `delivery(E10): wave-4 payload-completeness-gate delivered` no topo acima do `delivery(E10): wave-3 telegram-reply-handler delivered`.

- [ ] **Step 7: NÃO pushar.** Merge pra main condicional ao bloco OH completo (wave-7 self-test PASS).

---

## Checklist final

- [ ] **Phase 1-3 tests:** 21/21 Python (kanban-tasks) + 11/11 vitest TS (MC) = **32/32 verdes**.
- [ ] **MC baseline tests:** não regrediram (vitest completo passa).
- [ ] **Smoke CLI:** 4 cenários PASS (argparse missing, payload vazio, parcial, completo + audit events).
- [ ] **Smoke HTTP:** 422 sem payload, 200 com payload completo (opcional se MC dev server rodando).
- [ ] **MC commit em feat branch:** `feat/e10-payload-completeness-gate`, 3 arquivos (route.ts + 2 novos). **NÃO pushada.** Unrelated uncommitted preservados.
- [ ] **bevox-knowledge commit em draft:** spec status delivered + 5 delivery notes + tracker entry. Branch ainda NÃO pushada.
- [ ] **Backups kanban-tasks:** `lib/task.py.pre-gate.bak` + `lib/api.py.pre-gate.bak` (rollback em 1 comando: `mv *.bak` → original).

---

## Próximos passos pós-delivery wave-4

1. Bernard testa criação via CLI com payload completo (task real do kanban).
2. Bernard **atualiza o prompt/CLAUDE.md do Vox** (agent main) pra SEMPRE incluir `dispatch_payload` completo quando criar task. Sem essa policy no Vox side, ele vai bater no gate + falhar a criação.
3. UI form `/kanban` new-task quebrada temporariamente; follow-up **wave-4.1 UI form com payload fields** fica como hygiene documental / próxima sessão dedicada.
4. **Wave-5 (kanban-blocked-by-schema E5/F4)** próxima — `blocked_by` como array estruturado (AND semantics + auto-block quando upstream rejected/archived). Spec canônica em `35_specs/2026-04-21-e5-f4-kanban-blocked-by-schema.md`.
5. Quando bloco OH completo (wave-7 PASS), push das 3 branches:
   - `bevox-knowledge/draft/adr-009-clarification-daemon` → `main`
   - `knowledge-sync/feat/e10-clarification-commands-plugin` → `main`
   - `mission-control/feat/e10-payload-completeness-gate` → `main`
