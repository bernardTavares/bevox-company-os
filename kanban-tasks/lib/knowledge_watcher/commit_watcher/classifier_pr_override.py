"""classifier_pr_override.py — Layer 3 human override via commit body marker."""
from __future__ import annotations

import re
from typing import Optional

from lib.knowledge_watcher.commit_watcher import (
    ClassifierLayer, ClassifierResult, Commit, DocType,
)

_MARKER = re.compile(r"<!--\s*knowledge:\s*type=([a-z\-]+)\s*-->", re.IGNORECASE)


def extract_pr_override(commit: Commit) -> Optional[ClassifierResult]:
    m = _MARKER.search(commit.body)
    if not m:
        return None
    raw = m.group(1).lower().strip()
    try:
        dt = DocType(raw)
    except ValueError:
        return None
    return ClassifierResult(
        doc_type=dt, confidence=1.0,
        rationale=f"PR-template override: type={raw}",
        source=ClassifierLayer.HUMAN,
    )
