"""retirement/ — F4 retirement detector modules.

Spec: bevox-knowledge/35_specs/_shared/2026-05-08-bevox-knowledge-contribute-skill-v2.md §10

5 categorias semânticas com confidence scores. Compound score >= 0.7 → flag.
Nunca auto-retira (per spec §10.4 — sempre review humano via Telegram digest).
"""
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import List, Optional


class RetirementCategory(Enum):
    A_MARKERS = "A_markers"
    B_CODE_BROKEN = "B_code_broken"
    C_SUPERSESSION = "C_supersession"
    D_LIFECYCLE = "D_lifecycle"
    E_ORPHAN = "E_orphan"


@dataclass
class CategorySignal:
    """One detection signal from one category."""
    category: RetirementCategory
    confidence: float  # 0.0 — 1.0
    evidence: str  # human-readable why


@dataclass
class RetirementCandidate:
    """A doc flagged as retirement candidate."""
    path: Path  # absolute path to canonical doc
    relative_path: str  # e.g. "30_adr/bevox-direct/ADR-005.md"
    project_slug: Optional[str]  # extracted from path; None if _shared
    score: float  # compound score [0..1]
    signals: List[CategorySignal] = field(default_factory=list)
