"""CLI clarification-agent."""

import argparse
import json
import sys
import time
from typing import Any, Optional

from . import drafter as drafter_lib
from . import lifecycle as lifecycle_lib
from . import poller as poller_lib
from . import store

EXIT_OK = 0
EXIT_INPUT = 1
EXIT_STATE = 2
EXIT_PROPOSES_REJECTION = 3
EXIT_REJECTED_TASK = 4

VALID_REJECT_CATEGORIES = {
    "task_malformed", "spec_inconsistent", "requires_re_decomposition",
    "inexecutable", "manual",
}

_EXIT_BY_CODE = {
    "KANBAN_CLI_TIMEOUT": EXIT_STATE,
    "KANBAN_CLI_FAILED": EXIT_STATE,
    "KANBAN_CLI_BAD_JSON": EXIT_STATE,
    "TASK_NOT_FOUND": EXIT_INPUT,
    "CLAUDE_SUBPROCESS_FAILED": EXIT_STATE,
    "CLAUDE_EXIT_NONZERO": EXIT_STATE,
    "PARSE_NO_JSON": EXIT_STATE,
    "PARSE_JSON_INVALID": EXIT_STATE,
    "PARSE_MISSING_FIELD": EXIT_STATE,
    "INVALID_REJECT_CATEGORY": EXIT_INPUT,
    "CLARIFICATION_NOT_FOUND": EXIT_INPUT,
    "QUESTION_FILE_READ_FAILED": EXIT_INPUT,
}


def _err(msg: str, code: str, json_mode: bool) -> int:
    if json_mode:
        print(json.dumps({"ok": False, "error": msg, "code": code}))
    else:
        print(f"ERROR ({code}): {msg}", file=sys.stderr)
    return _EXIT_BY_CODE.get(code, EXIT_STATE)


def _print(payload: Any, json_mode: bool, human: Optional[str] = None) -> None:
    if json_mode:
        print(json.dumps(payload, ensure_ascii=False, indent=2))
    else:
        if human is not None:
            print(human)
        else:
            print(json.dumps(payload, ensure_ascii=False, indent=2))


def cmd_answer(args: argparse.Namespace) -> int:
    """Processar resposta de Bernard a uma clarification."""
    from . import reply_handler

    clarification_id = args.clarification_id
    reply_text = args.answer

    try:
        success = reply_handler.handle_reply(clarification_id, reply_text)
        if success:
            if args.json:
                print(json.dumps({"ok": True, "clarification_id": clarification_id, "status": "resolved"}))
            else:
                print(f"✅ Clarification {clarification_id} resolvida!")
            return EXIT_OK
        else:
            return _err("Falha ao processar resposta", "ANSWER_FAILED", args.json)
    except Exception as e:
        return _err(str(e), "ANSWER_EXCEPTION", args.json)


def cmd_ask(args: argparse.Namespace) -> int:
    if args.question_file:
        try:
            with open(args.question_file, "r", encoding="utf-8") as f:
                question = f.read().strip()
        except OSError as e:
            return _err(str(e), "QUESTION_FILE_READ_FAILED", args.json)
    else:
        question = args.question or ""
        if not question.strip():
            return _err(
                "--question ou --question-file obrigatorio",
                "invalid_input", args.json,
            )

    try:
        result = lifecycle_lib.ask_and_draft(
            args.task_id, question, model=args.model,
        )
    except (lifecycle_lib.LifecycleError, drafter_lib.DrafterError) as e:
        return _err(e.detail, e.code, args.json)

    cid = result["clarification_id"]
    outcome = result["outcome"]

    if not args.and_wait:
        _print(result, args.json,
               f"clarification {cid}: {outcome}\n"
               f"  question: {result['question_path']}\n"
               f"  answer:   {result['answer_path']}")
        return EXIT_OK

    if outcome == "safe":
        _print({"answer": result["answer_text"], "confidence": "safe",
                "sources_path": result["answer_path"]},
               args.json, result["answer_text"])
        return EXIT_OK

    # Unsafe: poll loop
    try:
        while True:
            sig = store.read_signal(cid)
            if sig:
                break
            time.sleep(5)
    except KeyboardInterrupt:
        return _err(
            "canceled by SIGTERM/SIGINT during --and-wait",
            "SIGTERM_CANCELED", args.json,
        )

    if sig.get("outcome") in ("safe", "override"):
        ans_path = store.ANSWERS_DIR / f"{cid}.md"
        if sig.get("outcome") == "override":
            ov = store.ANSWERS_DIR / f"{cid}-override.md"
            if ov.exists():
                ans_path = ov
        try:
            content = ans_path.read_text(encoding="utf-8")
        except OSError:
            content = "(answer file unavailable)"
        _print({"answer_file_content": content, "outcome": sig["outcome"]},
               args.json, content)
        return EXIT_OK
    if sig.get("outcome") == "rejected":
        _print({"outcome": "rejected"}, args.json,
               "CLARIFICATION_REJECTED_TASK: task foi movida para rejected")
        return EXIT_REJECTED_TASK
    return _err(f"outcome desconhecido: {sig}", "INVALID_SIGNAL", args.json)


def cmd_escalations(args: argparse.Namespace) -> int:
    escalations = store.list_escalations()
    if args.json:
        _print({"escalations": escalations}, True)
        return EXIT_OK
    if not escalations:
        print("(nenhuma escalation pending)")
        return EXIT_OK
    print("CLARIFICATION_ID                           ESCALATION_PATH")
    for e in escalations:
        print(f"{e['clarification_id']:42s} {e['escalation_path']}")
    return EXIT_OK


def cmd_show(args: argparse.Namespace) -> int:
    target = args.target
    if "-clr-" not in target:
        import re
        pat = re.compile(re.escape(target) + r"-clr-\d+\.md$")
        if not store.QUESTIONS_DIR.exists():
            return _err(
                f"nenhuma clarification pra {target}",
                "CLARIFICATION_NOT_FOUND", args.json,
            )
        matches = sorted([p.stem for p in store.QUESTIONS_DIR.iterdir()
                          if pat.match(p.name)])
        if not matches:
            return _err(
                f"nenhuma clarification pra {target}",
                "CLARIFICATION_NOT_FOUND", args.json,
            )
        if args.json:
            _print({"clarification_ids": matches}, True)
            return EXIT_OK
        print(f"clarifications for {target}:")
        for cid in matches:
            print(f"  {cid}")
        return EXIT_OK

    cid = target
    qpath = store.QUESTIONS_DIR / f"{cid}.md"
    apath = store.ANSWERS_DIR / f"{cid}.md"
    if not qpath.exists():
        return _err(
            f"question {cid} nao existe", "CLARIFICATION_NOT_FOUND", args.json,
        )
    q_content = qpath.read_text(encoding="utf-8")
    a_content = apath.read_text(encoding="utf-8") if apath.exists() else "(answer pending)"
    if args.json:
        _print({"clarification_id": cid, "question": q_content,
                "answer": a_content}, True)
        return EXIT_OK
    print(f"=== {cid} — QUESTION ===\n{q_content}\n")
    print(f"=== {cid} — ANSWER ===\n{a_content}")
    return EXIT_OK


def cmd_override(args: argparse.Namespace) -> int:
    import re
    pat = re.compile(re.escape(args.task_id) + r"-clr-(\d+)\.md$")
    max_seq = 0
    latest_cid = None
    if store.QUESTIONS_DIR.exists():
        for p in store.QUESTIONS_DIR.iterdir():
            m = pat.match(p.name)
            if m and int(m.group(1)) > max_seq:
                max_seq = int(m.group(1))
                latest_cid = p.stem
    if latest_cid is None:
        return _err(
            f"nenhuma clarification pending pra {args.task_id}",
            "CLARIFICATION_NOT_FOUND", args.json,
        )

    override_path = store.ANSWERS_DIR / f"{latest_cid}-override.md"
    body = f"""# Clarification override — {latest_cid}

**Overridden by:** bernard
**Overridden at:** {store.now_iso()}
**Confidence:** manual_override (human-authored)

---

## Answer

{args.answer}
"""
    store._atomic_write(override_path, body)

    try:
        lifecycle_lib.unblock(args.task_id)
        lifecycle_lib.merge_dispatch_payload(args.task_id, {
            "last_clarification_confidence": "manual_override",
            "last_clarification_override_path": str(override_path),
            "last_clarification_resolved_at": store.now_iso(),
        })
    except lifecycle_lib.LifecycleError as e:
        return _err(e.detail, e.code, args.json)

    store.emit_signal(latest_cid, "override")
    store.clear_escalation_symlink(latest_cid)

    # Schema v2: mark notifier-state entry resolved + route confirmation
    # via entry.token_alias (Tasks 6-7 of clarification-reply-via-gateway-plugin).
    # Best-effort: doesn't fail the command if state write or confirmation fails.
    try:
        from . import reply_handler
        state_path = store.ROOT / "notifier-state.json"
        state = store.load_state_v2(state_path)
        entry = state.get("notifications", {}).get(latest_cid)
        if entry is not None and entry.get("status") != "resolved":
            updated = dict(entry)
            updated["status"] = "resolved"
            updated["resolved_at"] = store.now_iso()
            updated["resolved_via"] = "slash_command"
            state["notifications"][latest_cid] = updated
            store.save_state_v2(state_path, state)
        reply_handler.send_confirmation_message(latest_cid, args.task_id)
    except Exception as e:
        print(f"⚠️ Falha ao atualizar notifier-state ou enviar confirmação: {e}")

    _print({"ok": True, "clarification_id": latest_cid,
            "override_path": str(override_path)},
           args.json,
           f"override committed: {latest_cid}\n  unblocked {args.task_id}")
    return EXIT_OK


def cmd_reject_task(args: argparse.Namespace) -> int:
    parts = args.reason.split(":", 1)
    if not parts or parts[0].strip() not in VALID_REJECT_CATEGORIES:
        return _err(
            f"categoria invalida. Use '<cat>: <detail>' com cat em "
            f"{sorted(VALID_REJECT_CATEGORIES)}",
            "INVALID_REJECT_CATEGORY", args.json,
        )
    try:
        lifecycle_lib.reject_task(args.task_id, args.reason)
    except lifecycle_lib.LifecycleError as e:
        return _err(e.detail, e.code, args.json)

    import re
    pat = re.compile(re.escape(args.task_id) + r"-clr-(\d+)\.md$")
    latest_cid = None
    max_seq = 0
    if store.QUESTIONS_DIR.exists():
        for p in store.QUESTIONS_DIR.iterdir():
            m = pat.match(p.name)
            if m and int(m.group(1)) > max_seq:
                max_seq = int(m.group(1))
                latest_cid = p.stem
    if latest_cid:
        store.emit_signal(latest_cid, "rejected")
        store.clear_escalation_symlink(latest_cid)

    _print({"ok": True, "task_id": args.task_id, "reason": args.reason},
           args.json,
           f"rejected: {args.task_id} (reason: {args.reason})")
    return EXIT_OK


def cmd_redraft(args: argparse.Namespace) -> int:
    import re
    pat = re.compile(re.escape(args.task_id) + r"-clr-(\d+)\.md$")
    max_seq = 0
    latest_cid = None
    for p in store.QUESTIONS_DIR.iterdir():
        m = pat.match(p.name)
        if m and int(m.group(1)) > max_seq:
            max_seq = int(m.group(1))
            latest_cid = p.stem
    if latest_cid is None:
        return _err(
            f"nenhuma clarification pra {args.task_id}",
            "CLARIFICATION_NOT_FOUND", args.json,
        )
    qpath = store.QUESTIONS_DIR / f"{latest_cid}.md"
    content = qpath.read_text(encoding="utf-8")
    idx = content.find("\n---\n\n")
    question = content[idx + 6:].strip() if idx >= 0 else content
    store.clear_escalation_symlink(latest_cid)
    try:
        result = lifecycle_lib.ask_and_draft(
            args.task_id, question, model=args.model,
        )
    except (lifecycle_lib.LifecycleError, drafter_lib.DrafterError) as e:
        return _err(e.detail, e.code, args.json)
    _print(result, args.json,
           f"redraft {result['clarification_id']}: {result['outcome']}")
    return EXIT_OK


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
    if not store.POLL_JSONL.exists():
        _print({"ticks": 0, "last_tick": None}, args.json,
               "(nenhum tick registrado ainda)")
        return EXIT_OK
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


def build_parser() -> argparse.ArgumentParser:
    common = argparse.ArgumentParser(add_help=False)
    common.add_argument("--json", action="store_true")
    common.add_argument("--actor", default="clarification")

    p = argparse.ArgumentParser(prog="clarification-agent")
    sub = p.add_subparsers(dest="cmd", required=True)
    def leaf(psub, name):
        return psub.add_parser(name, parents=[common])

    ak = leaf(sub, "ask")
    ak.add_argument("task_id")
    ak.add_argument("--question", default=None)
    ak.add_argument("--question-file", default=None)
    ak.add_argument("--and-wait", action="store_true")
    ak.add_argument("--model", default="claude-haiku-4-5")
    ak.set_defaults(func=cmd_ask)

    # Comando answer: processar resposta de Bernard
    ans = leaf(sub, "answer")
    ans.add_argument("clarification_id", help="ID da clarification (ex: T-0024-clr-4)")
    ans.add_argument("--answer", required=True, help="Resposta de Bernard")
    ans.set_defaults(func=cmd_answer)

    es = leaf(sub, "escalations")
    es.set_defaults(func=cmd_escalations)

    sh = leaf(sub, "show")
    sh.add_argument("target", help="task-id ou clarification-id")
    sh.set_defaults(func=cmd_show)

    ov = leaf(sub, "override")
    ov.add_argument("task_id")
    ov.add_argument("--answer", required=True)
    ov.add_argument("--commit", action="store_true")
    ov.set_defaults(func=cmd_override)

    rj = leaf(sub, "reject-task")
    rj.add_argument("task_id")
    rj.add_argument("--reason", required=True)
    rj.add_argument("--commit", action="store_true")
    rj.set_defaults(func=cmd_reject_task)

    rd = leaf(sub, "redraft")
    rd.add_argument("task_id")
    rd.add_argument("--model", default="claude-haiku-4-5")
    rd.set_defaults(func=cmd_redraft)

    pt = leaf(sub, "poll-tick")
    pt.add_argument("--once", action="store_true", default=True)
    pt.add_argument("--dry-run", action="store_true")
    pt.set_defaults(func=cmd_poll_tick)

    ps = leaf(sub, "poll-status")
    ps.set_defaults(func=cmd_poll_status)

    return p


def main(argv=None) -> int:
    p = build_parser()
    args = p.parse_args(argv)
    if args.cmd in ("override", "reject-task") and not getattr(args, "commit", False):
        print("ERROR: --commit obrigatorio pra aplicar (gate humano)",
              file=sys.stderr)
        return EXIT_INPUT
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
