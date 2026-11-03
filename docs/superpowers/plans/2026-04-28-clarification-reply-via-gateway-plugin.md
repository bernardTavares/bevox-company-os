# Clarification Reply via Gateway Plugin Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Consolidar caminho de ingestão Telegram de replies de clarification no plugin `clarification-commands` do gateway; deletar daemon paralelo `openclaw-clarification-daemon` e bumpar `notifier-state.json` para schema v2 com tupla canônica completa.

**Architecture:** Token discipline (1 token = 1 consumer); `notifier-state.json` schema v2 é SoT compartilhada (Python notifier escreve, Node plugin lê); 3 caminhos de ingestão equivalentes (swipe-reply nativo, `/clr_override`, CLI manual) todos invocando `cmd_answer`; pré-condição `topics.clarifications` validada no envio com fallback central.

**Tech Stack:** Python 3.13 (clarification-agent + scripts), Node.js (plugin Node.js ESM em `~/.openclaw/extensions/clarification-commands/`), Bash (bootstrap/systemd), `unittest` (Python tests), Telegram Bot API.

**Spec:** `docs/superpowers/specs/2026-04-28-clarification-reply-via-gateway-plugin-design.md`

---

## File Structure

### Modificados

| Arquivo | Responsabilidade |
|---|---|
| `clarification-agent/lib/store.py` | Helpers de I/O do `notifier-state.json` schema v2 + função `migrate_v1_to_v2()` |
| `clarification-agent/lib/notifier.py` | Escreve schema v2 + valida `topics.clarifications` + fallback central |
| `clarification-agent/lib/reply_handler.py` | Reduzido: `handle_reply()` atualiza `status=resolved` no notifier-state; `send_confirmation_message()` usa `entry.token_alias` |
| `clarification-agent/lib/api.py` | Remove `cmd_poll_replies` + parser; mantém `cmd_answer` e `cmd_poll_tick` |
| `clarification-agent/tests/test_store.py` | NOVO — testes do schema v2 + migração |
| `clarification-agent/tests/test_notifier.py` | Estende — testes da pré-condição + fallback |
| `clarification-agent/tests/test_reply_handler.py` | Estende — testes do confirmation routing |
| `~/.openclaw/extensions/clarification-commands/lib/*.js` | Schema v2 awareness + cross-validation `(chat_id, thread_id)` + idempotência `status==pending` |
| `~/.openclaw/scripts/bootstrap-telegram-agent.sh` | Force-inject `clarification-commands` no `--skills` default + validação pós-bootstrap |

### Deletados

| Caminho | Motivo |
|---|---|
| `clarification-agent/lib/poller.py` | Daemon poll-replies aposentado |
| `clarification-agent/lib/dynamic_reply_handler.py` | Daemon poll-replies aposentado |
| `clarification-agent/lib/*.pre-poll.bak` (3 arquivos) | Backups manuais obsoletos |
| `clarification-agent/bot-states/` (diretório) | State files do daemon |
| `clarification-agent/telegram-reply-state.json` | Cursor legacy do daemon |
| `clarification-agent/systemd/openclaw-clarification-daemon.service` | Daemon aposentado |
| `clarification-agent/systemd/openclaw-clarification-daemon.timer` | Daemon aposentado |

### Criados (artefatos canônicos em bevox-knowledge — branch `draft/`)

| Caminho | Tipo |
|---|---|
| `bevox-knowledge/30_adr/company-os/ADR-011-clarification-reply-via-gateway-plugin.md` | ADR nova |
| `bevox-knowledge/35_specs/openclaw/2026-04-28-clarification-reply-via-gateway-plugin.md` | Spec canônica |

### Já criados nesta sessão (de brainstorming)

| Caminho | Estado |
|---|---|
| `~/.openclaw/docs/superpowers/specs/2026-04-28-clarification-reply-via-gateway-plugin-design.md` | commitado em main (commit `8464fe2`) |
| `bevox-knowledge/10_prd/_shared/2026-04-28-knowledge-as-living-system-investigation-prd.md` | criado, não commitado |
| `bevox-knowledge/00_inbox/openclaw/2026-04-28-workspace-template-structure-investigation.md` | criado, não commitado |

---

## Test Conventions

Framework: `unittest` (já usado pelo clarification-agent). Comando-padrão para rodar testes:

```bash
cd ~/.openclaw/clarification-agent && python3 -m unittest tests/<test_file>.py -v
```

Para subset: `python3 -m unittest tests.test_X.TestY.test_specific -v`.

Imports nos testes seguem padrão existente: `from lib import notifier` (cwd = `clarification-agent/`).

---

## Task 1 — Phase 0: Disable daemon + backup notifier-state

**Files:**
- Modify (system state): systemd user units `openclaw-clarification-daemon.timer`/`.service`
- Modify (data): `~/.openclaw/clarification-agent/notifier-state.json` → backup como `.v1.bak`

- [ ] **Step 1: Verify daemon is currently active**

```bash
systemctl --user is-active openclaw-clarification-daemon.timer
```
Expected: `active`

- [ ] **Step 2: Stop and disable daemon timer + service**

```bash
systemctl --user disable --now openclaw-clarification-daemon.timer
systemctl --user disable --now openclaw-clarification-daemon.service 2>/dev/null || true
systemctl --user is-active openclaw-clarification-daemon.timer
```
Expected (last command): `inactive`

- [ ] **Step 3: Confirm timer file remains on disk (will be deleted in Task 10)**

```bash
ls -la ~/.config/systemd/user/openclaw-clarification-daemon.* 2>/dev/null
```
Expected: 2 files listed (timer + service).

- [ ] **Step 4: Backup current notifier-state.json**

```bash
cp ~/.openclaw/clarification-agent/notifier-state.json ~/.openclaw/clarification-agent/notifier-state.v1.bak
diff ~/.openclaw/clarification-agent/notifier-state.json ~/.openclaw/clarification-agent/notifier-state.v1.bak
```
Expected: diff returns nothing (identical files).

- [ ] **Step 5: Confirm `openclaw-clarification-notifier` (envio) ainda está ativo**

```bash
systemctl --user is-active openclaw-clarification-notifier.timer
```
Expected: `active` — esse é serviço diferente, NÃO desabilitar.

- [ ] **Step 6: Commit no-op marker (state change is on disk; no code change)**

This task changes only system state and data files (.bak); no code commit needed. Move on to Task 2.

---

## Task 2 — Phase 1a: Schema v2 helpers em `store.py`

**Files:**
- Modify: `~/.openclaw/clarification-agent/lib/store.py` (adiciona helpers)
- Test: `~/.openclaw/clarification-agent/tests/test_store_v2.py` (NOVO)

- [ ] **Step 1: Write the failing tests**

Create `~/.openclaw/clarification-agent/tests/test_store_v2.py`:

```python
"""Tests for notifier-state.json schema v2 helpers."""
import json
import tempfile
import unittest
from pathlib import Path

from lib import store


class TestSchemaV2(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False)
        self.tmp.close()
        self.path = Path(self.tmp.name)

    def tearDown(self):
        if self.path.exists():
            self.path.unlink()

    def test_load_state_v2_returns_empty_when_missing(self):
        self.path.unlink()
        result = store.load_state_v2(self.path)
        self.assertEqual(result["schema_version"], 2)
        self.assertEqual(result["notifications"], {})

    def test_save_state_v2_writes_atomic(self):
        state = {
            "schema_version": 2,
            "heartbeat_at": "2026-04-28T14:00:00Z",
            "notifications": {
                "T-0001-clr-1": {
                    "task_id": "T-0001",
                    "project": "bevox-site",
                    "token_alias": "project-bevox-site",
                    "chat_id": "-100123456",
                    "thread_id": 18,
                    "telegram_message_id": 273,
                    "sent_at": "2026-04-28T11:36:01Z",
                    "status": "pending",
                    "resolved_at": None,
                    "resolved_via": None,
                }
            }
        }
        store.save_state_v2(self.path, state)
        loaded = json.loads(self.path.read_text(encoding="utf-8"))
        self.assertEqual(loaded["schema_version"], 2)
        self.assertEqual(loaded["notifications"]["T-0001-clr-1"]["status"], "pending")

    def test_load_state_v2_returns_v2_when_v1_detected(self):
        # v1 schema (current production)
        v1 = {
            "schema_version": 1,
            "heartbeat_at": "2026-04-28T14:00:00Z",
            "notifications": {
                "T-0024-clr-4": {
                    "task_id": "T-0024",
                    "notified_at": "2026-04-27T14:33:42Z",
                    "telegram_message_id": 273,
                    "source_path": "/path/to/escalation.md",
                }
            }
        }
        self.path.write_text(json.dumps(v1))
        result = store.load_state_v2(self.path)
        # load_state_v2 NEVER mutates schema by itself — caller calls migrate
        self.assertEqual(result["schema_version"], 1)


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run test to verify it fails**

```bash
cd ~/.openclaw/clarification-agent && python3 -m unittest tests.test_store_v2 -v
```
Expected: FAIL — `AttributeError: module 'lib.store' has no attribute 'load_state_v2'`

- [ ] **Step 3: Implement `load_state_v2` and `save_state_v2` in `store.py`**

Append to `~/.openclaw/clarification-agent/lib/store.py`:

```python
SCHEMA_V2_EMPTY = {
    "schema_version": 2,
    "heartbeat_at": None,
    "notifications": {},
}


def load_state_v2(path: Path) -> dict:
    """Load notifier-state.json. Returns dict with schema_version field intact.

    Caller must check schema_version and call migrate_v1_to_v2() if needed.
    Missing/corrupt file returns empty v2 shape.
    """
    if not path.exists():
        return dict(SCHEMA_V2_EMPTY, notifications={})
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
    except (OSError, json.JSONDecodeError):
        return dict(SCHEMA_V2_EMPTY, notifications={})
    if not isinstance(data, dict) or "notifications" not in data:
        return dict(SCHEMA_V2_EMPTY, notifications={})
    data.setdefault("schema_version", 1)
    data.setdefault("heartbeat_at", None)
    return data


def save_state_v2(path: Path, state: dict) -> None:
    """Atomic write of schema v2 state. Uses _atomic_write helper."""
    path.parent.mkdir(parents=True, exist_ok=True)
    state.setdefault("schema_version", 2)
    _atomic_write(path, json.dumps(state, ensure_ascii=False, indent=2))
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
cd ~/.openclaw/clarification-agent && python3 -m unittest tests.test_store_v2 -v
```
Expected: 3 tests PASS

- [ ] **Step 5: Commit**

```bash
cd ~/.openclaw && git add clarification-agent/lib/store.py clarification-agent/tests/test_store_v2.py
git commit -m "$(cat <<'EOF'
feat(store): schema v2 load/save helpers for notifier-state.json

Adds load_state_v2() and save_state_v2() for the new schema with full
clarification tuple per entry. Atomic write via existing _atomic_write.
load_state_v2 preserves schema_version field (no auto-migration; caller
controls when migration runs).

Part of clarification-reply-via-gateway-plugin redesign (spec 2026-04-28).

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 3 — Phase 1b: Migration v1 → v2

**Files:**
- Modify: `~/.openclaw/clarification-agent/lib/store.py` (adiciona `migrate_v1_to_v2`)
- Test: `~/.openclaw/clarification-agent/tests/test_store_v2.py` (estende)

- [ ] **Step 1: Add failing tests for migration**

Append to `~/.openclaw/clarification-agent/tests/test_store_v2.py`:

```python
class TestMigrationV1V2(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False)
        self.tmp.close()
        self.path = Path(self.tmp.name)

    def tearDown(self):
        if self.path.exists():
            self.path.unlink()

    def test_migrate_marks_unresolvable_as_orphan(self):
        v1 = {
            "schema_version": 1,
            "notifications": {
                "T-0024-clr-4": {
                    "task_id": "T-0024",
                    "notified_at": "2026-04-27T14:33:42Z",
                    "telegram_message_id": 273,
                    "source_path": "/path/to/escalation.md",
                }
            }
        }
        # Empty resolver = nothing can be resolved
        def resolver(task_id):
            return None
        result = store.migrate_v1_to_v2(v1, resolver)
        entry = result["notifications"]["T-0024-clr-4"]
        self.assertEqual(result["schema_version"], 2)
        self.assertEqual(entry["status"], "orphan")
        self.assertEqual(entry["telegram_message_id"], 273)
        self.assertIsNone(entry.get("project"))

    def test_migrate_resolves_when_meta_available(self):
        v1 = {
            "schema_version": 1,
            "notifications": {
                "T-0105-clr-1": {
                    "task_id": "T-0105",
                    "notified_at": "2026-04-28T11:36:01Z",
                    "telegram_message_id": 273,
                }
            }
        }
        def resolver(task_id):
            if task_id == "T-0105":
                return {
                    "project": "bevox-site",
                    "token_alias": "project-bevox-site",
                    "chat_id": "-100xxxxx",
                    "thread_id": 18,
                }
            return None
        result = store.migrate_v1_to_v2(v1, resolver)
        entry = result["notifications"]["T-0105-clr-1"]
        self.assertEqual(entry["status"], "pending")
        self.assertEqual(entry["project"], "bevox-site")
        self.assertEqual(entry["token_alias"], "project-bevox-site")
        self.assertEqual(entry["thread_id"], 18)
        self.assertEqual(entry["telegram_message_id"], 273)

    def test_migrate_idempotent_on_v2_input(self):
        v2 = {
            "schema_version": 2,
            "notifications": {
                "T-0001-clr-1": {
                    "task_id": "T-0001",
                    "status": "pending",
                    "project": "bevox-site",
                }
            }
        }
        def resolver(task_id):
            return None
        result = store.migrate_v1_to_v2(v2, resolver)
        self.assertEqual(result, v2)
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
cd ~/.openclaw/clarification-agent && python3 -m unittest tests.test_store_v2.TestMigrationV1V2 -v
```
Expected: 3 FAIL with `AttributeError: module 'lib.store' has no attribute 'migrate_v1_to_v2'`

- [ ] **Step 3: Implement `migrate_v1_to_v2` in `store.py`**

Append to `~/.openclaw/clarification-agent/lib/store.py`:

```python
def migrate_v1_to_v2(state: dict, resolver) -> dict:
    """Convert schema v1 entries to schema v2.

    `resolver(task_id) -> dict or None` is called per entry to resolve
    `(project, token_alias, chat_id, thread_id)`. If resolver returns
    None, entry is marked status="orphan".

    Idempotent: if state already has schema_version=2, returns unchanged.
    """
    if state.get("schema_version") == 2:
        return state

    new_notifications = {}
    for cid, old in state.get("notifications", {}).items():
        resolved = resolver(old.get("task_id"))
        if resolved:
            new_notifications[cid] = {
                "task_id": old.get("task_id"),
                "project": resolved.get("project"),
                "token_alias": resolved.get("token_alias"),
                "chat_id": resolved.get("chat_id"),
                "thread_id": resolved.get("thread_id"),
                "telegram_message_id": old.get("telegram_message_id"),
                "sent_at": old.get("notified_at"),
                "status": "pending",
                "resolved_at": None,
                "resolved_via": None,
            }
        else:
            new_notifications[cid] = {
                "task_id": old.get("task_id"),
                "project": None,
                "token_alias": None,
                "chat_id": None,
                "thread_id": None,
                "telegram_message_id": old.get("telegram_message_id"),
                "sent_at": old.get("notified_at"),
                "status": "orphan",
                "resolved_at": None,
                "resolved_via": None,
            }
    return {
        "schema_version": 2,
        "heartbeat_at": state.get("heartbeat_at"),
        "notifications": new_notifications,
    }
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
cd ~/.openclaw/clarification-agent && python3 -m unittest tests.test_store_v2.TestMigrationV1V2 -v
```
Expected: 3 tests PASS

- [ ] **Step 5: Commit**

```bash
cd ~/.openclaw && git add clarification-agent/lib/store.py clarification-agent/tests/test_store_v2.py
git commit -m "$(cat <<'EOF'
feat(store): migrate_v1_to_v2 for notifier-state.json

Idempotent migration from schema v1 to v2 with caller-provided resolver
for (project, token_alias, chat_id, thread_id). Entries that cannot be
resolved are marked status="orphan" with partial fields preserved.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 4 — Phase 2a: Notifier escreve schema v2

**Files:**
- Modify: `~/.openclaw/clarification-agent/lib/notifier.py` (linhas ~369-376 dentro de `tick()`)
- Test: `~/.openclaw/clarification-agent/tests/test_notifier.py` (estende)

- [ ] **Step 1: Read current `tick()` write block to anchor changes**

```bash
sed -n '365,385p' ~/.openclaw/clarification-agent/lib/notifier.py
```
Current write at line ~369:
```python
state["notifications"][cid] = {
    "task_id": task_id,
    "notified_at": _now_iso(),
    "telegram_message_id": result.get("message_id"),
    "chat_id": str(eff_chat_id),
    "thread_id": eff_thread_id,
    "source_path": source_path,
}
```

- [ ] **Step 2: Add failing test for schema v2 entry shape**

Append to `~/.openclaw/clarification-agent/tests/test_notifier.py`:

```python
class TestNotifierWritesSchemaV2(unittest.TestCase):
    def test_tick_writes_v2_entry_with_token_alias_and_status(self):
        from unittest.mock import MagicMock
        from lib import notifier

        with tempfile.TemporaryDirectory() as td:
            esc_dir = Path(td) / "escalations"
            esc_dir.mkdir()
            (esc_dir / "T-9999-clr-1.md").write_text("dummy")
            state_path = Path(td) / "notifier-state.json"
            jsonl_path = Path(td) / "notifier.jsonl"

            with patch.object(notifier, "send_telegram_message",
                              return_value=(True, {"message_id": 555})):
                notifier.tick(
                    escalations_dir=esc_dir,
                    state_path=state_path,
                    jsonl_path=jsonl_path,
                    token="TOK", chat_id="-100abc", thread_id=18,
                )

            data = json.loads(state_path.read_text())
            self.assertEqual(data.get("schema_version"), 2)
            entry = data["notifications"]["T-9999-clr-1"]
            self.assertEqual(entry["telegram_message_id"], 555)
            self.assertEqual(entry["chat_id"], "-100abc")
            self.assertEqual(entry["thread_id"], 18)
            self.assertEqual(entry["status"], "pending")
            self.assertIn("sent_at", entry)
            self.assertIn("token_alias", entry)
            self.assertIsNone(entry["resolved_at"])
            self.assertIsNone(entry["resolved_via"])
```

- [ ] **Step 3: Run test to verify it fails**

```bash
cd ~/.openclaw/clarification-agent && python3 -m unittest tests.test_notifier.TestNotifierWritesSchemaV2 -v
```
Expected: FAIL — entry shape mismatch (no `status`, no `token_alias`, etc.)

- [ ] **Step 4: Modify `tick()` write block in `notifier.py`**

Find the block (around line 369-376) and replace with:

```python
state["notifications"][cid] = {
    "task_id": task_id,
    "project": slug,
    "token_alias": _alias_for(slug, eff_token, token),
    "chat_id": str(eff_chat_id),
    "thread_id": eff_thread_id,
    "telegram_message_id": result.get("message_id"),
    "sent_at": _now_iso(),
    "status": "pending",
    "resolved_at": None,
    "resolved_via": None,
    "source_path": source_path,  # mantém para diagnostics
}
```

Add helper at top of `notifier.py` (after imports):

```python
def _alias_for(slug, eff_token, default_token):
    """Return token_alias: 'project-<slug>' if eff_token != default else 'openclaw-central'."""
    if slug and eff_token != default_token:
        return f"project-{slug}"
    return "openclaw-central"
```

Update `save_state` (or its call in tick) to ensure `state["schema_version"] = 2` before write. Edit `_EMPTY_STATE`:

```python
_EMPTY_STATE = {
    "schema_version": 2,
    "heartbeat_at": None,
    "notifications": {},
}
```

And ensure `load_state` upgrades schema_version on read if missing:

```python
def load_state(path: Path) -> dict:
    # ... existing logic ...
    data.setdefault("schema_version", 2)  # was 1
    data.setdefault("heartbeat_at", None)
    return data
```

- [ ] **Step 5: Run all notifier tests**

```bash
cd ~/.openclaw/clarification-agent && python3 -m unittest tests.test_notifier -v
```
Expected: TestNotifierWritesSchemaV2 PASS; existing tests pass (or fail with deterministic shape change — fix any that asserted on v1 shape).

- [ ] **Step 6: Commit**

```bash
cd ~/.openclaw && git add clarification-agent/lib/notifier.py clarification-agent/tests/test_notifier.py
git commit -m "$(cat <<'EOF'
feat(notifier): write schema v2 entries with status/token_alias/sent_at

Each notifier-state.json entry now carries the full canonical tuple:
(task_id, project, token_alias, chat_id, thread_id, telegram_message_id,
 sent_at, status, resolved_at, resolved_via). Plugin clarification-commands
will consume this directly via reply_to_message.message_id lookup.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 5 — Phase 2b: Notifier valida `topics.clarifications`, fallback central

**Files:**
- Modify: `~/.openclaw/clarification-agent/lib/notifier.py` (lógica de resolução de target em `tick()`)
- Test: `~/.openclaw/clarification-agent/tests/test_notifier.py` (estende)

- [ ] **Step 1: Add failing test for fallback behavior**

Append to `~/.openclaw/clarification-agent/tests/test_notifier.py`:

```python
class TestNotifierFallbackToCentral(unittest.TestCase):
    def test_fallback_when_topics_clarifications_missing(self):
        from unittest.mock import MagicMock, patch
        from lib import notifier

        with tempfile.TemporaryDirectory() as td:
            esc_dir = Path(td) / "escalations"
            esc_dir.mkdir()
            (esc_dir / "T-8888-clr-1.md").write_text("dummy")
            state_path = Path(td) / "notifier-state.json"
            jsonl_path = Path(td) / "notifier.jsonl"

            # Mock telegram_meta.resolve_telegram_target to return None
            # (simula projects-meta.json sem topics.clarifications)
            with patch.object(notifier, "send_telegram_message",
                              return_value=(True, {"message_id": 100})):
                with patch("lib.notifier._slug_for_clarification",
                           return_value="bevox-site"):
                    # No mock of resolve_telegram_target → import will fail
                    # OR returns None — either way fallback path is taken
                    notifier.tick(
                        escalations_dir=esc_dir,
                        state_path=state_path,
                        jsonl_path=jsonl_path,
                        token="CENTRAL_TOK", chat_id="-100central", thread_id=99,
                    )

            data = json.loads(state_path.read_text())
            entry = data["notifications"]["T-8888-clr-1"]
            self.assertEqual(entry["chat_id"], "-100central")
            self.assertEqual(entry["thread_id"], 99)
            self.assertEqual(entry["token_alias"], "openclaw-central")

            # Verify event was logged
            with open(jsonl_path) as f:
                events = [json.loads(line) for line in f if line.strip()]
            event_names = [e["event"] for e in events]
            self.assertIn("clarification_fallback_to_central", event_names)
```

- [ ] **Step 2: Run test to verify it fails**

```bash
cd ~/.openclaw/clarification-agent && python3 -m unittest tests.test_notifier.TestNotifierFallbackToCentral -v
```
Expected: FAIL — event `clarification_fallback_to_central` not yet emitted.

- [ ] **Step 3: Modify `tick()` to emit fallback event**

In `notifier.py`, find the block around line 348-358 that resolves `target`. Replace:

```python
slug = _slug_for_clarification(task_id, cid)
eff_token, eff_chat_id, eff_thread_id = token, chat_id, thread_id
if slug:
    try:
        from telegram_meta import resolve_telegram_target  # type: ignore
    except ImportError:
        resolve_telegram_target = None  # type: ignore
    if resolve_telegram_target is not None:
        target = resolve_telegram_target(slug, "clarifications")
        if target is not None:
            eff_token, eff_chat_id, eff_thread_id = target
        else:
            append_event(jsonl_path, "clarification_fallback_to_central", {
                "clarification_id": cid,
                "project": slug,
                "reason": "topics.clarifications missing or unresolvable",
            })
```

(Add the `else` branch with the new event.)

- [ ] **Step 4: Run tests to verify pass**

```bash
cd ~/.openclaw/clarification-agent && python3 -m unittest tests.test_notifier -v
```
Expected: all PASS

- [ ] **Step 5: Commit**

```bash
cd ~/.openclaw && git add clarification-agent/lib/notifier.py clarification-agent/tests/test_notifier.py
git commit -m "$(cat <<'EOF'
feat(notifier): emit clarification_fallback_to_central event

When project lacks topics.clarifications in projects-meta.json, notifier
falls back to central token/chat (already happening implicitly) and now
emits an explicit jsonl event so the gap is observable.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 6 — Phase 3a: `handle_reply` atualiza notifier-state status

**Files:**
- Modify: `~/.openclaw/clarification-agent/lib/reply_handler.py` (`handle_reply` function)
- Test: `~/.openclaw/clarification-agent/tests/test_reply_handler.py` (NOVO)

- [ ] **Step 1: Write failing test**

Create `~/.openclaw/clarification-agent/tests/test_reply_handler.py`:

```python
"""Tests reply_handler.handle_reply — schema v2 status update."""
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch, MagicMock

from lib import reply_handler, store


class TestHandleReplyUpdatesStatus(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.state_path = Path(self.tmpdir) / "notifier-state.json"
        # Seed v2 entry pending
        state = {
            "schema_version": 2,
            "heartbeat_at": None,
            "notifications": {
                "T-7777-clr-1": {
                    "task_id": "T-7777",
                    "project": "bevox-site",
                    "token_alias": "project-bevox-site",
                    "chat_id": "-100xxx",
                    "thread_id": 18,
                    "telegram_message_id": 999,
                    "sent_at": "2026-04-28T10:00:00Z",
                    "status": "pending",
                    "resolved_at": None,
                    "resolved_via": None,
                }
            }
        }
        self.state_path.write_text(json.dumps(state))

    def test_handle_reply_marks_resolved(self):
        with patch.object(store, "ROOT", Path(self.tmpdir)):
            with patch.object(reply_handler, "unblock_task", return_value=True):
                with patch.object(reply_handler, "send_confirmation_message"):
                    success = reply_handler.handle_reply(
                        "T-7777-clr-1", "Opção A",
                        source="telegram_reply",
                    )
        self.assertTrue(success)
        data = json.loads(self.state_path.read_text())
        entry = data["notifications"]["T-7777-clr-1"]
        self.assertEqual(entry["status"], "resolved")
        self.assertEqual(entry["resolved_via"], "telegram_reply")
        self.assertIsNotNone(entry["resolved_at"])

    def test_handle_reply_idempotent_on_already_resolved(self):
        # Pre-seed as resolved
        state = json.loads(self.state_path.read_text())
        state["notifications"]["T-7777-clr-1"]["status"] = "resolved"
        state["notifications"]["T-7777-clr-1"]["resolved_at"] = "2026-04-28T11:00:00Z"
        self.state_path.write_text(json.dumps(state))

        with patch.object(store, "ROOT", Path(self.tmpdir)):
            with patch.object(reply_handler, "unblock_task", return_value=True) as mock_unblock:
                with patch.object(reply_handler, "send_confirmation_message"):
                    success = reply_handler.handle_reply(
                        "T-7777-clr-1", "Opção B",
                        source="telegram_reply",
                    )

        # Skipped → unblock not called second time
        mock_unblock.assert_not_called()
        self.assertTrue(success)  # idempotent: returns True
```

- [ ] **Step 2: Run test to verify it fails**

```bash
cd ~/.openclaw/clarification-agent && python3 -m unittest tests.test_reply_handler -v
```
Expected: FAIL — `handle_reply` doesn't have `source` kwarg, doesn't update notifier-state.

- [ ] **Step 3: Modify `handle_reply` in `reply_handler.py`**

Replace the existing `handle_reply` function with:

```python
def handle_reply(clarification_id: str, reply_text: str, source: str = "manual_cli") -> bool:
    """Handler principal: processa resposta e desbloqueia task.

    Args:
        clarification_id: T-XXXX-clr-N
        reply_text: texto livre da resposta
        source: origem ("telegram_reply" | "slash_command" | "manual_cli")
    """
    print(f"📝 Processando resposta para {clarification_id} (source={source})...")

    from . import store, lifecycle
    state_path = store.ROOT / "notifier-state.json"

    # Idempotency: skip if already resolved
    state = store.load_state_v2(state_path)
    entry = state.get("notifications", {}).get(clarification_id)
    if entry and entry.get("status") == "resolved":
        print(f"⚠️  {clarification_id} já está resolved (idempotent skip)")
        return True

    if not process_reply_file(clarification_id, reply_text):
        print("❌ Falha ao salvar resposta")
        return False

    try:
        store.clear_escalation_symlink(clarification_id)
    except OSError as e:
        print(f"⚠️  clear_escalation_symlink falhou: {e}")

    match = re.match(r"^(T-\d{4})-clr-", clarification_id)
    if not match:
        print("❌ clarification_id inválido")
        return False
    task_id = match.group(1)

    try:
        lifecycle.merge_dispatch_payload(task_id, {
            "last_clarification_confidence": "manual_override",
            "last_clarification_resolved_at": store.now_iso(),
            "last_clarification_source": source,
        })
        store.emit_signal(clarification_id, "override")
    except Exception as e:
        print(f"⚠️ Falha ao atualizar metadata da clarification: {e}")

    if not unblock_task(clarification_id):
        print("❌ Falha ao desbloquear task")
        return False

    # Update notifier-state status=resolved (best-effort; doesn't fail handler)
    try:
        if entry is not None:
            entry["status"] = "resolved"
            entry["resolved_at"] = store.now_iso()
            entry["resolved_via"] = source
            store.save_state_v2(state_path, state)
    except Exception as e:
        print(f"⚠️ Falha ao atualizar notifier-state: {e}")

    send_confirmation_message(clarification_id, task_id)
    print(f"✅ Clarification {clarification_id} resolvida com sucesso!")
    return True
```

- [ ] **Step 4: Run tests to verify pass**

```bash
cd ~/.openclaw/clarification-agent && python3 -m unittest tests.test_reply_handler -v
```
Expected: 2 tests PASS

- [ ] **Step 5: Commit**

```bash
cd ~/.openclaw && git add clarification-agent/lib/reply_handler.py clarification-agent/tests/test_reply_handler.py
git commit -m "$(cat <<'EOF'
feat(reply_handler): handle_reply updates schema v2 status + idempotent

handle_reply now:
- accepts source kwarg ("telegram_reply" | "slash_command" | "manual_cli")
- skips if entry.status == "resolved" (idempotency)
- updates notifier-state[cid] with status="resolved", resolved_at,
  resolved_via after successful unblock

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 7 — Phase 3b: `send_confirmation_message` usa `entry.token_alias`

**Files:**
- Modify: `~/.openclaw/clarification-agent/lib/reply_handler.py` (`send_confirmation_message`)
- Test: `~/.openclaw/clarification-agent/tests/test_reply_handler.py` (estende)

- [ ] **Step 1: Add failing test**

Append to `tests/test_reply_handler.py`:

```python
class TestConfirmationRouting(unittest.TestCase):
    def test_confirmation_sent_via_entry_token(self):
        from lib import reply_handler
        with tempfile.TemporaryDirectory() as td:
            state_path = Path(td) / "notifier-state.json"
            state = {
                "schema_version": 2,
                "notifications": {
                    "T-5555-clr-1": {
                        "task_id": "T-5555",
                        "token_alias": "project-bevox-site",
                        "chat_id": "-100site",
                        "thread_id": 18,
                        "telegram_message_id": 50,
                        "status": "pending",
                    }
                }
            }
            state_path.write_text(json.dumps(state))

            sent_calls = []
            def fake_send(token, payload):
                sent_calls.append({"token": token, "payload": payload})
                return True

            with patch.object(reply_handler, "store") as mock_store:
                mock_store.ROOT = Path(td)
                mock_store.load_state_v2 = lambda p: state
                with patch.object(reply_handler, "_send_via_token", fake_send):
                    with patch.object(reply_handler, "_resolve_token_for_alias",
                                      return_value="PROJECT_TOKEN"):
                        reply_handler.send_confirmation_message(
                            "T-5555-clr-1", "T-5555",
                        )

        self.assertEqual(len(sent_calls), 1)
        self.assertEqual(sent_calls[0]["token"], "PROJECT_TOKEN")
        self.assertEqual(sent_calls[0]["payload"]["chat_id"], "-100site")
```

- [ ] **Step 2: Run test to verify it fails**

```bash
cd ~/.openclaw/clarification-agent && python3 -m unittest tests.test_reply_handler.TestConfirmationRouting -v
```
Expected: FAIL — `_send_via_token` and `_resolve_token_for_alias` don't exist.

- [ ] **Step 3: Refactor `send_confirmation_message`**

Replace the existing `send_confirmation_message` function in `reply_handler.py` with:

```python
def _resolve_token_for_alias(alias: str, env: dict) -> Optional[str]:
    """Map token_alias to actual bot token via env vars.

    'openclaw-central' -> TELEGRAM_BOT_TOKEN
    'project-<slug>' -> BOT_TOKEN_<UPPER_SLUG>  (or BOT_TOKEN_VOZ_<UPPER_SLUG>)
    """
    if alias == "openclaw-central":
        return env.get("TELEGRAM_BOT_TOKEN")
    if alias and alias.startswith("project-"):
        slug = alias[len("project-"):].upper().replace("-", "_")
        # Try both naming conventions used in this repo
        for key in (f"BOT_TOKEN_VOZ_{slug}", f"BOT_TOKEN_{slug}"):
            tok = env.get(key)
            if tok:
                return tok
    return None


def _send_via_token(token: str, payload: dict) -> bool:
    """POST to Telegram sendMessage with given token. Returns True on 200."""
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    try:
        req = urllib.request.Request(
            url,
            data=json.dumps(payload).encode('utf-8'),
            headers={"Content-Type": "application/json"},
        )
        with urllib.request.urlopen(req, timeout=10) as resp:
            return resp.status == 200
    except Exception as e:
        print(f"⚠️ Confirmation send failed: {e}")
        return False


def send_confirmation_message(clarification_id: str, task_id: str):
    """Enviar confirmação no MESMO bot/chat/thread que enviou a clarification."""
    from . import store
    state = store.load_state_v2(store.ROOT / "notifier-state.json")
    entry = state.get("notifications", {}).get(clarification_id, {})
    alias = entry.get("token_alias")
    chat_id = entry.get("chat_id")
    thread_id = entry.get("thread_id")

    if not (alias and chat_id):
        print(f"⚠️ Sem token_alias/chat_id para {clarification_id}; skipping confirmation")
        return

    env = load_env()
    token = _resolve_token_for_alias(alias, env)
    if not token:
        print(f"⚠️ Não consegui resolver token para alias={alias}; skipping confirmation")
        return

    text = (
        f"✅ Clarification resolvida\n"
        f"Task: {task_id}\n"
        f"ID: `{clarification_id}`\n"
        f"Task desbloqueada e movida para ready."
    )
    payload = {"chat_id": chat_id, "text": text, "parse_mode": "Markdown"}
    if thread_id:
        payload["message_thread_id"] = int(thread_id)

    if _send_via_token(token, payload):
        print("✅ Confirmação enviada")
```

- [ ] **Step 4: Run tests to verify pass**

```bash
cd ~/.openclaw/clarification-agent && python3 -m unittest tests.test_reply_handler -v
```
Expected: all PASS

- [ ] **Step 5: Commit**

```bash
cd ~/.openclaw && git add clarification-agent/lib/reply_handler.py clarification-agent/tests/test_reply_handler.py
git commit -m "$(cat <<'EOF'
feat(reply_handler): confirmation uses entry.token_alias (not legacy env)

send_confirmation_message now reads notifier-state[cid].token_alias and
routes the confirmation back through the SAME bot that originally sent
the clarification — fixing the drift where confirmation was always
emitted via TELEGRAM_BOT_TOKEN regardless of project bot.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 8 — Phase 4: Plugin Node — schema v2 + cross-validation

**Files:**
- Modify: `~/.openclaw/extensions/clarification-commands/lib/*.js` (arquivos exatos a confirmar via leitura na Step 1)
- Test: depende do framework de teste atual do plugin

- [ ] **Step 1: Read current plugin structure to identify modification points**

```bash
ls -la ~/.openclaw/extensions/clarification-commands/lib/
cat ~/.openclaw/extensions/clarification-commands/index.js
```
Identify:
- File that reads `notifier-state.json` (likely `lib/state.js` or similar)
- File that handles `reply_to_message.message_id` lookup
- File that handles `/clr_override` command

Document the exact paths in scratch notes for steps below.

- [ ] **Step 2: Read current notifier-state lookup function**

Locate the function that loads `notifier-state.json` and currently extracts `telegram_message_id`. Note the file path and function name.

- [ ] **Step 3: Add schema v2 awareness — read full entry**

Modify the lookup function to return the full entry (not just `task_id`):

```javascript
function findEntryByMessageId(state, messageId) {
  for (const [cid, entry] of Object.entries(state.notifications || {})) {
    if (entry.telegram_message_id === messageId) {
      return { cid, ...entry };
    }
  }
  return null;
}

function findPendingByTaskId(state, taskId) {
  let latest = null;
  for (const [cid, entry] of Object.entries(state.notifications || {})) {
    if (entry.task_id !== taskId) continue;
    if (entry.status !== "pending") continue;
    if (!latest || entry.sent_at > latest.sent_at) {
      latest = { cid, ...entry };
    }
  }
  return latest;
}
```

- [ ] **Step 4: Add cross-validation in reply path**

In the handler that processes `reply_to_message.message_id`:

```javascript
async function handleReplyToClarification(ctx, entry) {
  // Cross-validation
  if (String(ctx.chat.id) !== String(entry.chat_id)) {
    log.warn("clarification_reply_chat_mismatch", {
      cid: entry.cid, expected: entry.chat_id, got: ctx.chat.id,
    });
    return; // no-op
  }
  const msgThreadId = ctx.message.message_thread_id || 0;
  if (Number(msgThreadId) !== Number(entry.thread_id || 0)) {
    log.warn("clarification_reply_thread_mismatch", {
      cid: entry.cid, expected: entry.thread_id, got: msgThreadId,
    });
    return;
  }
  if (entry.status !== "pending") {
    log.info("clarification_reply_already_resolved", { cid: entry.cid });
    return;
  }

  // Invoke CLI
  await execCli([
    "answer", entry.cid,
    "--answer", ctx.message.text || ctx.message.caption || "",
    "--actor", `telegram:${ctx.from.id}`,
  ]);
}
```

- [ ] **Step 5: Add similar cross-validation in `/clr_override` handler**

For commands without explicit task-id (rely on reply-to inference) OR with task-id:

```javascript
async function handleClrOverride(ctx, taskIdArg, answerText) {
  const state = await loadNotifierState();
  let entry;
  if (taskIdArg) {
    entry = findPendingByTaskId(state, taskIdArg);
    if (!entry) {
      await ctx.reply(`Nenhuma clarification pendente para ${taskIdArg}.`);
      return;
    }
  } else if (ctx.message.reply_to_message) {
    entry = findEntryByMessageId(state, ctx.message.reply_to_message.message_id);
    if (!entry) {
      await ctx.reply("Reply-to não corresponde a clarification conhecida. Use `/clr_override <task> <texto>`.");
      return;
    }
  } else {
    await ctx.reply("Use: `/clr_override <task-id> <texto>` ou responda à mensagem da clarification.");
    return;
  }

  // ... cross-validation as in reply path ...
  if (entry.status !== "pending") {
    await ctx.reply(`Clarification ${entry.cid} já foi resolvida.`);
    return;
  }

  await execCli(["answer", entry.cid, "--answer", answerText, "--actor", `telegram:${ctx.from.id}`]);
  await ctx.reply(`✅ ${entry.cid} processada.`);
}
```

- [ ] **Step 6: Run plugin tests (if exist)**

```bash
cd ~/.openclaw/extensions/clarification-commands && npm test 2>&1 | head -50
```
Expected: existing tests still PASS; if tests for new behavior were added, they pass.

- [ ] **Step 7: Restart all gateways to load updated plugin**

```bash
systemctl --user restart openclaw-gateway.service
systemctl --user restart openclaw-gateway-bevox-site.service
systemctl --user restart openclaw-gateway@bevox-mobile.service
systemctl --user restart openclaw-gateway@financeiro.service
sleep 3
systemctl --user is-active openclaw-gateway.service openclaw-gateway-bevox-site.service openclaw-gateway@bevox-mobile.service openclaw-gateway@financeiro.service
```
Expected: all 4 active.

- [ ] **Step 8: Commit (in plugin source repo if separate, OR in installed location)**

The plugin source is at `~/code/knowledge-sync/plugins/clarification-commands/` per spec wave-3 (`bernardTavares/knowledge-sync` monorepo). Commit there:

```bash
cd ~/code/knowledge-sync && git add plugins/clarification-commands/
git commit -m "$(cat <<'EOF'
feat(clarification-commands): schema v2 awareness + cross-validation

- read full notifier-state entry (token_alias, chat_id, thread_id, status)
- cross-validate reply chat_id/thread_id matches entry
- skip if status != pending (idempotency)
- /clr_override checks status before invoking CLI

Companion to clarification-reply-via-gateway-plugin spec (2026-04-28).

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

Then re-deploy to `~/.openclaw/extensions/clarification-commands/` per existing install workflow.

---

## Task 9 — Phase 5: `bootstrap-telegram-agent.sh` força plugin no default

**Files:**
- Modify: `~/.openclaw/scripts/bootstrap-telegram-agent.sh`

- [ ] **Step 1: Modify default `SKILLS` (line 23)**

Replace line 23:
```bash
-SKILLS="knowledge-sync-commands"
+SKILLS="knowledge-sync-commands,clarification-commands"
```

- [ ] **Step 2: Modify force-inject in Python heredoc (lines ~155-158)**

Replace the existing `if "knowledge-sync-commands" not in skills` block:

```python
for required in ("knowledge-sync-commands", "clarification-commands"):
    if required not in skills:
        skills.insert(0, required)
```

- [ ] **Step 3: Add validation after `systemctl --user enable` (around line 186)**

Add immediately after the existing `is-active` check inside the `NON_INTERACTIVE` block (around line 185):

```bash
  # Validate clarification-commands plugin is wired
  if ! python3 -c "
import json, sys
with open('$PROFILE_DIR/openclaw.json') as f:
    cfg = json.load(f)
allow = cfg.get('plugins', {}).get('allow', [])
sys.exit(0 if 'clarification-commands' in allow else 1)
"; then
    echo "FAIL: clarification-commands not in plugins.allow after bootstrap" >&2
    exit 1
  fi
```

- [ ] **Step 4: Update checklist message at line 238**

Replace:
```
-     - plugins.allow: adicionar opcionais (ex: clarification-commands) se desejar
+     - plugins.allow: clarification-commands incluído por default; opt-out com --skills knowledge-sync-commands
```

- [ ] **Step 5: Test the script in dry-run mode**

```bash
~/.openclaw/scripts/bootstrap-telegram-agent.sh \
    --token DUMMY_TOKEN --chat-id -100123 --allow-from 7593 \
    --non-interactive --json --dry-run test-bootstrap-validation 19999
```
Expected: dry-run completes without error; observe `plugins.allow` would contain `clarification-commands`.

- [ ] **Step 6: Commit**

```bash
cd ~/.openclaw && git add scripts/bootstrap-telegram-agent.sh
git commit -m "$(cat <<'EOF'
feat(bootstrap-telegram): force clarification-commands plugin by default

Pós-(iii) o caminho de reply de clarification depende exclusivamente do
plugin no gateway. Bootstrap default agora inclui clarification-commands
em plugins.allow + valida pós-bootstrap. Opt-out continua possível com
--skills knowledge-sync-commands explícito.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 10 — Phase 6: Deletar legacy

**Files:**
- Delete: `clarification-agent/lib/poller.py`
- Delete: `clarification-agent/lib/dynamic_reply_handler.py`
- Delete: `clarification-agent/lib/*.pre-poll.bak`
- Delete: `clarification-agent/bot-states/`
- Delete: `clarification-agent/telegram-reply-state.json`
- Delete: `clarification-agent/systemd/openclaw-clarification-daemon.service`
- Delete: `clarification-agent/systemd/openclaw-clarification-daemon.timer`
- Delete: systemd unit files in `~/.config/systemd/user/openclaw-clarification-daemon.*`
- Modify: `clarification-agent/lib/api.py` (remove `cmd_poll_replies` + parser)

- [ ] **Step 1: Remove `cmd_poll_replies` from `api.py`**

Read current api.py to locate:
```bash
grep -n "cmd_poll_replies\|poll-replies\|poll_replies" ~/.openclaw/clarification-agent/lib/api.py
```

Remove:
- The function `cmd_poll_replies` (around lines 80-101)
- The argparse subparser for `poll-replies` (lines ~440-442)

- [ ] **Step 2: Remove dead imports (poller, dynamic_reply_handler) referenced in api.py if any**

```bash
grep -n "from \. import poller\|import dynamic_reply_handler" ~/.openclaw/clarification-agent/lib/api.py
```
Remove any lines that import deleted modules.

- [ ] **Step 3: Verify api.py still parses**

```bash
cd ~/.openclaw/clarification-agent && python3 -m lib.api --help 2>&1 | head -20
```
Expected: help output without `poll-replies` listed.

- [ ] **Step 4: Delete legacy Python files**

```bash
rm ~/.openclaw/clarification-agent/lib/poller.py
rm ~/.openclaw/clarification-agent/lib/dynamic_reply_handler.py
rm ~/.openclaw/clarification-agent/lib/*.pre-poll.bak 2>/dev/null
rm -rf ~/.openclaw/clarification-agent/bot-states
rm -f ~/.openclaw/clarification-agent/telegram-reply-state.json
ls ~/.openclaw/clarification-agent/lib/ | grep -E "poller|dynamic_reply|pre-poll" || echo "OK: legacy files removed"
```
Expected: `OK: legacy files removed`

- [ ] **Step 5: Delete systemd unit files**

```bash
rm ~/.openclaw/clarification-agent/systemd/openclaw-clarification-daemon.service
rm ~/.openclaw/clarification-agent/systemd/openclaw-clarification-daemon.timer
rm ~/.config/systemd/user/openclaw-clarification-daemon.service
rm ~/.config/systemd/user/openclaw-clarification-daemon.timer
systemctl --user daemon-reload
systemctl --user list-unit-files | grep openclaw-clarification-daemon || echo "OK: daemon units removed"
```
Expected: `OK: daemon units removed`

- [ ] **Step 6: Run remaining tests to ensure nothing references deleted modules**

```bash
cd ~/.openclaw/clarification-agent && python3 -m unittest discover tests/ -v 2>&1 | tail -30
```
Expected: all tests PASS or fail only with explicit "test of removed module" — investigate any other failure.

- [ ] **Step 7: Commit**

```bash
cd ~/.openclaw && git add -A clarification-agent/ && git status --short clarification-agent/
git commit -m "$(cat <<'EOF'
chore(clarification-agent): delete poll-replies daemon (legacy)

Removes the parallel poll-replies path now that clarification-commands
plugin in the gateway is the sole consumer of Telegram updates.

Deleted:
- lib/poller.py, lib/dynamic_reply_handler.py
- lib/*.pre-poll.bak
- bot-states/ directory
- telegram-reply-state.json (legacy cursor)
- systemd/openclaw-clarification-daemon.{service,timer}
- ~/.config/systemd/user/openclaw-clarification-daemon.{service,timer}
- cmd_poll_replies from api.py (subcommand removed from CLI)

Race with OpenClaw notifier on TELEGRAM_BOT_TOKEN now physically
impossible (token discipline by construction).

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 11 — Phase 7: Smoke test 3 caminhos × 2 bots

**Files:**
- Test (manual, end-to-end): infra running

- [ ] **Step 1: Confirm system state**

```bash
systemctl --user is-active openclaw-clarification-notifier.timer  # should be active
systemctl --user list-units | grep clarification-daemon || echo "OK: daemon gone"
ls ~/.openclaw/clarification-agent/notifier-state.json
python3 -c "import json; d=json.load(open('$HOME/.openclaw/clarification-agent/notifier-state.json')); print('schema_version:', d.get('schema_version')); print('entries:', len(d.get('notifications',{})))"
```
Expected: schema_version=2 (after first notifier run post-deploy).

- [ ] **Step 2: Create test clarification (escalation file) for central bot**

Write a dummy escalation:
```bash
cd ~/.openclaw/clarification-agent
TASK_ID="T-TEST"
CID="${TASK_ID}-clr-1"
echo "Test escalation" > escalations/${CID}.md
echo "Test question?" > questions/${CID}.md
```

Wait for notifier tick OR force:
```bash
~/.openclaw/clarification-agent/cli.sh poll-tick --once  # if drafter; else trigger notifier
```

Verify message arrived in Telegram central topic; note the `message_id`.

- [ ] **Step 3: Test path A — swipe-reply nativo**

In Telegram: swipe-right on the clarification message, type "Resposta de teste A", send.

Verify:
```bash
sleep 5
python3 -c "
import json
d = json.load(open('$HOME/.openclaw/clarification-agent/notifier-state.json'))
e = d['notifications']['$CID']
print('status:', e.get('status'), 'resolved_via:', e.get('resolved_via'))
"
```
Expected: `status: resolved`, `resolved_via: telegram_reply`.

Verify task moved to ready:
```bash
~/.openclaw/kanban-tasks/cli.sh task show T-TEST --json | python3 -c "import json,sys; d=json.load(sys.stdin); print(d.get('status'), d.get('blocked'))"
```
Expected: `ready False`.

- [ ] **Step 4: Test path B — `/clr_override`**

Reset task to blocked + create new clarification (CID-2). In Telegram:
```
/clr_override T-TEST Resposta de teste B
```
Verify same observability as Step 3 (status=resolved, resolved_via=slash_command).

- [ ] **Step 5: Test path C — CLI manual**

Reset + create new clarification (CID-3). Run:
```bash
~/.openclaw/clarification-agent/cli.sh answer T-TEST-clr-3 --answer "Resposta de teste C"
```
Verify status=resolved, resolved_via=manual_cli.

- [ ] **Step 6: Repeat path A in bevox-site bot**

Create test escalation from a task associated with bevox-site project. Verify clarification arrives in bevox-site Telegram group, swipe-reply, verify status updated, **AND verify confirmation came back in bevox-site bot** (not central).

```bash
python3 -c "
import json
d = json.load(open('$HOME/.openclaw/clarification-agent/notifier-state.json'))
for cid, e in d['notifications'].items():
    if e.get('task_id') == 'T-TEST-SITE':
        print(cid, e.get('token_alias'), e.get('status'), e.get('resolved_via'))
"
```
Expected: `token_alias: project-bevox-site`, `status: resolved`.

- [ ] **Step 7: Cleanup test data**

```bash
~/.openclaw/kanban-tasks/cli.sh task delete T-TEST --commit 2>/dev/null
rm ~/.openclaw/clarification-agent/escalations/T-TEST-clr-*.md 2>/dev/null
rm ~/.openclaw/clarification-agent/answers/T-TEST-clr-*.md 2>/dev/null
rm ~/.openclaw/clarification-agent/questions/T-TEST-clr-*.md 2>/dev/null
rm ~/.openclaw/clarification-agent/signals/T-TEST-clr-*.signal 2>/dev/null
```

- [ ] **Step 8: Commit smoke-test artifacts (or note results in PR description)**

This task produces no commit; its output is the verification log.

If smoke test reveals bugs, return to relevant Task (4-8) and iterate before continuing.

---

## Task 12 — Phase 8: Update workspace-template docs (7 arquivos)

**Files:**
- Modify: `~/.openclaw/workspace-template/shared/CLARIFICATION_FLOW_CONTRACT.md` (reescrever inteiro)
- Modify: `~/.openclaw/workspace-template/AGENTS.md` (L226-264)
- Modify: `~/.openclaw/workspace-template/memory/integrations/clarification.md`
- Modify: `~/.openclaw/workspace-template/memory/integrations/telegram-bot.md`
- Modify: `~/.openclaw/workspace-template/TOOLS.md` (L18, L46-49)
- Modify: `~/.openclaw/workspace-template/HEARTBEAT.md` (L11-12, verificar)
- Modify: `~/.openclaw/workspace-template/memory/MEMORY.md` (L24)

- [ ] **Step 1: Reescrever `CLARIFICATION_FLOW_CONTRACT.md`**

Use o esqueleto na §8.1 do design doc (`docs/superpowers/specs/2026-04-28-clarification-reply-via-gateway-plugin-design.md`). Substitui o conteúdo atual integralmente.

- [ ] **Step 2: Atualizar `AGENTS.md` L226-264**

Localiza a seção "Telegram Poll-Replies Dinâmico" e substitui pelo bloco curto da §8.1 do design doc.

- [ ] **Step 3: Reescrever `memory/integrations/clarification.md`**

Substitui o §"Notificação Telegram" e §"Como Bernard responde" pelo conteúdo da §8.1 do design doc.

- [ ] **Step 4: Atualizar `memory/integrations/telegram-bot.md`**

- §"Bootstrap automatizado": atualizar exemplo `--skills` (default agora inclui clarification-commands).
- §"Pré-condições para clarification reply" (NOVA): adicionar bloco da §8.1 do design.
- §"Anti-patterns": adicionar "NÃO implementar polling Telegram em código de agente".

- [ ] **Step 5: Atualizar `TOOLS.md` L18 e L46-49**

```bash
grep -n "poll-replies\|poll_replies" ~/.openclaw/workspace-template/TOOLS.md
```
Remove qualquer linha referenciando `poll-replies`. Mantém `ask`, `answer`, `list`, `poll-tick`. Adiciona nota no fim do cheatsheet:
```markdown
> Não há subcomando `poll-replies`. Ingestão de reply Telegram é responsabilidade do plugin `clarification-commands` no gateway.
```

- [ ] **Step 6: Verificar `HEARTBEAT.md` L11-12**

```bash
sed -n '10,15p' ~/.openclaw/workspace-template/HEARTBEAT.md
```
Se `cli.sh list --open` ainda for válido (provavelmente sim — leitura), mantém. Se foi removido junto com poll, atualizar.

- [ ] **Step 7: Atualizar `memory/MEMORY.md` L24**

Verifica linha 24 e atualiza one-line hook do link para `clarification.md`:
```markdown
- [Integration: clarification-agent](integrations/clarification.md) — fluxo ask/answer + 3 caminhos de reply (swipe-reply, /clr_*, CLI manual)
```

- [ ] **Step 8: Verificar que todos os arquivos OK no §8.2 não foram tocados**

```bash
git status workspace-template/ | head -20
```
Confirma: só os 7 arquivos planejados aparecem como modified. Se outros aparecem, investigar.

- [ ] **Step 9: Commit**

```bash
cd ~/.openclaw && git add workspace-template/
git commit -m "$(cat <<'EOF'
docs(workspace-template): clarification reply via gateway plugin

Atualiza CLARIFICATION_FLOW_CONTRACT.md (reescrita integral), AGENTS.md
seção Telegram, memory/integrations/{clarification,telegram-bot}.md,
TOOLS.md cheatsheet, HEARTBEAT.md e MEMORY.md index para refletir o
novo modelo: 3 caminhos de ingestão (swipe-reply, /clr_override, CLI
manual) consolidados via plugin clarification-commands; daemon poll-
replies aposentado.

Pré-condições do canal Telegram (3 itens) explicitadas. Token discipline
hard rule documentada. Anti-pattern "polling Telegram em código de
agente" registrado.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

- [ ] **Step 10: Notar dívida de propagação para 11 workspaces materializados**

Os 11 workspaces materializados (`~/.openclaw/workspace-bevox-mobile`, `-bevox-site`, etc.) **não recebem** essas mudanças automaticamente. Conforme §8.3 do design, a recomendação é **opção C** (marcar como dívida e tratar fora desta wave).

Verificar que o inbox correlato registra essa dívida:
```bash
grep -A2 "11 workspaces materializados" ~/bevox-knowledge/00_inbox/openclaw/2026-04-28-workspace-template-structure-investigation.md | head
```
Expected: dívida documentada.

---

## Task 13 — Phase 9: Update bevox-knowledge (15 itens) — branch `draft/`

**Files:**
- Branch novo: `draft/adr-011-clarification-reply-via-gateway-plugin` em `bevox-knowledge`
- Create: `bevox-knowledge/30_adr/company-os/ADR-011-clarification-reply-via-gateway-plugin.md`
- Modify: `bevox-knowledge/30_adr/company-os/ADR-009-clarification-loop-unified-local-first.md`
- Create: `bevox-knowledge/35_specs/openclaw/2026-04-28-clarification-reply-via-gateway-plugin.md`
- Modify: `bevox-knowledge/35_specs/openclaw/2026-04-21-e10-telegram-reply-handler.md`
- Modify: `bevox-knowledge/35_specs/openclaw/2026-04-21-e10-clarification-daemon-local-first.md`
- Move: `bevox-knowledge/35_specs/openclaw/2026-04-23-clarification-telegram-enhancement.md` → `_retired/`
- Modify: `bevox-knowledge/35_specs/openclaw/2026-04-19-e10-dispatcher-and-clarification-agents.md`
- Modify: `bevox-knowledge/20_architecture/openclaw/clarification-agent.md`
- Modify: `bevox-knowledge/20_architecture/_shared/health-registry.yml` (delete L219-227)
- Modify: `bevox-knowledge/40_roadmap/_shared/delivery-tracker.yml`
- Modify: `bevox-knowledge/40_roadmap/company-os/2026-04-09-openclaw-company-os-roadmap.md`
- Already created (commit too): `bevox-knowledge/10_prd/_shared/2026-04-28-knowledge-as-living-system-investigation-prd.md`
- Already created (commit too): `bevox-knowledge/00_inbox/openclaw/2026-04-28-workspace-template-structure-investigation.md`

- [ ] **Step 1: Create draft branch in bevox-knowledge**

```bash
cd ~/bevox-knowledge && git status --short
git checkout -b draft/adr-011-clarification-reply-via-gateway-plugin
```
Expected: clean branch created from current state.

- [ ] **Step 2: Create ADR-011**

Use the skeleton from §9.3 of the design doc. Save to:
`bevox-knowledge/30_adr/company-os/ADR-011-clarification-reply-via-gateway-plugin.md`

- [ ] **Step 3: Update ADR-009 status field + add §Consequências bloco**

In `30_adr/company-os/ADR-009-clarification-loop-unified-local-first.md`:

Change line 3:
```markdown
- **Status:** parcialmente superseded por ADR-011 (2026-04-28); push-mode CLI e drafter local-first permanecem canônicos
```

Append at end of "## Consequências" section (before "## Impacto em Specs Futuras"):
```markdown
### 2026-04-28 — Aposentadoria parcial via ADR-011

- Daemon `clarification-agent/poll-replies` (Opção C original) aposentado.
  Caminho de ingestão de reply consolidado no plugin
  `clarification-commands` do gateway.
- Push-mode CLI (`clarification-agent ask`) e drafter local-first
  (`poll-tick`) **permanecem canônicos** — não são tocados pela ADR-011.
- Detalhes: `30_adr/company-os/ADR-011-clarification-reply-via-gateway-plugin.md`.
```

- [ ] **Step 4: Create the canonical spec**

Create `bevox-knowledge/35_specs/openclaw/2026-04-28-clarification-reply-via-gateway-plugin.md`. Mirror sections 1-7 of the design doc (`docs/superpowers/specs/2026-04-28-clarification-reply-via-gateway-plugin-design.md`) plus add the delivery plan from §10 with current task numbers and the acceptance criteria from §11.

- [ ] **Step 5: Annotate spec wave-3 (delivered) with "Extended by"**

In `bevox-knowledge/35_specs/openclaw/2026-04-21-e10-telegram-reply-handler.md`, add header note immediately after the front matter block:

```markdown
---

> **Extended by `35_specs/openclaw/2026-04-28-clarification-reply-via-gateway-plugin.md`** (2026-04-28) — multi-bot awareness + schema v2 do `notifier-state.json`. Wave-3 original permanece canônica para os 5 comandos `/clr_*` e o reply-to-message inference; extension adiciona cross-validation `(chat_id, thread_id)` e idempotência via `status=pending`.
```

- [ ] **Step 6: Annotate spec daemon-local-first as parcialmente superseded**

In `bevox-knowledge/35_specs/openclaw/2026-04-21-e10-clarification-daemon-local-first.md`:

Change Status field:
```markdown
**Status:** parcialmente superseded por 35_specs/openclaw/2026-04-28-clarification-reply-via-gateway-plugin.md
```

Add note at top after front matter:
```markdown
---

> **Daemon mode (poll-replies) aposentado em 2026-04-28** via ADR-011 + spec `2026-04-28-clarification-reply-via-gateway-plugin.md`. Drafter local-first (`poll-tick`) e pre-filter determinístico **permanecem canônicos** — não tocados pelo redesign.
```

- [ ] **Step 7: Move telegram-enhancement spec to _retired/ + add §Aposentadoria**

```bash
cd ~/bevox-knowledge
git mv 35_specs/openclaw/2026-04-23-clarification-telegram-enhancement.md _retired/
```

Append at end of the moved file:
```markdown
---

## Aposentadoria

- **Data:** 2026-04-28
- **Motivo:** descrevia o estado com 5 bugs auditados em 2026-04-28; implementação `reply_handler.py` (poll-replies) deletada inteira na wave consolidada via plugin.
- **Substituído por:** `35_specs/openclaw/2026-04-28-clarification-reply-via-gateway-plugin.md` + ADR-011.
- **Aprendizados:** persistência incompleta da triple `(chat_id, thread_id, message_id)` no `notifier-state.json` foi a causa-raiz dos bugs; schema v2 corrige.
```

- [ ] **Step 8: Annotate dispatcher-and-clarification-agents spec**

In `bevox-knowledge/35_specs/openclaw/2026-04-19-e10-dispatcher-and-clarification-agents.md`, add header note at top:

```markdown
---

> **Push-mode CLI permanece canônico**. Reply-mode evoluiu via wave-3 (`2026-04-21-e10-telegram-reply-handler.md`) e refinada por `2026-04-28-clarification-reply-via-gateway-plugin.md`. Telegram §97/§1010 (out-of-wave originais) resolvidos pela ADR-011.
```

- [ ] **Step 9: Update architecture doc clarification-agent.md**

In `bevox-knowledge/20_architecture/openclaw/clarification-agent.md`:
- Atualizar §"Outputs": notifier-state schema v2.
- Atualizar §"Skills": remover qualquer menção a `poll-replies`; manter `poll-tick` (drafter pull, não confundir).
- Adicionar **§"Reply ingestion"** novo descrevendo os 3 caminhos canônicos e que plugin é o consumer único do canal Telegram.
- Atualizar §"Limites": "agente não faz polling Telegram".

- [ ] **Step 10: Edit health-registry — delete daemon entry**

```bash
sed -i '/^  openclaw-clarification-daemon:$/,/^  openclaw-clarification-notifier:/{/^  openclaw-clarification-notifier:/!d}' ~/bevox-knowledge/20_architecture/_shared/health-registry.yml
grep -A8 "openclaw-clarification" ~/bevox-knowledge/20_architecture/_shared/health-registry.yml
```
Expected: only `openclaw-clarification-notifier` block remains.

- [ ] **Step 11: Add wave to delivery-tracker**

In `bevox-knowledge/40_roadmap/_shared/delivery-tracker.yml`, locate the E10 OH-followup block and add (use the skeleton from §9.3 of design doc):

```yaml
      - id: clarification-reply-via-gateway-plugin
        wave: E10/clarification-reply-via-gateway-plugin
        spec: 35_specs/openclaw/2026-04-28-clarification-reply-via-gateway-plugin.md
        adr: 30_adr/company-os/ADR-011-clarification-reply-via-gateway-plugin.md
        status: proposed
        prerequisites: [clarification-daemon-local-first, telegram-reply-handler]
        deliverables:
          - "notifier-state.json schema v2"
          - "plugin clarification-commands estendido (multi-bot + cross-validation)"
          - "daemon openclaw-clarification-daemon aposentado (units + state files removidos)"
          - "bootstrap-telegram-agent.sh força clarification-commands no default"
```

- [ ] **Step 12: Add narrative line to roadmap**

In `bevox-knowledge/40_roadmap/company-os/2026-04-09-openclaw-company-os-roadmap.md`, locate the E10/OH section and add:

```markdown
Em 2026-04-28, a wave de `clarification-reply-via-gateway-plugin` consolidou ingestão Telegram de replies no plugin do gateway, aposentando o daemon paralelo (ADR-011).
```

- [ ] **Step 13: Verify all changes; status check**

```bash
cd ~/bevox-knowledge && git status --short
```
Expected: 11 files modified/created/moved + 2 already-created (PRD + inbox from brainstorming session).

- [ ] **Step 14: Commit em branch draft (NÃO push)**

```bash
cd ~/bevox-knowledge && git add -A
git commit -m "$(cat <<'EOF'
docs: clarification reply via gateway plugin (ADR-011 + spec)

Adoção do consenso de brainstorming 2026-04-28: ingestão de reply de
clarification consolidada no plugin clarification-commands do gateway;
daemon poll-replies aposentado; notifier-state.json schema v2.

Artefatos criados:
- ADR-011 (proposta)
- spec 35_specs/openclaw/2026-04-28-...
- PRD investigativo 10_prd/_shared/2026-04-28-knowledge-as-living-system-...
- inbox 00_inbox/openclaw/2026-04-28-workspace-template-structure-...

Artefatos modificados:
- ADR-009 status: parcialmente superseded
- spec wave-3 (delivered): annotation "Extended by"
- spec daemon-local-first: status superseded; drafter local-first preservado
- architecture/openclaw/clarification-agent.md: §Reply ingestion reescrita
- health-registry.yml: removida entrada openclaw-clarification-daemon
- delivery-tracker.yml: wave nova adicionada
- roadmap: linha narrativa

Artefato movido para _retired/:
- spec 2026-04-23-clarification-telegram-enhancement.md (estado com bugs)

Branch: draft/adr-011-clarification-reply-via-gateway-plugin
Próximo passo: review humano antes de merge para main.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

- [ ] **Step 15: Aguardar approval explícito antes de merge para main**

Per CLAUDE.md §3 e §8: mudança canônica em bevox-knowledge é sensível e requer approval explícito. Não fazer merge automático.

Reportar a Bernard:
```
Branch draft/adr-011-clarification-reply-via-gateway-plugin pronta com
13 itens canônicos. PR/review necessário antes de merge para main.
```

---

## Self-Review Checklist (post-write, before handoff)

**Spec coverage** — cada seção do design doc tem task correspondente?

| Design § | Implementado em |
|---|---|
| §3 Arquitetura | Tasks 4-8 (componentes implementados) |
| §4.1 store.py helpers | Task 2 |
| §4.2-4.3 notifier.py + reply_handler.py | Tasks 4, 5, 6, 7 |
| §4.3 plugin Node | Task 8 |
| §4.4 schema v2 | Task 2 (helpers) + Task 4 (writer) |
| §4.5 migração | Task 3 |
| §4.6 token alias | Task 4 (helper `_alias_for`) + Task 7 (`_resolve_token_for_alias`) |
| §4.7 pré-condição + fallback | Task 5 |
| §4.8 bootstrap force plugin | Task 9 |
| §5 data flow | Tasks 4-8 (componentes) + Task 11 (smoke E2E) |
| §6 error handling | Implícito nas tasks 4-7 (try/except, log + best-effort); smoke valida em Task 11 |
| §7 observabilidade | Task 5 (event clarification_fallback_to_central); restante implícito (jsonl appends nas tasks) |
| §8 workspace-template docs | Task 12 |
| §9 bevox-knowledge docs | Task 13 |
| §10 phases | 13 tasks = 9 phases mapeadas (algumas phases têm 1 task, outras 2) |
| §11 acceptance criteria | Validados em Task 11 (smoke) + Task 13 (docs) |

**Placeholder scan**: verifiquei. Cada step tem código/comando concreto. "TBD" ausente. "Read current code" steps são explícitos sobre o que ler antes de modificar.

**Type consistency**:
- `entry.token_alias` usado em Task 4 (escrita) e Task 7 (leitura). ✓
- `status="pending"` / `"resolved"` / `"orphan"` consistente entre Tasks 2, 3, 6, 7. ✓
- `_alias_for(slug, eff_token, default_token)` (Task 4) ↔ `_resolve_token_for_alias(alias, env)` (Task 7) — aliases gerados em Task 4 são consumidos em Task 7. ✓
- Eventos jsonl: `clarification_fallback_to_central` (Task 5), schema v2 entry shape (Task 4) — consistentes com §7.1 do design. ✓

**Áreas com risco residual reconhecido**:
- Task 8 (plugin Node) tem menos detalhe de código — depende de leitura prévia do código atual (Step 1 + 2). Aceito porque modificações Node são fora do escopo Python que o design priorizou. Subagent vai ler antes de implementar.
- Task 11 (smoke) depende de tasks de teste pré-existentes (`T-TEST` etc.) que precisam ser criadas; é manual / interactive. Aceito.
- Task 13 (bevox-knowledge) faz commit em branch draft mas não push/merge — Bernard tem approval explícito como gate.
