"""guardrails.py — 4 hallucination guardrails for F3 LLM output post-process.

Per spec §9.5:
1. Status: Proposta sempre em ADR (nunca Aceita)
2. Cite-or-stay-silent (verify file paths/env vars exist em SourceSignals)
3. Confidence-marked alternatives (low-conf wrapped em HTML comment)
4. Diff-friendly format (paragraph wrap, no excessive blank lines)
"""
from __future__ import annotations

import re
import textwrap
from typing import List, Tuple

from lib.knowledge_watcher.greenfield import SourceSignals


_STATUS_RE = re.compile(r"^(\**Status:\**\s*)(\w+)", re.MULTILINE | re.IGNORECASE)
_BACKTICK_TOKEN_RE = re.compile(r"`([^`]+)`")
_PATH_RE = re.compile(r"^(apps|lib|prisma)/[\w./\-]+$")
_ENV_RE = re.compile(r"^[A-Z][A-Z0-9_]{3,}$")
_HASH_RE = re.compile(r"^[a-f0-9]{7,40}$")
_ALT_HEADING_RE = re.compile(
    r"^##\s+(Alternatives\s+considered|Alternativas\s+consideradas)\s*$",
    re.IGNORECASE,
)


def _g1_status_proposta(markdown: str, doc_type: str) -> Tuple[str, List[str]]:
    if doc_type != "adr":
        return markdown, []
    warnings: List[str] = []
    match = _STATUS_RE.search(markdown)
    if match and match.group(2) != "Proposta":
        original = match.group(2)
        markdown = _STATUS_RE.sub(
            lambda m: f"{m.group(1)}Proposta", markdown, count=1
        )
        warnings.append(f"G1: Status forced to Proposta (was: {original})")
    return markdown, warnings


def _classify_token(token: str) -> str | None:
    """Return 'path' | 'env' | 'hash' | None."""
    if _PATH_RE.match(token):
        return "path"
    if _ENV_RE.match(token):
        return "env"
    if _HASH_RE.match(token) and not _ENV_RE.match(token):
        return "hash"
    return None


def _verify_token(token: str, kind: str, signals: SourceSignals) -> bool:
    if kind == "path":
        if token == "prisma/schema.prisma":
            return signals.has_schema_prisma
        if not token:
            return False
        token_norm = token.rstrip("/")
        prefix = token_norm + "/"
        return any(
            s == token_norm or s.startswith(prefix)
            for s in signals.main_services
        )
    if kind == "env":
        return token in signals.env_vars
    if kind == "hash":
        return True  # not verifiable from signals; leave alone
    return True


def _g2_cite_or_silent(markdown: str, signals: SourceSignals) -> Tuple[str, List[str]]:
    warnings: List[str] = []

    def _process(match: re.Match) -> str:
        token = match.group(1)
        kind = _classify_token(token)
        if kind is None or kind == "hash":
            return match.group(0)
        if _verify_token(token, kind, signals):
            return match.group(0)
        warnings.append(f"G2: unverified reference: `{token}`")
        return f"<!-- unverified -->`{token}`"

    new_md = _BACKTICK_TOKEN_RE.sub(_process, markdown)
    return new_md, warnings


def _g3_low_confidence_alternatives(markdown: str, doc_type: str) -> Tuple[str, List[str]]:
    if doc_type != "adr":
        return markdown, []
    warnings: List[str] = []
    lines = markdown.splitlines()
    out_lines: List[str] = []
    in_alt_section = False
    for line in lines:
        if _ALT_HEADING_RE.match(line):
            in_alt_section = True
            out_lines.append(line)
            continue
        if in_alt_section and line.startswith("## "):
            in_alt_section = False
            out_lines.append(line)
            continue
        if in_alt_section and line.lstrip().startswith("- "):
            if "`" not in line:
                out_lines.append("<!-- low-confidence: review -->")
                out_lines.append(line)
                warnings.append(f"G3: low-confidence alternative: {line.strip()}")
                continue
        out_lines.append(line)
    return "\n".join(out_lines), warnings


def _is_paragraph_line(line: str) -> bool:
    """True if line is a regular paragraph (not header/list/code/table/quote)."""
    stripped = line.lstrip()
    if not stripped:
        return False
    if stripped.startswith(("#", "|", "-", "*", ">", "```")):
        return False
    if line.startswith("    ") or line.startswith("\t"):
        return False
    return True


def _g4_diff_friendly(markdown: str) -> Tuple[str, List[str]]:
    # Collapse 4+ consecutive newlines into 3 (= max 2 blank lines between content)
    collapsed = re.sub(r"\n{4,}", "\n\n\n", markdown)

    # Hard-wrap paragraph lines at 100 chars
    in_code_block = False
    in_frontmatter = False
    lines = collapsed.splitlines()
    out: List[str] = []
    for i, line in enumerate(lines):
        if line.strip() == "---" and i == 0:
            out.append(line)
            in_frontmatter = True
            continue
        if in_frontmatter and line.strip() == "---":
            in_frontmatter = False
            out.append(line)
            continue
        if in_frontmatter:
            out.append(line)
            continue
        if line.strip().startswith("```"):
            in_code_block = not in_code_block
            out.append(line)
            continue
        if in_code_block:
            out.append(line)
            continue
        if _is_paragraph_line(line) and len(line) > 100:
            wrapped = textwrap.wrap(
                line, width=100, break_long_words=False, break_on_hyphens=False
            )
            out.extend(wrapped)
        else:
            out.append(line)

    # Ensure single trailing newline
    text = "\n".join(out).rstrip() + "\n"
    return text, []


# G5 — Telemetry sanitizer (W6)
_TELEMETRY_PATTERNS = [
    re.compile(r"\bConfiança \d+\.\d+", re.IGNORECASE),
    re.compile(
        r"\b(?:has_org_id_pattern|has_auth_middleware|has_schema_prisma|"
        r"has_env_vars|organizationId)\s*:\s*(?:true|false|n/a|null)\b"
    ),
    re.compile(r"\bmain_services?\s*:\s*n/a\b", re.IGNORECASE),
    re.compile(r"\bsinal(?:es)? de detecção\b", re.IGNORECASE),
    re.compile(r"\bConfiança do sinal\b", re.IGNORECASE),
    re.compile(r"\bsinais factuais\b", re.IGNORECASE),
]

_TELEMETRY_LINE_THRESHOLD = 0.40


def _telemetry_matches_in_line(line: str):
    """Yield (match_text, span) for each telemetry pattern hit in line."""
    matches = []
    for pat in _TELEMETRY_PATTERNS:
        for m in pat.finditer(line):
            matches.append((m.group(0), m.span()))
    return matches


def _g5_telemetry_sanitizer(markdown: str) -> Tuple[str, List[str]]:
    """Strip telemetry tokens leaked from signals.py into Sonnet output.

    Strategy:
    - Per line: collect all telemetry pattern matches
    - Compute total telemetry chars / line chars ratio
    - If ratio > threshold (40%) → strip whole line
    - Else → substitute each match inline with ``<!-- telemetry stripped -->``

    Returns (cleaned_markdown, warnings).
    """
    warnings: List[str] = []
    out_lines: List[str] = []
    for line in markdown.splitlines(keepends=False):
        if not line.strip():
            out_lines.append(line)
            continue
        matches = _telemetry_matches_in_line(line)
        if not matches:
            out_lines.append(line)
            continue
        line_len = len(line)
        telemetry_chars = sum(end - start for _, (start, end) in matches)
        ratio = telemetry_chars / line_len if line_len else 0.0
        if ratio > _TELEMETRY_LINE_THRESHOLD:
            for match_text, _ in matches:
                warnings.append(f"G5: stripped telemetry line containing: '{match_text[:60]}'")
            continue  # skip line
        new_line = line
        for match_text, (start, end) in reversed(matches):
            new_line = new_line[:start] + "<!-- telemetry stripped -->" + new_line[end:]
            warnings.append(f"G5: stripped telemetry token: '{match_text[:60]}'")
        out_lines.append(new_line)
    text = "\n".join(out_lines)
    if markdown.endswith("\n"):
        text += "\n"
    return text, warnings


# G2 V2 — Negation detection (W6)
_NEGATION_PATTERNS = [
    # PT primary; negative lookahead to avoid "sem dúvida", "sem perda"
    re.compile(
        r"\b(?:não há|não tem|não usa|não existe|não suporta|"
        r"sem(?!\s+(?:dúvida|perda)))\s+([\w\-]+)",
        re.IGNORECASE,
    ),
    # EN fallback
    re.compile(
        r"\b(?:no|without|doesn't have|not used|lacks)\s+([\w\-]+)",
        re.IGNORECASE,
    ),
]

# claim_keyword (lower) → (signals_attribute, expected_value_when_signal_true)
_SIGNAL_NEGATION_MAP = {
    "multi-tenancy": ("has_org_id_pattern", True),
    "multitenancy": ("has_org_id_pattern", True),
    "organizationid": ("has_org_id_pattern", True),
    "multi": ("has_org_id_pattern", True),  # "sem multi-tenancy" → group(1)="multi"
    "auth": ("has_auth_middleware", True),
    "authentication": ("has_auth_middleware", True),
    "auth-middleware": ("has_auth_middleware", True),
    "middleware": ("has_auth_middleware", True),
    "schema": ("has_schema_prisma", True),
    "prisma": ("has_schema_prisma", True),
}


def _identify_alternatives_region(lines: List[str]) -> set:
    """Return set of line indices inside 'Alternativas consideradas' section."""
    skip_indices = set()
    in_alt = False
    for i, line in enumerate(lines):
        if _ALT_HEADING_RE.match(line):
            in_alt = True
            continue
        if in_alt and line.startswith("## "):
            in_alt = False
            continue
        if in_alt:
            skip_indices.add(i)
    return skip_indices


def _g2_v2_negation(
    markdown: str, signals: SourceSignals, *, doc_type: str,
) -> Tuple[str, List[str]]:
    """Detect negation claims contradicting signals.<attr>=True.

    Skip 'Alternativas consideradas' section (negations there are factual
    about alternatives, not hallucinations about main system).

    Returns (annotated_markdown, warnings). Wrap offending line with
    HTML comment ``<!-- G2 V2: contradicts signals.{attr}={expected} -->``.
    """
    if doc_type != "adr":
        return markdown, []

    warnings: List[str] = []
    lines = markdown.splitlines(keepends=False)
    alt_indices = _identify_alternatives_region(lines)
    out_lines: List[str] = []

    for i, line in enumerate(lines):
        if i in alt_indices:
            out_lines.append(line)
            continue
        annotated = False
        for pat in _NEGATION_PATTERNS:
            for m in pat.finditer(line):
                claim = m.group(1).lower().rstrip(".,;:")
                mapping = _SIGNAL_NEGATION_MAP.get(claim)
                if mapping is None:
                    continue
                attr, expected = mapping
                actual = getattr(signals, attr, None)
                if actual == expected:
                    if not annotated:
                        comment = (
                            f"<!-- G2 V2: contradicts signals.{attr}={expected} "
                            f"(observed in repo) -->"
                        )
                        out_lines.append(comment)
                        annotated = True
                    warnings.append(
                        f"G2 V2: negation '{m.group(0)}' contradicts "
                        f"signals.{attr}={expected}"
                    )
        out_lines.append(line)

    text = "\n".join(out_lines)
    if markdown.endswith("\n"):
        text += "\n"
    return text, warnings


def apply_guardrails(
    markdown: str, signals: SourceSignals, *, doc_type: str,
) -> Tuple[str, List[str]]:
    """Apply F3 hallucination guardrails. Returns (processed_md, warnings).

    Pipeline order (W6): G1 → G2 → G2 V2 → G3 → G5 → G4

    - G1: Status forced to Proposta (ADR only)
    - G2: cite-or-silent (verify backtick paths/env against signals)
    - G2 V2: negation contradicts signals.{attr}=True (ADR only, skip Alternatives)
    - G3: low-confidence alternatives wrapped (ADR only)
    - G5: strip signals.py telemetry tokens
    - G4: diff-friendly format (paragraph wrap)
    """
    warnings: List[str] = []

    md, w1 = _g1_status_proposta(markdown, doc_type)
    warnings.extend(w1)

    md, w2 = _g2_cite_or_silent(md, signals)
    warnings.extend(w2)

    md, w2v2 = _g2_v2_negation(md, signals, doc_type=doc_type)
    warnings.extend(w2v2)

    md, w3 = _g3_low_confidence_alternatives(md, doc_type)
    warnings.extend(w3)

    md, w5 = _g5_telemetry_sanitizer(md)
    warnings.extend(w5)

    md, w4 = _g4_diff_friendly(md)
    warnings.extend(w4)

    return md, warnings


# W4 backward-compat alias (apply_4_guardrails name preserved)
apply_4_guardrails = apply_guardrails
