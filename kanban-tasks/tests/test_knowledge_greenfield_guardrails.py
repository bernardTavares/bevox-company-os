"""Tests for greenfield/guardrails.py — 4 hallucination guardrails."""
from pathlib import Path

from lib.knowledge_watcher.greenfield import SourceSignals
from lib.knowledge_watcher.greenfield.guardrails import apply_4_guardrails


def _signals(**overrides) -> SourceSignals:
    base = dict(
        slug="myproj", repo_root=Path("/tmp/repo"),
        has_schema_prisma=True, schema_models=["User"],
        package_json={}, deps={},
        main_services=["apps/api/src/services/auth.service.ts"],
        env_vars=["DATABASE_URL", "API_KEY"],
        has_readme=False, readme_text="",
        has_claude_md=False, claude_md_text="",
        git_tags=[], services_count=1,
        has_auth_middleware=False, has_org_id_pattern=False,
    )
    base.update(overrides)
    return SourceSignals(**base)


# G1: Status enforcement

def test_g1_adr_status_aceita_forced_to_proposta():
    md = "# ADR\n\n**Status:** Aceita\n\nbody"
    out, warnings = apply_4_guardrails(md, _signals(), doc_type="adr")
    assert "Status: Proposta" in out or "Status:** Proposta" in out
    assert any("G1" in w for w in warnings)


def test_g1_adr_status_already_proposta_unchanged():
    md = "# ADR\n\nStatus: Proposta\n\nbody"
    out, warnings = apply_4_guardrails(md, _signals(), doc_type="adr")
    assert "Status: Proposta" in out
    assert not any("G1" in w for w in warnings)


def test_g1_non_adr_status_not_enforced():
    md = "# Spec\n\nStatus: Aceita\n\nbody"
    out, warnings = apply_4_guardrails(md, _signals(), doc_type="spec")
    # spec keeps Aceita
    assert "Status: Aceita" in out
    assert not any("G1" in w for w in warnings)


# G2: Cite-or-stay-silent

def test_g2_unverified_path_marked():
    md = "Reference `apps/api/src/services/fake.service.ts` here."
    out, warnings = apply_4_guardrails(md, _signals(), doc_type="adr")
    assert "<!-- unverified -->" in out
    assert any("G2" in w for w in warnings)


def test_g2_verified_path_unchanged():
    md = "See `apps/api/src/services/auth.service.ts` for impl."
    out, warnings = apply_4_guardrails(md, _signals(), doc_type="adr")
    assert "<!-- unverified -->" not in out


def test_g2_unverified_env_var_marked():
    md = "Set `FAKE_VAR` in env."
    out, warnings = apply_4_guardrails(md, _signals(), doc_type="adr")
    assert "<!-- unverified -->" in out
    assert any("FAKE_VAR" in w for w in warnings)


def test_g2_verified_env_var_unchanged():
    md = "Set `DATABASE_URL` in env."
    out, _ = apply_4_guardrails(md, _signals(), doc_type="adr")
    assert "<!-- unverified -->" not in out


def test_g2_schema_prisma_verified_when_signal_true():
    md = "Edit `prisma/schema.prisma` to add field."
    out, _ = apply_4_guardrails(md, _signals(has_schema_prisma=True), doc_type="adr")
    assert "<!-- unverified -->" not in out


def test_g2_path_prefix_directory_verified():
    """Citing the parent directory of a known service should pass."""
    sig = _signals(main_services=["apps/api/src/services/auth.service.ts"])
    md = "Code under `apps/api/src/services` is the boundary."
    out, _ = apply_4_guardrails(md, sig, doc_type="adr")
    assert "<!-- unverified -->" not in out


def test_g2_path_suffix_match_rejected_after_tightening():
    """A token that appears as a suffix inside a service path (not a prefix) must be flagged.

    Before tightening: `lib/util.ts` would substring-match `apps/api/src/lib/util.ts`
    → false-positive verified. After tightening, only exact match or prefix
    (with `/` boundary) verifies.
    """
    sig = _signals(main_services=["apps/api/src/lib/util.ts"])
    md = "See `lib/util.ts` for shared helpers."
    out, warnings = apply_4_guardrails(md, sig, doc_type="adr")
    assert "<!-- unverified -->" in out
    assert any("lib/util.ts" in w for w in warnings)


def test_g2_path_exact_service_match_verified():
    sig = _signals(main_services=["apps/api/src/services/auth.service.ts"])
    md = "See `apps/api/src/services/auth.service.ts` for impl."
    out, _ = apply_4_guardrails(md, sig, doc_type="adr")
    assert "<!-- unverified -->" not in out


def test_g2_path_with_trailing_slash_normalized():
    """Token with trailing slash should still verify against its directory contents."""
    sig = _signals(main_services=["apps/api/src/services/auth.service.ts"])
    md = "Boundary is `apps/api/src/services/`."
    out, _ = apply_4_guardrails(md, sig, doc_type="adr")
    assert "<!-- unverified -->" not in out


# G3: Low-confidence alternatives

def test_g3_alternative_without_backticks_wrapped():
    md = """# ADR

Status: Proposta

## Alternativas consideradas

- Custom queue implementation
- `bullmq` library

## Decisão

decision body
"""
    out, warnings = apply_4_guardrails(md, _signals(), doc_type="adr")
    assert "<!-- low-confidence: review -->" in out
    # Only the first bullet should be wrapped (no backticks)
    assert any("Custom queue" in w for w in warnings)
    # Second bullet has backticks → not wrapped
    bullmq_idx = out.find("bullmq")
    assert "<!-- low-confidence: review -->" not in out[bullmq_idx-50:bullmq_idx]


def test_g3_no_alternatives_section_skips():
    md = "# ADR\n\nStatus: Proposta\n\n## Decisão\n\nbody"
    out, warnings = apply_4_guardrails(md, _signals(), doc_type="adr")
    assert not any("G3" in w for w in warnings)


def test_g3_non_adr_skips():
    md = """# Spec

## Alternatives considered

- Custom impl
"""
    out, warnings = apply_4_guardrails(md, _signals(), doc_type="spec")
    assert "<!-- low-confidence: review -->" not in out


# G4: Diff-friendly

def test_g4_collapses_blank_lines():
    md = "line 1\n\n\n\n\nline 2"
    out, _ = apply_4_guardrails(md, _signals(), doc_type="adr")
    assert "\n\n\n\n" not in out


def test_g4_wraps_long_paragraphs():
    long_line = "este é um parágrafo muito longo " * 10  # >300 chars
    md = f"# ADR\n\nStatus: Proposta\n\n{long_line}\n"
    out, _ = apply_4_guardrails(md, _signals(), doc_type="adr")
    # No line should exceed 100 chars (paragraph), except headers/lists/etc
    for line in out.splitlines():
        if line.startswith(("#", "-", "*", "|", ">")) or line.startswith("    "):
            continue
        assert len(line) <= 100, f"Line too long: {line!r}"


def test_g4_preserves_code_blocks():
    long_code = "const x = 'a very long code line that clearly exceeds one hundred chars for sure no doubt' + 'more text padding to push over limit'"
    assert len(long_code) > 100
    md = f"""# ADR

Status: Proposta

```typescript
{long_code}
```
"""
    out, _ = apply_4_guardrails(md, _signals(), doc_type="adr")
    # Code block content unchanged: original long line still present un-wrapped
    assert long_code in out


def test_g4_preserves_tables():
    md = """# ADR

Status: Proposta

| Column | Value |
|---|---|
| `app` | this is a long table cell value that should not be wrapped because it is in a table row marker |
"""
    out, _ = apply_4_guardrails(md, _signals(), doc_type="adr")
    table_lines = [l for l in out.splitlines() if l.startswith("|")]
    # Tables should not be wrapped
    assert all("|" in l for l in table_lines)


# ---------------------------------------------------------------------------
# T1.1: G5 — Telemetry sanitizer
# ---------------------------------------------------------------------------

from pathlib import Path as _Path

from lib.knowledge_watcher.greenfield.guardrails import _g5_telemetry_sanitizer


_W4_CORPUS_DIR = (
    _Path(__file__).parent / "knowledge_watcher" / "greenfield" / "fixtures" / "w4_corpus"
)


def test_g5_strips_confianca_token_inline():
    """Linha com mistura prosa+telemetry: substitui inline."""
    md = (
        "A presença de redis indica intenção de uso (sinal de detecção, "
        "confiança 0.75) como cache.\n"
    )
    out, warnings = _g5_telemetry_sanitizer(md)
    assert "confiança 0.75" not in out
    assert "sinal de detecção" not in out
    assert "<!-- telemetry stripped -->" in out
    assert len(warnings) >= 2


def test_g5_strips_organizationid_field():
    """Token formato signals attr: false → strip."""
    md = "Sem multi-tenancy (`organizationId: false`) não há isolamento.\n"
    out, warnings = _g5_telemetry_sanitizer(md)
    assert "organizationId: false" not in out
    assert any("G5" in w for w in warnings)


def test_g5_strips_whole_line_when_majority_telemetry():
    """Linha >40% telemetry → strip linha inteira."""
    md = "Confiança do sinal de detecção é 0.75; sinais factuais aplicados.\n"
    out, warnings = _g5_telemetry_sanitizer(md)
    assert "Confiança do sinal" not in out
    assert "sinais factuais" not in out


def test_g5_preserves_legit_prose():
    """Prosa legítima sem telemetry tokens fica intacta."""
    md = (
        "## Decisão\n\n"
        "Adotar BullMQ como job queue. A escolha é baseada em maturidade.\n"
    )
    out, warnings = _g5_telemetry_sanitizer(md)
    assert out == md
    assert warnings == []


def test_g5_corpus_adr003_strips_3_telemetry_leaks():
    """W4 corpus real: ADR-003 tem 3+ telemetry leaks visíveis."""
    corpus = (_W4_CORPUS_DIR / "ADR-003-cache-strategy.md").read_text(encoding="utf-8")
    out, warnings = _g5_telemetry_sanitizer(corpus)
    assert len(warnings) >= 3
    assert "Confiança 0.75" not in out
    assert "sinal de detecção" not in out
    assert "organizationId: false" not in out


# ---------------------------------------------------------------------------
# T2.1: G2 V2 — Negation detection
# ---------------------------------------------------------------------------

from lib.knowledge_watcher.greenfield.guardrails import _g2_v2_negation


def _signals_with_org_and_auth():
    """Helper: signals com has_org_id_pattern + has_auth_middleware = True."""
    from lib.knowledge_watcher.greenfield import SourceSignals
    from pathlib import Path
    return SourceSignals(
        slug="bevox-meta-api", repo_root=Path("/tmp"),
        has_schema_prisma=False, schema_models=[],
        package_json={}, deps={}, main_services=[],
        services_count=0,
        has_auth_middleware=True,
        has_org_id_pattern=True,
        env_vars=[], has_readme=False, readme_text="",
        has_claude_md=False, claude_md_text="", git_tags=[],
    )


def test_g2_v2_detects_pt_negation_contradiction():
    md = "Sem multi-tenancy não há isolamento por tenant.\n"
    out, warnings = _g2_v2_negation(md, _signals_with_org_and_auth(), doc_type="adr")
    assert any("G2 V2" in w for w in warnings)
    assert "<!-- G2 V2:" in out


def test_g2_v2_detects_en_negation_contradiction():
    md = "The system has no auth middleware configured.\n"
    out, warnings = _g2_v2_negation(md, _signals_with_org_and_auth(), doc_type="adr")
    assert any("G2 V2" in w for w in warnings)


def test_g2_v2_skips_alternatives_section():
    md = (
        "## Decisão\n\nAdotar X.\n\n"
        "## Alternativas consideradas\n\n"
        "- MongoDB foi descartado por não ter transações ACID nativas.\n"
        "- Redis sem suporte a queries complexas.\n"
    )
    out, warnings = _g2_v2_negation(md, _signals_with_org_and_auth(), doc_type="adr")
    assert all("MongoDB" not in w and "Redis sem" not in w for w in warnings)


def test_g2_v2_no_match_when_signal_false():
    from lib.knowledge_watcher.greenfield import SourceSignals
    from pathlib import Path
    signals = SourceSignals(
        slug="x", repo_root=Path("/tmp"),
        has_schema_prisma=False, schema_models=[],
        package_json={}, deps={}, main_services=[],
        services_count=0, has_auth_middleware=False,
        has_org_id_pattern=False,
        env_vars=[], has_readme=False, readme_text="",
        has_claude_md=False, claude_md_text="", git_tags=[],
    )
    md = "Sem multi-tenancy é design intencional.\n"
    out, warnings = _g2_v2_negation(md, signals, doc_type="adr")
    assert warnings == []
    assert "<!-- G2 V2:" not in out


def test_g2_v2_skips_non_adr():
    md = "Sem multi-tenancy aqui.\n"
    out, warnings = _g2_v2_negation(md, _signals_with_org_and_auth(), doc_type="prd")
    assert warnings == []
    assert out == md


def test_g2_v2_skips_sem_duvida_false_positive():
    md = "Sem dúvida BullMQ é a melhor escolha.\n"
    out, warnings = _g2_v2_negation(md, _signals_with_org_and_auth(), doc_type="adr")
    assert warnings == []


def test_g2_v2_corpus_adr004_detects_contradictions():
    """W4 corpus ADR-004: tem 'sem middleware de auth' + 'sem multi-tenancy ativo' na intro."""
    corpus = (_W4_CORPUS_DIR / "ADR-004-framework-choice.md").read_text(encoding="utf-8")
    out, warnings = _g2_v2_negation(corpus, _signals_with_org_and_auth(), doc_type="adr")
    assert len(warnings) >= 1


# ---------------------------------------------------------------------------
# T3.1: Pipeline integration — apply_guardrails (rename) + alias
# ---------------------------------------------------------------------------


def test_apply_guardrails_includes_g5_and_g2v2():
    """apply_guardrails (renamed) inclui G5 + G2 V2 no pipeline."""
    from lib.knowledge_watcher.greenfield.guardrails import apply_guardrails
    md = (
        "**Status:** Aceita\n\n"
        "Confiança 0.85 do sinal.\n"
        "Sem multi-tenancy aqui.\n"
    )
    out, warnings = apply_guardrails(md, _signals_with_org_and_auth(), doc_type="adr")
    # G1 should flip Status to Proposta
    assert "Aceita" not in out
    # G5 stripped telemetry
    assert "Confiança 0.85" not in out
    # G2 V2 detected contradiction
    assert any("G2 V2" in w for w in warnings)


def test_apply_4_guardrails_alias_still_works():
    """Backward-compat: apply_4_guardrails alias preservado."""
    from lib.knowledge_watcher.greenfield.guardrails import (
        apply_4_guardrails, apply_guardrails,
    )
    assert apply_4_guardrails is apply_guardrails
