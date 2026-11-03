# Clarification Daemon + Local-First Drafter — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Estender `clarification-agent` com subcomando `poll-tick` (pull mode via systemd timer) + refatorar `drafter` pra provider local-first (ollama/qwen2.5-coder:14b) com fallback cloud 1x em `unsafe`, adicionar pre-filter determinístico e fast-fail de payload vazio (zero-LLM pros casos T-0006/T-0008), sem quebrar push mode existente.

**Architecture:** Novo módulo `lib/provider.py` abstrai subprocess LLM (ollama | claude_cli). Novo módulo `lib/poller.py` com pipeline `run_tick` (pre-filter → fast-fail → context_load → drafter → resolve). CLI `api.py` ganha `poll-tick` subparser. Audit em `poll.jsonl` append-only separado dos artefatos push. Fcntl lock global + kill-switch por arquivo (padrão reaper/cron-dispatcher). Systemd user timer 10min default ship como templates.

**Tech Stack:** Python 3 stdlib apenas (zero pip install — decisão arquitetural E10 Plano B Spike-5). `unittest` pra testes. `fcntl` pra locking. `subprocess` pra ollama/claude CLI. `bash` pra smoke E2E. Systemd user units pra timers.

**Spec canônica:** `bevox-knowledge/35_specs/2026-04-21-e10-clarification-daemon-local-first.md`
**ADR governante:** `bevox-knowledge/30_adr/ADR-009-clarification-loop-unified-local-first.md`
**Runtime source:** `~/.openclaw/clarification-agent/`

---

## File Structure

**Arquivos a criar:**
- `~/.openclaw/clarification-agent/lib/provider.py` — abstração LLM multi-provider
- `~/.openclaw/clarification-agent/lib/poller.py` — lógica do tick (pre-filter, fast-fail, orchestration)
- `~/.openclaw/clarification-agent/tests/__init__.py`
- `~/.openclaw/clarification-agent/tests/test_provider.py`
- `~/.openclaw/clarification-agent/tests/test_poller.py`
- `~/.openclaw/clarification-agent/tests/test_store_poll_append.py`
- `~/.openclaw/clarification-agent/smoke_e2e.sh` — 14 cenários
- `~/.openclaw/clarification-agent/systemd/openclaw-clarification-daemon.service`
- `~/.openclaw/clarification-agent/systemd/openclaw-clarification-daemon.timer`

**Arquivos a modificar:**
- `~/.openclaw/clarification-agent/lib/drafter.py` — delegar chamada LLM ao `provider.run` (preservando interface pública)
- `~/.openclaw/clarification-agent/lib/store.py` — adicionar `append_poll_event`, `POLL_JSONL`, `POLL_LOCK`, `POLL_DISABLED`
- `~/.openclaw/clarification-agent/lib/lifecycle.py` — adicionar `auto_draft_for_task` (pull mode), `acquire_clarification_lock`
- `~/.openclaw/clarification-agent/lib/api.py` — adicionar `cmd_poll_tick`, `cmd_poll_status`, subparsers correspondentes
- `~/.openclaw/clarification-agent/playbook.md` — seção nova "Pull mode (daemon)"
- `~/.openclaw/bevox-mobile/scripts/request-clarification.sh` — checar `clarification_lock.holder` antes de agir
- `~/.openclaw/health/registry.yml` — entrada nova `openclaw-clarification-daemon`
- `bevox-knowledge/35_specs/2026-04-21-bevox-mobile-auto-unblock.md` — header "Status: superseded"
- `bevox-knowledge/20_architecture/agents/bevox-mobile-auto-unblock-status.md` — "deprecated" note

---

## Phase 0 — Setup baseline

### Task 1: Criar tests/ dir + backups dos arquivos a modificar

**Files:**
- Create: `~/.openclaw/clarification-agent/tests/__init__.py` (empty)
- Copy: `drafter.py → drafter.py.pre-provider.bak`, `api.py → api.py.pre-poll.bak`, `store.py → store.py.pre-poll.bak`, `lifecycle.py → lifecycle.py.pre-poll.bak`

- [ ] **Step 1: Criar tests dir + init**

```bash
mkdir -p ~/.openclaw/clarification-agent/tests
touch ~/.openclaw/clarification-agent/tests/__init__.py
```

- [ ] **Step 2: Backup dos 4 arquivos principais**

```bash
cd ~/.openclaw/clarification-agent/lib
cp drafter.py drafter.py.pre-provider.bak
cp api.py api.py.pre-poll.bak
cp store.py store.py.pre-poll.bak
cp lifecycle.py lifecycle.py.pre-poll.bak
```

Expected: 4 `.bak` files criados, originais intactos.

- [ ] **Step 3: Verificar push mode ainda funciona (smoke baseline)**

```bash
# Confirma que o CLI atual ainda roda listando escalations
~/.openclaw/clarification-agent/cli.sh escalations --json
```

Expected: JSON com 3 escalations pendentes (T-0006-clr-2, T-0008-clr-1, T-0008-clr-2).

- [ ] **Step 4: Nenhum commit nesta task** (runtime não é git; mudanças ficam no próprio `~/.openclaw/`).

---

## Phase 1 — Provider abstraction (refactor sem quebrar push)

### Task 2: Test skeleton `test_provider.py` (falhando)

**Files:**
- Create: `~/.openclaw/clarification-agent/tests/test_provider.py`

- [ ] **Step 1: Escrever test falhando de `provider.run` com provider ollama mock**

Cria arquivo `~/.openclaw/clarification-agent/tests/test_provider.py`:

```python
"""Testes provider.run — local-first abstraction."""
import json
import unittest
from unittest.mock import patch

from lib import provider


class TestProviderRun(unittest.TestCase):
    def test_ollama_success_returns_parsed(self):
        raw_json = '{"answer":"ok","sources":["/x"],"confidence":"safe","escalation_reason":""}'
        with patch("lib.provider._run_ollama") as mock:
            mock.return_value = (raw_json, 1234)
            out = provider.run(prompt="p", model="qwen2.5-coder:14b",
                               timeout=15, provider="ollama")
        self.assertEqual(out["provider_used"], "ollama")
        self.assertEqual(out["parsed"]["confidence"], "safe")
        self.assertEqual(out["latency_ms"], 1234)
        self.assertIsNone(out["error"])

    def test_claude_cli_success_returns_parsed(self):
        raw_json = '```json\n{"answer":"ok","sources":["/x"],"confidence":"unsafe","escalation_reason":"r"}\n```'
        with patch("lib.provider._run_claude_cli") as mock:
            mock.return_value = (raw_json, 2345)
            out = provider.run(prompt="p", model="claude-haiku-4-5",
                               timeout=20, provider="claude_cli")
        self.assertEqual(out["provider_used"], "claude_cli")
        self.assertEqual(out["parsed"]["confidence"], "unsafe")

    def test_timeout_returns_error(self):
        with patch("lib.provider._run_ollama") as mock:
            mock.side_effect = TimeoutError("15s hit")
            out = provider.run(prompt="p", model="qwen2.5-coder:14b",
                               timeout=15, provider="ollama")
        self.assertEqual(out["error"], "timeout")
        self.assertIsNone(out["parsed"])


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Rodar teste pra confirmar que falha (módulo ainda não existe)**

```bash
cd ~/.openclaw/clarification-agent
python3 -m unittest tests.test_provider -v
```

Expected: FAIL com `ModuleNotFoundError: No module named 'lib.provider'`.

### Task 3: Implementar `lib/provider.py` (mínimo pra passar)

**Files:**
- Create: `~/.openclaw/clarification-agent/lib/provider.py`

- [ ] **Step 1: Escrever minimal `provider.py`**

```python
"""Provider abstraction: ollama local + claude CLI cloud.

Padrão: receber prompt + model + timeout + provider name; retornar
dict com parsed JSON, raw, latency_ms, provider_used, error.

Zero pip install (stdlib apenas: subprocess, json, re, time).
"""
import json
import re
import subprocess
import time
from typing import Any, Dict, Optional


OLLAMA_BIN = "ollama"
CLAUDE_BIN = "claude"


def _extract_json(raw: str) -> Optional[Dict[str, Any]]:
    """Extrai bloco JSON do output; tolera ```json``` wrapping."""
    m = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", raw, re.DOTALL)
    if m:
        block = m.group(1)
    else:
        start = raw.find("{")
        end = raw.rfind("}")
        if start == -1 or end == -1 or end <= start:
            return None
        block = raw[start:end + 1]
    try:
        parsed = json.loads(block)
    except json.JSONDecodeError:
        return None
    for field in ("answer", "sources", "confidence"):
        if field not in parsed:
            return None
    if not isinstance(parsed["sources"], list):
        parsed["sources"] = [str(parsed["sources"])]
    parsed.setdefault("escalation_reason", "")
    return parsed


def _run_ollama(prompt: str, model: str, timeout: int) -> (str, int):
    t0 = time.monotonic()
    r = subprocess.run(
        [OLLAMA_BIN, "run", model],
        input=prompt, capture_output=True, text=True,
        check=False, timeout=timeout,
    )
    latency_ms = int((time.monotonic() - t0) * 1000)
    if r.returncode != 0:
        raise RuntimeError(f"ollama exit={r.returncode} stderr={r.stderr[:200]}")
    return r.stdout, latency_ms


def _run_claude_cli(prompt: str, model: str, timeout: int) -> (str, int):
    t0 = time.monotonic()
    r = subprocess.run(
        [CLAUDE_BIN, "-p", prompt, "--model", model, "--allowedTools", ""],
        capture_output=True, text=True, check=False, timeout=timeout,
    )
    latency_ms = int((time.monotonic() - t0) * 1000)
    if r.returncode != 0:
        raise RuntimeError(f"claude exit={r.returncode} stderr={r.stderr[:200]}")
    return r.stdout, latency_ms


def run(
    *, prompt: str, model: str, timeout: int, provider: str,
) -> Dict[str, Any]:
    """Retorna: {raw, parsed (dict|None), latency_ms, provider_used, error (str|None)}."""
    assert provider in ("ollama", "claude_cli"), f"unknown provider: {provider}"
    runner = _run_ollama if provider == "ollama" else _run_claude_cli
    try:
        raw, latency_ms = runner(prompt, model, timeout)
    except subprocess.TimeoutExpired:
        return {"raw": "", "parsed": None, "latency_ms": timeout * 1000,
                "provider_used": provider, "error": "timeout"}
    except TimeoutError:  # for test mocking
        return {"raw": "", "parsed": None, "latency_ms": timeout * 1000,
                "provider_used": provider, "error": "timeout"}
    except Exception as e:
        return {"raw": "", "parsed": None, "latency_ms": 0,
                "provider_used": provider, "error": f"subprocess_error:{e}"}
    parsed = _extract_json(raw)
    if parsed is None:
        return {"raw": raw[:2000], "parsed": None, "latency_ms": latency_ms,
                "provider_used": provider, "error": "parse_failed"}
    return {"raw": raw[:2000], "parsed": parsed, "latency_ms": latency_ms,
            "provider_used": provider, "error": None}
```

- [ ] **Step 2: Rodar tests e confirmar PASS**

```bash
cd ~/.openclaw/clarification-agent
python3 -m unittest tests.test_provider -v
```

Expected: 3 tests PASS.

### Task 4: Refactor `drafter.py` pra usar `provider.run`

**Files:**
- Modify: `~/.openclaw/clarification-agent/lib/drafter.py`

- [ ] **Step 1: Substituir a chamada `subprocess.run([claude, ...])` em `draft_answer` por `provider.run`**

Edit em `drafter.py`:

**Imports no topo (adicionar):**
```python
from . import provider as provider_lib
```

**Constantes (ampliar):**
```python
DRAFTER_MODEL_LOCAL = "qwen2.5-coder:14b"
DRAFTER_PROVIDER_LOCAL = "ollama"
DRAFTER_MODEL_CLOUD = "claude-haiku-4-5"
DRAFTER_PROVIDER_CLOUD = "claude_cli"
DRAFTER_TIMEOUT_LOCAL = 30
DRAFTER_TIMEOUT_CLOUD = 20
```

**Reescrever `draft_answer` pra aceitar `provider` param + delegar:**

```python
def draft_answer(
    task_id: str, question: str,
    ctx_bundle: Optional[Dict[str, Any]] = None,
    model: str = DRAFTER_MODEL_CLOUD,
    provider: str = DRAFTER_PROVIDER_CLOUD,
    timeout: int = DRAFTER_TIMEOUT_CLOUD,
) -> Dict[str, Any]:
    if ctx_bundle is None:
        ctx_bundle = context_loader.build_context_bundle(task_id)
    prompt = _build_prompt(task_id, question, ctx_bundle)
    out = provider_lib.run(
        prompt=prompt, model=model, timeout=timeout, provider=provider,
    )
    if out["error"] == "timeout":
        raise DrafterError("CLAUDE_SUBPROCESS_FAILED",
                           f"{provider} timeout after {timeout}s")
    if out["error"] and out["error"].startswith("subprocess_error"):
        raise DrafterError("CLAUDE_SUBPROCESS_FAILED", out["error"])
    if out["error"] == "parse_failed":
        raise DrafterError("PARSE_NO_JSON",
                           f"provider={provider} raw sem JSON: {out['raw'][:300]}")
    parsed = out["parsed"]
    for field in ("answer", "sources", "confidence"):
        if field not in parsed:
            raise DrafterError("PARSE_MISSING_FIELD", f"field '{field}' ausente")
    effective_confidence, effective_reason = safety.enforce_safety(
        parsed["confidence"], parsed["sources"],
        parsed.get("escalation_reason", ""),
    )
    return {
        "answer": parsed["answer"],
        "sources": parsed["sources"],
        "confidence": effective_confidence,
        "escalation_reason": effective_reason,
        "raw_response": out["raw"][:5000],
        "drafter_model": model,
        "drafter_provider": out["provider_used"],
        "drafter_latency_ms": out["latency_ms"],
    }
```

Observação: **preserva a interface pública** `draft_answer(task_id, question, ctx_bundle, model)`. O parâmetro `provider` default permanece `"claude_cli"` e `model` default permanece `claude-haiku-4-5` — push mode continua idêntico. Novos campos no retorno (`drafter_provider`, `drafter_latency_ms`) são aditivos.

- [ ] **Step 2: Remover `_parse_response` do drafter (movido pra provider)**

Delete a função `_parse_response` do `drafter.py` (já está implementada em `provider._extract_json`).

- [ ] **Step 3: Smoke push mode — `vox clarification ask`**

```bash
# Tu precisa ter uma task blocked disponível. Usa T-0008-clr-1 que já existe:
~/.openclaw/clarification-agent/cli.sh escalations --json
# Pega um task_id, tenta um dry ask
~/.openclaw/clarification-agent/cli.sh ask T-9999-nonexistent \
  --question "test prompt" --json 2>&1 | head -20
```

Expected: erro `TASK_NOT_FOUND` (a task não existe). O importante: **não** quebra com AttributeError/import error. A mudança preserva o shape antigo.

- [ ] **Step 4: Nada a commitar (runtime)**

### Task 5: Test pra chain local-first (local-safe | local-unsafe+cloud-safe | local-unsafe+cloud-unsafe)

**Files:**
- Modify: `~/.openclaw/clarification-agent/tests/test_provider.py` (adicionar class)

- [ ] **Step 1: Adicionar classe `TestDrafterLocalFirst` no arquivo**

Append ao `tests/test_provider.py`:

```python
from lib import drafter as drafter_lib


class TestDrafterLocalFirst(unittest.TestCase):
    """draft_answer com provider local já cobre o caso happy local.
    A escolha local→cloud é orquestrada por draft_answer_local_first
    (criado na task 6). Este test valida apenas o provider switch."""

    def _ctx(self):
        return {
            "task": {"title": "x", "epic_id": "E10", "wave_ref": "w"},
            "dispatch_payload": {"goal": "g", "acceptance_criteria": ["a"],
                                 "files_relevant": [], "guardrails": [],
                                 "out_of_scope": []},
            "read_refs": [{"ref": "s", "path": "~/bevox-knowledge/README.md",
                           "content": "stub"}],
            "unresolved_refs": [],
        }

    def test_provider_param_is_respected(self):
        """Provider local invocado quando passado explicit."""
        raw_json = '{"answer":"ok","sources":["~/bevox-knowledge/README.md"],"confidence":"safe","escalation_reason":""}'
        with patch("lib.provider._run_ollama") as mo, \
             patch("lib.safety.validate_sources") as ms:
            mo.return_value = (raw_json, 1000)
            ms.return_value = (["~/bevox-knowledge/README.md"], [])
            out = drafter_lib.draft_answer(
                "T-1", "q?", ctx_bundle=self._ctx(),
                model="qwen2.5-coder:14b", provider="ollama", timeout=30,
            )
        self.assertEqual(out["drafter_provider"], "ollama")
        self.assertEqual(out["confidence"], "safe")
```

- [ ] **Step 2: Rodar**

```bash
python3 -m unittest tests.test_provider.TestDrafterLocalFirst -v
```

Expected: 1 test PASS.

### Task 6: Implement `drafter.draft_answer_local_first` (chain wrapper)

**Files:**
- Modify: `~/.openclaw/clarification-agent/lib/drafter.py`

- [ ] **Step 1: Adicionar função wrapper**

Append ao `drafter.py`:

```python
def draft_answer_local_first(
    task_id: str, question: str,
    ctx_bundle: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Tenta ollama local (qwen2.5-coder:14b). Em unsafe local, 1 fallback claude cloud.

    Retorna o mesmo shape de draft_answer, com campo extra:
    - `local_first_fallback_used`: bool
    - `local_first_local_confidence`: "safe"|"unsafe"|"error"
    """
    local_result = None
    try:
        local_result = draft_answer(
            task_id, question, ctx_bundle=ctx_bundle,
            model=DRAFTER_MODEL_LOCAL, provider=DRAFTER_PROVIDER_LOCAL,
            timeout=DRAFTER_TIMEOUT_LOCAL,
        )
    except DrafterError as e:
        # Local falhou (timeout, parse fail, exit nonzero) — tenta cloud
        cloud_result = draft_answer(
            task_id, question, ctx_bundle=ctx_bundle,
            model=DRAFTER_MODEL_CLOUD, provider=DRAFTER_PROVIDER_CLOUD,
            timeout=DRAFTER_TIMEOUT_CLOUD,
        )
        cloud_result["local_first_fallback_used"] = True
        cloud_result["local_first_local_confidence"] = "error"
        cloud_result["local_first_local_error"] = f"{e.code}:{e.detail[:100]}"
        return cloud_result

    if local_result["confidence"] == "safe":
        local_result["local_first_fallback_used"] = False
        local_result["local_first_local_confidence"] = "safe"
        return local_result

    # Local unsafe → fallback cloud 1x
    try:
        cloud_result = draft_answer(
            task_id, question, ctx_bundle=ctx_bundle,
            model=DRAFTER_MODEL_CLOUD, provider=DRAFTER_PROVIDER_CLOUD,
            timeout=DRAFTER_TIMEOUT_CLOUD,
        )
    except DrafterError:
        # Cloud também falhou — retorna o local unsafe
        local_result["local_first_fallback_used"] = True
        local_result["local_first_local_confidence"] = "unsafe"
        local_result["local_first_cloud_error"] = "cloud_drafter_failed"
        return local_result

    cloud_result["local_first_fallback_used"] = True
    cloud_result["local_first_local_confidence"] = "unsafe"
    cloud_result["local_first_local_escalation_reason"] = local_result["escalation_reason"]
    return cloud_result
```

- [ ] **Step 2: Adicionar test chain completa em test_provider.py**

```python
class TestLocalFirstChain(unittest.TestCase):
    def _ctx(self):
        return {"task":{},"dispatch_payload":{"goal":"g","acceptance_criteria":["a"],"files_relevant":[],"guardrails":[],"out_of_scope":[]},"read_refs":[],"unresolved_refs":[]}

    def test_local_safe_skips_cloud(self):
        raw = '{"answer":"ok","sources":["~/bevox-knowledge/README.md"],"confidence":"safe","escalation_reason":""}'
        with patch("lib.provider._run_ollama") as mo, \
             patch("lib.provider._run_claude_cli") as mc, \
             patch("lib.safety.validate_sources") as ms:
            mo.return_value = (raw, 1000)
            ms.return_value = (["~/bevox-knowledge/README.md"], [])
            out = drafter_lib.draft_answer_local_first("T-1", "q?", ctx_bundle=self._ctx())
        self.assertFalse(out["local_first_fallback_used"])
        self.assertEqual(out["confidence"], "safe")
        mc.assert_not_called()

    def test_local_unsafe_triggers_cloud(self):
        raw_local = '{"answer":"maybe","sources":[],"confidence":"unsafe","escalation_reason":"ambig"}'
        raw_cloud = '{"answer":"ok-cloud","sources":["~/bevox-knowledge/README.md"],"confidence":"safe","escalation_reason":""}'
        with patch("lib.provider._run_ollama") as mo, \
             patch("lib.provider._run_claude_cli") as mc, \
             patch("lib.safety.validate_sources") as ms:
            mo.return_value = (raw_local, 1100)
            mc.return_value = (raw_cloud, 2100)
            ms.return_value = (["~/bevox-knowledge/README.md"], [])
            out = drafter_lib.draft_answer_local_first("T-1", "q?", ctx_bundle=self._ctx())
        self.assertTrue(out["local_first_fallback_used"])
        self.assertEqual(out["confidence"], "safe")
        self.assertEqual(out["drafter_provider"], "claude_cli")
        self.assertEqual(out["local_first_local_confidence"], "unsafe")
```

- [ ] **Step 3: Rodar**

```bash
python3 -m unittest tests.test_provider.TestLocalFirstChain -v
```

Expected: 2 tests PASS.

---

## Phase 2 — Store support pra poll.jsonl + paths

### Task 7: Adicionar constantes e `append_poll_event` em `store.py`

**Files:**
- Modify: `~/.openclaw/clarification-agent/lib/store.py`

- [ ] **Step 1: Adicionar constantes + função**

No topo de `store.py`, após `SIGNALS_DIR`:

```python
POLL_JSONL = ROOT / "poll.jsonl"
POLL_LOCK = ROOT / "poll.lock"
POLL_DISABLED = ROOT / "poll.disabled"
```

E nova função no final do arquivo:

```python
def append_poll_event(tick_id: str, event: str, payload: Dict[str, Any]) -> None:
    ROOT.mkdir(parents=True, exist_ok=True)
    entry = {
        "ts": now_iso(),
        "tick_id": tick_id,
        "event": event,
        "payload": payload,
    }
    line = json.dumps(entry, ensure_ascii=False) + "\n"
    with open(POLL_JSONL, "a", encoding="utf-8") as f:
        f.write(line)
```

- [ ] **Step 2: Criar `tests/test_store_poll_append.py`**

```python
"""Test store.append_poll_event."""
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from lib import store


class TestAppendPollEvent(unittest.TestCase):
    def test_append_one_line_per_call(self):
        with tempfile.TemporaryDirectory() as d:
            tmp_root = Path(d)
            tmp_jsonl = tmp_root / "poll.jsonl"
            with patch.object(store, "POLL_JSONL", tmp_jsonl), \
                 patch.object(store, "ROOT", tmp_root):
                store.append_poll_event("tick-1", "ev_a", {"k": 1})
                store.append_poll_event("tick-1", "ev_b", {"k": 2})
            lines = tmp_jsonl.read_text().strip().split("\n")
        self.assertEqual(len(lines), 2)
        e0 = json.loads(lines[0])
        self.assertEqual(e0["tick_id"], "tick-1")
        self.assertEqual(e0["event"], "ev_a")
        self.assertEqual(e0["payload"]["k"], 1)


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 3: Rodar**

```bash
cd ~/.openclaw/clarification-agent
python3 -m unittest tests.test_store_poll_append -v
```

Expected: 1 test PASS.

---

## Phase 3 — Poller: pre-filter, fast-fail, dedup

### Task 8: Test skeleton `test_poller.py` — pre-filter `blocked_reason_not_clarification`

**Files:**
- Create: `~/.openclaw/clarification-agent/tests/test_poller.py`

- [ ] **Step 1: Escrever test**

```python
"""Tests poller: pre-filter, fast-fail, dedup."""
import unittest

from lib import poller


def _task(task_id="T-1", status="blocked", blocked=True,
          blocked_reason="clarification_required: ...",
          dispatch_payload=None):
    return {
        "id": task_id,
        "status": status,
        "blocked": blocked,
        "blocked_reason": blocked_reason,
        "dispatch_payload": dispatch_payload or {
            "spec_ref": "35_specs/x.md",
            "acceptance_criteria": ["ac1"],
        },
    }


class TestPrefilter(unittest.TestCase):
    def test_skip_when_not_blocked(self):
        t = _task(blocked=False)
        skip, reason, _ = poller.prefilter(t)
        self.assertTrue(skip)
        self.assertEqual(reason, "not_blocked")

    def test_skip_when_reason_is_execution_failed(self):
        t = _task(blocked_reason="execution_failed: exit 1")
        skip, reason, _ = poller.prefilter(t)
        self.assertTrue(skip)
        self.assertEqual(reason, "blocked_reason_not_clarification")

    def test_skip_when_reason_is_test_failed(self):
        t = _task(blocked_reason="test_failed: AC1 nao passou")
        skip, reason, _ = poller.prefilter(t)
        self.assertTrue(skip)
        self.assertEqual(reason, "blocked_reason_not_clarification")

    def test_keep_when_clarification_required(self):
        t = _task(blocked_reason="clarification_required: qual endpoint?")
        skip, reason, _ = poller.prefilter(t)
        self.assertFalse(skip)


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Rodar (deve falhar)**

```bash
python3 -m unittest tests.test_poller.TestPrefilter -v
```

Expected: FAIL com `ModuleNotFoundError: No module named 'lib.poller'`.

### Task 9: Implementar `lib/poller.py` skeleton + prefilter

**Files:**
- Create: `~/.openclaw/clarification-agent/lib/poller.py`

- [ ] **Step 1: Escrever skeleton**

```python
"""Poller: pull mode do clarification-agent.

Orquestra tick deterministico: pre-filter → fast-fail → context_load →
drafter → resolve. Zero LLM nos caminhos descartados.

Padrão inspirado em dispatcher-agent/lib/cron.py e reaper.py.
"""
import contextlib
import fcntl
import hashlib
import json
import os
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from . import store


CLARIFICATION_PREFIXES = (
    "clarification_required:",
    "clarification_escalation_required:",
)

DEFAULT_BUDGET_PER_TASK_PER_DAY = int(
    os.environ.get("OPENCLAW_CLR_BUDGET_PER_TASK_PER_DAY", "3"),
)


def prefilter(task: Dict[str, Any]) -> Tuple[bool, str, Dict[str, Any]]:
    """Retorna (skip, reason, detail)."""
    if not task.get("blocked"):
        return True, "not_blocked", {}
    reason = task.get("blocked_reason") or ""
    if not any(reason.startswith(p) for p in CLARIFICATION_PREFIXES):
        return True, "blocked_reason_not_clarification", {"blocked_reason": reason[:80]}
    # Further filters (already_pending, budget, dedup, lock) virão em tasks seguintes
    return False, "", {}
```

- [ ] **Step 2: Rodar**

```bash
python3 -m unittest tests.test_poller.TestPrefilter -v
```

Expected: 4 tests PASS.

### Task 10: Expandir prefilter — already_pending

**Files:**
- Modify: `~/.openclaw/clarification-agent/lib/poller.py`
- Modify: `~/.openclaw/clarification-agent/tests/test_poller.py`

- [ ] **Step 1: Adicionar test**

Append em `test_poller.py`:

```python
class TestPrefilterAlreadyPending(unittest.TestCase):
    def test_skip_when_question_exists_without_answer(self):
        import tempfile, os
        from pathlib import Path
        from unittest.mock import patch
        with tempfile.TemporaryDirectory() as d:
            qdir = Path(d) / "questions"
            adir = Path(d) / "answers"
            qdir.mkdir()
            adir.mkdir()
            (qdir / "T-1-clr-1.md").write_text("q")
            with patch("lib.poller.store.QUESTIONS_DIR", qdir), \
                 patch("lib.poller.store.ANSWERS_DIR", adir):
                t = _task()
                skip, reason, _ = poller.prefilter(t)
        self.assertTrue(skip)
        self.assertEqual(reason, "already_pending")

    def test_continue_when_answer_exists(self):
        import tempfile
        from pathlib import Path
        from unittest.mock import patch
        with tempfile.TemporaryDirectory() as d:
            qdir = Path(d) / "questions"
            adir = Path(d) / "answers"
            qdir.mkdir()
            adir.mkdir()
            (qdir / "T-1-clr-1.md").write_text("q")
            (adir / "T-1-clr-1.md").write_text("a")
            with patch("lib.poller.store.QUESTIONS_DIR", qdir), \
                 patch("lib.poller.store.ANSWERS_DIR", adir):
                t = _task()
                skip, reason, _ = poller.prefilter(t)
        self.assertFalse(skip)
```

- [ ] **Step 2: Expandir `prefilter` em `poller.py`**

Modificar função `prefilter` pra checar questions/ vs answers/:

```python
def _has_pending_clarification(task_id: str) -> bool:
    """Task tem clarification com question sem answer correspondente."""
    import re
    pat = re.compile(re.escape(task_id) + r"-clr-(\d+)\.md$")
    if not store.QUESTIONS_DIR.exists():
        return False
    for p in store.QUESTIONS_DIR.iterdir():
        m = pat.match(p.name)
        if not m:
            continue
        answer_path = store.ANSWERS_DIR / p.name
        if not answer_path.exists():
            return True
    return False


def prefilter(task: Dict[str, Any]) -> Tuple[bool, str, Dict[str, Any]]:
    if not task.get("blocked"):
        return True, "not_blocked", {}
    reason = task.get("blocked_reason") or ""
    if not any(reason.startswith(p) for p in CLARIFICATION_PREFIXES):
        return True, "blocked_reason_not_clarification", {"blocked_reason": reason[:80]}
    if _has_pending_clarification(task["id"]):
        return True, "already_pending", {}
    return False, "", {}
```

- [ ] **Step 3: Rodar**

```bash
python3 -m unittest tests.test_poller -v
```

Expected: 6 tests PASS.

### Task 11: Expandir prefilter — budget + dedup_hash

**Files:**
- Modify: `~/.openclaw/clarification-agent/lib/poller.py`
- Modify: `~/.openclaw/clarification-agent/tests/test_poller.py`

- [ ] **Step 1: Tests novos**

```python
class TestPrefilterBudget(unittest.TestCase):
    def test_skip_when_budget_exhausted_today(self):
        today = "2026-04-22"
        t = _task(dispatch_payload={
            "spec_ref": "x", "acceptance_criteria": ["a"],
            "clarification_budget": {"count_today": 3, "day": today, "limit": 3},
        })
        from unittest.mock import patch
        with patch("lib.poller._today_iso", return_value=today):
            skip, reason, _ = poller.prefilter(t)
        self.assertTrue(skip)
        self.assertEqual(reason, "budget_exhausted")

    def test_continue_when_budget_different_day(self):
        from unittest.mock import patch
        t = _task(dispatch_payload={
            "spec_ref": "x", "acceptance_criteria": ["a"],
            "clarification_budget": {"count_today": 3, "day": "2026-04-21", "limit": 3},
        })
        with patch("lib.poller._today_iso", return_value="2026-04-22"):
            skip, reason, _ = poller.prefilter(t)
        self.assertFalse(skip)


class TestPrefilterDedupHash(unittest.TestCase):
    def test_skip_when_hash_matches(self):
        q_hash = poller.compute_dedup_hash("T-1", "qual endpoint?",
                                           {"spec_ref":"x","acceptance_criteria":["a"]})
        t = _task(dispatch_payload={
            "spec_ref": "x", "acceptance_criteria": ["a"],
            "clarification_dedup_hash_last": q_hash,
        })
        skip, reason, _ = poller.prefilter(t, proposed_question="qual endpoint?")
        self.assertTrue(skip)
        self.assertEqual(reason, "dedup_hash_match")
```

- [ ] **Step 2: Expandir poller com `_today_iso`, `compute_dedup_hash`, e ampliar prefilter**

Em `poller.py`:

```python
def _today_iso() -> str:
    return datetime.now(tz=timezone.utc).strftime("%Y-%m-%d")


def compute_dedup_hash(task_id: str, question_text: str,
                       dispatch_payload: Dict[str, Any]) -> str:
    """Hash estável pra dedup. Muda quando task_id, question OR payload-signature muda."""
    sig = {
        "task_id": task_id,
        "question": question_text.strip(),
        "spec_ref": dispatch_payload.get("spec_ref") or "",
        "ac": dispatch_payload.get("acceptance_criteria") or [],
        "goal": (dispatch_payload.get("goal") or "")[:500],
    }
    blob = json.dumps(sig, sort_keys=True, ensure_ascii=False).encode("utf-8")
    return "sha256:" + hashlib.sha256(blob).hexdigest()


def prefilter(
    task: Dict[str, Any], *, proposed_question: Optional[str] = None,
) -> Tuple[bool, str, Dict[str, Any]]:
    if not task.get("blocked"):
        return True, "not_blocked", {}
    reason = task.get("blocked_reason") or ""
    if not any(reason.startswith(p) for p in CLARIFICATION_PREFIXES):
        return True, "blocked_reason_not_clarification", {"blocked_reason": reason[:80]}
    if _has_pending_clarification(task["id"]):
        return True, "already_pending", {}

    payload = task.get("dispatch_payload") or {}
    budget = payload.get("clarification_budget") or {}
    if budget.get("day") == _today_iso() and budget.get("count_today", 0) >= budget.get("limit", DEFAULT_BUDGET_PER_TASK_PER_DAY):
        return True, "budget_exhausted", {"count": budget.get("count_today"), "limit": budget.get("limit")}

    if proposed_question is not None:
        last_hash = payload.get("clarification_dedup_hash_last")
        if last_hash:
            curr_hash = compute_dedup_hash(task["id"], proposed_question, payload)
            if curr_hash == last_hash:
                return True, "dedup_hash_match", {"hash": curr_hash}

    return False, "", {}
```

- [ ] **Step 3: Rodar**

```bash
python3 -m unittest tests.test_poller -v
```

Expected: 9 tests PASS.

### Task 12: Fast-fail payload incompleto

**Files:**
- Modify: `~/.openclaw/clarification-agent/lib/poller.py`
- Modify: `~/.openclaw/clarification-agent/tests/test_poller.py`

- [ ] **Step 1: Test**

Append em `test_poller.py`:

```python
class TestFastFail(unittest.TestCase):
    def test_fast_fail_when_spec_ref_empty(self):
        t = _task(dispatch_payload={"spec_ref": "", "acceptance_criteria": ["a"]})
        fail, missing = poller.is_payload_incomplete(t)
        self.assertTrue(fail)
        self.assertIn("spec_ref", missing)

    def test_fast_fail_when_ac_empty(self):
        t = _task(dispatch_payload={"spec_ref": "x", "acceptance_criteria": []})
        fail, missing = poller.is_payload_incomplete(t)
        self.assertTrue(fail)
        self.assertIn("acceptance_criteria", missing)

    def test_fast_fail_when_both_missing(self):
        t = _task(dispatch_payload={})
        fail, missing = poller.is_payload_incomplete(t)
        self.assertTrue(fail)
        self.assertIn("spec_ref", missing)
        self.assertIn("acceptance_criteria", missing)

    def test_pass_when_both_populated(self):
        t = _task(dispatch_payload={"spec_ref": "x", "acceptance_criteria": ["a"]})
        fail, missing = poller.is_payload_incomplete(t)
        self.assertFalse(fail)
        self.assertEqual(missing, [])
```

- [ ] **Step 2: Implement in `poller.py`**

```python
def is_payload_incomplete(task: Dict[str, Any]) -> Tuple[bool, List[str]]:
    """Detecta payload canonico faltando campos essenciais.

    Retorna (incomplete, missing_fields).
    """
    p = task.get("dispatch_payload") or {}
    missing = []
    spec_ref = p.get("spec_ref")
    if not spec_ref or (isinstance(spec_ref, list) and len(spec_ref) == 0):
        missing.append("spec_ref")
    ac = p.get("acceptance_criteria")
    if not ac or (isinstance(ac, list) and len(ac) == 0):
        missing.append("acceptance_criteria")
    return (len(missing) > 0, missing)
```

- [ ] **Step 3: Rodar**

```bash
python3 -m unittest tests.test_poller -v
```

Expected: 13 tests PASS.

---

## Phase 4 — Tick orchestration + lock + kill-switch

### Task 13: Lock global + kill-switch

**Files:**
- Modify: `~/.openclaw/clarification-agent/lib/poller.py`
- Modify: `~/.openclaw/clarification-agent/tests/test_poller.py`

- [ ] **Step 1: Tests**

```python
class TestLocksAndKillSwitch(unittest.TestCase):
    def test_lock_contention_returns_none(self):
        import tempfile, fcntl
        from pathlib import Path
        from unittest.mock import patch
        with tempfile.TemporaryDirectory() as d:
            lock_path = Path(d) / "poll.lock"
            # Segurando um lock externo
            with open(lock_path, "w") as f:
                fcntl.flock(f, fcntl.LOCK_EX | fcntl.LOCK_NB)
                with patch("lib.poller.store.POLL_LOCK", lock_path):
                    got = poller.try_acquire_lock()
                self.assertIsNone(got)

    def test_killswitch_active(self):
        import tempfile
        from pathlib import Path
        from unittest.mock import patch
        with tempfile.TemporaryDirectory() as d:
            kill = Path(d) / "poll.disabled"
            kill.touch()
            with patch("lib.poller.store.POLL_DISABLED", kill):
                self.assertTrue(poller.killswitch_active())

    def test_killswitch_absent(self):
        import tempfile
        from pathlib import Path
        from unittest.mock import patch
        with tempfile.TemporaryDirectory() as d:
            kill = Path(d) / "poll.disabled"
            with patch("lib.poller.store.POLL_DISABLED", kill):
                self.assertFalse(poller.killswitch_active())
```

- [ ] **Step 2: Implement**

```python
def killswitch_active() -> bool:
    return store.POLL_DISABLED.exists()


@contextlib.contextmanager
def _lock_file(path: Path):
    path.parent.mkdir(parents=True, exist_ok=True)
    f = open(path, "w")
    try:
        try:
            fcntl.flock(f, fcntl.LOCK_EX | fcntl.LOCK_NB)
            yield f
        except BlockingIOError:
            yield None
    finally:
        f.close()


def try_acquire_lock() -> Optional[Any]:
    """Tenta adquirir lock global. Retorna file handle ou None se contention."""
    f = open(store.POLL_LOCK, "w")
    try:
        fcntl.flock(f, fcntl.LOCK_EX | fcntl.LOCK_NB)
        return f
    except BlockingIOError:
        f.close()
        return None
```

- [ ] **Step 3: Rodar**

```bash
python3 -m unittest tests.test_poller -v
```

Expected: 16 tests PASS.

### Task 14: `run_tick` orchestration (dry-run first)

**Files:**
- Modify: `~/.openclaw/clarification-agent/lib/poller.py`
- Modify: `~/.openclaw/clarification-agent/tests/test_poller.py`

- [ ] **Step 1: Test happy path dry-run**

```python
class TestRunTickDryRun(unittest.TestCase):
    def test_dry_run_no_mutations(self):
        import tempfile
        from pathlib import Path
        from unittest.mock import patch
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            jsonl = root / "poll.jsonl"
            with patch("lib.poller.store.POLL_JSONL", jsonl), \
                 patch("lib.poller.store.POLL_LOCK", root / "poll.lock"), \
                 patch("lib.poller.store.POLL_DISABLED", root / "poll.disabled"), \
                 patch("lib.poller.store.QUESTIONS_DIR", root / "questions"), \
                 patch("lib.poller.store.ANSWERS_DIR", root / "answers"), \
                 patch("lib.poller._list_blocked_tasks", return_value=[
                     _task("T-A", dispatch_payload={"spec_ref":"", "acceptance_criteria":[]}),
                     _task("T-B"),
                 ]):
                result = poller.run_tick(once=True, dry_run=True)
        # Dry-run não grava eventos no JSONL
        self.assertFalse(jsonl.exists() and jsonl.stat().st_size > 0)
        self.assertEqual(result["tasks_scanned"], 2)
        self.assertTrue(result["dry_run"])
```

- [ ] **Step 2: Implement `run_tick` + `_list_blocked_tasks` + `make_tick_id`**

```python
def make_tick_id() -> str:
    ts = datetime.now(tz=timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    return f"{ts}-{uuid.uuid4().hex[:8]}"


def _list_blocked_tasks() -> List[Dict[str, Any]]:
    """Lê kanban-tasks state.json e retorna tasks com blocked=True."""
    kanban_state = Path(os.path.expanduser(
        "~/.openclaw/kanban-tasks/state.json"))
    if not kanban_state.exists():
        return []
    try:
        d = json.loads(kanban_state.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return []
    tasks = d.get("tasks") or []
    return [t for t in tasks if t.get("blocked")]


def run_tick(*, once: bool = True, dry_run: bool = False,
             as_json: bool = False) -> Dict[str, Any]:
    import time as _time
    t_mono_start = _time.monotonic()
    tick_id = make_tick_id()

    if killswitch_active():
        if not dry_run:
            store.append_poll_event(tick_id, "tick_skipped_killswitch",
                                    {"killswitch_path": str(store.POLL_DISABLED)})
        return {"tick_id": tick_id, "outcome": "killswitch",
                "dry_run": dry_run, "tasks_scanned": 0}

    lock = try_acquire_lock()
    if lock is None:
        if not dry_run:
            store.append_poll_event(tick_id, "tick_skipped_lock", {})
        return {"tick_id": tick_id, "outcome": "lock_skipped",
                "dry_run": dry_run, "tasks_scanned": 0}

    try:
        if not dry_run:
            store.append_poll_event(tick_id, "tick_started",
                                    {"trigger": "cli", "dry_run": False})
        tasks = _list_blocked_tasks()
        if not dry_run:
            store.append_poll_event(tick_id, "tasks_blocked_scanned",
                                    {"count": len(tasks),
                                     "task_ids": [t["id"] for t in tasks]})

        summary = {
            "tick_id": tick_id, "outcome": "completed",
            "dry_run": dry_run, "tasks_scanned": len(tasks),
            "filtered": 0, "fast_failed": 0,
            "clarified_local": 0, "clarified_cloud": 0,
            "auto_unblocks": 0, "escalations_emitted": 0,
            "decisions": [],
        }

        for task in tasks:
            decision = _process_task(task, tick_id, dry_run=dry_run)
            summary["decisions"].append(decision)
            cat = decision["category"]
            if cat == "filtered": summary["filtered"] += 1
            elif cat == "fast_failed": summary["fast_failed"] += 1
            elif cat == "clarified_local_safe": summary["clarified_local"] += 1; summary["auto_unblocks"] += 1
            elif cat == "clarified_cloud_safe": summary["clarified_cloud"] += 1; summary["auto_unblocks"] += 1
            elif cat.startswith("escalated"): summary["escalations_emitted"] += 1

        if not dry_run:
            duration_ms = int((_time.monotonic() - t_mono_start) * 1000)
            store.append_poll_event(tick_id, "tick_finished", {
                "duration_ms": duration_ms,
                **{k: v for k, v in summary.items() if k != "decisions"},
            })
        return summary
    finally:
        if lock is not None:
            lock.close()


def _process_task(task: Dict[str, Any], tick_id: str, *, dry_run: bool) -> Dict[str, Any]:
    """Placeholder; expansão nas tasks seguintes."""
    skip, reason, detail = prefilter(task)
    if skip:
        if not dry_run:
            store.append_poll_event(tick_id, "poll_skipped_filter", {
                "task_id": task["id"], "reason": reason, "detail": detail,
            })
        return {"task_id": task["id"], "category": "filtered", "reason": reason}
    incomplete, missing = is_payload_incomplete(task)
    if incomplete:
        if not dry_run:
            store.append_poll_event(tick_id, "fast_fail_payload_incomplete", {
                "task_id": task["id"], "missing_fields": missing,
            })
        return {"task_id": task["id"], "category": "fast_failed",
                "missing_fields": missing}
    # LLM path — implementado em tasks seguintes
    return {"task_id": task["id"], "category": "pending_llm"}
```

- [ ] **Step 3: Rodar**

```bash
python3 -m unittest tests.test_poller -v
```

Expected: 17 tests PASS.

### Task 15: Fast-fail path gera escalation real (non-dry-run)

**Files:**
- Modify: `~/.openclaw/clarification-agent/lib/lifecycle.py`
- Modify: `~/.openclaw/clarification-agent/lib/poller.py`

- [ ] **Step 1: Adicionar `emit_payload_incomplete_escalation` em `lifecycle.py`**

Append ao `lifecycle.py`:

```python
def emit_payload_incomplete_escalation(task_id: str, missing_fields: list) -> str:
    """Cria clarification + answer unsafe 'dispatch_payload_incomplete' sem LLM.

    Retorna clarification_id.
    """
    seq = store.next_clarification_seq(task_id)
    cid = store.make_clarification_id(task_id, seq)
    q_text = (f"[AUTO-FAST-FAIL] dispatch_payload incompleto. "
              f"Campos faltando: {missing_fields}")
    qpath = store.write_question(cid, q_text)
    ans_body = (
        "Nenhuma fonte canonica disponivel. "
        f"dispatch_payload esta sem os campos: {missing_fields}. "
        "Scrum-master OR humano upstream deve popular spec_ref + "
        "acceptance_criteria antes de retry."
    )
    store.write_answer(
        cid, qpath, ans_body, "unsafe",
        sources=[],
        drafter="clarification-poller (fast-fail)",
        escalation_reason=f"dispatch_payload_incomplete: missing {missing_fields}",
    )
    store.write_escalation_symlink(cid)
    mark_escalation(task_id, f"dispatch_payload_incomplete: missing {missing_fields}")
    merge_dispatch_payload(task_id, {
        "last_clarification_id": cid,
        "last_clarification_confidence": "unsafe",
        "last_clarification_source": "poller_fast_fail",
        "last_clarification_escalated_at": store.now_iso(),
    })
    return cid
```

- [ ] **Step 2: Integrar `emit_payload_incomplete_escalation` no `_process_task`**

Em `poller.py`, substituir o trecho do fast_fail:

```python
    incomplete, missing = is_payload_incomplete(task)
    if incomplete:
        from . import lifecycle as lc
        if dry_run:
            return {"task_id": task["id"], "category": "fast_failed",
                    "missing_fields": missing, "dry_run": True}
        try:
            cid = lc.emit_payload_incomplete_escalation(task["id"], missing)
        except lc.LifecycleError as e:
            store.append_poll_event(tick_id, "fast_fail_error", {
                "task_id": task["id"], "code": e.code, "detail": e.detail[:200],
            })
            return {"task_id": task["id"], "category": "fast_fail_error"}
        store.append_poll_event(tick_id, "fast_fail_payload_incomplete", {
            "task_id": task["id"], "missing_fields": missing,
            "clarification_id": cid,
        })
        store.append_poll_event(tick_id, "unsafe_escalation_emitted", {
            "task_id": task["id"], "clarification_id": cid,
            "reason": "dispatch_payload_incomplete",
        })
        return {"task_id": task["id"], "category": "fast_failed",
                "missing_fields": missing, "clarification_id": cid}
```

- [ ] **Step 3: Rodar tests + smoke no runtime real**

```bash
python3 -m unittest tests.test_poller -v
```

Expected: todos passam (ainda 17 — não adicionamos tests novos, só mudou código).

### Task 16: LLM path com local-first integration

**Files:**
- Modify: `~/.openclaw/clarification-agent/lib/poller.py`
- Modify: `~/.openclaw/clarification-agent/lib/lifecycle.py`

- [ ] **Step 1: `auto_draft_for_task` no lifecycle**

Append ao `lifecycle.py`:

```python
def extract_question_from_blocked(blocked_reason: str) -> str:
    """Extrai pergunta do blocked_reason (formato 'clarification_required: <pergunta>')."""
    for prefix in ("clarification_required:", "clarification_escalation_required:"):
        if blocked_reason.startswith(prefix):
            return blocked_reason[len(prefix):].strip()
    return blocked_reason.strip()


def auto_draft_for_task(
    task_id: str, question_text: str,
) -> Dict[str, Any]:
    """Pull-mode analog de ask_and_draft, com drafter local-first."""
    seq = store.next_clarification_seq(task_id)
    cid = store.make_clarification_id(task_id, seq)
    qpath = store.write_question(cid, question_text)
    merge_dispatch_payload(task_id, {
        "last_clarification_id": cid,
        "last_clarification_question_path": str(qpath),
        "clarification_count": seq,
        "last_clarification_source": "poller",
    })
    draft = drafter_lib.draft_answer_local_first(task_id, question_text)
    answer_path = store.write_answer(
        cid, qpath,
        draft["answer"], draft["confidence"], draft["sources"],
        drafter=f"clarification-agent ({draft['drafter_model']} via {draft['drafter_provider']})",
        escalation_reason=draft.get("escalation_reason") or None,
    )
    if draft["confidence"] == "safe":
        unblock(task_id)
        merge_dispatch_payload(task_id, {
            "last_clarification_answer_path": str(answer_path),
            "last_clarification_confidence": "safe",
            "last_clarification_resolved_at": store.now_iso(),
            "last_clarification_source": "poller",
        })
        store.emit_signal(cid, "safe")
        return {"clarification_id": cid, "outcome": "safe",
                "answer_path": str(answer_path),
                "fallback_used": draft.get("local_first_fallback_used", False),
                "drafter_provider": draft["drafter_provider"]}
    store.write_escalation_symlink(cid)
    mark_escalation(task_id, draft["escalation_reason"])
    merge_dispatch_payload(task_id, {
        "last_clarification_answer_path": str(answer_path),
        "last_clarification_confidence": "unsafe",
        "last_clarification_escalated_at": store.now_iso(),
    })
    return {"clarification_id": cid, "outcome": "escalated",
            "answer_path": str(answer_path),
            "escalation_reason": draft["escalation_reason"],
            "fallback_used": draft.get("local_first_fallback_used", False),
            "drafter_provider": draft["drafter_provider"]}
```

- [ ] **Step 2: Integrar em `_process_task` (poller.py)**

Substituir o `return {"category": "pending_llm"}` por:

```python
    # LLM path — via local-first drafter
    from . import lifecycle as lc
    question = lc.extract_question_from_blocked(task.get("blocked_reason") or "")

    # Dedup-hash check (agora com proposed_question conhecido)
    skip2, reason2, detail2 = prefilter(task, proposed_question=question)
    if skip2:
        if not dry_run:
            store.append_poll_event(tick_id, "poll_skipped_filter", {
                "task_id": task["id"], "reason": reason2, "detail": detail2,
            })
        return {"task_id": task["id"], "category": "filtered", "reason": reason2}

    if dry_run:
        return {"task_id": task["id"], "category": "pending_llm",
                "dry_run": True, "question": question[:80]}

    try:
        result = lc.auto_draft_for_task(task["id"], question)
    except (lc.LifecycleError, Exception) as e:
        store.append_poll_event(tick_id, "auto_draft_error", {
            "task_id": task["id"], "error": str(e)[:200],
        })
        return {"task_id": task["id"], "category": "auto_draft_error"}

    # Log provider used
    ev_name = "drafter_escalated_to_cloud" if result.get("fallback_used") else "drafter_used_local"
    store.append_poll_event(tick_id, ev_name, {
        "task_id": task["id"],
        "clarification_id": result["clarification_id"],
        "provider_final": result.get("drafter_provider"),
        "outcome": result["outcome"],
    })

    if result["outcome"] == "safe":
        store.append_poll_event(tick_id, "clarification_auto_unblock", {
            "task_id": task["id"],
            "clarification_id": result["clarification_id"],
            "actor": "clarification-poller",
        })
        cat = "clarified_cloud_safe" if result.get("fallback_used") else "clarified_local_safe"
    else:
        store.append_poll_event(tick_id, "unsafe_escalation_emitted", {
            "task_id": task["id"],
            "clarification_id": result["clarification_id"],
            "reason": result.get("escalation_reason", "")[:200],
        })
        cat = "escalated_cloud" if result.get("fallback_used") else "escalated_local"

    return {"task_id": task["id"], "category": cat, **result}
```

- [ ] **Step 3: Rodar tests (não adicionamos novos; validar regressões)**

```bash
python3 -m unittest -v
```

Expected: tests passam.

---

## Phase 5 — CLI wiring + poll-status

### Task 17: `cmd_poll_tick` em `api.py`

**Files:**
- Modify: `~/.openclaw/clarification-agent/lib/api.py`

- [ ] **Step 1: Adicionar função + subparser**

No topo do arquivo (imports), adicionar:
```python
from . import poller as poller_lib
```

No final do arquivo, antes de `def build_parser`:

```python
def cmd_poll_tick(args: argparse.Namespace) -> int:
    result = poller_lib.run_tick(
        once=args.once, dry_run=args.dry_run, as_json=args.json,
    )
    _print(result, args.json,
           f"poll-tick {result['tick_id']}: {result['outcome']} "
           f"(scanned={result.get('tasks_scanned',0)} filtered={result.get('filtered',0)} "
           f"fast_failed={result.get('fast_failed',0)} "
           f"unblocks={result.get('auto_unblocks',0)} "
           f"escalations={result.get('escalations_emitted',0)})")
    return EXIT_OK


def cmd_poll_status(args: argparse.Namespace) -> int:
    """Lê últimas N linhas de poll.jsonl e agrega contadores 24h."""
    from . import store
    if not store.POLL_JSONL.exists():
        _print({"ticks": 0, "last_tick": None}, args.json,
               "(nenhum tick registrado ainda)")
        return EXIT_OK
    import time
    cutoff = time.time() - 86400
    events = []
    with open(store.POLL_JSONL, "r", encoding="utf-8") as f:
        for line in f.readlines()[-5000:]:
            try:
                e = json.loads(line)
            except json.JSONDecodeError:
                continue
            events.append(e)
    counts = {}
    for e in events:
        counts[e["event"]] = counts.get(e["event"], 0) + 1
    last = events[-1] if events else None
    _print({"recent_events_count": len(events), "by_event": counts,
            "last_event": last}, args.json)
    return EXIT_OK
```

Em `build_parser`, adicionar depois de `rd.set_defaults(func=cmd_redraft)`:

```python
    pt = leaf(sub, "poll-tick")
    pt.add_argument("--once", action="store_true", default=True)
    pt.add_argument("--dry-run", action="store_true")
    pt.set_defaults(func=cmd_poll_tick)

    ps = leaf(sub, "poll-status")
    ps.set_defaults(func=cmd_poll_status)
```

- [ ] **Step 2: Smoke CLI**

```bash
~/.openclaw/clarification-agent/cli.sh poll-tick --dry-run --json 2>&1 | head -60
```

Expected: JSON com `tick_id`, `outcome` e lista de `decisions` (em dry-run).

- [ ] **Step 3: Rodar tick real**

```bash
~/.openclaw/clarification-agent/cli.sh poll-tick --json 2>&1 | head -30
```

Expected: tick real — as 3 escalations pendentes T-0006/T-0008 **não** devem ser re-escaladas porque já estão `already_pending`. Verificar em `poll.jsonl`:

```bash
tail -20 ~/.openclaw/clarification-agent/poll.jsonl
```

Expected: eventos `tick_started`, `tasks_blocked_scanned`, `poll_skipped_filter` (reason=already_pending) pra cada clarification em voo.

---

## Phase 6 — Systemd + health

### Task 18: Ship systemd templates

**Files:**
- Create: `~/.openclaw/clarification-agent/systemd/openclaw-clarification-daemon.service`
- Create: `~/.openclaw/clarification-agent/systemd/openclaw-clarification-daemon.timer`

- [ ] **Step 1: Criar service**

```ini
[Unit]
Description=OpenClaw Clarification Daemon (pull mode) — E10 operational-loop-hardening wave-1
After=openclaw-gateway.service

[Service]
Type=oneshot
WorkingDirectory=%h/.openclaw/clarification-agent
ExecStart=%h/.openclaw/clarification-agent/cli.sh poll-tick --once
Environment=PYTHONUNBUFFERED=1
TimeoutStartSec=180
```

- [ ] **Step 2: Criar timer**

```ini
[Unit]
Description=Timer — OpenClaw Clarification Daemon (10min default)

[Timer]
OnBootSec=120
OnUnitActiveSec=600
AccuracySec=10s
Persistent=true

[Install]
WantedBy=timers.target
```

- [ ] **Step 3: Instalação manual (Bernard executa pós-aprovação)**

```bash
mkdir -p ~/.config/systemd/user
cp ~/.openclaw/clarification-agent/systemd/*.{service,timer} ~/.config/systemd/user/
systemctl --user daemon-reload
systemctl --user enable --now openclaw-clarification-daemon.timer
systemctl --user list-timers | grep clarification
```

Expected: timer listed, próximo tick em ≤ 120s.

### Task 19: Entrada em health registry

**Files:**
- Modify: `~/.openclaw/health/registry.yml`

- [ ] **Step 1: Ler entrada atual (para ver formato)**

```bash
grep -A 5 "openclaw-cron-dispatcher" ~/.openclaw/health/registry.yml
```

- [ ] **Step 2: Adicionar entrada**

Append no registry.yml (mesmo formato):

```yaml
  - id: openclaw-clarification-daemon
    name: "OpenClaw Clarification Daemon (pull)"
    epic: "E10"
    critical: false
    check_type: "systemd_active"
    systemd_unit: "openclaw-clarification-daemon.timer"
```

- [ ] **Step 3: Trigger health check + validar**

```bash
systemctl --user start openclaw-health-check.service
sleep 5
jq '.services["openclaw-clarification-daemon"]' ~/.openclaw/health/state.json
```

Expected: entry com `status: up` (se timer já foi enabled).

---

## Phase 7 — Coexistência bevox-mobile

### Task 20: clarification_lock em `lifecycle.py`

**Files:**
- Modify: `~/.openclaw/clarification-agent/lib/lifecycle.py`

- [ ] **Step 1: Adicionar helpers**

Append:

```python
def acquire_clarification_lock(task_id: str, holder: str = "clarification-poller") -> bool:
    """Tenta reservar clarification_lock no dispatch_payload. Retorna True se conseguiu."""
    from . import store
    # Best-effort check: se ja existe lock de outro holder ha < 10min, respeita
    state_path = Path(os.path.expanduser("~/.openclaw/kanban-tasks/state.json"))
    import os
    try:
        d = json.loads(state_path.read_text())
        for t in d.get("tasks") or []:
            if t.get("id") == task_id:
                lock = (t.get("dispatch_payload") or {}).get("clarification_lock") or {}
                existing_holder = lock.get("holder")
                if existing_holder and existing_holder != holder:
                    # Assume lock valido por 10min
                    from datetime import datetime, timezone, timedelta
                    aq = lock.get("acquired_at")
                    if aq:
                        try:
                            aq_dt = datetime.fromisoformat(aq.replace("Z", "+00:00"))
                            if datetime.now(tz=timezone.utc) - aq_dt < timedelta(minutes=10):
                                return False
                        except (ValueError, TypeError):
                            pass
                break
    except (OSError, json.JSONDecodeError):
        pass
    merge_dispatch_payload(task_id, {
        "clarification_lock": {
            "holder": holder,
            "acquired_at": store.now_iso(),
        },
    })
    return True


def release_clarification_lock(task_id: str) -> None:
    merge_dispatch_payload(task_id, {"clarification_lock": None})
```

- [ ] **Step 2: Integrar `acquire_clarification_lock` em `_process_task` ANTES de chamar auto_draft**

Em `poller.py`, dentro do bloco LLM path, ANTES de `auto_draft_for_task`:

```python
    if not lc.acquire_clarification_lock(task["id"], holder="clarification-poller"):
        if not dry_run:
            store.append_poll_event(tick_id, "poll_skipped_filter", {
                "task_id": task["id"], "reason": "lock_held_elsewhere", "detail": {},
            })
        return {"task_id": task["id"], "category": "filtered",
                "reason": "lock_held_elsewhere"}
```

- [ ] **Step 3: Smoke manual**

```bash
# Simula bevox-mobile pegando lock primeiro
~/.openclaw/kanban-tasks/cli.sh task set-dispatch-payload T-0006 \
  --payload '{"clarification_lock": {"holder":"bevox-mobile-scripts","acquired_at":"'"$(date -u +%Y-%m-%dT%H:%M:%SZ)"'"}}' \
  --merge --actor test

# Tenta poll-tick — deve skipar T-0006 com reason lock_held_elsewhere
~/.openclaw/clarification-agent/cli.sh poll-tick --json | jq '.decisions[] | select(.task_id=="T-0006")'

# Cleanup
~/.openclaw/kanban-tasks/cli.sh task set-dispatch-payload T-0006 \
  --payload '{"clarification_lock": null}' --merge --actor test
```

Expected: `{"task_id":"T-0006","category":"filtered","reason":"lock_held_elsewhere"}`.

### Task 21: Patch `bevox-mobile/scripts/request-clarification.sh`

**Files:**
- Modify: `~/.openclaw/bevox-mobile/scripts/request-clarification.sh`

- [ ] **Step 1: Ler script atual**

```bash
cat ~/.openclaw/bevox-mobile/scripts/request-clarification.sh
```

- [ ] **Step 2: Adicionar check de clarification_lock no topo (após parse de args)**

Adicionar (ajustar posição conforme script atual — depois que `TASK_ID` é setado):

```bash
# Dedup lock com clarification-agent canonico (ADR-009)
LOCK_HOLDER=$(~/.openclaw/kanban-tasks/cli.sh task show "$TASK_ID" --json 2>/dev/null | \
  python3 -c "import sys,json; d=json.load(sys.stdin); print((d.get('dispatch_payload') or {}).get('clarification_lock',{}).get('holder') or '')")

if [ "$LOCK_HOLDER" = "clarification-poller" ]; then
  echo "[skip] clarification-agent canonico ja processando $TASK_ID" >&2
  echo "skipped_canonical_took_over" >> ~/.openclaw/bevox-mobile/clarifications/log.txt
  exit 0
fi
```

- [ ] **Step 3: Smoke — forçar canonico tomar lock e rodar o script**

```bash
# Tomar lock como poller
~/.openclaw/kanban-tasks/cli.sh task set-dispatch-payload T-0006 \
  --payload '{"clarification_lock":{"holder":"clarification-poller","acquired_at":"'"$(date -u +%Y-%m-%dT%H:%M:%SZ)"'"}}' \
  --merge --actor test

# Rodar script deveria detectar e skipar
bash ~/.openclaw/bevox-mobile/scripts/request-clarification.sh T-0006 2>&1 | head -5

# Cleanup
~/.openclaw/kanban-tasks/cli.sh task set-dispatch-payload T-0006 \
  --payload '{"clarification_lock": null}' --merge --actor test
```

Expected: script sai com exit 0 e mensagem "skipped_canonical_took_over".

---

## Phase 8 — Smoke E2E

### Task 22: Criar `smoke_e2e.sh` com 14 cenários da spec

**Files:**
- Create: `~/.openclaw/clarification-agent/smoke_e2e.sh`

- [ ] **Step 1: Escrever script (estrutura)**

Cada cenário em função. Executa → checa output → conta pass/fail. Finaliza com sumário.

```bash
#!/bin/bash
# Smoke E2E — clarification-daemon-local-first wave-1
# Cobre 14 cenários da spec 2026-04-21-e10-clarification-daemon-local-first §10.
set -u

PASS=0
FAIL=0
FAILED_NAMES=()

_ok()   { echo "  ✓ $1"; PASS=$((PASS+1)); }
_fail() { echo "  ✗ $1"; FAIL=$((FAIL+1)); FAILED_NAMES+=("$1"); }

CLI=~/.openclaw/clarification-agent/cli.sh
KANBAN=~/.openclaw/kanban-tasks/cli.sh
POLL_JSONL=~/.openclaw/clarification-agent/poll.jsonl

# ========= Cenário 1: Happy path pull local-safe =========
echo "=== 1. Happy pull local-safe ==="
# (Requer task preparada; neste skeleton apenas placeholder operacional)
# Em execução real, cria T-SMOKE-1 blocked com spec_ref válida + question.
# Roda poll-tick, confere event drafter_used_local e auto_unblock.

# ========= Cenário 3: Fast-fail payload vazio =========
echo "=== 3. Fast-fail payload vazio ==="
# Usa T-0006/T-0008 existentes que ja tem payload vazio.
# Limpa clarifications pendentes antes pra permitir re-processamento (simulado).

# ... (cenários 2, 4-14 seguindo padrão, com setups específicos)

echo "===================="
echo "PASS: $PASS / FAIL: $FAIL"
[ $FAIL -eq 0 ] && exit 0
echo "Failed: ${FAILED_NAMES[@]}"
exit 1
```

- [ ] **Step 2: Tornar executável**

```bash
chmod +x ~/.openclaw/clarification-agent/smoke_e2e.sh
```

### Task 23: Implementar cenários 1-7 no smoke (primeiros 7 da spec §10)

- [ ] **Step 1: Cenário 3 (fast-fail real)**

```bash
_scenario_fast_fail() {
    # Usa task T-SMOKE-FASTFAIL: criada com blocked + clarification_required + payload vazio
    TID="T-SMOKE-FF-$(date +%s)"
    $KANBAN task new --id "$TID" --project openclaw --title "smoke fast-fail" --goal "" \
        --actor smoke > /dev/null 2>&1 || true
    $KANBAN task block "$TID" --reason "clarification_required: payload vazio intencional" --actor smoke
    # Garante payload vazio
    $KANBAN task set-dispatch-payload "$TID" --payload '{"spec_ref":"","acceptance_criteria":[]}' --merge --actor smoke

    TICK_OUT=$($CLI poll-tick --json)
    FAST_FAILED=$(echo "$TICK_OUT" | python3 -c "import sys,json;d=json.load(sys.stdin);print(d.get('fast_failed',0))")
    if [ "$FAST_FAILED" -ge 1 ]; then _ok "fast_fail emitiu escalation sem LLM"
    else _fail "fast_fail não detectado"; fi

    # Cleanup
    $KANBAN task move "$TID" rejected --reason "manual: smoke cleanup" --actor smoke --force > /dev/null 2>&1 || true
}
_scenario_fast_fail
```

- [ ] **Step 2: Cenário 4 (pre-filter non-clarification)**

Similar pattern; task blocked com reason `execution_failed` → expected skip `blocked_reason_not_clarification`.

- [ ] **Step 3: Cenário 8 (lock contention)**

```bash
_scenario_lock_contention() {
    # Roda 2 poll-tick em paralelo
    $CLI poll-tick --json > /tmp/tick-a.json &
    PID_A=$!
    $CLI poll-tick --json > /tmp/tick-b.json &
    PID_B=$!
    wait $PID_A; wait $PID_B
    # Um dos dois deve ter outcome=lock_skipped
    A=$(jq -r '.outcome' /tmp/tick-a.json)
    B=$(jq -r '.outcome' /tmp/tick-b.json)
    if [ "$A" = "lock_skipped" ] || [ "$B" = "lock_skipped" ]; then
        _ok "fcntl lock previniu concorrencia"
    else
        _fail "nenhum tick reportou lock_skipped"
    fi
}
```

- [ ] **Step 4: Cenário 9 (kill-switch)**

```bash
_scenario_killswitch() {
    touch ~/.openclaw/clarification-agent/poll.disabled
    OUT=$($CLI poll-tick --json)
    OUTCOME=$(echo "$OUT" | jq -r '.outcome')
    rm ~/.openclaw/clarification-agent/poll.disabled
    if [ "$OUTCOME" = "killswitch" ]; then _ok "killswitch detectado"
    else _fail "killswitch nao respeitado"; fi
}
```

### Task 24: Cenários 10-14 (push regression + dry-run + local down + --provider override)

- [ ] **Step 1: Cenário 10 (dry-run zero mutação)**

```bash
_scenario_dryrun() {
    BEFORE_LINES=$(wc -l < $POLL_JSONL 2>/dev/null || echo 0)
    $CLI poll-tick --dry-run --json > /dev/null
    AFTER_LINES=$(wc -l < $POLL_JSONL 2>/dev/null || echo 0)
    if [ "$AFTER_LINES" = "$BEFORE_LINES" ]; then
        _ok "dry-run nao grava em poll.jsonl"
    else
        _fail "dry-run gravou em poll.jsonl"
    fi
}
```

- [ ] **Step 2: Cenário 12 (push mode regression)**

```bash
_scenario_push_regression() {
    # Usa um task_id que nao existe; espera erro TASK_NOT_FOUND
    OUT=$($CLI ask T-NONEXISTENT-$(date +%s) --question "test" --json 2>&1 | tail -1)
    CODE=$(echo "$OUT" | jq -r '.code' 2>/dev/null || echo "")
    if [ "$CODE" = "TASK_NOT_FOUND" ]; then
        _ok "push mode (ask) ainda retorna TASK_NOT_FOUND"
    else
        _fail "push mode retornou shape inesperado: $OUT"
    fi
}
```

- [ ] **Step 3: Cenário 13 (local ollama down)**

Cenário requer parar ollama. Documenta como manual:

```bash
_scenario_ollama_down_manual() {
    echo "  (manual) Parar ollama (systemctl stop ollama), rodar poll-tick, verificar fallback cloud ou graceful error."
    echo "  (manual) Retomar ollama pos-teste."
    # Pular automático — apenas documentar.
}
```

- [ ] **Step 4: Rodar smoke completo**

```bash
bash ~/.openclaw/clarification-agent/smoke_e2e.sh 2>&1 | tail -30
```

Expected: todos ✓; `PASS: N / FAIL: 0`.

---

## Phase 9 — Docs + handoff

### Task 25: Update playbook.md do clarification-agent

**Files:**
- Modify: `~/.openclaw/clarification-agent/playbook.md`

- [ ] **Step 1: Adicionar seção "Pull mode (daemon)"**

Append após seção "Playbook operacional":

```markdown
## Pull mode (daemon) — ADR-009 + E10 wave-1 operational-loop-hardening

Desde 2026-04-21 o clarification-agent opera em 2 modos:

- **Push** (CLI `ask` invocada por Claude Code): intocada.
- **Pull** (subcomando `poll-tick` via systemd timer 10min): novo.

### Comando novo

- `vox clarification poll-tick [--once] [--dry-run] [--json]`
- `vox clarification poll-status [--json]`

### Pipeline do tick

1. Kill-switch check (`poll.disabled`) + fcntl lock global (`poll.lock`).
2. Lista tasks `blocked=true` do kanban state.json.
3. Pre-filter determinístico (skip non-clarification reason, already-pending, budget, dedup-hash, lock).
4. Fast-fail em payload incompleto → escalation `dispatch_payload_incomplete` zero-LLM.
5. LLM path local-first (ollama/qwen2.5-coder:14b) → fallback cloud 1x em unsafe.
6. Resolve: safe→auto-unblock; unsafe→escalation + hook `unsafe_escalation_emitted`.
7. Audit append-only em `poll.jsonl`.

### Observabilidade

- Events de interesse no `poll.jsonl`: `tick_started`, `drafter_used_local`, `drafter_escalated_to_cloud`, `fast_fail_payload_incomplete`, `clarification_auto_unblock`, `unsafe_escalation_emitted`, `tick_finished`.
- Health: service `openclaw-clarification-daemon` registrado em `~/.openclaw/health/registry.yml`.

### Rollback

- Desabilitar timer: `systemctl --user disable --now openclaw-clarification-daemon.timer`.
- Forçar cloud: env var `OPENCLAW_DRAFTER_PROVIDER=claude_cli` no service unit.
- Killswitch temporário: `touch ~/.openclaw/clarification-agent/poll.disabled`.
```

### Task 26: Header supersession na spec bevox-mobile-auto-unblock

**Files:**
- Modify: `bevox-knowledge/35_specs/2026-04-21-bevox-mobile-auto-unblock.md`

- [ ] **Step 1: Adicionar header no topo do arquivo**

Substituir a linha `**Status:** draft` por:

```markdown
**Status:** superseded by ADR-009 + `35_specs/2026-04-21-e10-clarification-daemon-local-first.md`

> **Nota 2026-04-22:** Esta spec foi substituída pela consolidação canônica
> em ADR-009. Coexistência Fase A vigente; Fase C (dia 14+) move scripts pra
> `~/.openclaw/_retired/bevox-mobile-auto-unblock-2026-04-21/`. Ver §8 da
> spec superseding.
```

- [ ] **Step 2: Commitar no bevox-knowledge (draft branch já existe)**

```bash
cd ~/bevox-knowledge
git checkout draft/adr-009-clarification-daemon
git add 35_specs/2026-04-21-bevox-mobile-auto-unblock.md
git commit -m "spec: mark bevox-mobile-auto-unblock superseded by ADR-009

Consolidacao canonica em clarification-daemon-local-first. Fase A
coexistencia; Fase C dia 14+ archive scripts."
```

### Task 27: Atualizar status doc do bevox-mobile-auto-unblock

**Files:**
- Modify: `bevox-knowledge/20_architecture/agents/bevox-mobile-auto-unblock-status.md`

- [ ] **Step 1: Adicionar header "deprecated" + linkar canonical path**

No topo do arquivo (após título):

```markdown
> **⚠️ DEPRECATED 2026-04-22:** Substituído por ADR-009 (clarification-daemon-local-first).
> MVP local mantido em coexistência Fase A → Fase C dia 14+. Artefatos migram pra
> `~/.openclaw/_retired/bevox-mobile-auto-unblock-2026-04-21/`. Status operacional canônico:
> `~/.openclaw/clarification-agent/poll.jsonl`.
```

- [ ] **Step 2: Commit no bevox-knowledge**

```bash
cd ~/bevox-knowledge
git add 20_architecture/agents/bevox-mobile-auto-unblock-status.md
git commit -m "docs: mark bevox-mobile-auto-unblock status as deprecated

Aponta para clarification-daemon-local-first como canonical."
```

### Task 28: Delivery snapshot pós-wave

**Files:**
- Delivery snapshot (não é git; é runtime log)

- [ ] **Step 1: Registrar delivery local**

```bash
# Pequeno registro local de entrega pra referência futura
cat >> ~/.openclaw/clarification-agent/README.md <<EOF

---

## 2026-04-22 — Wave-1 delivered

Daemon pull mode + local-first drafter em produção.
Spec: \`bevox-knowledge/35_specs/2026-04-21-e10-clarification-daemon-local-first.md\`
ADR: \`bevox-knowledge/30_adr/ADR-009-clarification-loop-unified-local-first.md\`
EOF
```

- [ ] **Step 2: Atualizar delivery-tracker.yml (draft branch bevox-knowledge)**

Em `40_roadmap/delivery-tracker.yml`, adicionar entrada nova em E10:

```yaml
      - id: clarification-daemon-local-first
        status: delivered
        delivered_at: 2026-04-22
        spec: 35_specs/2026-04-21-e10-clarification-daemon-local-first.md
        adr: 30_adr/ADR-009-clarification-loop-unified-local-first.md
        narrative: "Operational Loop Hardening 2026-04-21 — wave-1 de 6"
        features:
          - "clarification-agent ganha subcomando poll-tick (systemd timer 10min)"
          - "drafter refatorado para provider abstraction (ollama local-first + claude cloud fallback)"
          - "pre-filter deterministico (non_clarification_reason, already_pending, budget, dedup_hash, lock_held_elsewhere)"
          - "fast-fail em dispatch_payload vazio (zero LLM pra casos T-0006/T-0008-like)"
          - "14 eventos novos em poll.jsonl (append-only separado do push mode)"
          - "plano deprecacao bevox-mobile/scripts (Fase A coexistencia + Fase C dia 14 move _retired/)"
```

- [ ] **Step 3: Commit no bevox-knowledge**

```bash
cd ~/bevox-knowledge
git add 40_roadmap/delivery-tracker.yml
git commit -m "delivery: E10/clarification-daemon-local-first wave-1 delivered

Operational Loop Hardening 2026-04-21 wave-1 de 6.
ADR-009 aceita + spec implementada + smoke E2E validado."
```

---

## Self-review final

Rodar **antes de considerar a wave entregue**:

- [ ] `cd ~/.openclaw/clarification-agent && python3 -m unittest discover tests -v` — todos tests passam
- [ ] `bash ~/.openclaw/clarification-agent/smoke_e2e.sh` — PASS: N / FAIL: 0
- [ ] `~/.openclaw/clarification-agent/cli.sh escalations --json` — lista as escalations pendentes esperadas (inclui fast-fail se T-0006/T-0008 re-processadas)
- [ ] `systemctl --user status openclaw-clarification-daemon.timer` — active, last-trigger recente
- [ ] `jq '.services["openclaw-clarification-daemon"]' ~/.openclaw/health/state.json` — status: up
- [ ] Coexistência: rodar bevox-mobile/scripts e confirmar "skipped_canonical_took_over" em `~/.openclaw/bevox-mobile/clarifications/log.txt`
- [ ] Custo observado: `tail -200 ~/.openclaw/clarification-agent/poll.jsonl | jq -s '[.[] | select(.event=="drafter_escalated_to_cloud")] | length'` — contador baixo (indicando local-first funcionando)

**Não declarar wave delivered sem todos os 7 checks acima passando.**
