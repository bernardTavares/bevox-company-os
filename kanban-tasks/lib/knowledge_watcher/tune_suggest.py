"""Weekly analyzer surveying feedback DB and suggesting tunings (W8.P6).

Surveys signal-combo aggregates over last N days; if `keep_ratio > 0.9` for
combos with `n >= MIN_N` runs, surfaces a suggestion. Bernard confirms via
`/tune <doc_type> threshold <value>` (or skips). No auto-apply.
"""
from __future__ import annotations

from typing import Dict, List

from lib.knowledge_watcher.feedback_stats import stats_by_signal_combo


KEEP_RATIO_THRESHOLD = 0.90
MIN_N = 4


def analyze_tuning_candidates(days: int = 28) -> List[Dict]:
    """Return list of {doc_type, signal_combo, keep_ratio, n, suggestion,
    tune_command} dicts for combos exceeding threshold.
    """
    suggestions = []
    for r in stats_by_signal_combo(days, min_n=MIN_N):
        if r["keep_ratio"] >= KEEP_RATIO_THRESHOLD:
            suggestions.append({
                **r,
                "suggestion": (
                    f"Pattern {r['doc_type']} + {r['signal_combo']} teve "
                    f"keep_ratio {r['keep_ratio']*100:.0f}% em n={r['n']} "
                    f"runs — considerar bumpar threshold."
                ),
                "tune_command": (
                    f"/tune {r['doc_type']} threshold 1.0"
                ),
            })
    return suggestions


def format_suggestions_for_telegram(suggestions: List[Dict]) -> str:
    if not suggestions:
        return (
            "💡 [feedback-loop] sem suggestions de tuning esta semana.\n"
            "Nenhum signal combo bateu keep_ratio ≥ 90% em n≥4 runs."
        )
    lines = ["💡 [feedback-loop] tuning suggestions:\n"]
    for s in suggestions:
        lines.append(
            f"• {s['doc_type']} + {s['signal_combo']} "
            f"(keep {s['keep_ratio']*100:.0f}%, n={s['n']})"
        )
        lines.append(f"  Action: `{s['tune_command']}`")
    return "\n".join(lines)
