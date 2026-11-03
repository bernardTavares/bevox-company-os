"""release_note.py — Strategy DRAFT_FILLED for release-note doc-type."""
from __future__ import annotations

import re
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Tuple

from lib.knowledge_watcher.commit_watcher import (
    ClassifierResult, Commit, GapDraft, Strategy,
)

_VERSION_RE = re.compile(r"v(\d+\.\d+\.\d+)")


def _extract_version(subject: str) -> str:
    m = _VERSION_RE.search(subject)
    return m.group(1) if m else datetime.now(timezone.utc).strftime("%Y.%m.%d")


def _list_release_commits(repo_root: Path, release_sha: str) -> List[Tuple[str, str]]:
    """Get all commits up to release_sha. Return list of (prefix, full_subject)."""
    try:
        out = subprocess.run(
            ["git", "log", release_sha, "-50", "--pretty=format:%s"],
            cwd=repo_root, capture_output=True, text=True, check=True,
        )
    except (subprocess.CalledProcessError, FileNotFoundError):
        return []
    pairs = []
    for line in out.stdout.splitlines():
        line = line.strip()
        if not line:
            continue
        m = re.match(r"^(\w+)[\(:]", line)
        if m:
            pairs.append((m.group(1).lower(), line))
        else:
            pairs.append(("misc", line))
    return pairs


def apply_release_note_strategy(
    *, commit: Commit, classifier_result: ClassifierResult,
    repo_root: Path, slug: str, kb_root: Path, dry_run: bool = False,
) -> GapDraft:
    version = _extract_version(commit.subject)
    pairs = _list_release_commits(repo_root, commit.sha)

    groups = {"feat": [], "fix": [], "refactor": [], "breaking": []}
    for prefix, full in pairs:
        if prefix == "release":
            continue
        bucket = "breaking" if "BREAKING" in full else prefix
        groups.setdefault(bucket, []).append(full)

    today = datetime.now(timezone.utc).date().isoformat()
    lines = [
        "---",
        f"title: Release {version} — {slug}",
        "status: Proposta",
        f"data: {today}",
        f"source-commit: {commit.short_sha}",
        "generated-by: openclaw knowledge audit",
        "---",
        "",
        f"# Release {version} — {slug}",
        "",
        f"_Auto-generated draft from commit `{commit.short_sha}` ({commit.timestamp_iso[:10]})._",
        "",
    ]

    if groups.get("breaking"):
        lines.append("## Breaking changes")
        lines.append("")
        for c in groups["breaking"]:
            lines.append(f"- {c}")
        lines.append("")
    if groups.get("feat"):
        lines.append("## Features")
        lines.append("")
        for c in groups["feat"]:
            lines.append(f"- {c}")
        lines.append("")
    if groups.get("fix"):
        lines.append("## Fixes")
        lines.append("")
        for c in groups["fix"]:
            lines.append(f"- {c}")
        lines.append("")
    if groups.get("refactor"):
        lines.append("## Refactors")
        lines.append("")
        for c in groups["refactor"]:
            lines.append(f"- {c}")
        lines.append("")

    lines.append("---")
    lines.append("")
    lines.append("> Review humano obrigatório. `/accept <id>` faz FF-merge da draft em main.")

    body = "\n".join(lines) + "\n"

    target = kb_root / "50_releases" / slug / f"{version}.md"
    if not dry_run:
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(body)

    rel = str(target.relative_to(kb_root))
    branch = f"draft/auto/{today}-{commit.short_sha}-release-note"
    return GapDraft(
        project_slug=slug, commit=commit, classifier_result=classifier_result,
        strategy=Strategy.DRAFT_FILLED, draft_branch=branch,
        draft_file_relative=rel,
        gaps_entry=f"- [ ] [{commit.short_sha}] release-note: {commit.subject} (filled draft) — /accept | /review | /dismiss",
        digest_line=f"release: {version} → release-note draft-filled (confidence: {classifier_result.confidence:.2f}, {classifier_result.source.value})",
    )
