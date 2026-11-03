"""Tests for retirement/markers.py — Categoria A (explicit markers)."""
from pathlib import Path

import pytest

from lib.knowledge_watcher.retirement import RetirementCategory
from lib.knowledge_watcher.retirement.markers import detect_markers


def _doc(tmp_path, name, content):
    p = tmp_path / name
    p.write_text(content)
    return p


def test_no_markers_returns_empty(tmp_path):
    p = _doc(tmp_path, "doc.md", "# Title\n\nNormal content.")
    assert detect_markers(p) == []


def test_frontmatter_status_superseded(tmp_path):
    """`Status: Superseded by ADR-XXX` → high-confidence signal."""
    p = _doc(tmp_path, "adr.md", """---
status: Superseded by ADR-005
---

# ADR-001
""")
    signals = detect_markers(p)
    assert len(signals) == 1
    assert signals[0].category == RetirementCategory.A_MARKERS
    assert signals[0].confidence >= 0.9


def test_frontmatter_status_replaced(tmp_path):
    """`Status: Replaced by <X>` → high signal."""
    p = _doc(tmp_path, "prd.md", """---
status: Replaced by PRD-v2
---
""")
    signals = detect_markers(p)
    assert len(signals) >= 1


def test_frontmatter_status_substituida_pt(tmp_path):
    """Portuguese: `Status: Substituída por X`."""
    p = _doc(tmp_path, "doc.md", """---
status: Substituída por ADR-007
---
""")
    signals = detect_markers(p)
    assert len(signals) >= 1


def test_body_substitui_does_not_flag_this_doc(tmp_path):
    """`**Substitui:** X` says THIS doc replaces X — does NOT flag THIS as retire."""
    p = _doc(tmp_path, "adr.md", """# ADR-005

**Status:** Aceita
**Substitui:** ADR-001

## Contexto
""")
    signals = detect_markers(p)
    # No retirement signal — Cat C (supersession) handles the OTHER side
    assert signals == []


def test_html_deprecated_comment(tmp_path):
    """`<!-- DEPRECATED -->` comment in body → signal."""
    p = _doc(tmp_path, "doc.md", """# Doc

<!-- DEPRECATED -->

Old content.
""")
    signals = detect_markers(p)
    assert len(signals) >= 1
    assert signals[0].category == RetirementCategory.A_MARKERS


def test_obsolete_callout_pt(tmp_path):
    """`> ⚠️ Esta doc é obsoleta` callout → signal."""
    p = _doc(tmp_path, "doc.md", """# Doc

> ⚠️ Esta doc é obsoleta. Ver outra-doc.md.

Content.
""")
    signals = detect_markers(p)
    assert len(signals) >= 1


def test_obsolete_callout_en(tmp_path):
    """English variants: `> ⚠️ This doc is obsolete`."""
    p = _doc(tmp_path, "doc.md", """# Doc

> ⚠️ This doc is obsolete. See newer-doc.md.

Content.
""")
    signals = detect_markers(p)
    assert len(signals) >= 1


def test_status_aceita_does_not_flag(tmp_path):
    """`Status: Aceita` (active doc) → no retirement signal."""
    p = _doc(tmp_path, "adr.md", """---
status: Aceita
---

# ADR-001
""")
    signals = detect_markers(p)
    assert signals == []


def test_missing_file_returns_empty(tmp_path):
    """Non-existent file → empty (degrades)."""
    fake = tmp_path / "does-not-exist.md"
    assert detect_markers(fake) == []


def test_marker_deep_in_body_does_not_flag(tmp_path):
    """Marker past line 30 of body is example/reference content, not a
    deprecation banner. Real banners belong at top.
    """
    filler = "\n".join(f"line {i:03d}" for i in range(40))
    p = _doc(tmp_path, "doc.md", f"""# Real spec

Active spec. The detector below is described as content:

{filler}

<!-- DEPRECATED -->
""")
    assert detect_markers(p) == []


def test_skill_v2_w2_plan_does_not_self_flag(tmp_path):
    """Regression: the F4 W2 plan describes its own patterns. Without
    head-only scan, every pattern in section 10 self-flags.
    """
    body = ["# F4 Retirement Detector Plan", "", "**Status:** Aceita", ""]
    body.extend(f"## Section {i}\n\nFiller content.\n" for i in range(1, 15))
    body.append("")
    body.append("## Markers detectados")
    body.append("")
    body.append("- `Status: Superseded by X` em frontmatter")
    body.append("- `<!-- DEPRECATED -->` HTML comment")
    body.append("- `> ⚠️ Esta doc é obsoleta` callout")
    p = _doc(tmp_path, "skill-v2-W2-plan.md", "\n".join(body))
    assert detect_markers(p) == []


def test_marker_in_first_lines_still_flags(tmp_path):
    """Sanity: legitimate top-of-doc deprecation banner still detected."""
    p = _doc(tmp_path, "doc.md", """# Old doc

<!-- DEPRECATED -->

> ⚠️ This doc is obsolete. See newer.md.

## Old content
""")
    signals = detect_markers(p)
    assert len(signals) >= 2  # both DEPRECATED + callout
