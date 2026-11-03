"""Clarification Reply Handler.

handle_reply() é o ponto de convergência dos 3 caminhos de ingestão de
reply de clarification:

1. swipe-reply nativo no Telegram (via plugin clarification-commands no
   gateway → execFile cli.sh answer)
2. comando /clr_override <task> "<texto>" (mesmo plugin, mesmo execFile)
3. CLI manual: ~/.openclaw/clarification-agent/cli.sh answer <cid> --answer "..."

Cada caminho passa source distinto ("telegram_reply" | "slash_command" |
"manual_cli") como audit trail no notifier-state.json.

Spec: docs/superpowers/specs/2026-04-28-clarification-reply-via-gateway-plugin-design.md
"""
from __future__ import annotations

import json
import re
import os
import sys
import subprocess
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional, Tuple

from . import store, lifecycle


def load_env() -> dict:
    """Carregar variáveis de ambiente do .env."""
    env_file = Path.home() / ".openclaw" / ".env"
    env = {}
    if env_file.exists():
        with open(env_file, 'r') as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith('#') and '=' in line:
                    key, _, value = line.partition('=')
                    env[key.strip()] = value.strip()
    return env


def process_reply_file(clarification_id: str, reply_text: str) -> bool:
    """Processar resposta salva manualmente via arquivo.
    
    Bernard pode salvar resposta em:
    ~/.openclaw/clarification-agent/answers/{clarification_id}.md
    
    Ou usar CLI: vox clarification answer T-XXXX-clr-N "resposta"
    """
    answers_dir = Path.home() / ".openclaw" / "clarification-agent" / "answers"
    answers_dir.mkdir(parents=True, exist_ok=True)
    
    answer_file = answers_dir / f"{clarification_id}.md"
    
    # Salvar resposta
    with open(answer_file, 'w', encoding='utf-8') as f:
        f.write(f"# Resposta de Bernard\n\n")
        f.write(f"**Clarification ID:** `{clarification_id}`\n\n")
        f.write(f"**Data:** {datetime.now(timezone.utc).isoformat()}\n\n")
        f.write(f"**Resposta:**\n\n{reply_text}\n")
    
    return True


def unblock_task(clarification_id: str) -> bool:
    """Desbloquear task após clarification respondida."""
    match = re.match(r"^(T-\d{4})-clr-", clarification_id)
    if not match:
        print(f"❌ clarification_id inválido: {clarification_id}")
        return False

    task_id = match.group(1)
    kanban_cli = Path.home() / ".openclaw" / "kanban-tasks" / "cli.sh"

    try:
        subprocess.run(
            [str(kanban_cli), "task", "unblock", task_id, "--actor", "clarification-handler", "--json"],
            check=False, capture_output=True, text=True, timeout=30,
        )
        move = subprocess.run(
            [str(kanban_cli), "task", "move", task_id, "ready", "--actor", "clarification-handler", "--reason", "clarification answered", "--json"],
            check=False, capture_output=True, text=True, timeout=30,
        )
    except (OSError, subprocess.TimeoutExpired) as e:
        print(f"❌ Falha ao desbloquear task {task_id}: {e}")
        return False

    if move.returncode == 0:
        print(f"✅ Task {task_id} desbloqueada e movida para ready")
        return True

    print(f"❌ Falha ao mover task {task_id} para ready: {move.stderr[:200]}")
    return False


def _resolve_token_for_alias(alias: str, env: dict) -> Optional[str]:
    """Map token_alias to actual bot token via env vars.

    'openclaw-central' -> TELEGRAM_BOT_TOKEN
    'project-<slug>' -> BOT_TOKEN_VOZ_<UPPER_SLUG_WITH_UNDERSCORES>
                    or BOT_TOKEN_<UPPER_SLUG_WITH_UNDERSCORES>
    """
    if alias == "openclaw-central":
        return env.get("TELEGRAM_BOT_TOKEN")
    if alias and alias.startswith("project-"):
        slug_lower = alias[len("project-"):]
        slug_upper = slug_lower.upper().replace("-", "_")
        # 1. env-var conventions
        for key in (f"BOT_TOKEN_VOZ_{slug_upper}", f"BOT_TOKEN_{slug_upper}"):
            tok = env.get(key)
            if tok:
                return tok
        # 2. fallback: read profile dir openclaw.json (where bootstrap-telegram-agent
        # actually persists the bot token — channels.telegram.botToken)
        from pathlib import Path
        for profile_dir in (
            Path.home() / f".openclaw-{slug_lower}",
            Path.home() / f".openclaw-{slug_lower.replace('bevox-', '')}",  # bevox-finance → financeiro variants
        ):
            cfg = profile_dir / "openclaw.json"
            if cfg.is_file():
                try:
                    with open(cfg, "r", encoding="utf-8") as f:
                        data = json.load(f)
                    tok = (data.get("channels", {}).get("telegram", {}) or {}).get("botToken")
                    if tok:
                        return tok
                except (OSError, json.JSONDecodeError):
                    continue
    return None


def _send_via_token(token: str, payload: dict) -> bool:
    """POST sendMessage to Telegram with given token. Returns True on 200."""
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
    """Enviar confirmação no MESMO bot/chat/thread que enviou a clarification.

    Reads notifier-state.json[cid] to get token_alias, chat_id, thread_id.
    Routes confirmation back through that bot's token (resolved via env vars).
    Best-effort: silent skip if alias/chat_id missing or token unresolvable.
    """
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


def handle_reply(clarification_id: str, reply_text: str, source: str = "manual_cli") -> bool:
    """Handler principal: processa resposta e desbloqueia task.

    Args:
        clarification_id: T-XXXX-clr-N
        reply_text: texto livre da resposta
        source: origem ("telegram_reply" | "slash_command" | "manual_cli")
    """
    print(f"📝 Processando resposta para {clarification_id} (source={source})...")

    state_path = store.ROOT / "notifier-state.json"

    # Idempotency: skip if already resolved
    state = store.load_state_v2(state_path)
    entry = state.get("notifications", {}).get(clarification_id)
    if entry and entry.get("status") == "resolved":
        print(f"⚠️  {clarification_id} já está resolved (idempotent skip)")
        return True

    match = re.match(r"^(T-\d{4})-clr-", clarification_id)
    if not match:
        print("❌ clarification_id inválido")
        return False
    task_id = match.group(1)

    if not process_reply_file(clarification_id, reply_text):
        print("❌ Falha ao salvar resposta")
        return False

    try:
        store.clear_escalation_symlink(clarification_id)
    except OSError as e:
        print(f"⚠️  clear_escalation_symlink falhou: {e}")

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

    # Best-effort: status update failure does not fail the handler (task is
    # already unblocked). However, on failure the next handle_reply call will
    # see status="pending" and re-execute the full flow — accept this as the
    # cost of avoiding handler failure on disk errors.
    try:
        if entry is not None:
            updated = dict(entry)
            updated["status"] = "resolved"
            updated["resolved_at"] = store.now_iso()
            updated["resolved_via"] = source
            state["notifications"][clarification_id] = updated
            store.save_state_v2(state_path, state)
    except Exception as e:
        print(f"⚠️ Falha ao atualizar notifier-state: {e}")

    send_confirmation_message(clarification_id, task_id)
    print(f"✅ Clarification {clarification_id} resolvida com sucesso!")
    return True


if __name__ == "__main__":
    import sys
    
    if len(sys.argv) < 3:
        print("Uso: python3 reply_handler.py <clarification_id> <resposta>")
        print("Exemplo: python3 reply_handler.py T-0024-clr-4 'A'")
        sys.exit(1)
    
    clarification_id = sys.argv[1]
    reply_text = sys.argv[2]
    
    success = handle_reply(clarification_id, reply_text)
    sys.exit(0 if success else 1)
