# Telegram Push Escalations — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Adicionar serviço standalone `clarification-notifier` que varre `~/.openclaw/clarification-agent/escalations/` a cada 60s via systemd timer e envia mensagem Telegram mínima (topico `clarifications`) para cada nova escalation unsafe; recovery silencioso; sem rate limit; rollback em 1 comando.

**Architecture:** Novo módulo `lib/notifier.py` (puro stdlib + fcntl) com funções testáveis separadas: `parse_escalation_filename`, `build_telegram_message`, `send_telegram_message`, `load_state`, `save_state`, `tick`. Wrapper `notifier.sh` invoca `python3 -m lib.notifier --tick`. Fonte-única-da-verdade é `escalations/` (populada por push+pull modes unificados pela wave-1). State idempotência em `notifier-state.json` atomic write. Audit append-only em `notifier.jsonl`. Lock `notifier.lock` via `fcntl` para evitar duplicação em tick concorrente.

**Tech Stack:** Python 3 stdlib apenas (zero pip install — decisão E10 Plano B Spike-5). `urllib.request` pra Bot API. `unittest.mock.patch` pra testar HTTP sem rede. `fcntl` pra lock. `bash` pra smoke E2E. Systemd user units pra timer 60s.

**Spec canônica:** `bevox-knowledge/35_specs/2026-04-21-e10-telegram-push-escalations.md`
**ADR governante:** `bevox-knowledge/30_adr/ADR-009-clarification-loop-unified-local-first.md`
**Runtime source:** `~/.openclaw/clarification-agent/`
**Bloco narrativo:** Operational Loop Hardening 2026-04-21 (wave-2 de 8)
**Branch draft bevox-knowledge:** `draft/adr-009-clarification-daemon`

**Ajustes pós-spec (validados com Bernard 2026-04-22):**
1. Sem validação remota no startup (spec §6.1 R1 mencionava `getForumTopic` que não existe na Bot API); validar só presença das env vars; primeiro `sendMessage` serve de teste live.
2. Layout segue wave-1: lógica em `lib/notifier.py` + `notifier.sh` wrapper; testes em `tests/test_notifier.py`.
3. Lock `fcntl` em `notifier.lock` (não explicitado na spec mas necessário para evitar duplicação).

---

## File Structure

**Arquivos a criar:**
- `~/.openclaw/clarification-agent/lib/notifier.py` — lógica completa (tick + helpers)
- `~/.openclaw/clarification-agent/tests/test_notifier.py` — suite unittest
- `~/.openclaw/clarification-agent/notifier.sh` — wrapper shell para systemd
- `~/.openclaw/clarification-agent/smoke_notifier.sh` — 7 cenários E2E da spec §5
- `~/.openclaw/clarification-agent/systemd/openclaw-clarification-notifier.service`
- `~/.openclaw/clarification-agent/systemd/openclaw-clarification-notifier.timer`

**Arquivos a modificar:**
- `~/.openclaw/clarification-agent/playbook.md` — seção nova "Push mode (Telegram notifier)"
- `~/.openclaw/clarification-agent/README.md` — bullet listando serviço notifier
- `~/.openclaw/.env` — adicionar 2 env vars (`TELEGRAM_CLARIFICATIONS_CHAT_ID`, `TELEGRAM_CLARIFICATIONS_THREAD_ID`)
- `~/.openclaw/health/registry.yml` — entrada nova `openclaw-clarification-notifier`
- `bevox-knowledge/35_specs/2026-04-21-e10-telegram-push-escalations.md` — status draft → delivered + ajustes finais (§6.1 R1)
- `bevox-knowledge/40_roadmap/delivery-tracker.yml` — entrada wave-2 delivered

**Arquivos runtime gerados em execução (não versionados):**
- `~/.openclaw/clarification-agent/notifier-state.json` — idempotência
- `~/.openclaw/clarification-agent/notifier.jsonl` — audit append-only
- `~/.openclaw/clarification-agent/notifier.lock` — fcntl lock

---

## Phase 0 — Baseline + pré-reqs

### Task 1: Confirmar pré-reqs wave-1 delivered + placeholder env vars

**Files:**
- Modify: `~/.openclaw/.env` (append 2 placeholders comentados)

- [ ] **Step 1: Confirmar wave-1 entregou o que precisamos**

```bash
ls ~/.openclaw/clarification-agent/escalations/
~/.openclaw/clarification-agent/cli.sh escalations --json | head -20
```

Expected: 3 symlinks visíveis (T-0006-clr-2, T-0008-clr-1, T-0008-clr-2) + JSON com 3 entradas `{"clarification_id": "...", "escalation_path": "..."}`.

- [ ] **Step 2: Confirmar função `store.list_escalations()` existe e retorna o esperado**

```bash
cd ~/.openclaw/clarification-agent
python3 -c "from lib import store; import json; print(json.dumps(store.list_escalations(), indent=2))"
```

Expected: JSON com 3 dicts, cada um `{"clarification_id": "T-XXXX-clr-N", "escalation_path": "~/.openclaw/clarification-agent/escalations/T-XXXX-clr-N.md"}`.

- [ ] **Step 3: Adicionar placeholders env vars no `.env`**

Abrir `~/.openclaw/.env` e acrescentar no final:

```bash
# OpenClaw clarification notifier (wave-2 — to be filled before systemd enable)
# TELEGRAM_CLARIFICATIONS_CHAT_ID=-100XXXXXXXXXX
# TELEGRAM_CLARIFICATIONS_THREAD_ID=
```

Deixar comentadas. Bernard ativa depois que prover `thread_id` real.

- [ ] **Step 4: Validar que `TELEGRAM_BOT_TOKEN` já existe no `.env`**

```bash
grep -c "^TELEGRAM_BOT_TOKEN=" ~/.openclaw/.env
```

Expected: `1` (já definida). Se `0`, bloquear e resolver antes de prosseguir.

- [ ] **Step 5: Nenhum commit nesta task** (runtime não é git).

---

## Phase 1 — Core pure units (TDD red→green)

### Task 2: Test skeleton `test_notifier.py` (red)

**Files:**
- Create: `~/.openclaw/clarification-agent/tests/test_notifier.py`

- [ ] **Step 1: Criar arquivo com 3 smoke tests para a unidade pura `parse_escalation_filename`**

```python
"""Testes notifier.py — standalone Telegram notifier."""
import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch, MagicMock

from lib import notifier


class TestParseFilename(unittest.TestCase):
    def test_valid_filename_returns_task_and_cid(self):
        task_id, cid = notifier.parse_escalation_filename("T-0006-clr-2.md")
        self.assertEqual(task_id, "T-0006")
        self.assertEqual(cid, "T-0006-clr-2")

    def test_double_digit_clr_number(self):
        task_id, cid = notifier.parse_escalation_filename("T-0042-clr-15.md")
        self.assertEqual(task_id, "T-0042")
        self.assertEqual(cid, "T-0042-clr-15")

    def test_invalid_filename_raises(self):
        with self.assertRaises(ValueError):
            notifier.parse_escalation_filename("garbage.md")


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Rodar pra confirmar falha**

```bash
cd ~/.openclaw/clarification-agent
python3 -m unittest tests.test_notifier -v
```

Expected: FAIL com `ModuleNotFoundError: No module named 'lib.notifier'`.

### Task 3: Implementar `parse_escalation_filename` em `lib/notifier.py`

**Files:**
- Create: `~/.openclaw/clarification-agent/lib/notifier.py`

- [ ] **Step 1: Escrever módulo mínimo**

```python
"""OpenClaw clarification notifier — E10/OH wave-2.

Serviço standalone (systemd user timer 60s) que varre
~/.openclaw/clarification-agent/escalations/ e envia notificação
Telegram no tópico `clarifications` para cada nova escalation unsafe.

Design tight: stdlib-only, fcntl lock, atomic state, audit jsonl.
Fonte-única-da-verdade: escalations/ (populada pela wave-1).
"""
from __future__ import annotations

import re
from pathlib import Path
from typing import Tuple

# Filename pattern: T-XXXX-clr-N.md (N = 1+ digits)
_FILENAME_RE = re.compile(r"^(T-\d{4})-clr-\d+\.md$")


def parse_escalation_filename(filename: str) -> Tuple[str, str]:
    """Extract (task_id, clarification_id) from escalation filename.

    Raises ValueError if filename does not match T-XXXX-clr-N.md pattern.
    """
    m = _FILENAME_RE.match(filename)
    if not m:
        raise ValueError(f"invalid escalation filename: {filename!r}")
    task_id = m.group(1)
    cid = filename[:-len(".md")]
    return task_id, cid
```

- [ ] **Step 2: Rodar tests de novo pra confirmar 3/3 passam**

```bash
cd ~/.openclaw/clarification-agent
python3 -m unittest tests.test_notifier -v
```

Expected: `Ran 3 tests in 0.00Xs / OK`.

### Task 4: `build_telegram_message` (red→green)

**Files:**
- Modify: `~/.openclaw/clarification-agent/tests/test_notifier.py` (append class)
- Modify: `~/.openclaw/clarification-agent/lib/notifier.py` (append function)

- [ ] **Step 1: Acrescentar tests no `test_notifier.py`**

```python
class TestBuildMessage(unittest.TestCase):
    def test_body_contains_task_id_and_hint(self):
        body = notifier.build_telegram_message(
            task_id="T-0006",
            cid="T-0006-clr-2",
            chat_id="-100XXXXXXXXXX",
            thread_id=42,
        )
        self.assertEqual(body["chat_id"], "-100XXXXXXXXXX")
        self.assertEqual(body["message_thread_id"], 42)
        self.assertIn("T-0006", body["text"])
        self.assertIn("T-0006-clr-2", body["text"])
        self.assertIn("vox clarification show", body["text"])
        self.assertTrue(body["disable_web_page_preview"])

    def test_text_is_exactly_two_lines(self):
        body = notifier.build_telegram_message(
            task_id="T-0006", cid="T-0006-clr-2",
            chat_id="-1", thread_id=1,
        )
        self.assertEqual(body["text"].count("\n"), 1)
```

- [ ] **Step 2: Rodar pra confirmar falha**

```bash
python3 -m unittest tests.test_notifier -v
```

Expected: FAIL com `AttributeError: module 'lib.notifier' has no attribute 'build_telegram_message'`.

- [ ] **Step 3: Implementar função no `notifier.py`**

```python
def build_telegram_message(
    task_id: str,
    cid: str,
    chat_id: str,
    thread_id: int,
) -> dict:
    """Construct sendMessage body for Telegram Bot API.

    Formato intencionalmente mínimo: 2 linhas, sem markdown.
    Conteúdo detalhado vem via `vox clarification show <cid>`.
    """
    text = f"🚫 {task_id} clarification unsafe\nRun: vox clarification show {cid}"
    return {
        "chat_id": chat_id,
        "message_thread_id": thread_id,
        "text": text,
        "disable_web_page_preview": True,
    }
```

- [ ] **Step 4: Rodar e confirmar 5/5**

```bash
python3 -m unittest tests.test_notifier -v
```

Expected: `Ran 5 tests ... OK`.

### Task 5: `load_state` / `save_state` atomic (red→green)

**Files:**
- Modify: `~/.openclaw/clarification-agent/tests/test_notifier.py`
- Modify: `~/.openclaw/clarification-agent/lib/notifier.py`

- [ ] **Step 1: Acrescentar tests**

```python
class TestState(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.state_path = Path(self.tmp) / "notifier-state.json"

    def tearDown(self):
        import shutil
        shutil.rmtree(self.tmp)

    def test_load_missing_returns_empty_shape(self):
        s = notifier.load_state(self.state_path)
        self.assertEqual(s["schema_version"], 1)
        self.assertEqual(s["notifications"], {})

    def test_save_then_load_roundtrip(self):
        s = {
            "schema_version": 1,
            "heartbeat_at": "2026-04-22T00:05:00Z",
            "notifications": {
                "T-0006-clr-2": {
                    "task_id": "T-0006",
                    "notified_at": "2026-04-21T21:41:15Z",
                    "telegram_message_id": 42,
                    "source_path": "/tmp/x",
                },
            },
        }
        notifier.save_state(self.state_path, s)
        loaded = notifier.load_state(self.state_path)
        self.assertEqual(loaded, s)

    def test_save_is_atomic_no_partial(self):
        """Arquivo nunca fica parcialmente escrito (usa tmp+rename)."""
        s = {"schema_version": 1, "heartbeat_at": "x", "notifications": {"a": {"x": 1}}}
        notifier.save_state(self.state_path, s)
        # Arquivo existe e é válido JSON
        with open(self.state_path) as f:
            parsed = json.load(f)
        self.assertEqual(parsed, s)

    def test_corrupt_file_returns_empty(self):
        self.state_path.write_text("{not valid json")
        s = notifier.load_state(self.state_path)
        self.assertEqual(s["notifications"], {})
```

- [ ] **Step 2: Rodar e confirmar falha**

```bash
python3 -m unittest tests.test_notifier -v
```

Expected: FAIL com `AttributeError: module 'lib.notifier' has no attribute 'load_state'`.

- [ ] **Step 3: Implementar `load_state` / `save_state` no `notifier.py`**

Acrescentar no topo:

```python
import json
import os
import tempfile

_EMPTY_STATE = {
    "schema_version": 1,
    "heartbeat_at": None,
    "notifications": {},
}


def load_state(path: Path) -> dict:
    """Load state JSON. Missing/corrupt → empty shape (first run semantics)."""
    if not path.exists():
        return dict(_EMPTY_STATE, notifications={})
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        if not isinstance(data, dict) or "notifications" not in data:
            return dict(_EMPTY_STATE, notifications={})
        data.setdefault("schema_version", 1)
        data.setdefault("heartbeat_at", None)
        return data
    except (OSError, json.JSONDecodeError):
        return dict(_EMPTY_STATE, notifications={})


def save_state(path: Path, state: dict) -> None:
    """Atomic write: write to temp + os.rename."""
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(
        prefix=".notifier-state-", suffix=".tmp", dir=str(path.parent)
    )
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(state, f, indent=2)
        os.rename(tmp, path)
    except Exception:
        if os.path.exists(tmp):
            os.unlink(tmp)
        raise
```

- [ ] **Step 4: Rodar e confirmar 9/9**

```bash
python3 -m unittest tests.test_notifier -v
```

Expected: `Ran 9 tests ... OK`.

### Task 6: `validate_env` (red→green)

**Files:**
- Modify: `~/.openclaw/clarification-agent/tests/test_notifier.py`
- Modify: `~/.openclaw/clarification-agent/lib/notifier.py`

- [ ] **Step 1: Acrescentar tests**

```python
class TestValidateEnv(unittest.TestCase):
    def test_all_present_returns_tuple(self):
        env = {
            "TELEGRAM_BOT_TOKEN": "abc:xyz",
            "TELEGRAM_CLARIFICATIONS_CHAT_ID": "-100XXXXXXXXXX",
            "TELEGRAM_CLARIFICATIONS_THREAD_ID": "42",
        }
        token, chat_id, thread_id = notifier.validate_env(env)
        self.assertEqual(token, "abc:xyz")
        self.assertEqual(chat_id, "-100XXXXXXXXXX")
        self.assertEqual(thread_id, 42)

    def test_missing_token_raises(self):
        env = {
            "TELEGRAM_CLARIFICATIONS_CHAT_ID": "-1",
            "TELEGRAM_CLARIFICATIONS_THREAD_ID": "1",
        }
        with self.assertRaises(notifier.EnvError) as ctx:
            notifier.validate_env(env)
        self.assertIn("TELEGRAM_BOT_TOKEN", str(ctx.exception))

    def test_non_integer_thread_id_raises(self):
        env = {
            "TELEGRAM_BOT_TOKEN": "t",
            "TELEGRAM_CLARIFICATIONS_CHAT_ID": "-1",
            "TELEGRAM_CLARIFICATIONS_THREAD_ID": "not_a_number",
        }
        with self.assertRaises(notifier.EnvError):
            notifier.validate_env(env)
```

- [ ] **Step 2: Rodar e confirmar falha**

```bash
python3 -m unittest tests.test_notifier -v
```

Expected: FAIL com `AttributeError: module 'lib.notifier' has no attribute 'validate_env'`.

- [ ] **Step 3: Implementar no `notifier.py`**

```python
class EnvError(RuntimeError):
    """Env validation failed (missing var or malformed value)."""


_REQUIRED_ENV = (
    "TELEGRAM_BOT_TOKEN",
    "TELEGRAM_CLARIFICATIONS_CHAT_ID",
    "TELEGRAM_CLARIFICATIONS_THREAD_ID",
)


def validate_env(env: dict) -> Tuple[str, str, int]:
    """Validate required env vars are present and well-formed.

    Returns (token, chat_id, thread_id_int). Raises EnvError otherwise.
    """
    missing = [k for k in _REQUIRED_ENV if not env.get(k)]
    if missing:
        raise EnvError(f"missing env vars: {', '.join(missing)}")
    token = env["TELEGRAM_BOT_TOKEN"]
    chat_id = env["TELEGRAM_CLARIFICATIONS_CHAT_ID"]
    raw_thread = env["TELEGRAM_CLARIFICATIONS_THREAD_ID"]
    try:
        thread_id = int(raw_thread)
    except (TypeError, ValueError):
        raise EnvError(
            f"TELEGRAM_CLARIFICATIONS_THREAD_ID must be integer, got {raw_thread!r}"
        )
    return token, chat_id, thread_id
```

- [ ] **Step 4: Rodar e confirmar 12/12**

```bash
python3 -m unittest tests.test_notifier -v
```

Expected: `Ran 12 tests ... OK`.

---

## Phase 2 — Telegram HTTP client (mocked)

### Task 7: `send_telegram_message` happy path (red→green)

**Files:**
- Modify: `~/.openclaw/clarification-agent/tests/test_notifier.py`
- Modify: `~/.openclaw/clarification-agent/lib/notifier.py`

- [ ] **Step 1: Acrescentar tests (com mock urllib)**

```python
class TestSendTelegram(unittest.TestCase):
    def test_happy_path_returns_ok_and_message_id(self):
        body = {
            "chat_id": "-1", "message_thread_id": 1,
            "text": "x", "disable_web_page_preview": True,
        }
        fake_response = json.dumps({
            "ok": True,
            "result": {"message_id": 4242, "chat": {"id": -1}, "text": "x"},
        }).encode("utf-8")

        mock_resp = MagicMock()
        mock_resp.read.return_value = fake_response
        mock_resp.status = 200
        mock_resp.__enter__ = MagicMock(return_value=mock_resp)
        mock_resp.__exit__ = MagicMock(return_value=False)

        with patch("lib.notifier.urllib.request.urlopen", return_value=mock_resp):
            ok, result = notifier.send_telegram_message(body, token="abc:xyz")
        self.assertTrue(ok)
        self.assertEqual(result["message_id"], 4242)
        self.assertIsNone(result.get("error"))

    def test_body_has_unicode_is_json_encoded_safely(self):
        body = {
            "chat_id": "-1", "message_thread_id": 1,
            "text": "🚫 special chars: \"\\n", "disable_web_page_preview": True,
        }
        fake_response = json.dumps({
            "ok": True, "result": {"message_id": 1},
        }).encode("utf-8")

        mock_resp = MagicMock()
        mock_resp.read.return_value = fake_response
        mock_resp.status = 200
        mock_resp.__enter__ = MagicMock(return_value=mock_resp)
        mock_resp.__exit__ = MagicMock(return_value=False)

        with patch("lib.notifier.urllib.request.urlopen", return_value=mock_resp) as m:
            ok, _ = notifier.send_telegram_message(body, token="t")
        self.assertTrue(ok)
        # Confirma que o body foi serializado e o token apareceu na URL
        req = m.call_args[0][0]
        self.assertIn("/bott/sendMessage", req.full_url)
        posted = json.loads(req.data.decode("utf-8"))
        self.assertEqual(posted["text"], body["text"])
```

- [ ] **Step 2: Rodar e confirmar falha**

```bash
python3 -m unittest tests.test_notifier -v
```

Expected: FAIL com `AttributeError: ... 'send_telegram_message'`.

- [ ] **Step 3: Implementar função + import no `notifier.py`**

Adicionar ao topo:

```python
import urllib.error
import urllib.request
```

Adicionar função:

```python
_TELEGRAM_API = "https://api.telegram.org/bot{token}/sendMessage"
_HTTP_TIMEOUT = 10.0  # seconds


def send_telegram_message(body: dict, token: str) -> Tuple[bool, dict]:
    """POST sendMessage to Telegram Bot API.

    Returns (ok, result_dict). On success, result = {"message_id": int}.
    On failure, ok=False and result contains {"error": "<classified>", ...}.
    No retries here — caller decides (notifier skips and retries next tick).
    """
    url = _TELEGRAM_API.format(token=token)
    payload = json.dumps(body).encode("utf-8")
    req = urllib.request.Request(
        url, data=payload,
        headers={"Content-Type": "application/json; charset=utf-8"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=_HTTP_TIMEOUT) as resp:
            raw = resp.read().decode("utf-8")
            parsed = json.loads(raw)
        if parsed.get("ok") is True and "result" in parsed:
            return True, {"message_id": parsed["result"].get("message_id")}
        return False, {"error": "telegram_api_not_ok", "body": parsed}
    except urllib.error.HTTPError as e:
        return False, {"error": f"telegram_api_{e.code}", "detail": str(e)}
    except urllib.error.URLError as e:
        return False, {"error": "telegram_api_network", "detail": str(e.reason)}
    except (OSError, json.JSONDecodeError, TimeoutError) as e:
        return False, {"error": "telegram_api_exception", "detail": str(e)}
```

- [ ] **Step 4: Rodar e confirmar 14/14**

```bash
python3 -m unittest tests.test_notifier -v
```

Expected: `Ran 14 tests ... OK`.

### Task 8: `send_telegram_message` erro paths (4xx / 5xx / network)

**Files:**
- Modify: `~/.openclaw/clarification-agent/tests/test_notifier.py`

- [ ] **Step 1: Acrescentar tests de erros**

```python
class TestSendTelegramErrors(unittest.TestCase):
    def _body(self):
        return {"chat_id": "-1", "message_thread_id": 1,
                "text": "x", "disable_web_page_preview": True}

    def test_http_400_returns_classified_error(self):
        import urllib.error
        err = urllib.error.HTTPError(
            url="http://x", code=400, msg="Bad Request",
            hdrs=None, fp=None,
        )
        with patch("lib.notifier.urllib.request.urlopen", side_effect=err):
            ok, result = notifier.send_telegram_message(self._body(), token="t")
        self.assertFalse(ok)
        self.assertEqual(result["error"], "telegram_api_400")

    def test_http_429_rate_limit(self):
        import urllib.error
        err = urllib.error.HTTPError(
            url="http://x", code=429, msg="Too Many Requests",
            hdrs=None, fp=None,
        )
        with patch("lib.notifier.urllib.request.urlopen", side_effect=err):
            ok, result = notifier.send_telegram_message(self._body(), token="t")
        self.assertFalse(ok)
        self.assertEqual(result["error"], "telegram_api_429")

    def test_http_500_returns_classified_error(self):
        import urllib.error
        err = urllib.error.HTTPError(
            url="http://x", code=500, msg="Internal Server Error",
            hdrs=None, fp=None,
        )
        with patch("lib.notifier.urllib.request.urlopen", side_effect=err):
            ok, result = notifier.send_telegram_message(self._body(), token="t")
        self.assertFalse(ok)
        self.assertEqual(result["error"], "telegram_api_500")

    def test_network_down_returns_classified_error(self):
        import urllib.error
        err = urllib.error.URLError("DNS failure")
        with patch("lib.notifier.urllib.request.urlopen", side_effect=err):
            ok, result = notifier.send_telegram_message(self._body(), token="t")
        self.assertFalse(ok)
        self.assertEqual(result["error"], "telegram_api_network")

    def test_response_not_ok_classified(self):
        fake = json.dumps({"ok": False, "description": "bad thread"}).encode("utf-8")
        mock_resp = MagicMock()
        mock_resp.read.return_value = fake
        mock_resp.status = 200
        mock_resp.__enter__ = MagicMock(return_value=mock_resp)
        mock_resp.__exit__ = MagicMock(return_value=False)
        with patch("lib.notifier.urllib.request.urlopen", return_value=mock_resp):
            ok, result = notifier.send_telegram_message(self._body(), token="t")
        self.assertFalse(ok)
        self.assertEqual(result["error"], "telegram_api_not_ok")
        self.assertEqual(result["body"]["description"], "bad thread")
```

- [ ] **Step 2: Rodar e confirmar 19/19 (implementação já cobre; se algum falhar, ajustar)**

```bash
python3 -m unittest tests.test_notifier -v
```

Expected: `Ran 19 tests ... OK`.

---

## Phase 3 — Tick orchestration

### Task 9: `append_event` audit jsonl (red→green)

**Files:**
- Modify: `~/.openclaw/clarification-agent/tests/test_notifier.py`
- Modify: `~/.openclaw/clarification-agent/lib/notifier.py`

- [ ] **Step 1: Acrescentar tests**

```python
class TestAppendEvent(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.jsonl = Path(self.tmp) / "notifier.jsonl"

    def tearDown(self):
        import shutil
        shutil.rmtree(self.tmp)

    def test_append_writes_single_line_json(self):
        notifier.append_event(self.jsonl, "tick_started", {"pending_count": 2})
        lines = self.jsonl.read_text().strip().splitlines()
        self.assertEqual(len(lines), 1)
        parsed = json.loads(lines[0])
        self.assertEqual(parsed["event"], "tick_started")
        self.assertEqual(parsed["payload"]["pending_count"], 2)
        self.assertIn("ts", parsed)

    def test_multiple_appends_keep_order(self):
        notifier.append_event(self.jsonl, "a", {"n": 1})
        notifier.append_event(self.jsonl, "b", {"n": 2})
        notifier.append_event(self.jsonl, "c", {"n": 3})
        lines = self.jsonl.read_text().strip().splitlines()
        self.assertEqual([json.loads(l)["event"] for l in lines], ["a", "b", "c"])

    def test_iso_timestamp_format(self):
        notifier.append_event(self.jsonl, "x", {})
        line = self.jsonl.read_text().strip()
        parsed = json.loads(line)
        # ISO 8601 UTC with Z
        self.assertRegex(parsed["ts"], r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$")
```

- [ ] **Step 2: Rodar e confirmar falha**

```bash
python3 -m unittest tests.test_notifier -v
```

Expected: FAIL com `AttributeError: ... 'append_event'`.

- [ ] **Step 3: Implementar no `notifier.py`**

Adicionar import no topo:

```python
from datetime import datetime, timezone
```

Adicionar função:

```python
def _now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def append_event(jsonl_path: Path, event: str, payload: dict) -> None:
    """Append single-line JSON event to audit log (truncate=False)."""
    jsonl_path.parent.mkdir(parents=True, exist_ok=True)
    record = {"ts": _now_iso(), "event": event, "payload": payload}
    with open(jsonl_path, "a", encoding="utf-8") as f:
        f.write(json.dumps(record) + "\n")
```

- [ ] **Step 4: Rodar e confirmar 22/22**

```bash
python3 -m unittest tests.test_notifier -v
```

Expected: `Ran 22 tests ... OK`.

### Task 10: `scan_escalations` → diff vs state (red→green)

**Files:**
- Modify: `~/.openclaw/clarification-agent/tests/test_notifier.py`
- Modify: `~/.openclaw/clarification-agent/lib/notifier.py`

- [ ] **Step 1: Acrescentar tests**

```python
class TestScanAndDiff(unittest.TestCase):
    def test_scan_empty_dir_returns_empty(self):
        with tempfile.TemporaryDirectory() as d:
            out = notifier.scan_escalations(Path(d))
            self.assertEqual(out, [])

    def test_scan_returns_cids_sorted(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d)
            (p / "T-0008-clr-2.md").touch()
            (p / "T-0006-clr-1.md").touch()
            (p / "T-0006-clr-2.md").touch()
            (p / "ignored.txt").touch()
            (p / "not-escalation.md").touch()
            out = notifier.scan_escalations(p)
            self.assertEqual([c[1] for c in out],
                             ["T-0006-clr-1", "T-0006-clr-2", "T-0008-clr-2"])
            # each entry is (task_id, cid, source_path)
            self.assertEqual(out[0][0], "T-0006")
            self.assertTrue(out[0][2].endswith("T-0006-clr-1.md"))

    def test_compute_diff_detects_new_and_resolved(self):
        pending = {"A", "B", "C"}
        state_cids = {"A", "D"}
        new, resolved = notifier.compute_diff(pending, state_cids)
        self.assertEqual(new, {"B", "C"})
        self.assertEqual(resolved, {"D"})
```

- [ ] **Step 2: Rodar e confirmar falha**

```bash
python3 -m unittest tests.test_notifier -v
```

Expected: FAIL com `AttributeError: ... 'scan_escalations'`.

- [ ] **Step 3: Implementar no `notifier.py`**

```python
from typing import List, Set


def scan_escalations(escalations_dir: Path) -> List[Tuple[str, str, str]]:
    """List (task_id, cid, source_path) for valid escalations, sorted by cid.

    Ignores files that don't match T-XXXX-clr-N.md. Includes symlinks + regular
    files (spec §3.2 allows both; wave-1 uses symlinks).
    """
    if not escalations_dir.exists():
        return []
    out = []
    for p in sorted(escalations_dir.iterdir()):
        try:
            task_id, cid = parse_escalation_filename(p.name)
        except ValueError:
            continue
        if not (p.is_symlink() or p.is_file()):
            continue
        out.append((task_id, cid, str(p)))
    return out


def compute_diff(pending: Set[str], state_cids: Set[str]) -> Tuple[Set[str], Set[str]]:
    """Return (new_to_notify, resolved_to_gc).

    new = pending - state (need to send)
    resolved = state - pending (GC from state, no message)
    """
    new = pending - state_cids
    resolved = state_cids - pending
    return new, resolved
```

- [ ] **Step 4: Rodar e confirmar 25/25**

```bash
python3 -m unittest tests.test_notifier -v
```

Expected: `Ran 25 tests ... OK`.

### Task 11: `tick` orchestração happy path (red→green)

**Files:**
- Modify: `~/.openclaw/clarification-agent/tests/test_notifier.py`
- Modify: `~/.openclaw/clarification-agent/lib/notifier.py`

- [ ] **Step 1: Acrescentar tests com fixture completa**

```python
class TestTick(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.esc_dir = self.tmp / "escalations"
        self.esc_dir.mkdir()
        self.state_path = self.tmp / "notifier-state.json"
        self.jsonl = self.tmp / "notifier.jsonl"
        # 2 escalations pending
        (self.esc_dir / "T-0006-clr-2.md").touch()
        (self.esc_dir / "T-0008-clr-1.md").touch()

    def tearDown(self):
        import shutil
        shutil.rmtree(self.tmp)

    def _mock_send(self, message_id=42):
        """Patch that always returns (True, {"message_id": message_id})."""
        return patch(
            "lib.notifier.send_telegram_message",
            return_value=(True, {"message_id": message_id}),
        )

    def test_first_tick_sends_both_and_updates_state(self):
        with self._mock_send():
            result = notifier.tick(
                escalations_dir=self.esc_dir,
                state_path=self.state_path,
                jsonl_path=self.jsonl,
                token="t", chat_id="-1", thread_id=1,
                dry_run=False,
            )
        self.assertEqual(result["sent"], 2)
        self.assertEqual(result["skipped_already"], 0)
        self.assertEqual(result["skipped_resolved"], 0)
        state = notifier.load_state(self.state_path)
        self.assertIn("T-0006-clr-2", state["notifications"])
        self.assertIn("T-0008-clr-1", state["notifications"])

    def test_second_tick_skips_already_sent(self):
        with self._mock_send():
            notifier.tick(
                escalations_dir=self.esc_dir,
                state_path=self.state_path,
                jsonl_path=self.jsonl,
                token="t", chat_id="-1", thread_id=1,
                dry_run=False,
            )
            result = notifier.tick(
                escalations_dir=self.esc_dir,
                state_path=self.state_path,
                jsonl_path=self.jsonl,
                token="t", chat_id="-1", thread_id=1,
                dry_run=False,
            )
        self.assertEqual(result["sent"], 0)
        self.assertEqual(result["skipped_already"], 2)

    def test_dry_run_does_not_send_nor_write_state(self):
        with self._mock_send() as m:
            result = notifier.tick(
                escalations_dir=self.esc_dir,
                state_path=self.state_path,
                jsonl_path=self.jsonl,
                token="t", chat_id="-1", thread_id=1,
                dry_run=True,
            )
        m.assert_not_called()
        self.assertFalse(self.state_path.exists())
        self.assertEqual(result["sent"], 0)
        self.assertEqual(result["would_send"], 2)

    def test_send_failure_skips_and_retries_next_tick(self):
        # First tick: send fails for one of them
        call_count = [0]
        def flaky(body, token):
            call_count[0] += 1
            if call_count[0] == 1:
                return False, {"error": "telegram_api_500"}
            return True, {"message_id": call_count[0]}
        with patch("lib.notifier.send_telegram_message", side_effect=flaky):
            result = notifier.tick(
                escalations_dir=self.esc_dir,
                state_path=self.state_path,
                jsonl_path=self.jsonl,
                token="t", chat_id="-1", thread_id=1,
                dry_run=False,
            )
        # 1 sent, 1 failed — state has only the sent one
        self.assertEqual(result["sent"], 1)
        self.assertEqual(result["failed"], 1)
        state = notifier.load_state(self.state_path)
        self.assertEqual(len(state["notifications"]), 1)
```

- [ ] **Step 2: Rodar e confirmar falha**

```bash
python3 -m unittest tests.test_notifier -v
```

Expected: FAIL com `AttributeError: ... 'tick'`.

- [ ] **Step 3: Implementar `tick` no `notifier.py`**

```python
def tick(
    *,
    escalations_dir: Path,
    state_path: Path,
    jsonl_path: Path,
    token: str,
    chat_id: str,
    thread_id: int,
    dry_run: bool = False,
) -> dict:
    """Run one tick. Returns summary dict (for --json output).

    Side effects (unless dry_run): append events to jsonl, update state.
    Never raises for Telegram failures — logs event + continues.
    """
    import time as _time
    started_at = _time.monotonic()
    state = load_state(state_path)
    pending_triples = scan_escalations(escalations_dir)
    pending_cids = {cid for (_t, cid, _p) in pending_triples}
    state_cids = set(state["notifications"].keys())
    new_cids, resolved_cids = compute_diff(pending_cids, state_cids)

    append_event(jsonl_path, "tick_started", {
        "dry_run": dry_run,
        "pending_count": len(pending_cids),
        "new_count": len(new_cids),
        "resolved_count": len(resolved_cids),
    })

    summary = {
        "sent": 0, "failed": 0,
        "skipped_already": len(pending_cids) - len(new_cids),
        "skipped_resolved": 0,
        "would_send": 0,
    }

    triples_by_cid = {cid: (t, cid, p) for (t, cid, p) in pending_triples}

    # Send new
    for cid in sorted(new_cids):
        task_id, _cid, source_path = triples_by_cid[cid]
        body = build_telegram_message(task_id, cid, chat_id, thread_id)
        if dry_run:
            append_event(jsonl_path, "notification_dry_run", {
                "clarification_id": cid, "body_text": body["text"],
            })
            summary["would_send"] += 1
            continue
        t_send_start = _time.monotonic()
        ok, result = send_telegram_message(body, token=token)
        latency_ms = int((_time.monotonic() - t_send_start) * 1000)
        if ok:
            state["notifications"][cid] = {
                "task_id": task_id,
                "notified_at": _now_iso(),
                "telegram_message_id": result.get("message_id"),
                "source_path": source_path,
            }
            append_event(jsonl_path, "notification_sent", {
                "clarification_id": cid, "task_id": task_id,
                "telegram_message_id": result.get("message_id"),
                "latency_ms": latency_ms,
            })
            summary["sent"] += 1
        else:
            append_event(jsonl_path, "notification_send_failed", {
                "clarification_id": cid,
                "error": result.get("error"),
                "detail": result.get("detail"),
                "retry_in_next_tick": True,
            })
            summary["failed"] += 1

    # GC resolved
    for cid in sorted(resolved_cids):
        was = state["notifications"].pop(cid, {})
        if dry_run:
            # restore on dry run
            if was:
                state["notifications"][cid] = was
            append_event(jsonl_path, "notification_skipped_resolved_dry_run", {
                "clarification_id": cid,
            })
            continue
        append_event(jsonl_path, "notification_skipped_resolved", {
            "clarification_id": cid,
            "was_notified_at": was.get("notified_at"),
        })
        summary["skipped_resolved"] += 1

    # Skipped already (pending ∩ state), 1 event per, for observability
    already = pending_cids & state_cids
    for cid in sorted(already):
        append_event(jsonl_path, "notification_skipped_already_sent", {
            "clarification_id": cid,
        })

    if not dry_run:
        state["heartbeat_at"] = _now_iso()
        save_state(state_path, state)

    append_event(jsonl_path, "notifier_heartbeat", {})
    duration_ms = int((_time.monotonic() - started_at) * 1000)
    append_event(jsonl_path, "tick_finished", {
        "sent": summary["sent"],
        "failed": summary["failed"],
        "skipped_already": summary["skipped_already"],
        "skipped_resolved": summary["skipped_resolved"],
        "would_send": summary["would_send"],
        "duration_ms": duration_ms,
    })
    return summary
```

- [ ] **Step 4: Rodar e confirmar 29/29**

```bash
python3 -m unittest tests.test_notifier -v
```

Expected: `Ran 29 tests ... OK`.

### Task 12: GC resolved + fcntl lock (red→green)

**Files:**
- Modify: `~/.openclaw/clarification-agent/tests/test_notifier.py`
- Modify: `~/.openclaw/clarification-agent/lib/notifier.py`

- [ ] **Step 1: Acrescentar tests de GC e lock**

```python
class TestGCAndLock(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.esc_dir = self.tmp / "escalations"
        self.esc_dir.mkdir()
        self.state_path = self.tmp / "notifier-state.json"
        self.jsonl = self.tmp / "notifier.jsonl"
        self.lock_path = self.tmp / "notifier.lock"

    def tearDown(self):
        import shutil
        shutil.rmtree(self.tmp)

    def test_resolved_cid_is_gc_without_message(self):
        # Seed state with cid that is no longer in escalations dir
        state = {
            "schema_version": 1, "heartbeat_at": None,
            "notifications": {
                "T-0001-clr-1": {
                    "task_id": "T-0001", "notified_at": "2026-01-01T00:00:00Z",
                    "telegram_message_id": 1, "source_path": "/gone",
                },
            },
        }
        notifier.save_state(self.state_path, state)

        with patch("lib.notifier.send_telegram_message") as m:
            m.return_value = (True, {"message_id": 99})
            result = notifier.tick(
                escalations_dir=self.esc_dir,
                state_path=self.state_path,
                jsonl_path=self.jsonl,
                token="t", chat_id="-1", thread_id=1,
                dry_run=False,
            )
        m.assert_not_called()  # no send because resolved
        self.assertEqual(result["skipped_resolved"], 1)
        post = notifier.load_state(self.state_path)
        self.assertNotIn("T-0001-clr-1", post["notifications"])

    def test_acquire_lock_blocks_concurrent_attempt(self):
        # First acquire succeeds
        fd = notifier.acquire_lock(self.lock_path)
        self.assertIsNotNone(fd)
        # Second acquire (same process, non-blocking) returns None
        fd2 = notifier.acquire_lock(self.lock_path)
        self.assertIsNone(fd2)
        notifier.release_lock(fd)
```

- [ ] **Step 2: Rodar e confirmar 1º passa (GC já implementado na Task 11) + 2º falha**

```bash
python3 -m unittest tests.test_notifier -v
```

Expected: 1 pass, 1 FAIL com `AttributeError: ... 'acquire_lock'`.

- [ ] **Step 3: Implementar `acquire_lock` / `release_lock`**

No topo do `notifier.py`:

```python
import fcntl
```

Adicionar funções:

```python
def acquire_lock(lock_path: Path):
    """Try to acquire exclusive fcntl lock. Returns fd if acquired, None if busy."""
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    fd = os.open(str(lock_path), os.O_WRONLY | os.O_CREAT, 0o644)
    try:
        fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        return fd
    except BlockingIOError:
        os.close(fd)
        return None


def release_lock(fd) -> None:
    """Release previously acquired lock."""
    try:
        fcntl.flock(fd, fcntl.LOCK_UN)
    finally:
        os.close(fd)
```

- [ ] **Step 4: Rodar e confirmar 31/31**

```bash
python3 -m unittest tests.test_notifier -v
```

Expected: `Ran 31 tests ... OK`.

---

## Phase 4 — CLI + main entry

### Task 13: Main entry `__main__` com argparse

**Files:**
- Modify: `~/.openclaw/clarification-agent/lib/notifier.py`
- Modify: `~/.openclaw/clarification-agent/tests/test_notifier.py`

- [ ] **Step 1: Acrescentar tests de CLI main (patching sys.argv + env)**

```python
class TestMain(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.env_patch = patch.dict(os.environ, {
            "OPENCLAW_CLARIFICATION_DIR": str(self.tmp),
            "TELEGRAM_BOT_TOKEN": "abc:xyz",
            "TELEGRAM_CLARIFICATIONS_CHAT_ID": "-100XXXXXXXXXX",
            "TELEGRAM_CLARIFICATIONS_THREAD_ID": "42",
        }, clear=False)
        self.env_patch.start()
        (self.tmp / "escalations").mkdir()

    def tearDown(self):
        self.env_patch.stop()
        import shutil
        shutil.rmtree(self.tmp)

    def test_main_tick_happy_exits_zero(self):
        with patch("lib.notifier.send_telegram_message",
                   return_value=(True, {"message_id": 1})):
            rc = notifier.main(["--tick"])
        self.assertEqual(rc, 0)

    def test_main_missing_env_exits_one(self):
        with patch.dict(os.environ, {
            "TELEGRAM_BOT_TOKEN": "",
            "TELEGRAM_CLARIFICATIONS_CHAT_ID": "",
            "TELEGRAM_CLARIFICATIONS_THREAD_ID": "",
        }, clear=False):
            rc = notifier.main(["--tick"])
        self.assertEqual(rc, 1)

    def test_main_dry_run_does_not_send(self):
        (self.tmp / "escalations" / "T-0006-clr-2.md").touch()
        with patch("lib.notifier.send_telegram_message") as m:
            rc = notifier.main(["--tick", "--dry-run"])
        m.assert_not_called()
        self.assertEqual(rc, 0)

    def test_main_json_outputs_parseable_summary(self):
        import io
        stdout_capture = io.StringIO()
        with patch("lib.notifier.send_telegram_message",
                   return_value=(True, {"message_id": 1})), \
             patch("sys.stdout", stdout_capture):
            rc = notifier.main(["--tick", "--json"])
        self.assertEqual(rc, 0)
        parsed = json.loads(stdout_capture.getvalue())
        self.assertIn("sent", parsed)
```

- [ ] **Step 2: Rodar e confirmar falha**

```bash
python3 -m unittest tests.test_notifier -v
```

Expected: FAIL com `AttributeError: ... 'main'`.

- [ ] **Step 3: Implementar `main` no `notifier.py`**

No topo:

```python
import argparse
import sys
```

No final do arquivo:

```python
def _resolve_paths() -> Tuple[Path, Path, Path, Path]:
    """Resolve runtime paths (env override for tests)."""
    base = Path(os.environ.get(
        "OPENCLAW_CLARIFICATION_DIR",
        str(Path.home() / ".openclaw" / "clarification-agent"),
    ))
    return (
        base / "escalations",
        base / "notifier-state.json",
        base / "notifier.jsonl",
        base / "notifier.lock",
    )


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(
        prog="openclaw-clarification-notifier",
        description="Push Telegram notification per unsafe escalation (E10/OH wave-2).",
    )
    parser.add_argument("--tick", action="store_true",
                        help="Run one tick and exit (systemd oneshot).")
    parser.add_argument("--dry-run", action="store_true",
                        help="Compute but do not send or persist.")
    parser.add_argument("--json", action="store_true",
                        help="Print summary as JSON to stdout.")
    args = parser.parse_args(argv)

    if not args.tick:
        parser.print_help()
        return 1

    try:
        token, chat_id, thread_id = validate_env(os.environ)
    except EnvError as e:
        print(f"error: {e}", file=sys.stderr)
        return 1

    esc_dir, state_path, jsonl_path, lock_path = _resolve_paths()
    if not esc_dir.exists():
        print(f"error: escalations dir does not exist: {esc_dir}", file=sys.stderr)
        return 1

    fd = acquire_lock(lock_path)
    if fd is None:
        append_event(jsonl_path, "tick_skipped_lock", {})
        if args.json:
            print(json.dumps({"skipped": "lock_busy"}))
        return 0

    try:
        try:
            summary = tick(
                escalations_dir=esc_dir,
                state_path=state_path,
                jsonl_path=jsonl_path,
                token=token, chat_id=chat_id, thread_id=thread_id,
                dry_run=args.dry_run,
            )
        except OSError as e:
            append_event(jsonl_path, "tick_fatal_io", {"error": str(e)})
            print(f"fatal io error: {e}", file=sys.stderr)
            return 2
    finally:
        release_lock(fd)

    if args.json:
        print(json.dumps(summary, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 4: Rodar e confirmar 35/35**

```bash
python3 -m unittest tests.test_notifier -v
```

Expected: `Ran 35 tests ... OK`.

### Task 14: Wrapper `notifier.sh` para systemd

**Files:**
- Create: `~/.openclaw/clarification-agent/notifier.sh`

- [ ] **Step 1: Criar wrapper**

```bash
cat > ~/.openclaw/clarification-agent/notifier.sh <<'SH'
#!/bin/bash
# Wrapper para lib.notifier — invocado pelo systemd oneshot.
# Carrega .env (tolerante a linhas comentadas) + passa args pro python.
set -eu

ROOT="$HOME/.openclaw/clarification-agent"
ENV_FILE="$HOME/.openclaw/.env"

if [[ -f "$ENV_FILE" ]]; then
  # Carrega apenas linhas KEY=VALUE (ignora # e linhas vazias).
  set -a
  # shellcheck disable=SC1090
  source <(grep -E '^[A-Z_][A-Z0-9_]*=' "$ENV_FILE" || true)
  set +a
fi

cd "$ROOT"
exec /usr/bin/python3 -m lib.notifier "$@"
SH
chmod +x ~/.openclaw/clarification-agent/notifier.sh
```

- [ ] **Step 2: Smoke manual do wrapper (env vars faltando → exit 1)**

```bash
# Sanity: remove temporariamente a env var pra verificar exit 1
env -u TELEGRAM_CLARIFICATIONS_CHAT_ID -u TELEGRAM_CLARIFICATIONS_THREAD_ID \
  ~/.openclaw/clarification-agent/notifier.sh --tick
echo "Exit: $?"
```

Expected: `error: missing env vars: ...` + `Exit: 1`.

---

## Phase 5 — Deployment assets

### Task 15: Systemd unit files

**Files:**
- Create: `~/.openclaw/clarification-agent/systemd/openclaw-clarification-notifier.service`
- Create: `~/.openclaw/clarification-agent/systemd/openclaw-clarification-notifier.timer`

- [ ] **Step 1: Criar `.service`**

```ini
[Unit]
Description=OpenClaw Clarification Notifier (Telegram push) — E10/OH wave-2
After=openclaw-gateway.service
Wants=network-online.target

[Service]
Type=oneshot
WorkingDirectory=%h/.openclaw/clarification-agent
ExecStart=%h/.openclaw/clarification-agent/notifier.sh --tick
Environment=PYTHONUNBUFFERED=1
TimeoutStartSec=60
```

Salvar em `~/.openclaw/clarification-agent/systemd/openclaw-clarification-notifier.service`.

- [ ] **Step 2: Criar `.timer`**

```ini
[Unit]
Description=Timer — OpenClaw Clarification Notifier (60s default)

[Timer]
OnBootSec=60
OnUnitActiveSec=60
AccuracySec=5s
Persistent=true

[Install]
WantedBy=timers.target
```

Salvar em `~/.openclaw/clarification-agent/systemd/openclaw-clarification-notifier.timer`.

- [ ] **Step 3: Sanity check dos unit files**

```bash
systemd-analyze verify ~/.openclaw/clarification-agent/systemd/openclaw-clarification-notifier.{service,timer}
```

Expected: sem erros de parsing. Warnings sobre paths relativos são esperados (unit ainda não instalado).

### Task 16: Health registry entry

**Files:**
- Modify: `~/.openclaw/health/registry.yml`

- [ ] **Step 1: Confirmar schema existente do registry**

```bash
head -30 ~/.openclaw/health/registry.yml
```

Expected: lista YAML de entradas; pegar padrão de campos usados (id, name, epic, critical, check_type, systemd_unit).

- [ ] **Step 2: Acrescentar entry novo**

Acrescentar no final do `registry.yml`:

```yaml
- id: openclaw-clarification-notifier
  name: "OpenClaw Clarification Notifier (Telegram)"
  epic: "E10"
  critical: false
  check_type: "systemd_active"
  systemd_unit: "openclaw-clarification-notifier.timer"
```

Se o schema real tiver campos adicionais (ex: `severity`, `owner`), seguir o padrão das demais entradas E10.

- [ ] **Step 3: Validar YAML**

```bash
python3 -c "import yaml; yaml.safe_load(open('~/.openclaw/health/registry.yml'))" && echo OK
```

Expected: `OK`.

### Task 17: `smoke_notifier.sh` — 7 cenários da spec §5

**Files:**
- Create: `~/.openclaw/clarification-agent/smoke_notifier.sh`

- [ ] **Step 1: Criar smoke script cobrindo os 7 cenários**

```bash
#!/bin/bash
# Smoke E2E — clarification-notifier wave-2
# Cobre 7 cenários da spec 2026-04-21-e10-telegram-push-escalations §5.
set -u

PASS=0
FAIL=0
FAILED_NAMES=()
_ok()   { echo "  ✓ $1"; PASS=$((PASS+1)); }
_fail() { echo "  ✗ $1"; FAIL=$((FAIL+1)); FAILED_NAMES+=("$1"); }

ROOT=~/.openclaw/clarification-agent
ESC="$ROOT/escalations"
STATE="$ROOT/notifier-state.json"
JSONL="$ROOT/notifier.jsonl"

# Backup estado antes do smoke
[ -f "$STATE" ] && cp "$STATE" "$STATE.smoke-bak"
[ -f "$JSONL" ] && cp "$JSONL" "$JSONL.smoke-bak"

_restore() {
  [ -f "$STATE.smoke-bak" ] && mv "$STATE.smoke-bak" "$STATE" || rm -f "$STATE"
  [ -f "$JSONL.smoke-bak" ] && mv "$JSONL.smoke-bak" "$JSONL" || rm -f "$JSONL"
}

# ========= 1. Happy path, 1 escalation nova =========
echo "=== 1. Happy path 1 escalation ==="
# Manual: requer Bot API real. Executar com live env.
echo "  (pending — requires live TELEGRAM_BOT_TOKEN + thread_id válido)"

# ========= 2. Dry run não envia nem grava =========
echo "=== 2. Dry run ==="
rm -f "$STATE" "$JSONL"
touch "$ESC/T-SMOKE-clr-1.md" 2>/dev/null || true
out=$("$ROOT/notifier.sh" --tick --dry-run --json 2>&1 || true)
if echo "$out" | grep -q '"would_send"'; then
  _ok "dry-run reports would_send"
else
  _fail "dry-run did NOT output would_send"
fi
[ ! -f "$STATE" ] && _ok "dry-run did not create state" || _fail "dry-run CREATED state"
rm -f "$ESC/T-SMOKE-clr-1.md"

# ========= 3. Env var ausente → exit 1 =========
echo "=== 3. Missing env var ==="
rc=$(env -u TELEGRAM_CLARIFICATIONS_THREAD_ID "$ROOT/notifier.sh" --tick 2>/dev/null; echo $?)
[ "$rc" = "1" ] && _ok "missing env var → exit 1" || _fail "expected exit 1 got $rc"

# ========= 4. Recovery silencioso =========
echo "=== 4. Recovery silencioso ==="
# Manual: resolve uma clarification (override/reject-task) e confirma que não há Telegram.
echo "  (pending — requires live override command + live Bot API observability)"

# ========= 5. Parse error não quebra o tick =========
echo "=== 5. Parse error em filename inválido ==="
rm -f "$STATE" "$JSONL"
touch "$ESC/garbage.md"
out=$("$ROOT/notifier.sh" --tick --dry-run --json 2>&1 || true)
# Garbage não deve aparecer em nenhum evento de notification
if grep -q "garbage" "$JSONL" 2>/dev/null; then
  _fail "garbage file appeared in audit events"
else
  _ok "garbage file ignored"
fi
rm -f "$ESC/garbage.md"

# ========= 6. Múltiplas escalations de uma vez =========
echo "=== 6. Multiple escalations ==="
# Manual: criar 5 escalations falsas + live send. Pending.
echo "  (pending — requires live Bot API)"

# ========= 7. Telegram API down (network) =========
echo "=== 7. Telegram API network failure ==="
# Manual: desconectar rede + tick + verificar event notification_send_failed.
echo "  (pending — requires network toggle + live run)"

_restore
echo ""
echo "== Smoke summary =="
echo "PASS=$PASS FAIL=$FAIL"
if [ "$FAIL" -gt 0 ]; then
  echo "Failed scenarios:"
  for n in "${FAILED_NAMES[@]}"; do echo "  - $n"; done
  exit 1
fi
exit 0
```

Tornar executável:

```bash
chmod +x ~/.openclaw/clarification-agent/smoke_notifier.sh
```

- [ ] **Step 2: Rodar o smoke e confirmar 3 automatizados passam**

```bash
~/.openclaw/clarification-agent/smoke_notifier.sh
```

Expected: 4 cenários PASS automatizados (2 assertions + 3 env + 5 garbage); 4 cenários pending (marcados para execução manual do Bernard com live Bot API).

---

## Phase 6 — Integração + docs

### Task 18: Atualizar playbook.md + README.md

**Files:**
- Modify: `~/.openclaw/clarification-agent/playbook.md`
- Modify: `~/.openclaw/clarification-agent/README.md`

- [ ] **Step 1: Ler playbook atual pra identificar ponto de inserção**

```bash
grep -n "^## " ~/.openclaw/clarification-agent/playbook.md
```

Expected: lista de seções; identificar onde inserir "Push mode (Telegram notifier)" (provavelmente depois de "Pull mode").

- [ ] **Step 2: Acrescentar seção no `playbook.md`**

Inserir após a seção existente de "Pull mode (daemon)":

```markdown
## Push mode (Telegram notifier)

Serviço standalone (wave-2 OH) que notifica Bernard via Telegram quando
nova escalation unsafe aparece em `escalations/`. Desacoplado do daemon
pull — não depende do clarification-daemon rodar.

**Ativar:**

    cp ~/.openclaw/clarification-agent/systemd/openclaw-clarification-notifier.{service,timer} \
       ~/.config/systemd/user/
    systemctl --user daemon-reload
    systemctl --user enable --now openclaw-clarification-notifier.timer

**Desativar (rollback):**

    systemctl --user disable --now openclaw-clarification-notifier.timer

Escalations continuam sendo escritas normalmente; apenas o push Telegram
para. Zero dado perdido.

**Forçar re-envio de todas as escalations pendentes:**

    rm ~/.openclaw/clarification-agent/notifier-state.json
    # próximo tick vai disparar uma msg por escalation ainda em escalations/

**Observabilidade:**

- Audit append-only: `~/.openclaw/clarification-agent/notifier.jsonl`
- State idempotência: `~/.openclaw/clarification-agent/notifier-state.json`
- Health: entrada `openclaw-clarification-notifier` em `health/registry.yml`
```

- [ ] **Step 3: Acrescentar bullet no `README.md`**

Identificar a lista de serviços existente (se houver) e acrescentar:

```markdown
- **clarification-notifier** (E10/OH wave-2, 60s timer) — envia Telegram
  push para tópico `clarifications` em cada nova escalation unsafe.
  Standalone. Rollback: `systemctl --user disable --now openclaw-clarification-notifier.timer`.
```

- [ ] **Step 4: Nenhum commit nesta task** (runtime não é git).

### Task 19: Re-executar suite completa + lint

**Files:** nenhum.

- [ ] **Step 1: Rodar a suite completa e contar tests**

```bash
cd ~/.openclaw/clarification-agent
python3 -m unittest discover tests -v 2>&1 | tail -30
```

Expected: todos os tests (wave-1 + wave-2) passam. Contagem esperada: wave-1 tinha 24 tests + wave-2 adiciona ~35 novos = ~59 tests OK.

- [ ] **Step 2: Smoke wave-1 ainda passa (guard regressão push mode)**

```bash
~/.openclaw/clarification-agent/smoke_e2e.sh 2>&1 | tail -10
```

Expected: cenários automatizados da wave-1 continuam PASS (fast-fail, killswitch, lock). Wave-1 smoke não deve regredir com a adição do notifier.

- [ ] **Step 3: Lint rápido — imports órfãos no notifier.py**

```bash
python3 -m py_compile ~/.openclaw/clarification-agent/lib/notifier.py && echo OK
```

Expected: `OK` sem warnings.

- [ ] **Step 4: Sanity CLI help**

```bash
~/.openclaw/clarification-agent/notifier.sh --help 2>&1 | head -20
```

Expected: argparse help com `--tick`, `--dry-run`, `--json`.

### Task 20: Atualizar spec canônica + delivery tracker + commit

**Files:**
- Modify: `bevox-knowledge/35_specs/2026-04-21-e10-telegram-push-escalations.md` (status + ajuste §6.1 R1)
- Modify: `bevox-knowledge/40_roadmap/delivery-tracker.yml` (entry wave-2 delivered)

- [ ] **Step 1: Confirmar branch draft ainda ativa**

```bash
cd ~/bevox-knowledge
git branch --show-current
```

Expected: `draft/adr-009-clarification-daemon`.

- [ ] **Step 2: Atualizar status da spec wave-2**

No topo da spec (`35_specs/2026-04-21-e10-telegram-push-escalations.md`), mudar:

```markdown
**Status:** draft
```

para:

```markdown
**Status:** delivered (2026-04-22)
```

Editar também §6.1 R1 removendo a referência a `getForumTopic` (endpoint não existe):

De:
```markdown
- **R1**: thread_id errado → msg vai pra geral do grupo ou 400. Mitigacao:
  validar `getForumTopic` no startup; sair exit 1 com msg clara se thread_id
  invalido.
```

Para:
```markdown
- **R1**: thread_id errado → msg vai pra geral do grupo ou 400. Mitigacao:
  validar presença das env vars no startup (exit 1 se ausente); primeira
  tentativa de sendMessage serve de teste live — 400/bad thread é loggado
  em `notification_send_failed` + retry no proximo tick. Evita roundtrip
  extra por tick.
```

- [ ] **Step 3: Acrescentar entrada no `delivery-tracker.yml`**

Abrir `40_roadmap/delivery-tracker.yml`, localizar o bloco da wave-1 delivered (E10 Operational Loop Hardening) e acrescentar wave-2 logo depois no mesmo padrão. Exemplo (ajustar ao schema real — seguir a wave-1 entry):

```yaml
  - wave: "E10/OH/wave-2-telegram-push-escalations"
    spec: "35_specs/2026-04-21-e10-telegram-push-escalations.md"
    status: "delivered"
    delivered_at: "2026-04-22"
    notes: "Push Telegram 60s timer. Standalone service. Tests 35/35. Rollback 1 cmd."
```

- [ ] **Step 4: Commit na branch draft**

```bash
cd ~/bevox-knowledge
git add 35_specs/2026-04-21-e10-telegram-push-escalations.md \
        40_roadmap/delivery-tracker.yml
git diff --cached --stat
git commit -m "delivery(E10): wave-2 telegram-push-escalations delivered

- Status draft → delivered (2026-04-22)
- §6.1 R1 ajustado: remove getForumTopic (endpoint inexistente); valida
  presença das env vars no startup; primeira sendMessage serve de teste live.
- Delivery tracker: entry OH/wave-2 delivered (35 tests OK).

Bloco OH restante: waves 3-6 spec + plan pendentes; wave-7 post-wave-6."
```

- [ ] **Step 5: NAO pushar** (bloco OH merge canônico para main condicional ao ciclo completo PASS no self-test wave-7).

- [ ] **Step 6: Confirmar log**

```bash
git log --oneline -5
```

Expected: novo commit `delivery(E10): wave-2 telegram-push-escalations delivered` no topo, acima de `707fa61 delivery(E10): wave-1 clarification-daemon-local-first delivered`.

---

## Checklist final

- [ ] **Fase 1-4 green:** 35 tests OK (`python3 -m unittest tests.test_notifier -v`).
- [ ] **Wave-1 não regrediu:** `tests.test_provider` + `tests.test_poller` + `tests.test_store_poll_append` todos ainda PASS.
- [ ] **Smoke wave-2:** 4 cenários automatizados PASS; 4 manuais marcados pending.
- [ ] **Wrapper funciona:** `notifier.sh --help` mostra argparse; `--tick` sem env vars retorna exit 1.
- [ ] **Systemd verify:** `systemd-analyze verify` sem erros.
- [ ] **Health registry atualizado:** YAML válido.
- [ ] **Docs:** `playbook.md` com seção nova; `README.md` com bullet.
- [ ] **Bevox-knowledge commit:** spec status delivered + tracker entry; branch ainda `draft/adr-009-clarification-daemon`; NAO pushado.
- [ ] **Env vars placeholder:** `.env` tem as 2 vars comentadas; Bernard descomenta + preenche thread_id quando ativar systemd.

---

## Próximos passos pós-delivery wave-2

1. Bernard prove `TELEGRAM_CLARIFICATIONS_THREAD_ID` real + descomenta no `.env`.
2. Bernard ativa systemd:
   ```bash
   cp ~/.openclaw/clarification-agent/systemd/openclaw-clarification-notifier.{service,timer} \
      ~/.config/systemd/user/
   systemctl --user daemon-reload
   systemctl --user enable --now openclaw-clarification-notifier.timer
   ```
3. Validação live: primeiro tick deve disparar 3 msgs (T-0006-clr-2, T-0008-clr-1, T-0008-clr-2) no tópico `clarifications`.
4. **Wave-3 (telegram-reply-handler)** próxima — plugin `clarification-commands` em `~/code/knowledge-sync/plugins/`.
