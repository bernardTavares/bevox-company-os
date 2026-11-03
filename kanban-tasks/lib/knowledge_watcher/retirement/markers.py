"""markers.py — Categoria A (explicit retirement markers in doc).

Detects:
- Frontmatter `Status: Superseded by X` / `Replaced by Y` / `Substituída por Z`
- Body (first 30 lines) `<!-- DEPRECATED -->` HTML comment
- Body (first 30 lines) callout `> ⚠️ Esta doc é obsoleta` / `> ⚠️ This doc is obsolete`

Body scan is limited to the first 30 lines because retirement markers
belong at the doc's TOP — not buried in section 10 of a long spec. Without
this limit, specs/plans of the F4 detector itself flag as candidates because
they describe the patterns F4 detects (self-reference loop). 30 lines covers
real deprecation banners (typically lines 1-10) while excluding mid-body
example or reference content.

NÃO detecta `**Substitui:** X` no body — esse marker indica que ESTA doc
substitui outra (handled by supersession.py Cat C as inbound signal pra
a OUTRA doc).
"""
from __future__ import annotations

import re
from pathlib import Path
from typing import List

from lib.knowledge_watcher.retirement import (
    CategorySignal, RetirementCategory,
)


# Frontmatter status patterns (case-insensitive)
_STATUS_SUPERSEDED_RE = re.compile(
    r"(?im)^\s*status\s*:\s*(superseded\s+by|replaced\s+by|superada\s+por|substitu[ií]da(\s+por)?)\b",
)

# HTML deprecated comment
_HTML_DEPRECATED_RE = re.compile(r"<!--\s*DEPRECATED\s*-->", re.IGNORECASE)

# Obsolete callout (PT or EN)
_OBSOLETE_CALLOUT_RE = re.compile(
    r"^>\s*⚠️.*(obsoleta?|obsolete|deprecated)",
    re.IGNORECASE | re.MULTILINE,
)


_BODY_HEAD_LINES = 30


def _split_frontmatter(content: str) -> tuple[str, str]:
    """Split YAML frontmatter from body. Returns (frontmatter, body)."""
    if not content.startswith("---"):
        return "", content
    parts = content.split("---", 2)
    if len(parts) < 3:
        return "", content
    return parts[1], parts[2]


def _body_head(body: str) -> str:
    """Top N lines of body — where deprecation banners actually belong."""
    return "\n".join(body.split("\n")[:_BODY_HEAD_LINES])


def detect_markers(doc_path: Path) -> List[CategorySignal]:
    """Detect retirement markers in a single canonical doc.

    Returns list of CategorySignal (Cat A). Empty if no markers.
    Degrades gracefully (missing file → []).
    """
    if not doc_path.is_file():
        return []
    try:
        content = doc_path.read_text(encoding="utf-8")
    except OSError:
        return []

    fm, body = _split_frontmatter(content)
    body_head = _body_head(body)
    signals: List[CategorySignal] = []

    if _STATUS_SUPERSEDED_RE.search(fm) or _STATUS_SUPERSEDED_RE.search(body_head):
        signals.append(CategorySignal(
            category=RetirementCategory.A_MARKERS,
            confidence=0.95,
            evidence="Status: Superseded/Replaced/Substituída marker present",
        ))

    if _HTML_DEPRECATED_RE.search(body_head):
        signals.append(CategorySignal(
            category=RetirementCategory.A_MARKERS,
            confidence=0.90,
            evidence="<!-- DEPRECATED --> HTML comment in body",
        ))

    if _OBSOLETE_CALLOUT_RE.search(body_head):
        signals.append(CategorySignal(
            category=RetirementCategory.A_MARKERS,
            confidence=0.90,
            evidence="Obsolete/deprecated callout (⚠️) in body",
        ))

    return signals
