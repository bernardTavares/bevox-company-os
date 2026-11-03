"""OpenClaw clarification notifier — E10/OH wave-2.

Serviço standalone (systemd user timer 60s) que varre
~/.openclaw/clarification-agent/escalations/ e envia notificação
Telegram no tópico `clarifications` para cada nova escalation unsafe.

Design tight: stdlib-only, fcntl lock, atomic state, audit jsonl.
Fonte-única-da-verdade: escalations/ (populada pela wave-1).
"""
from __future__ import annotations

import argparse
import fcntl
import json
import os
import re
import sys
import tempfile
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Set, Tuple

# --- Phase 4 import shim: shared telegram_meta helper -----------------------
import sys as _sys
_TM_LIB = f"{Path.home()}/.openclaw/scripts/lib"
if _TM_LIB not in _sys.path:
    _sys.path.insert(0, _TM_LIB)
from telegram_meta import resolve_thread_id  # noqa: E402
# ----------------------------------------------------------------------------

# Filename pattern: T-XXXX-clr-N.md (N = 1+ digits)
_FILENAME_RE = re.compile(r"^(T-\d{4})-clr-\d+\.md$")


def _alias_for(slug, eff_token, default_token):
    """Return token_alias for notifier-state schema v2.

    'project-<slug>' if eff_token differs from the central default;
    'openclaw-central' otherwise (slug is None or fallback was used).
    """
    if slug and eff_token != default_token:
        return f"project-{slug}"
    return "openclaw-central"


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


def _slug_for_clarification(task_id: str, cid: str) -> str | None:
    """Resolve project slug for a clarification (best-effort).

    Strategy (returns None on miss → caller falls back to env thread_id):
    1. Look in ~/.openclaw/clarification-agent/questions/<cid>.md frontmatter `project:`
    2. Then in ~/.openclaw/clarification-agent/answers/<cid>.md frontmatter `project:`
    3. Then look at kanban-tasks/state.json: tasks[].project where id == task_id
    """
    base = Path(f"{Path.home()}/.openclaw/clarification-agent")
    for sub in ("questions", "answers"):
        candidate = base / sub / f"{cid}.md"
        if candidate.is_file():
            try:
                text = candidate.read_text(encoding="utf-8")
            except OSError:
                continue
            m = re.search(r"^project:\s*([\w-]+)\s*$", text, re.MULTILINE)
            if m:
                return m.group(1)
    # Fallback: kanban state
    try:
        state = json.loads(
            Path(f"{Path.home()}/.openclaw/kanban-tasks/state.json").read_text(
                encoding="utf-8"
            )
        )
        for t in state.get("tasks", []) or []:
            if t.get("id") == task_id and t.get("project"):
                return str(t["project"])
    except (FileNotFoundError, json.JSONDecodeError, OSError):
        pass
    return None


def build_telegram_message(
    task_id: str,
    cid: str,
    chat_id: str,
    thread_id: int,
) -> dict:
    """Construct sendMessage body for Telegram Bot API.

    Formato melhorado: inclui pergunta completa + instruções de resposta.
    """
    # Tentar ler o arquivo de question para incluir na mensagem
    question_path = Path.home() / ".openclaw" / "clarification-agent" / "questions" / f"{cid}.md"
    
    if question_path.exists():
        try:
            with open(question_path, 'r', encoding='utf-8') as f:
                question_content = f.read()
            
            # Extrair apenas o conteúdo relevante (remover headers markdown)
            lines = question_content.split('\n')
            # Encontrar onde começa o conteúdo real (após "---")
            content_start = 0
            for i, line in enumerate(lines):
                if line.strip() == '---':
                    content_start = i + 1
                    break
            
            question_text = '\n'.join(lines[content_start:]).strip()
            
            # Limitar tamanho para não estourar limite do Telegram (~4096 chars)
            max_question_len = 2500
            if len(question_text) > max_question_len:
                question_text = question_text[:max_question_len] + "\n\n... (pergunta truncada, use `vox clarification show {cid}` para ver completa)"
            
            # Construir mensagem formatada
            text = f"""🚫 **Task Blocked: {task_id}**

**Clarification ID:** `{cid}`

---

**Pergunta do executor:**

{question_text}

---

**Como responder com segurança:**
• Responda neste tópico **citando o ID** `{cid}`
• Formato recomendado: `{cid}: sua resposta`
• Se a ingestão automática do canal falhar, registrar manualmente com:
`clarification-agent answer {cid} --answer "<resposta>"`

**Garantia operacional:** não assuma que reply simples no chat foi ingerido até a task sair de `blocked`."""
        except Exception:
            # Fallback para mensagem simples se falhar leitura
            text = (
                f"🚫 **Task Blocked: {task_id}**\n\n"
                f"**Clarification ID:** `{cid}`\n\n"
                f"Responda citando o ID: `{cid}: sua resposta`"
            )
    else:
        # Fallback se arquivo de question não existir
        text = (
            f"🚫 **Task Blocked: {task_id}**\n\n"
            f"**Clarification ID:** `{cid}`\n\n"
            f"Responda citando o ID: `{cid}: sua resposta`"
        )
    
    return {
        "chat_id": chat_id,
        "message_thread_id": thread_id,
        "text": text,
        "parse_mode": "Markdown",
        "disable_web_page_preview": True,
    }


# notifier.py owns its own state I/O (load_state/save_state/_EMPTY_STATE).
# store.py's load_state_v2/save_state_v2 are consumed by reply_handler.py
# and the gateway plugin (Tasks 6-8 of the clarification-reply-via-gateway-
# plugin wave). The two stacks coexist intentionally for now.
_EMPTY_STATE = {
    "schema_version": 2,
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
        # Note: existing v1 files keep their explicit "schema_version": 1.
        # One-shot migration via store.migrate_v1_to_v2() is the operator's
        # responsibility before the daemon writes v2 entries to the same file.
        data.setdefault("schema_version", 2)
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


def _now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def append_event(jsonl_path: Path, event: str, payload: dict) -> None:
    """Append single-line JSON event to audit log (truncate=False)."""
    jsonl_path.parent.mkdir(parents=True, exist_ok=True)
    record = {"ts": _now_iso(), "event": event, "payload": payload}
    with open(jsonl_path, "a", encoding="utf-8") as f:
        f.write(json.dumps(record) + "\n")


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
        # Phase 4: prefer per-project bot/group/thread when available.
        # CRITICAL: token+chat_id+thread_id must be a coherent triple — using
        # legacy token/chat_id with a per-project thread_id triggers Telegram
        # 400 ("message thread not found"). resolve_telegram_target returns
        # the full triple atomically or None (then we fall back to env legacy).
        slug = _slug_for_clarification(task_id, cid)
        eff_token, eff_chat_id, eff_thread_id = token, chat_id, thread_id

        def _log_fallback(reason: str) -> None:
            # Logs the routing decision (fallback to central). NOT a send outcome —
            # send success/failure is recorded separately via notification_sent /
            # notification_send_failed.
            append_event(jsonl_path, "clarification_fallback_to_central", {
                "clarification_id": cid,
                "task_id": task_id,
                "project": slug,
                "reason": reason,
            })

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
                    _log_fallback("topics.clarifications missing or unresolvable")
            else:
                _log_fallback("telegram_meta module unavailable")
        body = build_telegram_message(task_id, cid, eff_chat_id, eff_thread_id)
        if dry_run:
            append_event(jsonl_path, "notification_dry_run", {
                "clarification_id": cid, "body_text": body["text"],
            })
            summary["would_send"] += 1
            continue
        t_send_start = _time.monotonic()
        ok, result = send_telegram_message(body, token=eff_token)
        latency_ms = int((_time.monotonic() - t_send_start) * 1000)
        if ok:
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
                "source_path": source_path,  # mantido para diagnostics
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

    # Schema v2: when escalation symlink disappears, mark the entry as
    # resolved (preserve audit history) instead of popping. If cmd_answer
    # or cmd_override already set status="resolved" + resolved_via, leave
    # those fields intact. Entries with status="orphan" are NOT auto-flipped
    # to resolved (orphan migration semantics from store.migrate_v1_to_v2).
    for cid in sorted(resolved_cids):
        entry = state["notifications"].get(cid, {})
        prev_status = entry.get("status")
        if dry_run:
            append_event(jsonl_path, "notification_skipped_resolved_dry_run", {
                "clarification_id": cid,
            })
            continue
        if entry and prev_status not in ("resolved", "orphan"):
            updated = dict(entry)
            updated["status"] = "resolved"
            updated["resolved_at"] = updated.get("resolved_at") or _now_iso()
            # resolved_via stays as set by cmd_answer/cmd_override; if neither
            # ran (escalation file removed externally), record the path.
            if not updated.get("resolved_via"):
                updated["resolved_via"] = "escalation_removed"
            state["notifications"][cid] = updated
        append_event(jsonl_path, "notification_skipped_resolved", {
            "clarification_id": cid,
            "was_notified_at": entry.get("sent_at") or entry.get("notified_at"),
            "prev_status": prev_status,
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
