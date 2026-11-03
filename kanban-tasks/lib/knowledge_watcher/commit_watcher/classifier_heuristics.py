"""classifier_heuristics.py — Layer 1 deterministic classifier."""
from __future__ import annotations

import re
from typing import Optional

from lib.knowledge_watcher.commit_watcher import (
    ClassifierLayer, ClassifierResult, Commit, DocType,
)

_RELEASE_PREFIX = re.compile(r"^release[\(:]", re.IGNORECASE)
_FEAT_PREFIX = re.compile(r"^feat[\(:]", re.IGNORECASE)
_REFACTOR_PREFIX = re.compile(r"^refactor[\(:]", re.IGNORECASE)
_TEST_PATH = re.compile(r"\.(test|spec)\.[jt]sx?$|/tests?/")
_CI_PATH = re.compile(r"^(\.github/|\.gitlab-ci|\.gitignore$|.*\.ya?ml$|Dockerfile)")
_SERVICE_PATH = re.compile(r"^apps/[^/]+/src/services/[^/]+\.[jt]sx?$|^lib/[^/]+/[^/]+\.py$")


def _all_match(files: list[str], pattern: re.Pattern) -> bool:
    if not files:
        return False
    return all(pattern.search(f) for f in files)


def classify_heuristic(commit: Commit) -> Optional[ClassifierResult]:
    subject = commit.subject

    if _RELEASE_PREFIX.match(subject):
        return ClassifierResult(
            doc_type=DocType.RELEASE_NOTE, confidence=0.95,
            rationale="release: prefix in subject",
            source=ClassifierLayer.HEURISTIC,
        )

    if _all_match(commit.files_changed, _TEST_PATH):
        return ClassifierResult(
            doc_type=DocType.NONE, confidence=0.95,
            rationale="only test files modified",
            source=ClassifierLayer.HEURISTIC,
        )

    if _all_match(commit.files_changed, _CI_PATH):
        return ClassifierResult(
            doc_type=DocType.NONE, confidence=0.92,
            rationale="only CI/yaml/config files",
            source=ClassifierLayer.HEURISTIC,
        )

    has_schema = any("prisma/schema.prisma" in f for f in commit.files_changed)
    has_auth_middleware = any("middleware/auth" in f for f in commit.files_changed)
    if has_schema or has_auth_middleware:
        return ClassifierResult(
            doc_type=DocType.ADR, confidence=0.78,
            rationale="schema.prisma or auth middleware change → architectural",
            source=ClassifierLayer.HEURISTIC,
        )

    if _FEAT_PREFIX.match(subject):
        if any(_SERVICE_PATH.search(f) for f in commit.files_changed):
            return ClassifierResult(
                doc_type=DocType.SPEC, confidence=0.80,
                rationale="feat: + new service file",
                source=ClassifierLayer.HEURISTIC,
            )

    if _REFACTOR_PREFIX.match(subject):
        dirs = {"/".join(f.split("/")[:3]) for f in commit.files_changed if "/" in f}
        if len(dirs) >= 3:
            return ClassifierResult(
                doc_type=DocType.ARCHITECTURE, confidence=0.66,
                rationale=f"refactor: across {len(dirs)} dirs",
                source=ClassifierLayer.HEURISTIC,
            )

    return None
