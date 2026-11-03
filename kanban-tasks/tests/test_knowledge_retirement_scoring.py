"""Tests for retirement/scoring.py."""
from lib.knowledge_watcher.retirement import (
    CategorySignal, RetirementCategory,
)
from lib.knowledge_watcher.retirement.scoring import (
    compound_score,
    is_retirement_candidate,
    SCORE_THRESHOLD,
    CATEGORY_WEIGHTS,
)


def test_no_signals_score_zero():
    assert compound_score([]) == 0.0


def test_cat_a_alone_meets_threshold():
    """A=1.0 alone >= 0.7 threshold."""
    signals = [CategorySignal(RetirementCategory.A_MARKERS, 0.95, "x")]
    score = compound_score(signals)
    assert score >= 0.7
    assert is_retirement_candidate(signals)


def test_cat_b_alone_meets_threshold():
    """B=0.7 alone exactly at threshold."""
    signals = [CategorySignal(RetirementCategory.B_CODE_BROKEN, 0.7, "x")]
    score = compound_score(signals)
    assert score >= 0.7


def test_cat_c_alone_meets_threshold():
    """C=0.7 alone exactly at threshold."""
    signals = [CategorySignal(RetirementCategory.C_SUPERSESSION, 0.85, "x")]
    score = compound_score(signals)
    assert score >= 0.7


def test_cat_d_alone_does_not_meet():
    """D=0.4 alone < 0.7 threshold."""
    signals = [CategorySignal(RetirementCategory.D_LIFECYCLE, 0.5, "x")]
    score = compound_score(signals)
    assert score < 0.7
    assert not is_retirement_candidate(signals)


def test_cat_e_alone_does_not_meet():
    """E=0.3 alone < 0.7 threshold."""
    signals = [CategorySignal(RetirementCategory.E_ORPHAN, 0.4, "x")]
    score = compound_score(signals)
    assert score < 0.7


def test_cat_d_plus_e_meets():
    """D (0.4) + E (0.3) = 0.7 → meets."""
    signals = [
        CategorySignal(RetirementCategory.D_LIFECYCLE, 0.5, "x"),
        CategorySignal(RetirementCategory.E_ORPHAN, 0.4, "y"),
    ]
    score = compound_score(signals)
    assert score >= 0.7
    assert is_retirement_candidate(signals)


def test_multiple_signals_same_category_dont_double():
    """Two A signals don't add up — capped at category weight (max per cat)."""
    signals = [
        CategorySignal(RetirementCategory.A_MARKERS, 0.9, "x"),
        CategorySignal(RetirementCategory.A_MARKERS, 0.9, "y"),
    ]
    score = compound_score(signals)
    assert score == 1.0  # weight cap, not 2.0


def test_score_capped_at_1():
    """All 5 cats max → cap 1.0."""
    signals = [
        CategorySignal(RetirementCategory.A_MARKERS, 0.95, "a"),
        CategorySignal(RetirementCategory.B_CODE_BROKEN, 0.85, "b"),
        CategorySignal(RetirementCategory.C_SUPERSESSION, 0.9, "c"),
        CategorySignal(RetirementCategory.D_LIFECYCLE, 0.5, "d"),
        CategorySignal(RetirementCategory.E_ORPHAN, 0.4, "e"),
    ]
    score = compound_score(signals)
    assert score == 1.0


def test_threshold_constant_value():
    """SCORE_THRESHOLD = 0.7 per spec §10.3."""
    assert SCORE_THRESHOLD == 0.7


def test_category_weights_match_spec():
    """Per spec §10.3: A=1.0, B=0.7, C=0.7, D=0.4, E=0.3."""
    assert CATEGORY_WEIGHTS[RetirementCategory.A_MARKERS] == 1.0
    assert CATEGORY_WEIGHTS[RetirementCategory.B_CODE_BROKEN] == 0.7
    assert CATEGORY_WEIGHTS[RetirementCategory.C_SUPERSESSION] == 0.7
    assert CATEGORY_WEIGHTS[RetirementCategory.D_LIFECYCLE] == 0.4
    assert CATEGORY_WEIGHTS[RetirementCategory.E_ORPHAN] == 0.3


# ----- W7 doc-type-aware threshold ------------------------------------------


def test_adr_with_b_code_broken_alone_does_not_flag():
    """ADR with broken refs alone is NOT a retirement candidate.

    Decision records perdure even after referenced code moves. ADRs
    require A_markers OR C_supersession to flag.
    """
    signals = [CategorySignal(RetirementCategory.B_CODE_BROKEN, 0.85, "x")]
    assert not is_retirement_candidate(signals, doc_type="adr")
    # Same signals on default doc_type still flag
    assert is_retirement_candidate(signals)


def test_adr_with_b_plus_e_does_not_flag():
    """ADR B + E = score 1.0 but missing A/C still does not flag."""
    signals = [
        CategorySignal(RetirementCategory.B_CODE_BROKEN, 0.85, "x"),
        CategorySignal(RetirementCategory.E_ORPHAN, 0.4, "y"),
    ]
    assert compound_score(signals) == 1.0
    assert not is_retirement_candidate(signals, doc_type="adr")


def test_adr_with_a_markers_flags():
    """ADR with explicit Status: Superseded → flags."""
    signals = [CategorySignal(RetirementCategory.A_MARKERS, 0.95, "x")]
    assert is_retirement_candidate(signals, doc_type="adr")


def test_adr_with_c_supersession_flags():
    """ADR with another ADR superseding it → flags (need >=0.9 score so add B)."""
    signals = [
        CategorySignal(RetirementCategory.C_SUPERSESSION, 0.85, "x"),
        CategorySignal(RetirementCategory.B_CODE_BROKEN, 0.85, "y"),
    ]
    assert compound_score(signals) >= 0.9
    assert is_retirement_candidate(signals, doc_type="adr")


def test_architecture_with_b_alone_does_not_flag():
    """Architecture threshold is 0.8 — B alone (0.7) does not flag."""
    signals = [CategorySignal(RetirementCategory.B_CODE_BROKEN, 0.85, "x")]
    assert not is_retirement_candidate(signals, doc_type="architecture")
    # Same on default still flags
    assert is_retirement_candidate(signals)


def test_architecture_with_b_plus_e_flags():
    """Architecture B+E = 1.0 >= 0.8 threshold → flags."""
    signals = [
        CategorySignal(RetirementCategory.B_CODE_BROKEN, 0.85, "x"),
        CategorySignal(RetirementCategory.E_ORPHAN, 0.4, "y"),
    ]
    assert is_retirement_candidate(signals, doc_type="architecture")


def test_prd_with_b_alone_still_flags():
    """PRD/spec/roadmap default behavior unchanged: B alone flags."""
    signals = [CategorySignal(RetirementCategory.B_CODE_BROKEN, 0.85, "x")]
    assert is_retirement_candidate(signals, doc_type="prd")
    assert is_retirement_candidate(signals, doc_type="spec")
    assert is_retirement_candidate(signals, doc_type="roadmap")


def test_unknown_doc_type_uses_default():
    """Unknown doc_type → default 0.7 threshold, no required cats."""
    signals = [CategorySignal(RetirementCategory.B_CODE_BROKEN, 0.85, "x")]
    assert is_retirement_candidate(signals, doc_type="unknown_type")
