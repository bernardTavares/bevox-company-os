"""Tests for lib/cli/cmd_knowledge.py."""
import argparse
import io
from contextlib import redirect_stdout

import pytest

from lib.cli.cmd_knowledge import register_subcommand, EXIT_NOT_IMPLEMENTED, EXIT_OK


def _make_parser():
    """Build a minimal argparse with knowledge subcommand registered."""
    p = argparse.ArgumentParser()
    sub = p.add_subparsers(dest="cmd")
    knowledge = sub.add_parser("knowledge")
    knowledge_sub = knowledge.add_subparsers(dest="knowledge_cmd")

    def _leaf(parent, name):
        return parent.add_parser(name)

    register_subcommand(knowledge_sub, _leaf)
    return p


def test_knowledge_audit_subcommand_registered():
    """`knowledge audit` is parseable."""
    p = _make_parser()
    args = p.parse_args(["knowledge", "audit"])
    assert args.knowledge_cmd == "audit"


def test_knowledge_gap_report_subcommand_registered():
    """`knowledge gap-report` is parseable."""
    p = _make_parser()
    args = p.parse_args(["knowledge", "gap-report"])
    assert args.knowledge_cmd == "gap-report"


def test_knowledge_bootstrap_docs_subcommand_registered():
    """`knowledge bootstrap-docs` is parseable."""
    p = _make_parser()
    args = p.parse_args(["knowledge", "bootstrap-docs", "myslug"])
    assert args.knowledge_cmd == "bootstrap-docs"
    assert args.slug == "myslug"


def test_knowledge_retirement_scan_subcommand_registered():
    """`knowledge retirement-scan` is parseable."""
    p = _make_parser()
    args = p.parse_args(["knowledge", "retirement-scan"])
    assert args.knowledge_cmd == "retirement-scan"


def test_cmd_audit_stub_removed():
    """W0 stub deleted (no backcompat per CLAUDE.md)."""
    import lib.cli.cmd_knowledge as mod
    assert not hasattr(mod, "cmd_audit_stub")


def test_cmd_audit_returns_zero_on_empty_meta(tmp_path, monkeypatch):
    """audit on empty meta returns 0 + 'no opted-in' or empty results."""
    from lib.cli.cmd_knowledge import cmd_audit

    meta_path = tmp_path / "projects-meta.json"
    meta_path.write_text('{"version": 1, "projects": {}}')
    monkeypatch.setenv("OPENCLAW_DIR", str(tmp_path))
    monkeypatch.setenv("BEVOX_KNOWLEDGE_DIR", str(tmp_path / "kb"))
    monkeypatch.setenv("BEVOX_CODE_DIR", str(tmp_path / "code"))

    args = argparse.Namespace(repo=None, since=None, dry_run=False, json=False)
    buf = io.StringIO()
    with redirect_stdout(buf):
        rc = cmd_audit(args)
    assert rc == 0
    assert "no opted-in projects" in buf.getvalue().lower()


def test_cmd_audit_json_output_empty(tmp_path, monkeypatch):
    """audit --json on empty meta prints '[]'."""
    from lib.cli.cmd_knowledge import cmd_audit

    meta_path = tmp_path / "projects-meta.json"
    meta_path.write_text('{"version": 1, "projects": {}}')
    monkeypatch.setenv("OPENCLAW_DIR", str(tmp_path))
    monkeypatch.setenv("BEVOX_KNOWLEDGE_DIR", str(tmp_path / "kb"))
    monkeypatch.setenv("BEVOX_CODE_DIR", str(tmp_path / "code"))

    args = argparse.Namespace(repo=None, since=None, dry_run=False, json=True)
    buf = io.StringIO()
    with redirect_stdout(buf):
        rc = cmd_audit(args)
    assert rc == 0
    assert buf.getvalue().strip() == "[]"


def test_gap_report_returns_zero_on_empty_meta(tmp_path, monkeypatch):
    """gap-report on empty meta returns 0 (success, no gaps)."""
    from lib.cli.cmd_knowledge import cmd_gap_report

    meta_path = tmp_path / "projects-meta.json"
    meta_path.write_text('{"version": 1, "projects": {}}')
    monkeypatch.setenv("OPENCLAW_DIR", str(tmp_path))
    monkeypatch.setenv("BEVOX_KNOWLEDGE_DIR", str(tmp_path / "kb"))
    monkeypatch.setenv("BEVOX_CODE_DIR", str(tmp_path / "code"))

    args = argparse.Namespace(project=None, severity=None, json=False, all=False)
    buf = io.StringIO()
    with redirect_stdout(buf):
        rc = cmd_gap_report(args)
    assert rc == 0
    assert "no opted-in projects" in buf.getvalue().lower()


def test_cmd_bootstrap_docs_stub_removed():
    """W0 stub deleted (no backcompat per CLAUDE.md)."""
    import lib.cli.cmd_knowledge as mod
    assert not hasattr(mod, "cmd_bootstrap_docs_stub")


def test_cmd_bootstrap_docs_returns_zero_on_missing_repo(tmp_path, monkeypatch):
    """bootstrap-docs on missing repo prints skipped_reason + returns 0."""
    from lib.cli.cmd_knowledge import cmd_bootstrap_docs

    monkeypatch.setenv("BEVOX_KNOWLEDGE_DIR", str(tmp_path / "kb"))
    monkeypatch.setenv("BEVOX_CODE_DIR", str(tmp_path / "code"))

    args = argparse.Namespace(slug="missing", dry_run=True, no_adr=True, json=False)
    buf = io.StringIO()
    with redirect_stdout(buf):
        rc = cmd_bootstrap_docs(args)
    assert rc == 0
    assert "repo missing" in buf.getvalue().lower() or "skipped" in buf.getvalue().lower()


def test_cmd_bootstrap_docs_json_output(tmp_path, monkeypatch):
    """bootstrap-docs --json on missing repo prints valid JSON."""
    import json
    from lib.cli.cmd_knowledge import cmd_bootstrap_docs

    monkeypatch.setenv("BEVOX_KNOWLEDGE_DIR", str(tmp_path / "kb"))
    monkeypatch.setenv("BEVOX_CODE_DIR", str(tmp_path / "code"))

    args = argparse.Namespace(slug="missing", dry_run=True, no_adr=True, json=True)
    buf = io.StringIO()
    with redirect_stdout(buf):
        rc = cmd_bootstrap_docs(args)
    assert rc == 0
    data = json.loads(buf.getvalue())
    assert data["slug"] == "missing"
    assert data["skipped_reason"] is not None


def test_cmd_bootstrap_docs_dry_run_with_minimal_repo(tmp_path, monkeypatch):
    """bootstrap-docs --dry-run with empty git repo runs full pipeline (skipping LLM)."""
    import subprocess
    from lib.cli.cmd_knowledge import cmd_bootstrap_docs

    code = tmp_path / "code" / "myproj"
    code.mkdir(parents=True)
    subprocess.run(["git", "init", "-b", "main"], cwd=code, check=True, capture_output=True)
    subprocess.run(["git", "config", "user.email", "t@t.com"], cwd=code, check=True)
    subprocess.run(["git", "config", "user.name", "T"], cwd=code, check=True)
    (code / "f.txt").write_text("x")
    subprocess.run(["git", "add", "."], cwd=code, check=True)
    subprocess.run(["git", "commit", "-m", "feat: x"], cwd=code, check=True, capture_output=True)

    monkeypatch.setenv("BEVOX_KNOWLEDGE_DIR", str(tmp_path / "kb"))
    monkeypatch.setenv("BEVOX_CODE_DIR", str(tmp_path / "code"))

    args = argparse.Namespace(slug="myproj", dry_run=True, no_adr=True, json=False)
    buf = io.StringIO()
    with redirect_stdout(buf):
        rc = cmd_bootstrap_docs(args)
    assert rc == 0
    output = buf.getvalue()
    assert "knowledge bootstrap-docs myproj" in output
    assert "Total: $0.00" in output


def test_retirement_scan_returns_zero_on_empty_kb(tmp_path, monkeypatch):
    """retirement-scan on empty kb returns 0 + 'no retirement candidates' message."""
    from lib.cli.cmd_knowledge import cmd_retirement_scan

    monkeypatch.setenv("BEVOX_KNOWLEDGE_DIR", str(tmp_path / "kb"))
    monkeypatch.setenv("BEVOX_CODE_DIR", str(tmp_path / "code"))

    args = argparse.Namespace(project=None, json=False)
    buf = io.StringIO()
    with redirect_stdout(buf):
        rc = cmd_retirement_scan(args)
    assert rc == EXIT_OK
    assert "no retirement candidates" in buf.getvalue().lower()


def test_retirement_scan_json_output(tmp_path, monkeypatch):
    """retirement-scan --json on empty kb prints '[]'."""
    from lib.cli.cmd_knowledge import cmd_retirement_scan

    monkeypatch.setenv("BEVOX_KNOWLEDGE_DIR", str(tmp_path / "kb"))
    monkeypatch.setenv("BEVOX_CODE_DIR", str(tmp_path / "code"))

    args = argparse.Namespace(project=None, json=True)
    buf = io.StringIO()
    with redirect_stdout(buf):
        rc = cmd_retirement_scan(args)
    assert rc == EXIT_OK
    assert buf.getvalue().strip() == "[]"


def test_cmd_retirement_scan_stub_removed():
    """W0 stub deleted (no backcompat per CLAUDE.md)."""
    import lib.cli.cmd_knowledge as mod
    assert not hasattr(mod, "cmd_retirement_scan_stub")


# ---------------------------------------------------------------------------
# W3.5 — 7 action subcommand argparse tests
# ---------------------------------------------------------------------------

def _make_parser_ksub():
    """Build parser with knowledge_sub dest='ksub' to match subcommand name."""
    p = argparse.ArgumentParser()
    sub = p.add_subparsers(dest="cmd")
    knowledge = sub.add_parser("knowledge")
    knowledge_sub = knowledge.add_subparsers(dest="ksub")

    def leaf(s, n):
        return s.add_parser(n)

    register_subcommand(knowledge_sub, leaf)
    return p


def test_cmd_knowledge_subcommand_review_parses():
    """`knowledge review <gap-id>` is parseable."""
    p = _make_parser_ksub()
    args = p.parse_args(["knowledge", "review", "bevox-direct-aaa-spec"])
    assert args.ksub == "review"
    assert args.gap_id == "bevox-direct-aaa-spec"


def test_cmd_knowledge_subcommand_dismiss_parses():
    """`knowledge dismiss <gap-id>` is parseable."""
    p = _make_parser_ksub()
    args = p.parse_args(["knowledge", "dismiss", "bevox-direct-bbb-spec"])
    assert args.ksub == "dismiss"
    assert args.gap_id == "bevox-direct-bbb-spec"


def test_cmd_knowledge_subcommand_postpone_parses_days_int():
    """`knowledge postpone <gap-id> <days>` parses days as int."""
    p = _make_parser_ksub()
    args = p.parse_args(["knowledge", "postpone", "bevox-direct-aaa-spec", "7"])
    assert args.ksub == "postpone"
    assert args.gap_id == "bevox-direct-aaa-spec"
    assert args.days == 7
    assert isinstance(args.days, int)


def test_cmd_knowledge_subcommand_accept_optional_token_absent():
    """`knowledge accept <gap-id>` parses with token=None when omitted."""
    p = _make_parser_ksub()
    args = p.parse_args(["knowledge", "accept", "bevox-direct-aaa-spec"])
    assert args.ksub == "accept"
    assert args.gap_id == "bevox-direct-aaa-spec"
    assert args.token is None
    assert args.push is True


def test_cmd_knowledge_subcommand_accept_optional_token_present():
    """`knowledge accept <gap-id> <token>` parses token correctly."""
    p = _make_parser_ksub()
    args = p.parse_args(["knowledge", "accept", "bevox-direct-aaa-spec", "abc123"])
    assert args.ksub == "accept"
    assert args.token == "abc123"


def test_cmd_knowledge_subcommand_accept_no_push():
    """`knowledge accept <gap-id> --no-push` sets push=False."""
    p = _make_parser_ksub()
    args = p.parse_args(["knowledge", "accept", "bevox-direct-aaa-spec", "--no-push"])
    assert args.push is False


def test_cmd_knowledge_subcommand_retire_parses():
    """`knowledge retire <gap-id>` is parseable with push=True default."""
    p = _make_parser_ksub()
    args = p.parse_args(["knowledge", "retire", "bevox-direct-ccc-doc"])
    assert args.ksub == "retire"
    assert args.gap_id == "bevox-direct-ccc-doc"
    assert args.push is True


def test_cmd_knowledge_subcommand_retire_no_push():
    """`knowledge retire <gap-id> --no-push` sets push=False."""
    p = _make_parser_ksub()
    args = p.parse_args(["knowledge", "retire", "bevox-direct-ccc-doc", "--no-push"])
    assert args.push is False


def test_cmd_knowledge_subcommand_keep_parses():
    """`knowledge keep <gap-id>` is parseable."""
    p = _make_parser_ksub()
    args = p.parse_args(["knowledge", "keep", "bevox-direct-ddd-doc"])
    assert args.ksub == "keep"
    assert args.gap_id == "bevox-direct-ddd-doc"


def test_cmd_knowledge_subcommand_keep_permanent_parses():
    """`knowledge keep-permanent <gap-id>` is parseable with defaults."""
    p = _make_parser_ksub()
    args = p.parse_args(["knowledge", "keep-permanent", "bevox-direct-eee-doc"])
    assert args.ksub == "keep-permanent"
    assert args.gap_id == "bevox-direct-eee-doc"
    assert args.dry_run is False
    assert args.push is True


def test_cmd_knowledge_subcommand_keep_permanent_dry_run_no_push():
    """`knowledge keep-permanent <gap-id> --dry-run --no-push` sets flags correctly."""
    p = _make_parser_ksub()
    args = p.parse_args(
        ["knowledge", "keep-permanent", "bevox-direct-eee-doc", "--dry-run", "--no-push"]
    )
    assert args.dry_run is True
    assert args.push is False


def test_cmd_knowledge_subcommand_review_func_set():
    """`review` subcommand has func=cmd_review_cli set."""
    from lib.cli.cmd_knowledge import cmd_review_cli
    p = _make_parser_ksub()
    args = p.parse_args(["knowledge", "review", "some-gap"])
    assert args.func is cmd_review_cli


def test_cmd_knowledge_subcommand_dismiss_func_set():
    """`dismiss` subcommand has func=cmd_dismiss_cli set."""
    from lib.cli.cmd_knowledge import cmd_dismiss_cli
    p = _make_parser_ksub()
    args = p.parse_args(["knowledge", "dismiss", "some-gap"])
    assert args.func is cmd_dismiss_cli


def test_cmd_knowledge_subcommand_postpone_func_set():
    """`postpone` subcommand has func=cmd_postpone_cli set."""
    from lib.cli.cmd_knowledge import cmd_postpone_cli
    p = _make_parser_ksub()
    args = p.parse_args(["knowledge", "postpone", "some-gap", "14"])
    assert args.func is cmd_postpone_cli


def test_cmd_knowledge_subcommand_accept_func_set():
    """`accept` subcommand has func=cmd_accept_cli set."""
    from lib.cli.cmd_knowledge import cmd_accept_cli
    p = _make_parser_ksub()
    args = p.parse_args(["knowledge", "accept", "some-gap"])
    assert args.func is cmd_accept_cli


def test_cmd_knowledge_subcommand_retire_func_set():
    """`retire` subcommand has func=cmd_retire_cli set."""
    from lib.cli.cmd_knowledge import cmd_retire_cli
    p = _make_parser_ksub()
    args = p.parse_args(["knowledge", "retire", "some-gap"])
    assert args.func is cmd_retire_cli


def test_cmd_knowledge_subcommand_keep_func_set():
    """`keep` subcommand has func=cmd_keep_cli set."""
    from lib.cli.cmd_knowledge import cmd_keep_cli
    p = _make_parser_ksub()
    args = p.parse_args(["knowledge", "keep", "some-gap"])
    assert args.func is cmd_keep_cli


def test_cmd_knowledge_subcommand_keep_permanent_func_set():
    """`keep-permanent` subcommand has func=cmd_keep_permanent_cli set."""
    from lib.cli.cmd_knowledge import cmd_keep_permanent_cli
    p = _make_parser_ksub()
    args = p.parse_args(["knowledge", "keep-permanent", "some-gap"])
    assert args.func is cmd_keep_permanent_cli


def test_cmd_knowledge_existing_subcommands_still_work():
    """Original 4 subcommands (audit/gap-report/bootstrap-docs/retirement-scan) unaffected."""
    p = _make_parser_ksub()
    args_audit = p.parse_args(["knowledge", "audit"])
    assert args_audit.ksub == "audit"
    args_gap = p.parse_args(["knowledge", "gap-report"])
    assert args_gap.ksub == "gap-report"
    args_boot = p.parse_args(["knowledge", "bootstrap-docs", "myslug"])
    assert args_boot.ksub == "bootstrap-docs"
    assert args_boot.slug == "myslug"
    args_ret = p.parse_args(["knowledge", "retirement-scan"])
    assert args_ret.ksub == "retirement-scan"


# ---------------------------------------------------------------------------
# W5 — --force-topic flag on bootstrap-docs
# ---------------------------------------------------------------------------

def test_cmd_bootstrap_docs_accepts_force_topic_flag():
    """argparse aceita --force-topic repetido."""
    from lib.cli.cmd_knowledge import register_subcommand
    import argparse
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="cmd")
    knowledge = sub.add_parser("knowledge")
    knowledge_sub = knowledge.add_subparsers(dest="ksub")
    def leaf(s, n): return s.add_parser(n)
    register_subcommand(knowledge_sub, leaf)
    args = parser.parse_args([
        "knowledge", "bootstrap-docs", "myslug",
        "--force-topic", "stack-decisions",
        "--force-topic", "job-queue",
    ])
    assert args.slug == "myslug"
    assert args.force_topics == ["stack-decisions", "job-queue"]


def test_cmd_bootstrap_docs_force_topic_default_none():
    """Sem --force-topic, args.force_topics = None."""
    from lib.cli.cmd_knowledge import register_subcommand
    import argparse
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="cmd")
    knowledge = sub.add_parser("knowledge")
    knowledge_sub = knowledge.add_subparsers(dest="ksub")
    def leaf(s, n): return s.add_parser(n)
    register_subcommand(knowledge_sub, leaf)
    args = parser.parse_args(["knowledge", "bootstrap-docs", "myslug"])
    assert args.force_topics is None
