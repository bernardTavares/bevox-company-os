"""prd.py — Tier SEMI-AUTO PRD generator (Haiku via classifier_llm reuse)."""
from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

from lib.knowledge_watcher.commit_watcher.classifier_llm import (
    _call_haiku, _check_budget, _record_usage,
    _HAIKU_INPUT_USD_PER_M, _HAIKU_OUTPUT_USD_PER_M,
)
from lib.knowledge_watcher.greenfield import (
    DocGenResult, SourceSignals, Tier,
)


def _build_prompt(signals: SourceSignals) -> str:
    framework_hint = ""
    for dep in ("express", "fastify", "@nestjs/core", "next", "react"):
        if dep in signals.deps:
            framework_hint = dep
            break
    has_ts = any(k.startswith("@types/") or k == "typescript" for k in signals.deps)
    language = "TypeScript" if has_ts else ("Node.js" if signals.deps else "unknown")
    top_models = ", ".join(signals.schema_models[:5]) if signals.schema_models else "n/a"

    return f"""Você é um analista de produto. Gere um PRD curto (200-400 palavras) baseado nos sinais factuais abaixo. NÃO invente features que não estão evidenciadas no input — se não souber, omita a seção. Status do PRD será "Draft (greenfield bootstrap)" — review humano obrigatório.

Slug: {signals.slug}

README excerpt:
{signals.readme_text[:3000]}

CLAUDE.md excerpt:
{signals.claude_md_text[:1500]}

Tech stack hint: {language}, framework: {framework_hint or 'n/a'}, schema models: {top_models}, services count: {signals.services_count}

Output markdown apenas, em PT-BR. Estrutura:

# {signals.slug} — PRD

## Visão de uma linha
<1 frase derivada de README/CLAUDE>

## Problema
<problema que o projeto resolve, derivado do README>

## Objetivos
- <3-5 bullets, factuais derivados do código/docs>

## Métricas de sucesso
<se README/CLAUDE não menciona métricas, omita esta seção>

## Out-of-scope
<o que README/CLAUDE EXPLICITAMENTE excluem; se nada explícito, omita>

NÃO escreva preâmbulo, apenas o markdown final. NÃO use code fences.
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
        f"title: PRD — {slug}\n"
        "status: Draft (greenfield bootstrap)\n"
        f"data: {today}\n"
        "generated-by: openclaw knowledge bootstrap-docs (Tier SEMI-AUTO, Haiku)\n"
        "---\n"
        "\n"
        f"{body}\n"
        "\n---\n"
        "\n> Auto-generated draft. Review humano obrigatório antes de Status: Aceita.\n"
    )


def generate_prd(
    signals: SourceSignals, *, state_path: Path, budget_usd: float = 5.0,
) -> DocGenResult:
    """Generate PRD draft via Haiku. Skip if no source or budget exceeded."""
    relative_path = (
        f"10_prd/{signals.slug}/"
        f"{datetime.now(timezone.utc).date().isoformat()}-{signals.slug}-prd.md"
    )
    base_result = DocGenResult(
        tier=Tier.SEMI_AUTO,
        doc_type="prd",
        relative_path=relative_path,
        content="",
        cost_usd=0.0,
        warnings=[],
    )

    if not signals.has_readme and not signals.has_claude_md:
        base_result.warnings.append("no README or CLAUDE.md to derive PRD from")
        return base_result

    if not _check_budget(state_path, budget_usd):
        base_result.warnings.append("LLM budget exceeded for month")
        return base_result

    prompt = _build_prompt(signals)
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
        doc_type="prd",
        relative_path=relative_path,
        content=_wrap_with_frontmatter(signals.slug, body),
        cost_usd=cost,
        warnings=[],
    )
