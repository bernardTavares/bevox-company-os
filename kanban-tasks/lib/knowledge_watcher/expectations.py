"""expectations.py — folder-level expectation rules per project context.

Spec: bevox-knowledge/35_specs/_shared/2026-05-08-bevox-knowledge-contribute-skill-v2.md §8.1

Each canonical folder has a rule that takes project context and returns
ExpectationResult(severity, reason). 3 severity tiers:

- ALWAYS_REQUIRED: report as ❌ MISSING gap if folder is empty in adopted project
- CONDITIONAL: report as ⚠️ GAP if folder empty AND condition met
- OPTIONAL: never report as gap (e.g. 00_inbox is ad-hoc capture)

Rules use small heuristics from project context:
- age_months: months since first commit
- commit_count: total commits in repo
- commits_last_30d: commits in last 30 days
- has_git_tags: bool
- has_schema_prisma: bool (presence of prisma/schema.prisma)
- service_count: number of distinct services/apps
- has_customers_flag: bool from projects-meta
- has_metrics_flag: bool from projects-meta
- is_adopted: bool (project has projects-meta entry with source=adopted/user_created)
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Callable, Dict


class Severity(Enum):
    ALWAYS_REQUIRED = "always-required"
    CONDITIONAL = "conditional"
    OPTIONAL = "optional"


@dataclass
class ExpectationResult:
    severity: Severity
    reason: str  # human-readable why


def _always_required(ctx: dict) -> ExpectationResult:
    return ExpectationResult(Severity.ALWAYS_REQUIRED, "always-required for adopted projects")


def _established(ctx: dict) -> ExpectationResult:
    """30_adr: project considered "established" if age >= 6mo OR commits >= 100."""
    age = ctx.get("age_months", 0) or 0
    commits = ctx.get("commit_count", 0) or 0
    if age >= 6 or commits >= 100:
        return ExpectationResult(
            Severity.CONDITIONAL,
            f"established project (age={age}mo, commits={commits})",
        )
    return ExpectationResult(
        Severity.OPTIONAL,
        f"young project (age={age}mo, commits={commits}); ADR optional",
    )


def _active_30d(ctx: dict) -> ExpectationResult:
    """35_specs: expected if recent activity (commits last 30d > 0)."""
    recent = ctx.get("commits_last_30d", 0) or 0
    if recent > 0:
        return ExpectationResult(
            Severity.CONDITIONAL,
            f"active project ({recent} commits last 30d)",
        )
    return ExpectationResult(
        Severity.OPTIONAL,
        "inactive (0 commits last 30d); specs optional",
    )


def _complex(ctx: dict) -> ExpectationResult:
    """20_architecture: expected if has_schema_prisma OR service_count >= 3."""
    has_prisma = bool(ctx.get("has_schema_prisma"))
    services = ctx.get("service_count", 0) or 0
    if has_prisma or services >= 3:
        return ExpectationResult(
            Severity.CONDITIONAL,
            f"complex project (prisma={has_prisma}, services={services})",
        )
    return ExpectationResult(
        Severity.OPTIONAL,
        "simple project; architecture doc optional",
    )


def _shipped(ctx: dict) -> ExpectationResult:
    """50_releases: expected if has_git_tags."""
    if ctx.get("has_git_tags"):
        return ExpectationResult(
            Severity.CONDITIONAL,
            "project has git tags (released)",
        )
    return ExpectationResult(
        Severity.OPTIONAL,
        "no git tags; release-notes optional",
    )


def _customers(ctx: dict) -> ExpectationResult:
    """60_customer-feedback: expected if has_customers_flag."""
    if ctx.get("has_customers_flag"):
        return ExpectationResult(
            Severity.CONDITIONAL,
            "has customers (per projects-meta flag)",
        )
    return ExpectationResult(
        Severity.OPTIONAL,
        "no customers flag; feedback optional",
    )


def _metrics(ctx: dict) -> ExpectationResult:
    """70_metrics: expected if has_metrics_flag."""
    if ctx.get("has_metrics_flag"):
        return ExpectationResult(
            Severity.CONDITIONAL,
            "has metrics (per projects-meta flag)",
        )
    return ExpectationResult(
        Severity.OPTIONAL,
        "no metrics flag; measurements optional",
    )


def _optional(ctx: dict) -> ExpectationResult:
    return ExpectationResult(Severity.OPTIONAL, "optional capture folder")


# Folder → rule function
EXPECTATION_RULES: Dict[str, Callable[[dict], ExpectationResult]] = {
    "00_inbox": _optional,
    "10_prd": _always_required,
    "20_architecture": _complex,
    "30_adr": _established,
    "35_specs": _active_30d,
    "40_roadmap": _always_required,
    "50_releases": _shipped,
    "60_customer-feedback": _customers,
    "70_metrics": _metrics,
}


def folder_expectation(folder: str, ctx: dict) -> ExpectationResult:
    """Return expectation for a folder given project context.

    Unknown folders default to OPTIONAL (defensive — won't surface noise).
    """
    rule = EXPECTATION_RULES.get(folder)
    if rule is None:
        return ExpectationResult(
            Severity.OPTIONAL,
            f"unknown folder '{folder}' — no rule defined",
        )
    return rule(ctx)
