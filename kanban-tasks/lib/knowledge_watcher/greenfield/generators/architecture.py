"""architecture.py — Tier MECÂNICO factual system overview."""
from __future__ import annotations

from datetime import datetime, timezone
from typing import List

from lib.knowledge_watcher.greenfield import (
    DocGenResult, SourceSignals, Tier,
)


_FRAMEWORK_DEPS = {
    "express": "Express",
    "fastify": "Fastify",
    "@nestjs/core": "NestJS",
    "next": "Next.js",
    "react": "React (frontend)",
}


def _derive_language(signals: SourceSignals) -> str:
    has_ts = any(k.startswith("@types/") or k == "typescript" for k in signals.deps)
    has_py_services = any(s.endswith(".py") for s in signals.main_services)
    if has_ts:
        return "TypeScript / Node.js"
    if has_py_services and not signals.deps:
        return "Python"
    if signals.deps:
        return "JavaScript / Node.js"
    return "Node.js"


def _derive_framework(signals: SourceSignals) -> str:
    for dep, name in _FRAMEWORK_DEPS.items():
        if dep in signals.deps:
            return name
    return ""


def _derive_queue(signals: SourceSignals) -> str:
    if "pg-boss" in signals.deps:
        return "pg-boss"
    if "bullmq" in signals.deps or "bull" in signals.deps:
        return "BullMQ"
    return ""


def _render_top_deps(deps: dict, n: int = 10) -> List[str]:
    if not deps:
        return ["| _(no dependencies detected)_ | |"]
    lines: List[str] = []
    for name, ver in sorted(deps.items())[:n]:
        lines.append(f"| `{name}` | `{ver}` |")
    return lines


def generate_architecture(signals: SourceSignals) -> DocGenResult:
    """Render factual architecture overview from SourceSignals."""
    today = datetime.now(timezone.utc).date().isoformat()
    lines: List[str] = [
        f"# System overview — {signals.slug}",
        "",
        "**Status:** Aceita",
        f"**Data:** {today}",
        "**Origem:** Auto-generated factual snapshot via `openclaw knowledge bootstrap-docs`",
        f"**Source:** signals extraídos em {today} de `{signals.repo_root}`",
        "",
        "---",
        "",
        "## Tech stack",
        "",
        f"- **Language/runtime:** {_derive_language(signals)}",
    ]

    framework = _derive_framework(signals)
    if framework:
        lines.append(f"- **Framework:** {framework}")
    if signals.has_schema_prisma:
        lines.append("- **Database:** Postgres via Prisma")
    queue = _derive_queue(signals)
    if queue:
        lines.append(f"- **Job queue:** {queue}")
    if signals.has_auth_middleware:
        lines.append("- **Auth:** Custom middleware @ apps/api/middleware/auth/")

    lines.extend(["", "## Schema models (Prisma)", ""])
    if signals.schema_models:
        for m in signals.schema_models:
            lines.append(f"- `{m}`")
    else:
        lines.append("Schema not detected.")

    lines.extend(["", "## Top-level dependencies", "", "| Package | Version |", "|---|---|"])
    lines.extend(_render_top_deps(signals.deps))

    lines.extend(["", "## Main services", ""])
    if signals.main_services:
        for s in signals.main_services[:20]:
            lines.append(f"- `{s}`")
    else:
        lines.append("Services not detected. Repo may follow different layout.")

    lines.extend(["", "## Environment variables (detected)", ""])
    if signals.env_vars:
        for v in signals.env_vars[:30]:
            lines.append(f"- `{v}`")
    else:
        lines.append("No env vars detected.")

    lines.extend([
        "",
        "---",
        "",
        "> Auto-generated factual document. Human review optional but encouraged.",
    ])

    content = "\n".join(lines) + "\n"

    return DocGenResult(
        tier=Tier.MECANICO,
        doc_type="architecture",
        relative_path=f"20_architecture/{signals.slug}/system-overview.md",
        content=content,
        cost_usd=0.0,
        warnings=[],
    )
