"""commands — 7 handlers for skill-V2 W3.5 Telegram commands.

Each handler:
    cmd_<name>(state: dict, gap_id: str, **kwargs) → CommandResult

Handlers operate on state in-memory; caller is responsible for read/write
of state.json. Idempotent: terminal-status gaps return friendly noop reply.

Spec: bevox-knowledge/35_specs/_shared/2026-05-08-bevox-knowledge-contribute-skill-v2.md §11
Plan: bevox-knowledge/35_specs/_shared/plans/2026-05-09-skill-v2-W3.5-telegram-commands-plan.md
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Any, Dict, Optional


EXIT_OK = 0
EXIT_NOT_FOUND = 64
EXIT_TERMINAL_LOCK = 65
EXIT_INVALID_TOKEN = 66
EXIT_GIT_ERROR = 67


@dataclass
class CommandResult:
    ok: bool
    reply: str
    exit_code: int = EXIT_OK


def _record_gap_decision(g, decision: str) -> None:
    """Best-effort feedback record for a gap-aware command. Errors swallowed.

    W9.T1 fix: deserializes g.signals_json (persisted by F4 scanner) so
    feedback.db captures real signal combos (e.g. 'B', 'A+B+E') instead of
    always 'none'. F1 gaps still have signals_json=None → combo='none'
    (acceptable: F1 doesn't have categorial signals).
    """
    try:
        import json as _json
        from lib.knowledge_watcher.feedback import record_decision

        signals_payload = []
        raw = getattr(g, "signals_json", None)
        if raw:
            try:
                parsed = _json.loads(raw)
            except (_json.JSONDecodeError, TypeError):
                parsed = []
            # Build lightweight shim with .category.value / .confidence /
            # .evidence so feedback._serialize_signals can pickle it without
            # needing the RetirementCategory enum.
            class _CatShim:
                def __init__(self, value):
                    self.value = value

            class _SigShim:
                def __init__(self, d):
                    self.category = _CatShim(d.get("category"))
                    self.confidence = d.get("confidence")
                    self.evidence = d.get("evidence")
            signals_payload = [_SigShim(d) for d in parsed if isinstance(d, dict)]

        record_decision(
            gap_id=g.gap_id,
            source=getattr(g.source, "value", str(g.source)),
            doc_type=g.doc_type,
            project_slug=g.repo,
            signals=signals_payload,
            decision=decision,
        )
    except Exception:
        pass


def cmd_review(
    state: Dict[str, Any], gap_id: str, kb_remote_url: str,
) -> CommandResult:
    """Returns a GitHub URL pointing to the gap's draft branch (F1) or
    canonical path on main (F4)."""
    from .gap_registry import get_gap
    g = get_gap(state, gap_id)
    if g is None:
        return CommandResult(
            ok=False, exit_code=EXIT_NOT_FOUND,
            reply=f"❌ {gap_id}: gap não encontrada em state.json",
        )
    base = kb_remote_url.rstrip("/")
    if g.draft_branch:
        url = f"{base}/tree/{g.draft_branch}"
    else:
        url = f"{base}/blob/main/{g.path}"
    return CommandResult(
        ok=True,
        reply=f"🔗 {gap_id}\n{url}\n(status: {g.status.value})",
    )


def cmd_dismiss(state: Dict[str, Any], gap_id: str) -> CommandResult:
    """Mark gap dismissed (terminal). Idempotent on re-fire.
    Blocks if gap in different terminal state (accepted/retired)."""
    from .gap_registry import get_gap, update_gap, GapStatus
    g = get_gap(state, gap_id)
    if g is None:
        return CommandResult(
            ok=False, exit_code=EXIT_NOT_FOUND,
            reply=f"❌ {gap_id}: gap não encontrada",
        )
    if g.status is GapStatus.DISMISSED:
        return CommandResult(
            ok=True, reply=f"ℹ️  {gap_id} já dismissed (noop)",
        )
    if g.status.is_terminal:
        return CommandResult(
            ok=False, exit_code=EXIT_TERMINAL_LOCK,
            reply=(
                f"🔒 {gap_id} está em estado terminal "
                f"`{g.status.value}` — `/dismiss` não permitido. "
                f"Use `/reopen` (futuro) se quiser reativar."
            ),
        )
    update_gap(state, gap_id, status=GapStatus.DISMISSED)
    _record_gap_decision(g, "dismiss")
    return CommandResult(
        ok=True,
        reply=f"🗑️  {gap_id} dismissed",
    )


KEEP_DAYS = 90
KEEP_PERMANENT_COMMENT = "<!-- knowledge-watcher: do-not-retire -->"


def cmd_keep(state: Dict[str, Any], gap_id: str) -> CommandResult:
    """Keep gap for 90 days (F4 retirement only)."""
    from .gap_registry import get_gap, update_gap, GapStatus, GapSource
    g = get_gap(state, gap_id)
    if g is None:
        return CommandResult(
            ok=False, exit_code=EXIT_NOT_FOUND,
            reply=f"❌ {gap_id}: gap não encontrada",
        )
    if g.source is not GapSource.F4:
        return CommandResult(
            ok=False, exit_code=EXIT_OK,
            reply=(
                f"❌ /keep só vale pra F4 (retirement). "
                f"Para F1 gaps, use `/postpone {gap_id} <N>`."
            ),
        )
    if g.status.is_terminal:
        return CommandResult(
            ok=False, exit_code=EXIT_TERMINAL_LOCK,
            reply=f"🔒 {gap_id} já em estado terminal (`{g.status.value}`)",
        )
    until = datetime.now(timezone.utc) + timedelta(days=KEEP_DAYS)
    update_gap(state, gap_id, status=GapStatus.SNOOZED, snooze_until=until)
    _record_gap_decision(g, "keep")
    return CommandResult(
        ok=True,
        reply=f"📌 {gap_id} kept {KEEP_DAYS}d (até {until.date().isoformat()})",
    )


def cmd_keep_permanent(
    state: Dict[str, Any], gap_id: str,
    kb_dir: Path, dry_run: bool = False, push: bool = True,
) -> CommandResult:
    """Insert HTML comment in doc body marking it as never-retire.
    Commits in draft branch `draft/keep-permanent/<gap_id>`.
    """
    from .gap_registry import get_gap, update_gap, GapStatus, GapSource
    from .git_ops import commit_in_draft_branch
    g = get_gap(state, gap_id)
    if g is None:
        return CommandResult(
            ok=False, exit_code=EXIT_NOT_FOUND,
            reply=f"❌ {gap_id}: gap não encontrada",
        )
    if g.source is not GapSource.F4:
        return CommandResult(
            ok=False, exit_code=EXIT_OK,
            reply=f"❌ /keep-permanent só vale pra F4 (retirement)",
        )
    doc_path = kb_dir / g.path
    if not doc_path.is_file():
        return CommandResult(
            ok=False, exit_code=EXIT_NOT_FOUND,
            reply=f"❌ {gap_id}: doc {g.path} não existe em {kb_dir}",
        )
    content = doc_path.read_text(encoding="utf-8")
    if KEEP_PERMANENT_COMMENT in content:
        return CommandResult(
            ok=True,
            reply=f"ℹ️  {gap_id} já tem marker keep-permanent (noop)",
        )
    if dry_run:
        return CommandResult(
            ok=True,
            reply=f"[dry-run] {gap_id} would gain keep-permanent marker",
        )
    new_content = content.rstrip() + f"\n\n{KEEP_PERMANENT_COMMENT}\n"
    doc_path.write_text(new_content, encoding="utf-8")
    branch = f"draft/keep-permanent/{gap_id}"
    try:
        sha = commit_in_draft_branch(
            kb_dir, branch, g.path,
            f"chore(keep-permanent): mark {g.path} as never-retire",
            push=push,
        )
    except RuntimeError as e:
        return CommandResult(
            ok=False, exit_code=EXIT_GIT_ERROR,
            reply=f"❌ {gap_id}: git error — {e}",
        )
    update_gap(state, gap_id, status=GapStatus.DISMISSED)  # terminal: never re-flag
    _record_gap_decision(g, "keep_permanent")
    return CommandResult(
        ok=True,
        reply=(
            f"📌 {gap_id} marked keep-permanent\n"
            f"branch: {branch} ({sha[:7]})"
        ),
    )


def cmd_postpone(
    state: Dict[str, Any], gap_id: str, days: int,
) -> CommandResult:
    """Snooze gap N days. Replaces previous snooze (not cumulative).
    Days must be in [1, 365]. Status: OPEN/SNOOZED → SNOOZED.
    Terminal-locked gaps blocked.
    """
    from .gap_registry import get_gap, update_gap, GapStatus
    if not isinstance(days, int) or days < 1 or days > 365:
        return CommandResult(
            ok=False, exit_code=EXIT_OK,
            reply=f"❌ /postpone: days deve estar em [1, 365] (recebido: {days})",
        )
    g = get_gap(state, gap_id)
    if g is None:
        return CommandResult(
            ok=False, exit_code=EXIT_NOT_FOUND,
            reply=f"❌ {gap_id}: gap não encontrada",
        )
    if g.status.is_terminal:
        return CommandResult(
            ok=False, exit_code=EXIT_TERMINAL_LOCK,
            reply=f"🔒 {gap_id} está terminal (`{g.status.value}`)",
        )
    until = datetime.now(timezone.utc) + timedelta(days=days)
    update_gap(state, gap_id, status=GapStatus.SNOOZED, snooze_until=until)
    _record_gap_decision(g, "postpone")
    return CommandResult(
        ok=True,
        reply=f"💤 {gap_id} postponed {days}d (até {until.date().isoformat()})",
    )


# ---------------------------------------------------------------------------
# T2.6 — cmd_retire
# ---------------------------------------------------------------------------

import secrets
from datetime import date as _date


def cmd_retire(
    state: Dict[str, Any], gap_id: str,
    kb_dir: Path, push: bool = True,
) -> CommandResult:
    """Move doc to _retired/<repo>/<topic>/<date>-<filename> in a draft branch.

    F4-only. Idempotent when already RETIRED. Blocked on other terminal states.
    """
    from .gap_registry import get_gap, update_gap, GapStatus, GapSource
    from .git_ops import move_to_retired
    g = get_gap(state, gap_id)
    if g is None:
        return CommandResult(
            ok=False, exit_code=EXIT_NOT_FOUND,
            reply=f"❌ {gap_id}: gap não encontrada",
        )
    if g.source is not GapSource.F4:
        return CommandResult(
            ok=False, exit_code=EXIT_OK,
            reply=f"❌ /retire só vale pra F4 (retirement)",
        )
    if g.status is GapStatus.RETIRED:
        return CommandResult(
            ok=True, reply=f"ℹ️  {gap_id} já retired (noop)",
        )
    if g.status.is_terminal:
        return CommandResult(
            ok=False, exit_code=EXIT_TERMINAL_LOCK,
            reply=f"🔒 {gap_id} terminal `{g.status.value}` — não pode retire",
        )
    src = g.path
    parts = Path(src).parts
    if len(parts) >= 2:
        first = parts[0]
        topic = first.split("_", 1)[-1] if "_" in first else first
    else:
        topic = "misc"
    today = _date.today().isoformat()
    fname = Path(src).name
    dest = f"_retired/{g.repo}/{topic}/{today}-{fname}"
    branch = f"draft/auto/retire-{gap_id}"
    try:
        sha = move_to_retired(kb_dir, src, dest, branch, push=push)
    except RuntimeError as e:
        return CommandResult(
            ok=False, exit_code=EXIT_GIT_ERROR,
            reply=f"❌ {gap_id}: git error — {e}",
        )
    update_gap(state, gap_id, status=GapStatus.RETIRED)
    _record_gap_decision(g, "retire")
    return CommandResult(
        ok=True,
        reply=(
            f"🗑️  {gap_id} retired\n"
            f"{src} -> {dest}\n"
            f"branch: {branch} ({sha[:7]})"
        ),
    )


# ---------------------------------------------------------------------------
# T2.7 — cmd_accept
# ---------------------------------------------------------------------------

ACCEPT_TOKEN_TTL_SEC = 60


def cmd_accept(
    state: Dict[str, Any], gap_id: str,
    confirm_token: Optional[str], kb_dir: Path, push: bool = True,
) -> CommandResult:
    """2-step accept: generate token (step 1), consume with FF-merge (step 2).

    Step 1 (confirm_token=None): generate token, store in state['_pending_accept'][gap_id].
    Step 2 (confirm_token=<token>): validate + age check + FF-merge draft → main.

    F1-only and doc_type=release-note only (other docs: use /review + manual merge).
    """
    from .gap_registry import get_gap, update_gap, GapStatus, GapSource
    from .git_ops import ff_merge_to_main
    g = get_gap(state, gap_id)
    if g is None:
        return CommandResult(
            ok=False, exit_code=EXIT_NOT_FOUND,
            reply=f"❌ {gap_id}: gap não encontrada",
        )
    if g.status is GapStatus.ACCEPTED:
        return CommandResult(
            ok=True, reply=f"ℹ️  {gap_id} já accepted (noop)",
        )
    if g.status.is_terminal:
        return CommandResult(
            ok=False, exit_code=EXIT_TERMINAL_LOCK,
            reply=f"🔒 {gap_id} terminal `{g.status.value}` — não pode accept",
        )
    if g.source is not GapSource.F1:
        return CommandResult(
            ok=False, exit_code=EXIT_OK,
            reply=f"❌ /accept só vale pra F1 release-notes (FF-merge para main)",
        )
    if g.doc_type != "release-note":
        return CommandResult(
            ok=False, exit_code=EXIT_OK,
            reply=(
                f"❌ /accept só pra doc_type=release-note "
                f"(este é {g.doc_type}). Use /review e merge manual."
            ),
        )
    if not g.draft_branch:
        return CommandResult(
            ok=False, exit_code=EXIT_OK,
            reply=f"❌ {gap_id} sem draft_branch — nada pra merge",
        )
    pending = state.setdefault("_pending_accept", {})
    if confirm_token is None:
        # Step 1: generate token
        token = secrets.token_urlsafe(8)
        pending[gap_id] = {
            "token": token,
            "created_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        }
        return CommandResult(
            ok=True,
            reply=(
                f"⚠️  /accept é destrutivo (FF-merge -> main canonical).\n"
                f"Confirme em 60s:\n"
                f"  /accept {gap_id} {token}\n"
                f"Ou /cancel-accept {gap_id} pra abortar."
            ),
        )
    # Step 2: validate token + age
    p = pending.get(gap_id)
    if p is None:
        return CommandResult(
            ok=False, exit_code=EXIT_INVALID_TOKEN,
            reply=f"❌ {gap_id}: nenhum /accept pendente. Refaça step 1.",
        )
    if p["token"] != confirm_token:
        return CommandResult(
            ok=False, exit_code=EXIT_INVALID_TOKEN,
            reply=f"❌ {gap_id}: token inválido",
        )
    age = datetime.now(timezone.utc) - datetime.fromisoformat(
        p["created_at"].replace("Z", "+00:00")
    )
    if age.total_seconds() > ACCEPT_TOKEN_TTL_SEC:
        del pending[gap_id]
        return CommandResult(
            ok=False, exit_code=EXIT_INVALID_TOKEN,
            reply=f"❌ {gap_id}: token expirado ({age.total_seconds():.0f}s > {ACCEPT_TOKEN_TTL_SEC}s)",
        )
    # Step 2: execute FF-merge
    try:
        sha = ff_merge_to_main(kb_dir, g.draft_branch, push=push)
    except RuntimeError as e:
        return CommandResult(
            ok=False, exit_code=EXIT_GIT_ERROR,
            reply=(
                f"❌ {gap_id}: FF-merge falhou — {e}\n"
                f"Provável: main avançou desde draft. Rebase draft e re-tente."
            ),
        )
    update_gap(state, gap_id, status=GapStatus.ACCEPTED)
    _record_gap_decision(g, "accept")
    # F3 accept also records edit_distance via record_f3_accept (best-effort).
    if (g.path or "").startswith("30_adr/") or g.doc_type in (
        "adr", "prd", "architecture", "roadmap", "release-note"
    ):
        try:
            from lib.knowledge_watcher.feedback import record_f3_accept
            doc_full = kb_dir / g.path if g.path else None
            if doc_full and doc_full.is_file():
                record_f3_accept(
                    doc_path=g.path,
                    content_accepted=doc_full.read_text(encoding="utf-8"),
                )
        except Exception:
            pass
    del pending[gap_id]
    return CommandResult(
        ok=True,
        reply=(
            f"✅ {gap_id} accepted\n"
            f"FF-merged {g.draft_branch} -> main ({sha[:7]})"
        ),
    )
