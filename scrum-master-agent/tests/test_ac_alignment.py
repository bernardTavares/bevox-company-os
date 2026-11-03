"""Tests for ac_alignment heuristic.

Spec: bevox-knowledge/35_specs/openclaw/2026-05-07-task-ac-alignment-by-task-type-v1.md
T-0186 — Phase-1 Task 1.1.
"""
import unittest

from lib import ac_alignment


# ------------------------------------------------------------
# Fixtures: padroes do spec + caso T-0174
# ------------------------------------------------------------

DOCUMENTAL_TASK_T0174_LIKE = {
    "task_num": "1.1",
    "task_subject": "Consolidar a direção canônica da experiência mobile",
    "body": (
        "Esta task deve **consolidar** a spec, **definir** o "
        "breakpoint canônico e **mapear** os edge cases."
    ),
    # AC misto: 1 documental adequado, 1 de runtime (caso T-0174).
    "expected": [
        "a spec declara explicitamente que a experiência mobile dedicada "
        "é exclusiva do cenário abaixo do breakpoint",
        "a superfície desktop continua renderizando a experiência atual "
        "sem regressão estrutural",
    ],
}

PURE_IMPLEMENTATION_TASK = {
    "task_num": "2.1",
    "task_subject": "Integrar selector e router pro novo bundle",
    "body": "Implementacao de runtime; trocar componentes.",
    "expected": [
        "a aplicação seleciona a superfície mobile abaixo do breakpoint",
        "o bundle mobile não é carregado em desktop",
    ],
}

PURE_DOCUMENTAL_TASK = {
    "task_num": "1.2",
    "task_subject": "Documentar política canônica de fallback",
    "body": "Consolidar a regra; congelar a política; mapear edge cases.",
    "expected": [
        "a política canônica congela que o fallback fica delegado para QA",
        "casos ambíguos ficam mapeados sem bloquear implementação",
    ],
}


class TestSignalsInText(unittest.TestCase):
    """Helper de match e estavel e tolerante a variacoes minimas."""

    def test_matches_word_boundary(self):
        hits = ac_alignment._signals_in_text(
            "a aplicação renderiza tudo certo",
            ac_alignment.RUNTIME_AC_SIGNALS,
        )
        self.assertIn("renderiza", hits)

    def test_matches_multiword_phrase(self):
        hits = ac_alignment._signals_in_text(
            "a página continua acessível em desktop",
            ac_alignment.RUNTIME_AC_SIGNALS,
        )
        self.assertIn("continua acessível", hits)

    def test_case_insensitive(self):
        hits = ac_alignment._signals_in_text(
            "MONTA o componente, EXIBE o card",
            ac_alignment.RUNTIME_AC_SIGNALS,
        )
        self.assertIn("monta", hits)
        self.assertIn("exibe", hits)

    def test_no_match_on_unrelated_text(self):
        hits = ac_alignment._signals_in_text(
            "implementar feature de pagamento",
            ac_alignment.DOCUMENTAL_TASK_SIGNALS,
        )
        self.assertEqual(hits, [])

    def test_empty_input_safe(self):
        self.assertEqual(
            ac_alignment._signals_in_text("", ac_alignment.RUNTIME_AC_SIGNALS),
            [],
        )


class TestClassifyTaskType(unittest.TestCase):
    def test_documental_task_detected_via_subject(self):
        out = ac_alignment.classify_task_type({
            "task_subject": "Consolidar a regra canônica",
            "body": "",
            "expected": [],
        })
        self.assertEqual(out["task_type"], "documental")
        self.assertIn("consolidar", out["documental_signals"])

    def test_documental_task_detected_via_body(self):
        out = ac_alignment.classify_task_type({
            "task_subject": "task generica",
            "body": "Esta task deve **mapear** edge cases e **registrar**.",
            "expected": [],
        })
        self.assertEqual(out["task_type"], "documental")
        self.assertIn("mapear", out["documental_signals"])
        self.assertIn("registrar", out["documental_signals"])

    def test_unknown_when_no_signals(self):
        out = ac_alignment.classify_task_type({
            "task_subject": "Integrar selector e router",
            "body": "Implementacao de runtime",
            "expected": [],
        })
        self.assertEqual(out["task_type"], "unknown")
        self.assertEqual(out["documental_signals"], [])


class TestDetectAcAlignmentT0174Case(unittest.TestCase):
    """AC1 — heuristica detecta desalinhamento entre natureza documental
    e linguagem funcional. Caso motivador T-0174."""

    def test_t0174_pattern_flagged(self):
        out = ac_alignment.detect_ac_alignment(DOCUMENTAL_TASK_T0174_LIKE)
        self.assertEqual(out["task_type"], "documental")
        self.assertTrue(out["has_mismatch"])
        self.assertEqual(len(out["mismatches"]), 1)

    def test_t0174_pattern_flags_correct_ac(self):
        out = ac_alignment.detect_ac_alignment(DOCUMENTAL_TASK_T0174_LIKE)
        m = out["mismatches"][0]
        # AC suspeito e o de indice 1 (runtime), nao o 0 (documental).
        self.assertEqual(m["ac_index"], 1)
        self.assertIn("renderizando", m["ac_text"])

    def test_t0174_runtime_signals_listed(self):
        out = ac_alignment.detect_ac_alignment(DOCUMENTAL_TASK_T0174_LIKE)
        m = out["mismatches"][0]
        # "renderiza" deve aparecer (aceita sufixos via word-boundary)
        self.assertIn("renderiza", m["runtime_signals"])

    def test_documental_ac_not_flagged(self):
        out = ac_alignment.detect_ac_alignment(DOCUMENTAL_TASK_T0174_LIKE)
        flagged_indices = [m["ac_index"] for m in out["mismatches"]]
        # AC 0 e linguagem documental adequada -> nao flagged
        self.assertNotIn(0, flagged_indices)


class TestDetectionPointsToTaskAndAc(unittest.TestCase):
    """AC2 — resultado aponta qual task e qual AC sao suspeitos."""

    def test_result_includes_task_num(self):
        out = ac_alignment.detect_ac_alignment(DOCUMENTAL_TASK_T0174_LIKE)
        self.assertEqual(out["task_num"], "1.1")

    def test_result_includes_task_subject(self):
        out = ac_alignment.detect_ac_alignment(DOCUMENTAL_TASK_T0174_LIKE)
        self.assertIn("consolidar", out["task_subject"].lower())

    def test_mismatch_includes_ac_index_and_text(self):
        out = ac_alignment.detect_ac_alignment(DOCUMENTAL_TASK_T0174_LIKE)
        m = out["mismatches"][0]
        self.assertIn("ac_index", m)
        self.assertIn("ac_text", m)
        self.assertIsInstance(m["ac_index"], int)
        self.assertIsInstance(m["ac_text"], str)

    def test_mismatch_reason_mentions_documental_and_runtime(self):
        out = ac_alignment.detect_ac_alignment(DOCUMENTAL_TASK_T0174_LIKE)
        reason = out["mismatches"][0]["reason"]
        self.assertIn("documental", reason)
        self.assertIn("runtime", reason)


class TestHeuristicStaysHeuristic(unittest.TestCase):
    """AC3 — v1 permanece heuristica e util, sem exigir classificacao
    perfeita."""

    def test_pure_documental_task_no_mismatch(self):
        out = ac_alignment.detect_ac_alignment(PURE_DOCUMENTAL_TASK)
        self.assertEqual(out["task_type"], "documental")
        self.assertFalse(out["has_mismatch"])
        self.assertEqual(out["mismatches"], [])

    def test_implementation_task_skipped_by_v1(self):
        """v1 NAO avalia tasks nao-documentais — nao gera ruido."""
        out = ac_alignment.detect_ac_alignment(PURE_IMPLEMENTATION_TASK)
        self.assertEqual(out["task_type"], "unknown")
        self.assertFalse(out["has_mismatch"])

    def test_empty_expected_no_crash(self):
        out = ac_alignment.detect_ac_alignment({
            "task_num": "9.9",
            "task_subject": "Documentar coisa",
            "body": "consolidar X",
            "expected": [],
        })
        self.assertEqual(out["mismatches"], [])
        self.assertFalse(out["has_mismatch"])

    def test_missing_fields_safe(self):
        """Shape ausente nao quebra; retorna estrutura zero-mismatch."""
        out = ac_alignment.detect_ac_alignment({})
        self.assertEqual(out["task_num"], "")
        self.assertEqual(out["task_type"], "unknown")
        self.assertEqual(out["mismatches"], [])

    def test_runtime_signal_in_documental_ac_ignored_with_unknown_task(self):
        """Mesmo AC com `renderiza`, se a task nao for documental, nao
        flagga (heuristica conservadora)."""
        out = ac_alignment.detect_ac_alignment({
            "task_num": "2.2",
            "task_subject": "Integrar selector",
            "body": "implementacao runtime",
            "expected": ["a aplicação renderiza"],
        })
        self.assertFalse(out["has_mismatch"])


class TestPlanLevelDetection(unittest.TestCase):
    """Helper convenience: rodar deteccao em todo o plan parseado."""

    def test_detect_for_plan_returns_one_entry_per_task(self):
        parsed = {
            "tasks": [
                DOCUMENTAL_TASK_T0174_LIKE,
                PURE_IMPLEMENTATION_TASK,
                PURE_DOCUMENTAL_TASK,
            ],
        }
        results = ac_alignment.detect_ac_alignment_for_plan(parsed)
        self.assertEqual(len(results), 3)

    def test_detect_for_plan_flags_only_t0174_like(self):
        parsed = {
            "tasks": [
                DOCUMENTAL_TASK_T0174_LIKE,
                PURE_IMPLEMENTATION_TASK,
                PURE_DOCUMENTAL_TASK,
            ],
        }
        results = ac_alignment.detect_ac_alignment_for_plan(parsed)
        flagged = [r for r in results if r["has_mismatch"]]
        self.assertEqual(len(flagged), 1)
        self.assertEqual(flagged[0]["task_num"], "1.1")

    def test_detect_for_empty_plan_safe(self):
        results = ac_alignment.detect_ac_alignment_for_plan({"tasks": []})
        self.assertEqual(results, [])

    def test_detect_for_missing_tasks_key_safe(self):
        results = ac_alignment.detect_ac_alignment_for_plan({})
        self.assertEqual(results, [])


class TestSignalCoverage(unittest.TestCase):
    """Sanity: todos os signals canonicos da spec estao na constante."""

    def test_documental_signals_complete(self):
        for required in [
            "consolidar", "definir", "congelar", "modelar",
            "mapear", "documentar", "registrar", "alinhar canonicamente",
        ]:
            self.assertIn(required, ac_alignment.DOCUMENTAL_TASK_SIGNALS)

    def test_runtime_signals_complete(self):
        for required in [
            "renderiza", "funciona", "carrega", "monta", "exibe",
            "continua acessível", "seleciona em runtime",
            "valida visualmente",
        ]:
            self.assertIn(required, ac_alignment.RUNTIME_AC_SIGNALS)


if __name__ == "__main__":
    unittest.main()
