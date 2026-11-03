# MC Projects Factory Wave 2 — Phase 4: Telegram Topics Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Auto-create Telegram forum topics (`clarifications`, `dispatcher`) for a project's bot/group, triggered by a UI button on the project's "Geral" tab. Persist topic IDs in `projects-meta.json`. Update `clarification-agent` and `dispatcher-agent` notifiers to post into the right topic when present.

**Architecture:** New script `~/.openclaw/scripts/init-telegram-topics.py` calls the Telegram Bot API `createForumTopic` for each canonical topic, idempotently. New API route `POST /api/projects/[id]/telegram/init-topics` invokes it. Button on `ProjectGeralTab` (only visible when `telegram.bot_id` is set AND `telegram.topics` is empty/incomplete) calls the route. Notifiers read `telegram.topics.<name>` from `projects-meta.json` and pass `message_thread_id` to `sendMessage`.

**Tech Stack:** Python 3.13 + `requests`, Next.js 15 / TypeScript / React, existing notifier code (Python).

**Spec:** `bevox-knowledge/35_specs/openclaw/2026-04-28-mc-projects-factory-wave-2-vox-clone.md` §3.2, §3.3, §6 (Phase 4).

**Pre-requisites:**
- Phases 1-3 not strictly required (this phase is independent), but `mc-project-bot-connect` must be delivered (it is — 2026-04-27)
- Bot already connected to project via `Connect bot` UI; `projects-meta.json` has `bot_id`, `bot_token`/secret ref, and `chat_id` for the project
- Group is a Telegram **supergroup with forum/topics enabled** and the bot has admin permission `manage_topics`

---

## File Structure

| Path | Action | Responsibility |
|---|---|---|
| `~/.openclaw/scripts/init-telegram-topics.py` | CREATE | Calls Telegram API; idempotent; updates meta |
| `~/.openclaw/scripts/lib/projects_meta_lock.py` | CREATE (or reuse existing) | Lock helper for projects-meta.json |
| `~/.openclaw/kanban-tasks/tests/test_init_telegram_topics.py` | CREATE | Unit tests, Telegram API mocked |
| `mission-control/src/app/api/projects/[id]/telegram/init-topics/route.ts` | CREATE | API route |
| `mission-control/src/components/projects/ProjectGeralTab.tsx` | MODIFY | Add "Initialize topics" button |
| `~/.openclaw/clarification-agent/lib/notifier.py` (or equivalent) | MODIFY | Read `telegram.topics.clarifications`; pass `message_thread_id` |
| `~/.openclaw/dispatcher-agent/lib/notifier.py` (or equivalent) | MODIFY | Read `telegram.topics.dispatcher`; pass `message_thread_id` |
| Feature flag | NEW | `OPENCLAW_TELEGRAM_TOPICS` (default `1`) controls the notifier branch |

---

## Task 1: Setup branch + audit current state

- [ ] **Step 1: Branch**

```bash
cd ~/.openclaw
git checkout main && git pull
git checkout -b feat/mc-projects-factory-w2-phase-4-telegram-topics
```

- [ ] **Step 2: Locate the notifier code in clarification-agent and dispatcher-agent**

```bash
grep -rln "send_message\|sendMessage\|telegram" \
    ~/.openclaw/clarification-agent/ ~/.openclaw/dispatcher-agent/ 2>/dev/null \
    | grep -v __pycache__ | grep -v ".pyc"
```

Note the file(s) where each agent posts to Telegram. Patches in Tasks 6 & 7 must be applied to those exact files.

- [ ] **Step 3: Inspect current projects-meta.json shape**

```bash
python3 -c "
import json
m = json.load(open('~/.openclaw/projects-meta.json'))
for slug, entry in list(m.get('projects', {}).items())[:3]:
    print(slug, '→', list(entry.keys()))
"
```

Expected: keys include `bot_id`, `bot_username`, `bot_port`, etc. The new schema adds:
```json
{
  "telegram": {
    "chat_id": -100123,
    "topics": {
      "clarifications": 12,
      "dispatcher": 13
    }
  }
}
```

If the existing schema already has a `telegram` sub-object, adapt the writes below to merge cleanly.

---

## Task 2: TDD — Write failing tests for init-telegram-topics.py

**Files:**
- Create: `~/.openclaw/kanban-tasks/tests/test_init_telegram_topics.py`

(Placing the test file under `kanban-tasks/tests/` keeps it discoverable by the existing pytest invocation. The script itself lives in `~/.openclaw/scripts/` — the test imports from there via path manipulation.)

- [ ] **Step 1: Write tests**

```bash
cat > ~/.openclaw/kanban-tasks/tests/test_init_telegram_topics.py <<'EOF'
"""Tests for init-telegram-topics.py."""
import json
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

# Add scripts/ to path
SCRIPTS_DIR = Path(__file__).resolve().parents[2] / "scripts"
sys.path.insert(0, str(SCRIPTS_DIR))


@pytest.fixture
def meta_file(tmp_path):
    """Create a projects-meta.json fixture and return its path."""
    p = tmp_path / "projects-meta.json"
    p.write_text(json.dumps({
        "projects": {
            "myproj": {
                "name": "MyProj",
                "bot_id": "voz-myproj",
                "bot_username": "voz_myproj_bot",
                "bot_port": 18765,
                "telegram": {"chat_id": -100123, "topics": {}},
            }
        }
    }))
    return p


def _ok_response(thread_id: int):
    """Mock requests response for a successful createForumTopic."""
    r = MagicMock()
    r.status_code = 200
    r.json.return_value = {
        "ok": True,
        "result": {"message_thread_id": thread_id, "name": "x"},
    }
    return r


def test_creates_both_topics_when_none_exist(meta_file, monkeypatch, tmp_path):
    """When no topics exist, both are created and meta is updated."""
    # Bot token via env
    monkeypatch.setenv("BOT_TOKEN_VOZ_MYPROJ", "fake-token-123")

    import importlib
    mod = importlib.import_module("init-telegram-topics".replace("-", "_"))

    with patch.object(mod.requests, "post", side_effect=[
        _ok_response(11),  # clarifications
        _ok_response(22),  # dispatcher
    ]):
        result = mod.run(slug="myproj", meta_path=meta_file)

    assert result["created"] == ["clarifications", "dispatcher"]
    assert result["existing"] == []
    assert result["failed"] == []

    meta = json.loads(meta_file.read_text())
    topics = meta["projects"]["myproj"]["telegram"]["topics"]
    assert topics == {"clarifications": 11, "dispatcher": 22}


def test_skips_topics_already_present(meta_file, monkeypatch):
    """Existing topics in meta → only missing ones are created."""
    monkeypatch.setenv("BOT_TOKEN_VOZ_MYPROJ", "fake-token-123")

    # Pre-fill clarifications
    meta = json.loads(meta_file.read_text())
    meta["projects"]["myproj"]["telegram"]["topics"]["clarifications"] = 99
    meta_file.write_text(json.dumps(meta))

    import importlib
    mod = importlib.import_module("init-telegram-topics".replace("-", "_"))

    with patch.object(mod.requests, "post",
                      side_effect=[_ok_response(22)]) as post_mock:
        result = mod.run(slug="myproj", meta_path=meta_file)

    assert result["created"] == ["dispatcher"]
    assert result["existing"] == ["clarifications"]
    assert post_mock.call_count == 1

    meta = json.loads(meta_file.read_text())
    topics = meta["projects"]["myproj"]["telegram"]["topics"]
    assert topics == {"clarifications": 99, "dispatcher": 22}


def test_partial_failure_returns_partial_state(meta_file, monkeypatch):
    """Telegram API rejects one topic → meta updated for successes only."""
    monkeypatch.setenv("BOT_TOKEN_VOZ_MYPROJ", "fake-token-123")

    fail_resp = MagicMock()
    fail_resp.status_code = 400
    fail_resp.json.return_value = {"ok": False, "description": "BAD_REQUEST"}

    import importlib
    mod = importlib.import_module("init-telegram-topics".replace("-", "_"))

    with patch.object(mod.requests, "post",
                      side_effect=[_ok_response(11), fail_resp]):
        result = mod.run(slug="myproj", meta_path=meta_file)

    assert result["created"] == ["clarifications"]
    assert result["failed"] == [{"topic": "dispatcher", "error": "BAD_REQUEST"}]

    meta = json.loads(meta_file.read_text())
    assert meta["projects"]["myproj"]["telegram"]["topics"] == {"clarifications": 11}


def test_fails_when_bot_token_missing(meta_file, monkeypatch):
    monkeypatch.delenv("BOT_TOKEN_VOZ_MYPROJ", raising=False)

    import importlib
    mod = importlib.import_module("init-telegram-topics".replace("-", "_"))

    with pytest.raises(mod.InitTopicsError) as exc:
        mod.run(slug="myproj", meta_path=meta_file)
    assert "token" in str(exc.value).lower()


def test_fails_when_chat_id_missing(meta_file, monkeypatch):
    monkeypatch.setenv("BOT_TOKEN_VOZ_MYPROJ", "fake")
    meta = json.loads(meta_file.read_text())
    meta["projects"]["myproj"]["telegram"].pop("chat_id")
    meta_file.write_text(json.dumps(meta))

    import importlib
    mod = importlib.import_module("init-telegram-topics".replace("-", "_"))

    with pytest.raises(mod.InitTopicsError) as exc:
        mod.run(slug="myproj", meta_path=meta_file)
    assert "chat_id" in str(exc.value).lower()
EOF
```

- [ ] **Step 2: Run tests, verify all FAIL**

```bash
cd ~/.openclaw/kanban-tasks
python3 -m pytest tests/test_init_telegram_topics.py -v
```

Expected: 5 errors (`init-telegram-topics` module not yet present).

---

## Task 3: Implement init-telegram-topics.py

**Files:**
- Create: `~/.openclaw/scripts/init-telegram-topics.py`

- [ ] **Step 1: Write the script**

```bash
cat > ~/.openclaw/scripts/init_telegram_topics.py <<'EOF'
#!/usr/bin/env python3
"""init-telegram-topics — create canonical forum topics for a project's group.

Reads bot token from env (BOT_TOKEN_<UPPER_SLUG>); reads chat_id from
projects-meta.json. Calls Telegram createForumTopic API per topic; persists
message_thread_id back to meta. Idempotent.

Usage:
    init-telegram-topics.py --slug <slug> [--meta /path/to/projects-meta.json]

Output: JSON to stdout: {"created": [...], "existing": [...], "failed": [...]}
"""
from __future__ import annotations

import argparse
import fcntl
import json
import os
import sys
from pathlib import Path

import requests


CANONICAL_TOPICS = (
    {"name": "clarifications", "icon_color": 16478047},  # red
    {"name": "dispatcher",     "icon_color": 7322096},   # blue
)

DEFAULT_META = Path("~/.openclaw/projects-meta.json")


class InitTopicsError(Exception):
    pass


def _bot_token_env_name(slug: str) -> str:
    return "BOT_TOKEN_" + slug.upper().replace("-", "_")


def _read_meta_locked(meta_path: Path):
    """Open meta with shared lock for read; release immediately."""
    with open(meta_path, "r") as f:
        fcntl.flock(f, fcntl.LOCK_SH)
        try:
            return json.load(f)
        finally:
            fcntl.flock(f, fcntl.LOCK_UN)


def _update_meta_topic(meta_path: Path, slug: str, topic_name: str, thread_id: int):
    """Acquire EX lock, read+modify+write atomically."""
    with open(meta_path, "r+") as f:
        fcntl.flock(f, fcntl.LOCK_EX)
        try:
            meta = json.load(f)
            entry = meta["projects"][slug]
            entry.setdefault("telegram", {}).setdefault("topics", {})
            entry["telegram"]["topics"][topic_name] = thread_id
            f.seek(0)
            f.truncate()
            json.dump(meta, f, indent=2, ensure_ascii=False)
        finally:
            fcntl.flock(f, fcntl.LOCK_UN)


def _create_topic(token: str, chat_id: int, slug: str, topic: dict) -> dict:
    """Call Telegram createForumTopic. Returns parsed JSON or raises."""
    url = f"https://api.telegram.org/bot{token}/createForumTopic"
    name = f"{slug}:{topic['name']}"
    resp = requests.post(url, json={
        "chat_id": chat_id,
        "name": name,
        "icon_color": topic["icon_color"],
    }, timeout=15)
    return resp.json()


def run(*, slug: str, meta_path: Path = DEFAULT_META) -> dict:
    if not meta_path.is_file():
        raise InitTopicsError(f"meta file missing: {meta_path}")

    meta = _read_meta_locked(meta_path)
    entry = meta.get("projects", {}).get(slug)
    if not entry:
        raise InitTopicsError(f"project '{slug}' not found in meta")

    telegram = entry.get("telegram", {}) or {}
    chat_id = telegram.get("chat_id")
    if not chat_id:
        raise InitTopicsError(f"chat_id missing for '{slug}' (connect bot first)")

    token = os.environ.get(_bot_token_env_name(slug))
    if not token:
        raise InitTopicsError(
            f"bot token env {_bot_token_env_name(slug)} missing"
        )

    existing_topics = telegram.get("topics", {}) or {}
    created, existing, failed = [], [], []

    for topic in CANONICAL_TOPICS:
        name = topic["name"]
        if name in existing_topics:
            existing.append(name)
            continue
        payload = _create_topic(token, int(chat_id), slug, topic)
        if payload.get("ok"):
            thread_id = int(payload["result"]["message_thread_id"])
            _update_meta_topic(meta_path, slug, name, thread_id)
            created.append(name)
        else:
            failed.append({"topic": name, "error": payload.get("description") or "unknown"})

    return {"created": created, "existing": existing, "failed": failed}


def main(argv: list[str]) -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--slug", required=True)
    p.add_argument("--meta", default=str(DEFAULT_META))
    args = p.parse_args(argv)
    try:
        result = run(slug=args.slug, meta_path=Path(args.meta))
    except InitTopicsError as e:
        json.dump({"error": str(e)}, sys.stdout)
        sys.stdout.write("\n")
        return 2
    json.dump(result, sys.stdout)
    sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
EOF
chmod +x ~/.openclaw/scripts/init_telegram_topics.py
```

(File named with underscores so it's importable as a Python module. Optionally add a thin `init-telegram-topics.py` symlink for hyphenated CLI use, but tests + route call the underscore name directly.)

- [ ] **Step 2: Run tests, verify all PASS**

```bash
cd ~/.openclaw/kanban-tasks
python3 -m pytest tests/test_init_telegram_topics.py -v
```

Expected: 5 PASSED.

---

## Task 4: API route — POST /api/projects/[id]/telegram/init-topics

**Files:**
- Create: `mission-control/src/app/api/projects/[id]/telegram/init-topics/route.ts`

- [ ] **Step 1: Create route**

```ts
// mission-control/src/app/api/projects/[id]/telegram/init-topics/route.ts
import { spawn } from "node:child_process";

interface Result {
  created?: string[];
  existing?: string[];
  failed?: Array<{ topic: string; error: string }>;
  error?: string;
}

export async function POST(
  _req: Request,
  { params }: { params: Promise<{ id: string }> },
) {
  const { id } = await params;
  if (!id || !/^[a-z][a-z0-9-]*[a-z0-9]$/.test(id)) {
    return Response.json({ error: "invalid id" }, { status: 400 });
  }

  const script =
    process.env.INIT_TOPICS_SCRIPT
    ?? "~/.openclaw/scripts/init_telegram_topics.py";

  const result = await new Promise<Result>((resolve, reject) => {
    const child = spawn("python3", [script, "--slug", id], {
      env: { ...process.env },
      stdio: ["ignore", "pipe", "pipe"],
    });
    let stdout = ""; let stderr = "";
    child.stdout.on("data", (d) => { stdout += d; });
    child.stderr.on("data", (d) => { stderr += d; });
    child.on("error", reject);
    child.on("close", () => {
      try { resolve(JSON.parse(stdout)); }
      catch { resolve({ error: stderr.trim() || stdout.trim() || "no output" }); }
    });
  });

  const status = result.error ? 500 : 200;
  return Response.json(result, { status });
}
```

- [ ] **Step 2: Type-check**

```bash
cd ~/code/mission-control
npm run typecheck
```

---

## Task 5: ProjectGeralTab — add "Initialize topics" button

**Files:**
- Modify: `mission-control/src/components/projects/ProjectGeralTab.tsx`

- [ ] **Step 1: Read current file to find the Telegram section**

```bash
grep -n "telegram\|Telegram\|bot_id\|Connect bot" \
    ~/code/mission-control/src/components/projects/ProjectGeralTab.tsx
```

Locate the Telegram bot section (likely a card with `bot_id`, `bot_username` display + "Connect bot" button). The new button appears in the same card.

- [ ] **Step 2: Add state + handler in the component**

```tsx
const [initializing, setInitializing] = useState(false);
const [topicsResult, setTopicsResult] = useState<null | {
  created: string[]; existing: string[]; failed: { topic: string; error: string }[];
}>(null);

const topicsComplete =
  Boolean(project.telegram?.topics?.clarifications)
  && Boolean(project.telegram?.topics?.dispatcher);

async function onInitTopics() {
  setInitializing(true);
  try {
    const res = await fetch(
      `/api/projects/${project.id}/telegram/init-topics`,
      { method: "POST" },
    );
    const json = await res.json();
    setTopicsResult(json);
    if (!json.error) {
      // Refresh project data so the meta-derived state updates
      router.refresh();
    }
  } finally {
    setInitializing(false);
  }
}
```

- [ ] **Step 3: Render button below the bot info, only when needed**

In the JSX of the Telegram section, after bot info display:

```tsx
{project.telegram?.bot_id && !topicsComplete && (
  <div className="mt-3 space-y-2">
    <button
      type="button"
      onClick={onInitTopics}
      disabled={initializing}
      className="rounded-md bg-blue-600 px-3 py-1.5 text-sm text-white disabled:opacity-50"
    >
      {initializing ? "Criando tópicos..." : "Initialize topics"}
    </button>
    <p className="text-xs text-muted-foreground">
      Cria os tópicos canônicos no grupo Telegram (clarifications, dispatcher).
      Bot precisa ter permissão admin de "Manage topics" no grupo.
    </p>
  </div>
)}

{topicsResult && (
  <div className="mt-2 text-xs">
    {topicsResult.created.length > 0 && (
      <p className="text-green-700">
        Criados: {topicsResult.created.join(", ")}
      </p>
    )}
    {topicsResult.existing.length > 0 && (
      <p className="text-muted-foreground">
        Já existiam: {topicsResult.existing.join(", ")}
      </p>
    )}
    {topicsResult.failed && topicsResult.failed.length > 0 && (
      <p className="text-red-600">
        Falhas:{" "}
        {topicsResult.failed.map(f => `${f.topic} (${f.error})`).join(", ")}
      </p>
    )}
  </div>
)}
```

- [ ] **Step 4: Ensure project includes `telegram` in its API response**

If `GET /api/projects/[id]` does not currently return the `telegram` sub-object, extend its response to merge `meta.projects[id].telegram` into the JSON body.

- [ ] **Step 5: Type-check**

```bash
cd ~/code/mission-control
npm run typecheck
```

---

## Task 6: Update clarification-agent notifier

**Files:**
- Modify: the file identified in Task 1 step 2 (likely `~/.openclaw/clarification-agent/lib/notifier.py` or `cli.sh`'s helper module)

- [ ] **Step 1: Find where `sendMessage` (or equivalent) is called**

```bash
grep -n "sendMessage\|send_message" ~/.openclaw/clarification-agent/**/*.py 2>/dev/null
```

- [ ] **Step 2: Add helper that reads message_thread_id from meta**

In the same file, add (or replace existing helper) with:

```python
def _resolve_thread_id(slug: str, topic: str) -> int | None:
    """Read projects-meta.json and return telegram.topics[topic] for slug."""
    import json, os
    if os.environ.get("OPENCLAW_TELEGRAM_TOPICS", "1") == "0":
        return None
    meta_path = "~/.openclaw/projects-meta.json"
    try:
        with open(meta_path, "r") as f:
            meta = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return None
    entry = meta.get("projects", {}).get(slug, {})
    topics = (entry.get("telegram", {}) or {}).get("topics", {}) or {}
    val = topics.get(topic)
    return int(val) if val else None
```

- [ ] **Step 3: Use it in the notify call**

Find the call to Telegram `sendMessage` for clarifications. Add `message_thread_id`:

```python
thread_id = _resolve_thread_id(project_slug, "clarifications")
payload = {
    "chat_id": chat_id,
    "text": message_text,
    "parse_mode": "Markdown",
}
if thread_id is not None:
    payload["message_thread_id"] = thread_id
# existing send logic with `payload`
```

- [ ] **Step 4: Add a quick smoke test**

```bash
~/.openclaw/clarification-agent/cli.sh ask \
    --task <some-real-task-id> \
    --question "Test clarification routing — ignore"
```

If meta has `topics.clarifications`, message should appear in the topic. Else in general. Either way, no error.

After verifying, close/answer the test clarification immediately so it doesn't pollute real flow.

---

## Task 7: Update dispatcher-agent notifier

**Files:**
- Modify: dispatcher-agent notifier (likely from Task 1 step 2 grep)

- [ ] **Step 1: Replicate the helper**

Same `_resolve_thread_id` helper as Task 6 (copy or, ideally, factor into `~/.openclaw/scripts/lib/telegram_meta.py` and import from both agents).

If factoring, create `~/.openclaw/scripts/lib/telegram_meta.py`:

```python
"""Helper: resolve message_thread_id from projects-meta.json.

Used by clarification-agent and dispatcher-agent notifiers.
"""
import json, os
from pathlib import Path

DEFAULT_META = Path("~/.openclaw/projects-meta.json")


def resolve_thread_id(slug: str, topic: str, meta_path: Path = DEFAULT_META) -> int | None:
    if os.environ.get("OPENCLAW_TELEGRAM_TOPICS", "1") == "0":
        return None
    try:
        with open(meta_path, "r") as f:
            meta = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return None
    entry = meta.get("projects", {}).get(slug, {})
    topics = (entry.get("telegram", {}) or {}).get("topics", {}) or {}
    val = topics.get(topic)
    return int(val) if val else None
```

Then import:

```python
import sys
sys.path.insert(0, "~/.openclaw/scripts/lib")
from telegram_meta import resolve_thread_id
```

(Or a cleaner package layout if the agents already share helpers.)

- [ ] **Step 2: Use it in the dispatcher's task_done/task_failed notification**

```python
thread_id = resolve_thread_id(project_slug, "dispatcher")
payload = {"chat_id": chat_id, "text": text}
if thread_id is not None:
    payload["message_thread_id"] = thread_id
```

- [ ] **Step 3: Smoke test**

Run a real task end-to-end (or simulate task_done event) and confirm the notification arrives in the `dispatcher` topic when meta has the entry.

---

## Task 8: Add unit tests for the helper

**Files:**
- Create: `~/.openclaw/kanban-tasks/tests/test_telegram_meta.py`

- [ ] **Step 1: Write tests**

```python
"""Tests for scripts/lib/telegram_meta.py."""
import json
import sys
from pathlib import Path

import pytest

LIB_DIR = Path("~/.openclaw/scripts/lib")
sys.path.insert(0, str(LIB_DIR))


def _write_meta(path: Path, slug: str, topics: dict | None) -> None:
    meta = {"projects": {slug: {"telegram": {"chat_id": -100, "topics": topics or {}}}}}
    path.write_text(json.dumps(meta))


def test_returns_int_when_topic_present(tmp_path):
    from telegram_meta import resolve_thread_id
    p = tmp_path / "meta.json"
    _write_meta(p, "foo", {"clarifications": 42})
    assert resolve_thread_id("foo", "clarifications", meta_path=p) == 42


def test_returns_none_when_topic_missing(tmp_path):
    from telegram_meta import resolve_thread_id
    p = tmp_path / "meta.json"
    _write_meta(p, "foo", {})
    assert resolve_thread_id("foo", "clarifications", meta_path=p) is None


def test_returns_none_when_project_missing(tmp_path):
    from telegram_meta import resolve_thread_id
    p = tmp_path / "meta.json"
    _write_meta(p, "other", {"clarifications": 1})
    assert resolve_thread_id("foo", "clarifications", meta_path=p) is None


def test_feature_flag_disables_lookup(tmp_path, monkeypatch):
    from telegram_meta import resolve_thread_id
    p = tmp_path / "meta.json"
    _write_meta(p, "foo", {"clarifications": 99})
    monkeypatch.setenv("OPENCLAW_TELEGRAM_TOPICS", "0")
    assert resolve_thread_id("foo", "clarifications", meta_path=p) is None
```

- [ ] **Step 2: Run tests**

```bash
cd ~/.openclaw/kanban-tasks
python3 -m pytest tests/test_telegram_meta.py -v
```

Expected: 4 PASSED.

---

## Task 9: E2E smoke test

- [ ] **Step 1: Pre-conditions**

Pick an existing project that has a connected bot AND a real Telegram supergroup with forum/topics enabled. Confirm the bot is admin with `manage_topics` permission.

```bash
SLUG="<your-project-slug>"
python3 -c "
import json
m = json.load(open('~/.openclaw/projects-meta.json'))
e = m['projects']['$SLUG']
print('bot_id:', e.get('bot_id'))
print('telegram:', e.get('telegram'))
"
```

Confirm `bot_id` and `telegram.chat_id` are set; `telegram.topics` is empty or absent.

- [ ] **Step 2: Run the script directly**

```bash
SLUG="<your-project-slug>"
python3 ~/.openclaw/scripts/init_telegram_topics.py --slug "$SLUG" | jq
```

Expected: `created: ["clarifications", "dispatcher"]`, `existing: []`, `failed: []`.

In Telegram, two new topics should appear in the group.

- [ ] **Step 3: Verify meta updated**

```bash
python3 -c "
import json
m = json.load(open('~/.openclaw/projects-meta.json'))
print(json.dumps(m['projects']['$SLUG']['telegram']['topics'], indent=2))
"
```

Expected: integer thread IDs for both topics.

- [ ] **Step 4: Run again — verify idempotent**

```bash
python3 ~/.openclaw/scripts/init_telegram_topics.py --slug "$SLUG" | jq
```

Expected: `created: []`, `existing: ["clarifications", "dispatcher"]`. No duplicate topics in Telegram.

- [ ] **Step 5: Smoke notifiers**

Trigger a real clarification + a real task_done for that project. Confirm:
- Clarification message lands in the `<slug>:clarifications` topic
- task_done notification lands in the `<slug>:dispatcher` topic

- [ ] **Step 6: Smoke UI button**

```bash
cd ~/code/mission-control
npm run dev
```

Open `http://localhost:3000/projects/<some-OTHER-slug>` (one without topics). Click "Initialize topics". Verify result text + topics created in Telegram.

- [ ] **Step 7: Smoke feature flag**

```bash
OPENCLAW_TELEGRAM_TOPICS=0 ~/.openclaw/clarification-agent/cli.sh ask \
    --task <real-task-id> --question "flag-off test"
```

With flag off, message should arrive in the **general** topic, not in `clarifications`. Cleanup test message.

---

## Task 10: Commit + PR for openclaw repo

- [ ] **Step 1: Stage**

```bash
cd ~/.openclaw
git add scripts/init_telegram_topics.py \
        scripts/lib/telegram_meta.py \
        kanban-tasks/tests/test_init_telegram_topics.py \
        kanban-tasks/tests/test_telegram_meta.py \
        clarification-agent/ \
        dispatcher-agent/
git status
```

(Inspect — only the modified notifier files inside the agent dirs should be staged. Use precise paths if needed.)

- [ ] **Step 2: Commit**

```bash
git commit -m "feat(telegram): canonical forum topics per project + topic-aware notifiers

Phase 4 of mc-projects-factory wave-2.
- scripts/init_telegram_topics.py: idempotently create clarifications +
  dispatcher topics in a project's group; persist message_thread_id in
  projects-meta.json.
- scripts/lib/telegram_meta.py: shared helper to resolve message_thread_id.
- clarification-agent and dispatcher-agent notifiers now post into the
  per-project topic when present; fall back to general otherwise.
- Feature flag OPENCLAW_TELEGRAM_TOPICS (default 1) disables lookup.

Tests: unit tests for script + helper; smoke E2E in pull request."
```

- [ ] **Step 3: Push**

```bash
git push -u origin feat/mc-projects-factory-w2-phase-4-telegram-topics
```

---

## Task 11: Commit + PR for mission-control repo

- [ ] **Step 1: Stage MC changes**

```bash
cd ~/code/mission-control
git add src/app/api/projects/[id]/telegram/init-topics/route.ts \
        src/components/projects/ProjectGeralTab.tsx \
        src/app/api/projects/[id]/route.ts
git status
```

- [ ] **Step 2: Commit**

```bash
git commit -m "feat(projects): Initialize Telegram topics button

Phase 4 of mc-projects-factory wave-2. New POST /api/projects/[id]/telegram/init-topics
spawns ~/.openclaw/scripts/init_telegram_topics.py. ProjectGeralTab Telegram
section shows 'Initialize topics' button when bot is connected and topics
are missing/incomplete. Result toast shows created/existing/failed."
```

- [ ] **Step 3: Push + PRs (one per repo)**

```bash
git push -u origin feat/mc-projects-factory-w2-phase-4-telegram-topics

gh pr create --title "feat: Initialize Telegram topics (Phase 4 — MC side)" \
  --body "$(cat <<'EOF'
## Summary
- New API route POST /api/projects/[id]/telegram/init-topics
- New "Initialize topics" button in ProjectGeralTab Telegram section, visible only when bot connected AND topics missing
- Result toast surfaces created/existing/failed per topic

Pairs with openclaw PR for the script + notifier updates.

## Test plan
- [x] Type check
- [x] Manual UI smoke against a real project
EOF
)"
```

For the openclaw side, the openclaw repo PR was opened in Task 10. Add a cross-link in both descriptions.

---

## Phase 4 acceptance gate

- [ ] `init_telegram_topics.py` works idempotently (smoked twice, second run no duplicates)
- [ ] Tests passing (script + helper + meta lookup)
- [ ] API route + UI button work end-to-end
- [ ] Clarification posted by `clarification-agent` lands in the `<slug>:clarifications` topic when present
- [ ] task_done/task_failed posted by `dispatcher-agent` lands in `<slug>:dispatcher` topic
- [ ] Feature flag `OPENCLAW_TELEGRAM_TOPICS=0` causes notifiers to fall back to general
- [ ] Two PRs opened (openclaw + mission-control) and cross-linked
