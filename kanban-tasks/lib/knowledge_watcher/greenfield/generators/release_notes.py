"""release_notes.py — Tier MECÂNICO factual release notes per git tag."""
from __future__ import annotations

import re
import subprocess
from datetime import datetime, timezone
from typing import Dict, List

from lib.knowledge_watcher.greenfield import (
    DocGenResult, SourceSignals, Tier,
)


_PREFIX_RE = re.compile(r"^(\w+)[\(:]")
_VERSION_STRIP_V = re.compile(r"^v(\d+\.\d+(\.\d+)?)$")


def _strip_leading_v(tag: str) -> str:
    m = _VERSION_STRIP_V.match(tag)
    return m.group(1) if m else tag


def _list_commits(repo_root, tag: str, prev_tag: str | None) -> List[str]:
    """Return list of commit subjects in range. Empty list on git error."""
    if prev_tag:
        rev_range = f"{prev_tag}..{tag}"
        cmd = ["git", "log", rev_range, "--pretty=format:%s"]
    else:
        cmd = ["git", "log", tag, "--pretty=format:%s"]
    try:
        result = subprocess.run(
            cmd, cwd=repo_root, capture_output=True, text=True,
            check=True, timeout=10,
        )
    except (subprocess.CalledProcessError, FileNotFoundError, subprocess.TimeoutExpired):
        return []
    return [s.strip() for s in result.stdout.splitlines() if s.strip()]


def _group_by_prefix(subjects: List[str]) -> Dict[str, List[str]]:
    groups: Dict[str, List[str]] = {
        "breaking": [], "feat": [], "fix": [], "refactor": [], "misc": [],
    }
    for subject in subjects:
        if "BREAKING" in subject.upper():
            groups["breaking"].append(subject)
            continue
        m = _PREFIX_RE.match(subject)
        prefix = m.group(1).lower() if m else ""
        if prefix == "feat":
            groups["feat"].append(subject)
        elif prefix == "fix":
            groups["fix"].append(subject)
        elif prefix == "refactor":
            groups["refactor"].append(subject)
        elif prefix == "release":
            continue  # skip release commits themselves
        else:
            groups["misc"].append(subject)
    return groups


def _render_one_release(
    slug: str, tag: str, version: str, groups: Dict[str, List[str]],
    *, git_failed: bool = False,
) -> str:
    today = datetime.now(timezone.utc).date().isoformat()
    lines: List[str] = [
        "---",
        f"title: Release {version}",
        "status: Publicada",
        f"data: {today}",
        f"tag: {tag}",
        "generated-by: openclaw knowledge bootstrap-docs",
        "---",
        "",
        f"# Release {version} — {slug}",
        "",
        f"_Auto-generated factual release notes from git tag `{tag}`._",
        "",
    ]

    if git_failed:
        lines.append("Release notes not available (git log failed).")
        lines.append("")
    else:
        section_titles = {
            "breaking": "Breaking changes",
            "feat": "Features",
            "fix": "Fixes",
            "refactor": "Refactors",
            "misc": "Misc",
        }
        any_content = False
        for key in ("breaking", "feat", "fix", "refactor", "misc"):
            entries = groups.get(key, [])
            if not entries:
                continue
            any_content = True
            lines.append(f"## {section_titles[key]}")
            lines.append("")
            for s in entries:
                lines.append(f"- {s}")
            lines.append("")
        if not any_content:
            lines.append("_(no notable commits in range)_")
            lines.append("")

    lines.extend([
        "---",
        "",
        "> Auto-generated. Para detalhes, ver commits no repo.",
    ])
    return "\n".join(lines) + "\n"


def generate_release_notes(signals: SourceSignals) -> List[DocGenResult]:
    """Render factual release notes per git tag. Empty list if no tags."""
    if not signals.git_tags:
        return []

    # signals.git_tags is sorted by creatordate desc (per signals.py).
    # Reverse to chronological asc so prev_tag relationship is correct.
    tags_chrono = list(reversed(signals.git_tags))

    results: List[DocGenResult] = []
    for i, tag in enumerate(tags_chrono):
        prev_tag = tags_chrono[i - 1] if i > 0 else None
        version = _strip_leading_v(tag)
        subjects = _list_commits(signals.repo_root, tag, prev_tag)
        groups = _group_by_prefix(subjects)
        content = _render_one_release(
            signals.slug, tag, version, groups, git_failed=False,
        )
        warnings = []
        if not subjects:
            warnings.append(f"git log returned no commits for tag {tag}")
        results.append(DocGenResult(
            tier=Tier.MECANICO,
            doc_type="release-note",
            relative_path=f"50_releases/{signals.slug}/{version}.md",
            content=content,
            cost_usd=0.0,
            warnings=warnings,
        ))
    return results
