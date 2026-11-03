"""roadmap.py — Tier SEMI-AUTO roadmap generator (Haiku via classifier_llm reuse)."""
from __future__ import annotations

import json
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import List

from lib.knowledge_watcher.commit_watcher.classifier_llm import (
    _call_haiku, _check_budget, _record_usage,
    _HAIKU_INPUT_USD_PER_M, _HAIKU_OUTPUT_USD_PER_M,
)
from lib.knowledge_watcher.greenfield import (
    DocGenResult, SourceSignals, Tier,
)


def _recent_commit_subjects(repo_root: Path, limit: int = 50) -> List[str]:
    if not (repo_root / ".git").is_dir():
        return []
    try:
        result = subprocess.run(
            ["git", "log", f"-{limit}", "--pretty=format:%s"],
            cwd=repo_root, capture_output=True, text=True,
            check=True, timeout=10,
        )
    except (subprocess.CalledProcessError, FileNotFoundError, subprocess.TimeoutExpired):
        return []
    return [s.strip() for s in result.stdout.splitlines() if s.strip()]


def _gh_pr_labels(repo_root: Path, limit: int = 50) -> List[str]:
    """Best-effort: top frequent PR labels via gh CLI. Empty list on any failure."""
    try:
        result = subprocess.run(
            ["gh", "pr", "list", "--state", "all", "--limit", str(limit), "--json", "labels"],
            cwd=repo_root, capture_output=True, text=True,
            check=True, timeout=10,
        )
    except (subprocess.CalledProcessError, FileNotFoundError, subprocess.TimeoutExpired):
        return []
    try:
        prs = json.loads(result.stdout or "[]")
    except json.JSONDecodeError:
        return []
    counts: dict[str, int] = {}
    for pr in prs:
        for lbl in pr.get("labels", []):
            name = lbl.get("name") if isinstance(lbl, dict) else None
            if name:
                counts[name] = counts.get(name, 0) + 1
    sorted_labels = sorted(counts.items(), key=lambda x: x[1], reverse=True)
    return [n for n, _ in sorted_labels[:5]]


def _build_prompt(signals: SourceSignals, commit_subjects: List[str], labels: List[str]) -> str:
    framework_hint = ""
    for dep in ("express", "fastify", "@nestjs/core", "next", "react"):
        if dep in signals.deps:
            framework_hint = dep
            break
    has_ts = any(k.startswith("@types/") or k == "typescript" for k in signals.deps)
    language = "TypeScript" if has_ts else ("Node.js" if signals.deps else "unknown")

    commits_block = "\n".join(f"- {s}" for s in commit_subjects[:50]) or "(no commits)"
    labels_str = ", ".join(labels) if labels else "n/a"

    return f"""Você é um roadmap planner. Gere um roadmap de 3 trimestres (Q1/Q2/Q3) baseado nos themes recentes de commits e tech stack abaixo. NÃO invente milestones — derive de evidência. Status do roadmap: "Draft" — review humano obrigatório.

Slug: {signals.slug}

Recent commit subjects (last 50):
{commits_block}

Tech stack: {language}, framework: {framework_hint or 'n/a'}, services count: {signals.services_count}

PR labels recentes (se disponível): {labels_str}

Output markdown apenas, em PT-BR, estrutura:

# {signals.slug} — Roadmap

## Visão estratégica
<1-2 frases sobre direção projeto, derivada dos themes>

## Q1 (próximo trimestre)
- <2-4 milestones derivados>

## Q2
- <2-4 milestones derivados>

## Q3
- <2-4 milestones derivados>

## Risks / dependências
<se themes mostram blockers ou tech debt; senão omita>

NÃO invente features sem evidência. Se commits não mostram pattern, escreva "Themes não suficientemente claros pra roadmap" naquela seção. NÃO use code fences.
"""


def _strip_code_fence(text: str) -> str:
    text = text.strip()
    if text.startswith("```"):
        lines = text.splitlines()
        if lines and lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].startswith("```"):
            lines = lines[:-1]
        return "\n".join(lines).strip()
    return text


def _wrap_with_frontmatter(slug: str, body: str) -> str:
    today = datetime.now(timezone.utc).date().isoformat()
    return (
        "---\n"
        f"title: Roadmap — {slug}\n"
        "status: Draft\n"
        f"data: {today}\n"
        "generated-by: openclaw knowledge bootstrap-docs (Tier SEMI-AUTO, Haiku)\n"
        "---\n"
        "\n"
        f"{body}\n"
        "\n---\n"
        "\n> Auto-generated draft. Review humano obrigatório antes de Status: Aceita.\n"
    )


def generate_roadmap(
    signals: SourceSignals, *, state_path: Path, budget_usd: float = 5.0,
) -> DocGenResult:
    """Generate roadmap draft via Haiku. Skip if no git history or budget exceeded."""
    today = datetime.now(timezone.utc).date().isoformat()
    relative_path = f"40_roadmap/{signals.slug}/{today}-{signals.slug}-roadmap.md"
    base_result = DocGenResult(
        tier=Tier.SEMI_AUTO,
        doc_type="roadmap",
        relative_path=relative_path,
        content="",
        cost_usd=0.0,
        warnings=[],
    )

    commit_subjects = _recent_commit_subjects(signals.repo_root)
    if not commit_subjects:
        base_result.warnings.append("no git history to derive roadmap themes")
        return base_result

    if not _check_budget(state_path, budget_usd):
        base_result.warnings.append("LLM budget exceeded for month")
        return base_result

    labels = _gh_pr_labels(signals.repo_root)

    prompt = _build_prompt(signals, commit_subjects, labels)
    try:
        resp = _call_haiku(prompt)
    except Exception as e:
        base_result.warnings.append(
            f"LLM call failed: {type(e).__name__}: {str(e)[:200]}"
        )
        return base_result

    try:
        body_raw = resp.content[0].text
        in_tok = resp.usage.input_tokens
        out_tok = resp.usage.output_tokens
    except (AttributeError, IndexError):
        base_result.warnings.append("LLM response malformed")
        return base_result

    _record_usage(state_path, in_tok, out_tok)
    body = _strip_code_fence(body_raw)
    cost = round(
        in_tok / 1_000_000 * _HAIKU_INPUT_USD_PER_M
        + out_tok / 1_000_000 * _HAIKU_OUTPUT_USD_PER_M,
        6,
    )

    return DocGenResult(
        tier=Tier.SEMI_AUTO,
        doc_type="roadmap",
        relative_path=relative_path,
        content=_wrap_with_frontmatter(signals.slug, body),
        cost_usd=cost,
        warnings=[],
    )
