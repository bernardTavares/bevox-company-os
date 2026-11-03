"""commit_watcher/ — F1 commit watcher modules.

Spec: bevox-knowledge/35_specs/_shared/2026-05-08-bevox-knowledge-contribute-skill-v2.md §7
Plan: bevox-knowledge/35_specs/_shared/plans/2026-05-08-skill-v2-W3-f1-commit-watcher-plan.md

Detects documentation gaps from commits via Hybrid classifier (heuristics +
Haiku LLM fallback + PR-template override). Dispatches Telegram digest via
UBN escalation_dispatcher kind=doc-gap. Never auto-merges; review humano
sempre.
"""
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import List, Optional


class DocType(Enum):
    RELEASE_NOTE = "release-note"
    SPEC = "spec"
    ADR = "adr"
    ARCHITECTURE = "architecture"
    PRD = "prd"
    ROADMAP = "roadmap"
    NONE = "none"


class ClassifierLayer(Enum):
    HEURISTIC = "heuristic"
    LLM = "llm"
    HUMAN = "human"


class Strategy(Enum):
    DRAFT_FILLED = "draft-filled"
    DRAFT_SKELETON = "draft-skeleton"
    DETECT_FLAG_TEMPLATE = "detect-flag-template"
    DETECT_FLAG = "detect-flag"


@dataclass
class Commit:
    sha: str
    short_sha: str
    subject: str
    body: str
    files_changed: List[str]
    diffstat: str
    author: str
    timestamp_iso: str


@dataclass
class ClassifierResult:
    doc_type: DocType
    confidence: float
    rationale: str
    source: ClassifierLayer


@dataclass
class GapDraft:
    project_slug: str
    commit: Commit
    classifier_result: ClassifierResult
    strategy: Strategy
    draft_branch: str
    draft_file_relative: Optional[str]
    gaps_entry: str
    digest_line: str

    @property
    def gap_id(self) -> str:
        """Deterministic gap ID. W3.5: <repo>-<commit-short7>-<doctype>."""
        from ..gap_registry import derive_gap_id_f1
        return derive_gap_id_f1(
            self.project_slug,
            self.commit.sha,
            self.classifier_result.doc_type.value,
        )


@dataclass
class AuditResult:
    repo_slug: str
    new_commits_processed: int
    gaps_detected: int
    gaps: List[GapDraft] = field(default_factory=list)
    last_commit_processed: str = ""
    skipped_reason: Optional[str] = None
