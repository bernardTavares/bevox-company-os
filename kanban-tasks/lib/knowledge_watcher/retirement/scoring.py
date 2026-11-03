"""scoring.py — compound retirement score (5-category weights).

Per spec §10.3:
- A_MARKERS: 1.0
- B_CODE_BROKEN: 0.7
- C_SUPERSESSION: 0.7
- D_LIFECYCLE: 0.4
- E_ORPHAN: 0.3

Score = sum(max weight per category present). Capped at 1.0.

Threshold: score >= 0.7 (default) → retirement candidate. Doc-type-aware
overrides raise the bar for documents whose code-correlation drift does
not imply obsolescence:

- **ADR**: decision records perdure even after referenced code moves.
  Threshold 0.9 AND must include A_MARKERS or C_SUPERSESSION (B/D/E
  alone never flag).
- **Architecture**: describes intent, not current file structure.
  Threshold 0.8 (B alone insufficient).
- **PRD/spec/roadmap/release-note**: keep default 0.7 (current behavior).

Surfaced from W7-extras smoke (2026-05-10): 68 candidates dominated 100%
by B_code_broken; 16 ADRs flagged with broken-refs alone are decision-
record false positives.
"""
from __future__ import annotations

from typing import List, Optional

from lib.knowledge_watcher.retirement import (
    CategorySignal, RetirementCategory,
)


CATEGORY_WEIGHTS = {
    RetirementCategory.A_MARKERS: 1.0,
    RetirementCategory.B_CODE_BROKEN: 0.7,
    RetirementCategory.C_SUPERSESSION: 0.7,
    RetirementCategory.D_LIFECYCLE: 0.4,
    RetirementCategory.E_ORPHAN: 0.3,
}

SCORE_THRESHOLD = 0.7

# Per-doc-type threshold override. doc_type strings come from
# scanner._doc_type_from_path: 'adr' | 'architecture' | 'prd' | 'spec' |
# 'roadmap' | 'release-note' | etc. Missing entry → SCORE_THRESHOLD.
DOC_TYPE_THRESHOLDS: dict[str, float] = {
    "adr": 0.9,
    "architecture": 0.8,
}

# Per-doc-type required-category sets. If non-empty, the doc must include
# AT LEAST ONE signal from one of the required categories — otherwise it
# is NOT a candidate regardless of score. Used for decision-record types
# (ADR) where broken refs alone do not imply obsolescence.
DOC_TYPE_REQUIRED_CATEGORIES: dict[str, set[RetirementCategory]] = {
    "adr": {
        RetirementCategory.A_MARKERS,
        RetirementCategory.C_SUPERSESSION,
    },
}


def compound_score(signals: List[CategorySignal]) -> float:
    """Sum max-weight per category. Capped at 1.0."""
    if not signals:
        return 0.0
    by_cat: dict[RetirementCategory, float] = {}
    for s in signals:
        weight = CATEGORY_WEIGHTS.get(s.category, 0.0)
        by_cat[s.category] = max(by_cat.get(s.category, 0.0), weight)
    total = sum(by_cat.values())
    return round(min(total, 1.0), 2)


def threshold_for(doc_type: Optional[str]) -> float:
    """Resolve threshold with override hierarchy:

    1. skill_config.json `f4_overrides.doc_type_thresholds[<doc_type>]` (W8 /tune)
    2. DOC_TYPE_THRESHOLDS hardcoded (ADR=0.9, architecture=0.8 — W7 doctype)
    3. SCORE_THRESHOLD (0.7 default)
    """
    if doc_type is None:
        return SCORE_THRESHOLD
    try:
        from lib.knowledge_watcher.skill_config import get_doc_type_thresholds
        overrides = get_doc_type_thresholds()
    except Exception:
        overrides = {}
    if doc_type in overrides:
        return float(overrides[doc_type])
    return DOC_TYPE_THRESHOLDS.get(doc_type, SCORE_THRESHOLD)


def is_retirement_candidate(
    signals: List[CategorySignal],
    doc_type: Optional[str] = None,
) -> bool:
    """Decide if signals + doc_type meet the per-type retirement bar.

    Two-stage gate:
    1. compound_score(signals) must be >= threshold_for(doc_type)
    2. If doc_type has required categories, signals must include at least
       one signal from one of those categories.
    """
    if compound_score(signals) < threshold_for(doc_type):
        return False
    required = DOC_TYPE_REQUIRED_CATEGORIES.get(doc_type or "")
    if required:
        present = {s.category for s in signals}
        if not (present & required):
            return False
    return True
