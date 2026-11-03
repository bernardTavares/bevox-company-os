"""Tests for lib/knowledge_watcher/expectations.py."""
from lib.knowledge_watcher.expectations import (
    folder_expectation,
    Severity,
    EXPECTATION_RULES,
)


def test_10_prd_always_required():
    """10_prd is always-required for any adopted project."""
    ctx = {"is_adopted": True}
    result = folder_expectation("10_prd", ctx)
    assert result.severity == Severity.ALWAYS_REQUIRED


def test_40_roadmap_always_required():
    ctx = {"is_adopted": True}
    result = folder_expectation("40_roadmap", ctx)
    assert result.severity == Severity.ALWAYS_REQUIRED


def test_30_adr_conditional_established():
    """30_adr expected if age >= 6mo OR commits >= 100."""
    ctx = {"is_adopted": True, "age_months": 2, "commit_count": 30}
    assert folder_expectation("30_adr", ctx).severity == Severity.OPTIONAL

    ctx = {"is_adopted": True, "age_months": 7, "commit_count": 30}
    assert folder_expectation("30_adr", ctx).severity == Severity.CONDITIONAL

    ctx = {"is_adopted": True, "age_months": 2, "commit_count": 150}
    assert folder_expectation("30_adr", ctx).severity == Severity.CONDITIONAL


def test_35_specs_conditional_active():
    """35_specs expected if commits in last 30d."""
    ctx = {"is_adopted": True, "commits_last_30d": 5}
    assert folder_expectation("35_specs", ctx).severity == Severity.CONDITIONAL

    ctx = {"is_adopted": True, "commits_last_30d": 0}
    assert folder_expectation("35_specs", ctx).severity == Severity.OPTIONAL


def test_20_architecture_conditional_complex():
    """20_architecture expected if has_schema_prisma OR services >= 3."""
    ctx = {"is_adopted": True, "has_schema_prisma": True, "service_count": 1}
    assert folder_expectation("20_architecture", ctx).severity == Severity.CONDITIONAL

    ctx = {"is_adopted": True, "has_schema_prisma": False, "service_count": 5}
    assert folder_expectation("20_architecture", ctx).severity == Severity.CONDITIONAL

    ctx = {"is_adopted": True, "has_schema_prisma": False, "service_count": 1}
    assert folder_expectation("20_architecture", ctx).severity == Severity.OPTIONAL


def test_50_releases_conditional_shipped():
    """50_releases expected if has_git_tags."""
    ctx = {"is_adopted": True, "has_git_tags": True}
    assert folder_expectation("50_releases", ctx).severity == Severity.CONDITIONAL

    ctx = {"is_adopted": True, "has_git_tags": False}
    assert folder_expectation("50_releases", ctx).severity == Severity.OPTIONAL


def test_60_customer_feedback_conditional_flag():
    """60_customer-feedback expected if has_customers_flag."""
    ctx = {"is_adopted": True, "has_customers_flag": True}
    assert folder_expectation("60_customer-feedback", ctx).severity == Severity.CONDITIONAL

    ctx = {"is_adopted": True, "has_customers_flag": False}
    assert folder_expectation("60_customer-feedback", ctx).severity == Severity.OPTIONAL


def test_70_metrics_conditional_flag():
    """70_metrics expected if has_metrics_flag."""
    ctx = {"is_adopted": True, "has_metrics_flag": True}
    assert folder_expectation("70_metrics", ctx).severity == Severity.CONDITIONAL


def test_00_inbox_optional():
    """00_inbox is always optional (capture is ad-hoc)."""
    ctx = {"is_adopted": True}
    assert folder_expectation("00_inbox", ctx).severity == Severity.OPTIONAL


def test_unknown_folder_optional():
    """Unknown folder defaults to OPTIONAL (defensive)."""
    ctx = {"is_adopted": True}
    assert folder_expectation("99_unknown", ctx).severity == Severity.OPTIONAL


def test_expectation_rules_cover_all_canonical_folders():
    """Sanity: 9 canonical folders all have rules defined."""
    canonical = [
        "00_inbox", "10_prd", "20_architecture", "30_adr", "35_specs",
        "40_roadmap", "50_releases", "60_customer-feedback", "70_metrics",
    ]
    for folder in canonical:
        assert folder in EXPECTATION_RULES, f"missing rule for {folder}"
