# Dispatcher Telegram Notifier — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Emitir Telegram `task_done` / `task_failed` quando o dispatcher finaliza uma execução, com fail-safe (env-gated, graceful, jsonl audit).

**Architecture:** Novo módulo `dispatcher-agent/lib/notifier.py` (stdlib-only, padrão espelhado do `clarification-agent/lib/notifier.py`). Hook em `lifecycle.process_finished_session` após os dois branches terminais (`auto_move_to_testing` / `mark_execution_failed`). Sem state persistente próprio (jsonl append-only).

**Tech Stack:** Python 3 stdlib (`urllib.request`, `json`, `os`, `subprocess` pra lookup kanban), `unittest` + `unittest.mock` para testes. Sem dependências externas.

**Spec:** `bevox-knowledge/35_specs/openclaw/2026-04-24-dispatcher-telegram-notifier.md`

---

## File Structure

### Create
- `dispatcher-agent/tests/__init__.py` — marker vazio
- `dispatcher-agent/tests/test_notifier.py` — 4 testes unittest
- `dispatcher-agent/lib/notifier.py` — módulo novo (~120 linhas)

### Modify
- `dispatcher-agent/lib/lifecycle.py` — hook em `process_finished_session` (2 call sites)
- `dispatcher-agent/README.md` — documentar env vars novas

---

## Task 1: Scaffold tests dir + test stub

**Files:**
- Create: `dispatcher-agent/tests/__init__.py`
- Create: `dispatcher-agent/tests/test_notifier.py` (stub only)

- [ ] **Step 1: Criar diretório tests e marker**

```bash
mkdir -p ~/.openclaw/dispatcher-agent/tests
touch ~/.openclaw/dispatcher-agent/tests/__init__.py
```

- [ ] **Step 2: Criar test file com imports e skeleton**

Write `~/.openclaw/dispatcher-agent/tests/test_notifier.py`:

```python
"""Testes dispatcher-agent notifier — Telegram task_done/task_failed."""
import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch, MagicMock

from lib import notifier


class TestSendTaskEvent(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.jsonl = Path(self.tmp) / "notifier.jsonl"
        self.patcher = patch.object(notifier, "JSONL_PATH", self.jsonl)
        self.patcher.start()

    def tearDown(self):
        self.patcher.stop()
        import shutil
        shutil.rmtree(self.tmp)


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 3: Rodar suite pra confirmar import fail (notifier ainda não existe)**

Run: `cd ~/.openclaw/dispatcher-agent && python -m unittest tests.test_notifier -v`
Expected: `ImportError: cannot import name 'notifier' from 'lib'`

- [ ] **Step 4: Commit**

```bash
cd ~/.openclaw && git add dispatcher-agent/tests/__init__.py dispatcher-agent/tests/test_notifier.py && git commit -m "$(cat <<'EOF'
test(dispatcher): scaffold tests/ + test_notifier stub

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 2: Test 1 (env missing → noop) + minimal notifier

**Files:**
- Create: `dispatcher-agent/lib/notifier.py`
- Modify: `dispatcher-agent/tests/test_notifier.py`

- [ ] **Step 1: Escrever teste env-missing**

Adicionar ao `test_notifier.py` (dentro de `class TestSendTaskEvent`):

```python
    def test_env_vars_missing_is_noop(self):
        """Sem env vars → retorna sem HTTP call + jsonl event skipped."""
        ctx = {"project": "bevox-mobile", "title": "test", "log_path": "/tmp/x"}
        with patch.dict(os.environ, {}, clear=True):
            with patch.object(notifier, "_send_http") as mock_http:
                notifier.send_task_event("T-0001", "done", context=ctx)
                mock_http.assert_not_called()
        events = [json.loads(l) for l in self.jsonl.read_text().splitlines()]
        self.assertEqual(len(events), 1)
        self.assertTrue(events[0]["event"].startswith("skipped"))
        self.assertEqual(events[0]["task_id"], "T-0001")

    def test_env_thread_not_int_is_noop(self):
        """THREAD_ID não-numérico → skipped:env_invalid."""
        ctx = {"project": "p", "title": "t", "log_path": "/tmp/x"}
        env = {
            "TELEGRAM_BOT_TOKEN": "tok",
            "OPENCLAW_DISPATCHER_TELEGRAM_CHAT_ID": "-100",
            "OPENCLAW_DISPATCHER_TELEGRAM_THREAD_ID": "NOT_INT",
        }
        with patch.dict(os.environ, env, clear=True):
            with patch.object(notifier, "_send_http") as mock_http:
                notifier.send_task_event("T-0001", "done", context=ctx)
                mock_http.assert_not_called()
        events = [json.loads(l) for l in self.jsonl.read_text().splitlines()]
        self.assertEqual(events[-1]["event"], "skipped:env_invalid")
```

- [ ] **Step 2: Rodar teste (deve falhar: notifier não existe)**

Run: `cd ~/.openclaw/dispatcher-agent && python -m unittest tests.test_notifier -v`
Expected: `ImportError`.

- [ ] **Step 3: Criar notifier.py com implementação mínima**

Write `~/.openclaw/dispatcher-agent/lib/notifier.py`:

```python
"""Dispatcher Telegram notifier — emit task_done / task_failed.

Graceful, env-gated. Failures never raise to caller. Audit trail in
notifier.jsonl (append-only).

Spec: bevox-knowledge/35_specs/openclaw/2026-04-24-dispatcher-telegram-notifier.md
"""
from __future__ import annotations

import json
import os
import sys
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Literal, Optional, Tuple

JSONL_PATH = Path("~/.openclaw/dispatcher-agent/notifier.jsonl")
_TELEGRAM_API = "https://api.telegram.org/bot{token}/sendMessage"
_HTTP_TIMEOUT = 10.0
_REQUIRED_ENV = (
    "TELEGRAM_BOT_TOKEN",
    "OPENCLAW_DISPATCHER_TELEGRAM_CHAT_ID",
    "OPENCLAW_DISPATCHER_TELEGRAM_THREAD_ID",
)


def _now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _append_jsonl(event: str, task_id: str, outcome: str, detail: dict) -> None:
    try:
        JSONL_PATH.parent.mkdir(parents=True, exist_ok=True)
        record = {
            "ts": _now_iso(),
            "event": event,
            "task_id": task_id,
            "outcome": outcome,
            "detail": detail,
        }
        with JSONL_PATH.open("a", encoding="utf-8") as f:
            f.write(json.dumps(record, ensure_ascii=False) + "\n")
    except OSError as e:
        print(f"notifier.jsonl write failed: {e}", file=sys.stderr)


def _validate_env() -> Optional[Tuple[str, str, int]]:
    missing = [k for k in _REQUIRED_ENV if not os.environ.get(k)]
    if missing:
        return None
    raw_thread = os.environ["OPENCLAW_DISPATCHER_TELEGRAM_THREAD_ID"]
    try:
        thread_id = int(raw_thread)
    except (TypeError, ValueError):
        return ("__invalid__", "", 0)  # sentinel para distinguir missing vs invalid
    return (
        os.environ["TELEGRAM_BOT_TOKEN"],
        os.environ["OPENCLAW_DISPATCHER_TELEGRAM_CHAT_ID"],
        thread_id,
    )


def _send_http(url: str, payload: bytes) -> Tuple[bool, dict]:
    req = urllib.request.Request(
        url, data=payload,
        headers={"Content-Type": "application/json; charset=utf-8"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=_HTTP_TIMEOUT) as resp:
            raw = resp.read().decode("utf-8")
            parsed = json.loads(raw)
        if parsed.get("ok") is True:
            return True, {"message_id": parsed.get("result", {}).get("message_id")}
        return False, {"error": "telegram_api_not_ok", "body": parsed}
    except urllib.error.HTTPError as e:
        return False, {"error": f"telegram_api_{e.code}", "detail": str(e)}
    except urllib.error.URLError as e:
        return False, {"error": "telegram_api_network", "detail": str(e.reason)}
    except (OSError, json.JSONDecodeError, TimeoutError) as e:
        return False, {"error": "telegram_api_exception", "detail": str(e)}


def send_task_event(
    task_id: str,
    outcome: Literal["done", "failed"],
    *,
    context: dict,
) -> None:
    """Emit Telegram message for task terminal state. Graceful."""
    env = _validate_env()
    if env is None:
        _append_jsonl("skipped:env_missing", task_id, outcome, {})
        return
    if env[0] == "__invalid__":
        _append_jsonl("skipped:env_invalid", task_id, outcome, {})
        return
    # Stub happy path — implemented in Task 3.
    _append_jsonl("task_event_sent", task_id, outcome, {"stub": True})
```

- [ ] **Step 4: Rodar testes (deve passar)**

Run: `cd ~/.openclaw/dispatcher-agent && python -m unittest tests.test_notifier -v`
Expected: `test_env_vars_missing_is_noop ... ok`, `test_env_thread_not_int_is_noop ... ok`.

- [ ] **Step 5: Commit**

```bash
cd ~/.openclaw && git add dispatcher-agent/lib/notifier.py dispatcher-agent/tests/test_notifier.py && git commit -m "$(cat <<'EOF'
feat(dispatcher/notifier): env-gated skeleton + env-missing noop

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 3: Tests 2 & 3 (done + failed message format) + happy path

**Files:**
- Modify: `dispatcher-agent/lib/notifier.py`
- Modify: `dispatcher-agent/tests/test_notifier.py`

- [ ] **Step 1: Escrever testes de formato**

Adicionar ao `test_notifier.py`:

```python
    def _full_env(self):
        return {
            "TELEGRAM_BOT_TOKEN": "tok-abc",
            "OPENCLAW_DISPATCHER_TELEGRAM_CHAT_ID": "-1001234567890",
            "OPENCLAW_DISPATCHER_TELEGRAM_THREAD_ID": "42",
        }

    def test_done_message_format(self):
        ctx = {
            "project": "bevox-mobile",
            "title": "Implementar feature X",
            "log_path": "~/.openclaw/dispatcher-agent/executions/T-0001.log",
        }
        with patch.dict(os.environ, self._full_env(), clear=True):
            with patch.object(notifier, "_send_http", return_value=(True, {"message_id": 99})) as mock_http:
                notifier.send_task_event("T-0001", "done", context=ctx)
                self.assertEqual(mock_http.call_count, 1)
                url, payload = mock_http.call_args.args
                self.assertIn("/bottok-abc/sendMessage", url)
                body = json.loads(payload.decode("utf-8"))
                self.assertEqual(body["chat_id"], "-1001234567890")
                self.assertEqual(body["message_thread_id"], 42)
                self.assertIn("✅", body["text"])
                self.assertIn("T-0001", body["text"])
                self.assertIn("bevox-mobile", body["text"])
                self.assertIn("Implementar feature X", body["text"])
                self.assertIn("T-0001.log", body["text"])

    def test_failed_message_format(self):
        ctx = {
            "project": "bevox-backend",
            "title": "Fix bug Y",
            "log_path": "/tmp/T-0002.log",
            "failure_reason": "ImportError: no module foo",
            "exit_code": 1,
        }
        with patch.dict(os.environ, self._full_env(), clear=True):
            with patch.object(notifier, "_send_http", return_value=(True, {"message_id": 100})) as mock_http:
                notifier.send_task_event("T-0002", "failed", context=ctx)
                body = json.loads(mock_http.call_args.args[1].decode("utf-8"))
                self.assertIn("❌", body["text"])
                self.assertIn("T-0002", body["text"])
                self.assertIn("bevox-backend", body["text"])
                self.assertIn("Fix bug Y", body["text"])
                self.assertIn("ImportError", body["text"])
                self.assertIn("exit: 1", body["text"])
```

- [ ] **Step 2: Rodar testes (deve falhar — stub ainda)**

Run: `cd ~/.openclaw/dispatcher-agent && python -m unittest tests.test_notifier -v`
Expected: 2 novos FAIL (mock_http nunca chamado porque o stub não chama).

- [ ] **Step 3: Implementar happy path no notifier**

Substituir o final de `send_task_event` em `notifier.py`:

```python
def _format_message(task_id: str, outcome: str, context: dict) -> str:
    project = context.get("project", "?")
    title = context.get("title", "?")
    log_path = context.get("log_path", "?")
    if outcome == "done":
        return (
            f"✅ {task_id} done\n"
            f"project: {project}\n"
            f"title: {title}\n"
            f"log: {log_path}"
        )
    # failed
    reason = context.get("failure_reason", "?")
    exit_code = context.get("exit_code", "?")
    return (
        f"❌ {task_id} failed\n"
        f"project: {project}\n"
        f"title: {title}\n"
        f"reason: {reason}\n"
        f"exit: {exit_code}\n"
        f"log: {log_path}"
    )


def send_task_event(
    task_id: str,
    outcome: Literal["done", "failed"],
    *,
    context: dict,
) -> None:
    """Emit Telegram message for task terminal state. Graceful."""
    env = _validate_env()
    if env is None:
        _append_jsonl("skipped:env_missing", task_id, outcome, {})
        return
    if env[0] == "__invalid__":
        _append_jsonl("skipped:env_invalid", task_id, outcome, {})
        return
    token, chat_id, thread_id = env

    text = _format_message(task_id, outcome, context)
    body = {
        "chat_id": chat_id,
        "message_thread_id": thread_id,
        "text": text,
    }
    url = _TELEGRAM_API.format(token=token)
    payload = json.dumps(body).encode("utf-8")
    ok, result = _send_http(url, payload)
    if ok:
        _append_jsonl("task_event_sent", task_id, outcome, result)
    else:
        _append_jsonl(f"failed:{result.get('error', 'unknown')}", task_id, outcome, result)
```

(Remover a linha stub `_append_jsonl("task_event_sent", task_id, outcome, {"stub": True})` da versão anterior.)

- [ ] **Step 4: Rodar todos os testes**

Run: `cd ~/.openclaw/dispatcher-agent && python -m unittest tests.test_notifier -v`
Expected: 4 tests pass (env_missing, env_invalid, done_format, failed_format).

- [ ] **Step 5: Commit**

```bash
cd ~/.openclaw && git add dispatcher-agent/lib/notifier.py dispatcher-agent/tests/test_notifier.py && git commit -m "$(cat <<'EOF'
feat(dispatcher/notifier): implement send_task_event done/failed happy path

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 4: Test 4 (HTTP failure swallowed)

**Files:**
- Modify: `dispatcher-agent/tests/test_notifier.py`

- [ ] **Step 1: Escrever teste de HTTP failure swallowed**

Adicionar ao `test_notifier.py`:

```python
    def test_telegram_http_failure_swallowed(self):
        """urllib erro → função não raise, jsonl event 'failed:*'."""
        ctx = {"project": "p", "title": "t", "log_path": "/tmp/x"}
        env = {
            "TELEGRAM_BOT_TOKEN": "tok",
            "OPENCLAW_DISPATCHER_TELEGRAM_CHAT_ID": "-100",
            "OPENCLAW_DISPATCHER_TELEGRAM_THREAD_ID": "42",
        }
        import urllib.error
        with patch.dict(os.environ, env, clear=True):
            with patch("urllib.request.urlopen", side_effect=urllib.error.URLError("net down")):
                # Não deve levantar
                notifier.send_task_event("T-0003", "done", context=ctx)
        events = [json.loads(l) for l in self.jsonl.read_text().splitlines()]
        last = events[-1]
        self.assertTrue(last["event"].startswith("failed:"))
        self.assertEqual(last["task_id"], "T-0003")
```

- [ ] **Step 2: Rodar teste**

Run: `cd ~/.openclaw/dispatcher-agent && python -m unittest tests.test_notifier -v`
Expected: test passa direto (código de `_send_http` já captura `URLError`).

Se falhar porque o patch de `urllib.request.urlopen` não intercepta (o notifier importa o módulo, não a função por nome), ajustar para `patch("lib.notifier.urllib.request.urlopen", ...)`.

- [ ] **Step 3: Commit**

```bash
cd ~/.openclaw && git add dispatcher-agent/tests/test_notifier.py && git commit -m "$(cat <<'EOF'
test(dispatcher/notifier): HTTP failure is swallowed

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 5: Hook lifecycle.py

**Files:**
- Modify: `dispatcher-agent/lib/lifecycle.py`

- [ ] **Step 1: Ler lifecycle.py atual pra reconfirmar estrutura**

Abrir `~/.openclaw/dispatcher-agent/lib/lifecycle.py` (já inspecionado em sessão anterior — função `process_finished_session` em linha 68-108).

- [ ] **Step 2: Adicionar import e função helper de contexto**

No topo do arquivo, depois de `from . import store`:

```python
from . import notifier
```

Adicionar função helper antes de `process_finished_session`:

```python
def _build_notifier_context(task_id: str, status: Dict[str, Any]) -> Dict[str, Any]:
    """Monta context para notifier. Campos missing → '?' (never raise)."""
    ctx = {
        "project": "?",
        "title": "?",
        "log_path": status.get("log_path", "?"),
        "finished_at": status.get("finished_at"),
        "exit_code": status.get("exit_code"),
    }
    try:
        result = subprocess.run(
            [str(KANBAN_CLI), "task", "get", task_id, "--json"],
            capture_output=True, text=True, check=False, timeout=10,
        )
        if result.returncode == 0:
            data = json.loads(result.stdout)
            task = data.get("task") if isinstance(data, dict) else None
            if task:
                ctx["project"] = task.get("project") or "?"
                ctx["title"] = task.get("title") or "?"
    except (OSError, subprocess.TimeoutExpired, json.JSONDecodeError):
        pass
    return ctx
```

- [ ] **Step 3: Hook nos dois branches terminais**

Em `process_finished_session`, modificar os dois branches:

```python
    if exit_code == 0:
        auto_move_to_testing(task_id)
        merge_dispatch_payload(task_id, {
            "execution_finished_at": status["finished_at"],
            "execution_exit_code": 0,
            "auto_moved_to_testing_at": ts,
        })
        status["post_action"] = "auto_moved_to_testing"
        try:
            notifier.send_task_event(
                task_id, "done",
                context=_build_notifier_context(task_id, status),
            )
        except Exception as e:  # double-safety; notifier is already graceful
            print(f"notifier raised (swallowed): {e}", file=__import__("sys").stderr)
    else:
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
        try:
            ctx = _build_notifier_context(task_id, status)
            ctx["failure_reason"] = stderr_tail
            notifier.send_task_event(task_id, "failed", context=ctx)
        except Exception as e:
            print(f"notifier raised (swallowed): {e}", file=__import__("sys").stderr)
```

- [ ] **Step 4: Smoke import — garantir que lifecycle ainda importa**

Run: `cd ~/.openclaw/dispatcher-agent && python -c "from lib import lifecycle; print(lifecycle.process_finished_session.__doc__)"`
Expected: imprime docstring sem ImportError.

- [ ] **Step 5: Rodar suite completa pra confirmar zero regressão**

Run: `cd ~/.openclaw/dispatcher-agent && python -m unittest discover -v`
Expected: 4 notifier tests pass; outros tests existentes (se houver) continuam passando.

- [ ] **Step 6: Commit**

```bash
cd ~/.openclaw && git add dispatcher-agent/lib/lifecycle.py && git commit -m "$(cat <<'EOF'
feat(dispatcher/lifecycle): emit notifier task_done/task_failed

Hook em process_finished_session. Double-safety try/except absorbe
qualquer raise do notifier (já graceful por dentro). Context resolve
project/title via kanban CLI com fallback '?' se lookup falhar.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 6: Documentar env vars em README

**Files:**
- Modify: `dispatcher-agent/README.md`

- [ ] **Step 1: Adicionar seção "Notificações Telegram" ao README**

Após a seção "Troubleshooting" existente, adicionar:

```markdown
## Notificações Telegram (opcional)

O dispatcher pode emitir mensagens Telegram em transições terminais
(`task_done` após exit 0, `task_failed` após exit != 0 / reaper timeout).

Para ativar, exportar no environment do serviço systemd:

```bash
TELEGRAM_BOT_TOKEN=<token>                     # reusa bot existente
OPENCLAW_DISPATCHER_TELEGRAM_CHAT_ID=<chat_id> # mesmo chat dos outros tópicos
OPENCLAW_DISPATCHER_TELEGRAM_THREAD_ID=<int>   # thread_id do tópico "dispatcher"
```

Se qualquer uma faltar: função vira no-op silencioso (log em
`dispatcher-agent/notifier.jsonl` com event `skipped:env_missing`).

Audit trail append-only em `dispatcher-agent/notifier.jsonl`:
- `task_event_sent` — Telegram respondeu OK
- `skipped:env_missing` — uma das env vars não presente
- `skipped:env_invalid` — `THREAD_ID` não-numérico
- `failed:telegram_api_<code>` — HTTP falhou (swallow, audit only)
```

- [ ] **Step 2: Commit**

```bash
cd ~/.openclaw && git add dispatcher-agent/README.md && git commit -m "$(cat <<'EOF'
docs(dispatcher): documentar env vars do notifier Telegram

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 7: Push + pausa pro merge canônico

- [ ] **Step 1: Verificar branch e status**

Run: `cd ~/.openclaw && git status --short && git log --oneline -10`
Expected: branch atual é feature branch (ex: `feat/dispatcher-notifier`), 6 commits locais.

Se estiver em `main`, criar branch antes: `git checkout -b feat/dispatcher-notifier`.

- [ ] **Step 2: Push**

Run: `cd ~/.openclaw && git push -u origin HEAD`

- [ ] **Step 3: Abrir PR**

```bash
cd ~/.openclaw && gh pr create --title "feat(dispatcher): Telegram notifier task_done/task_failed" --body "$(cat <<'EOF'
## Summary
- Novo módulo `dispatcher-agent/lib/notifier.py` (stdlib-only, env-gated, graceful)
- Hook em `lifecycle.process_finished_session` emite `✅ done` / `❌ failed` em tópico Telegram dedicado
- 4 unit tests (`python -m unittest tests.test_notifier`)
- Sem mudança em `cron.py`, `runner.py`, `reaper.py`, `api.py`

Spec: `bevox-knowledge/35_specs/openclaw/2026-04-24-dispatcher-telegram-notifier.md`

## Test plan
- [ ] Tópico Telegram "dispatcher" criado no grupo existente
- [ ] Env vars setadas no systemd dropin de `openclaw-cron-dispatcher.service`
- [ ] `systemctl --user daemon-reload && systemctl --user restart openclaw-cron-dispatcher.timer`
- [ ] Smoke: task sintética exit 0 → mensagem `✅` recebida no tópico
- [ ] Smoke: task sintética exit 1 → mensagem `❌` recebida com reason/exit/log

🤖 Generated with [Claude Code](https://claude.com/claude-code)
EOF
)"
```

- [ ] **Step 4: PAUSA — aguardar merge do Bernard em `main`**

Parar execução aqui. Bernard revisa PR e merge manual. Retomar em Task 8 após merge confirmado.

---

## Task 8: Deploy — env setup + systemd reload + smoke manual

**Pré-requisito:** PR merged; `main` pulled local em `.openclaw`.

- [ ] **Step 1: Criar tópico Telegram "dispatcher"**

Bernard faz no cliente Telegram:
1. Abrir o grupo onde já existem os tópicos `clarifications` etc.
2. Criar novo tópico com nome `dispatcher`.
3. Copiar `thread_id` (visível na URL do tópico ou via bot API `getChat`).

Anotar: `THREAD_ID=<número>`.

- [ ] **Step 2: Criar dropin systemd com env vars**

```bash
sudo mkdir -p ~/.config/systemd/user/openclaw-cron-dispatcher.service.d/
cat > ~/.config/systemd/user/openclaw-cron-dispatcher.service.d/notifier.conf <<'EOF'
[Service]
Environment="TELEGRAM_BOT_TOKEN=<token-existente>"
Environment="OPENCLAW_DISPATCHER_TELEGRAM_CHAT_ID=<chat-id-existente>"
Environment="OPENCLAW_DISPATCHER_TELEGRAM_THREAD_ID=<thread-id-do-passo-1>"
EOF
```

Alternativa: usar `EnvironmentFile=` apontando para um `.env` com 600 perms. Escolher consistente com padrão existente do repo (checar `gateway/bots/*.env` e como são loaded).

- [ ] **Step 3: Reload systemd user daemon**

```bash
systemctl --user daemon-reload
systemctl --user restart openclaw-cron-dispatcher.timer
systemctl --user status openclaw-cron-dispatcher.timer
```

Expected: timer `active (waiting)`.

Nota: **não precisa rebuild** — é Python runtime puro, basta o daemon reload pra pegar o env novo.

- [ ] **Step 4: Smoke — success path**

Escolher task `ready` em projeto opted-in. Aguardar cron-tick (ver `systemctl --user list-timers openclaw-cron-dispatcher.timer`). Quando task termina exit 0:

- Verificar Telegram: mensagem `✅ T-XXXX done ...` no tópico `dispatcher`.
- Verificar jsonl: `tail -1 ~/.openclaw/dispatcher-agent/notifier.jsonl` → `"event": "task_event_sent"`.

Se sem task ready disponível, forçar uma task sintética:
```bash
~/.openclaw/kanban-tasks/cli.sh task add --project test-project --title "smoke-notifier-done" --goal "echo ok" --actor bernard
~/.openclaw/kanban-tasks/cli.sh task move <id> ready --actor bernard
```

- [ ] **Step 5: Smoke — fail path**

Criar task sintética com goal que força failure:
```bash
~/.openclaw/kanban-tasks/cli.sh task add --project test-project --title "smoke-notifier-fail" --goal "exit 1" --actor bernard
~/.openclaw/kanban-tasks/cli.sh task move <id> ready --actor bernard
```

Aguardar dispatch + finalização. Verificar:
- Mensagem `❌ T-XXXX failed` com `reason`, `exit: 1`, `log: ...`.
- jsonl event `task_event_sent` com `outcome: "failed"`.

- [ ] **Step 6: Smoke — env unset (sanity)**

Temporariamente unset uma env var, reiniciar timer, forçar task, verificar:
- Nenhuma mensagem Telegram.
- jsonl event `skipped:env_missing`.
- Dispatcher continua funcionando normal (transição kanban aplicada).

Restaurar env após.

- [ ] **Step 7: Marcar DoD como atingido**

Atualizar `bevox-knowledge/40_roadmap/_shared/delivery-tracker.yml` adicionando entry:
```yaml
- epic: E10
  wave: hotfix-dispatcher-notifier
  status: delivered
  delivered_at: <data>
  pr: <url do PR>
  spec: 35_specs/openclaw/2026-04-24-dispatcher-telegram-notifier.md
```

Commit + push no bevox-knowledge (branch `main` via flow normal).

---

## Self-review — validação do plano

**Spec coverage:**
- §3 (notifier module): Tasks 2-4 ✓
- §4 (lifecycle hook): Task 5 ✓
- §5 (files): create/modify list matches exato ✓
- §6 (edge cases): cobertos em 4 tests + double-safety em Task 5 ✓
- §7 (tests + smoke): Tasks 2-4 unit; Task 8 smoke manual ✓
- §8 (DoD): Task 8 step 7 registra delivery ✓

**Placeholder scan:** clean. Todo passo tem código concreto ou comando.

**Type consistency:** `send_task_event(task_id, outcome, *, context)` chamado consistentemente em Task 5. `_send_http(url, payload)` assinatura bate entre Task 2 stub e Task 3 uso no mock.

**Risco identificado:** Task 4 step 2 nota que pode ser preciso ajustar o patch target (`"urllib.request.urlopen"` vs `"lib.notifier.urllib.request.urlopen"`). Ambas alternativas estão documentadas inline.
