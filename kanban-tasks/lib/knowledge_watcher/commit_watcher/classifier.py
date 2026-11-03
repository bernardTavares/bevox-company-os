"""classifier.py — Orchestrator: L3 → L1 → L2 fallback."""
from __future__ import annotations

from pathlib import Path

from lib.knowledge_watcher.commit_watcher import ClassifierResult, Commit
from lib.knowledge_watcher.commit_watcher.classifier_heuristics import classify_heuristic
from lib.knowledge_watcher.commit_watcher.classifier_pr_override import extract_pr_override
from lib.knowledge_watcher.commit_watcher.classifier_llm import classify_llm


def classify(
    commit: Commit, *, state_path: Path,
    llm_threshold: float = 0.70, budget_usd: float = 5.0,
) -> ClassifierResult:
    override = extract_pr_override(commit)
    if override:
        return override

    heur = classify_heuristic(commit)
    if heur and heur.confidence >= llm_threshold:
        return heur

    llm = classify_llm(commit, state_path=state_path, budget_usd=budget_usd)
    if heur and llm.confidence < heur.confidence:
        return heur
    return llm
