"""Testes dependency_resolver (wave-6): build_phase_sequence, apply_overrides,
detect_cycles, resolve orchestration."""
import unittest

from lib import dependency_resolver as resolver


def _t(label, phase_num, depends=None):
    """Helper: constroi task dict mínimo para resolver."""
    return {"label": label, "phase_num": phase_num, "depends": depends or []}


class TestBuildPhaseSequenceDeps(unittest.TestCase):
    def test_single_phase_no_deps(self):
        tasks = [_t("Task 1.1", 1), _t("Task 1.2", 1)]
        deps = resolver.build_phase_sequence_deps(tasks)
        self.assertEqual(deps["Task 1.1"], [])
        self.assertEqual(deps["Task 1.2"], [])

    def test_two_phases_last_of_previous_is_pred(self):
        tasks = [
            _t("Task 1.1", 1), _t("Task 1.2", 1),
            _t("Task 2.1", 2), _t("Task 2.2", 2),
        ]
        deps = resolver.build_phase_sequence_deps(tasks)
        self.assertEqual(deps["Task 1.1"], [])
        self.assertEqual(deps["Task 1.2"], [])
        self.assertEqual(deps["Task 2.1"], ["Task 1.2"])
        self.assertEqual(deps["Task 2.2"], ["Task 1.2"])

    def test_three_phases_chain(self):
        tasks = [
            _t("Task 1.1", 1),
            _t("Task 2.1", 2),
            _t("Task 3.1", 3),
        ]
        deps = resolver.build_phase_sequence_deps(tasks)
        self.assertEqual(deps["Task 1.1"], [])
        self.assertEqual(deps["Task 2.1"], ["Task 1.1"])
        self.assertEqual(deps["Task 3.1"], ["Task 2.1"])


class TestApplyOverrides(unittest.TestCase):
    def test_hybrid_preserves_defaults_when_no_override(self):
        tasks = [_t("Task 1.1", 1), _t("Task 2.1", 2)]
        base = {"Task 1.1": [], "Task 2.1": ["Task 1.1"]}
        result = resolver.apply_overrides(base, tasks, mode="hybrid")
        self.assertEqual(result["Task 2.1"], ["Task 1.1"])

    def test_hybrid_override_replaces_default(self):
        tasks = [
            _t("Task 1.1", 1),
            _t("Task 2.1", 2, depends=["Task 1.1", "Task 3.2"]),
        ]
        base = {"Task 1.1": [], "Task 2.1": ["Task 1.1"]}
        result = resolver.apply_overrides(base, tasks, mode="hybrid")
        self.assertEqual(sorted(result["Task 2.1"]), ["Task 1.1", "Task 3.2"])

    def test_phase_sequence_mode_ignores_overrides(self):
        tasks = [
            _t("Task 1.1", 1),
            _t("Task 2.1", 2, depends=["Task 99.9"]),
        ]
        base = {"Task 1.1": [], "Task 2.1": ["Task 1.1"]}
        result = resolver.apply_overrides(base, tasks, mode="phase-sequence")
        self.assertEqual(result["Task 2.1"], ["Task 1.1"])

    def test_explicit_mode_requires_override_raises(self):
        tasks = [
            _t("Task 1.1", 1, depends=["Task 0.1"]),
            _t("Task 2.1", 2),
        ]
        with self.assertRaises(ValueError) as ctx:
            resolver.apply_overrides(
                {"Task 1.1": [], "Task 2.1": ["Task 1.1"]},
                tasks, mode="explicit")
        self.assertIn("Task 2.1", str(ctx.exception))

    def test_explicit_mode_first_task_can_have_empty_override(self):
        """Task 1.1 pode nao ter override se base tinha deps vazias (first)."""
        tasks = [_t("Task 1.1", 1, depends=[])]
        result = resolver.apply_overrides({"Task 1.1": []}, tasks, mode="explicit")
        self.assertEqual(result.get("Task 1.1", []), [])


class TestDetectCycles(unittest.TestCase):
    def test_no_cycle_linear(self):
        deps = {"A": [], "B": ["A"], "C": ["B"]}
        self.assertEqual(resolver.detect_cycles(deps), [])

    def test_self_cycle(self):
        deps = {"A": ["A"]}
        cycle = resolver.detect_cycles(deps)
        self.assertTrue(cycle)
        self.assertIn("A", cycle)

    def test_two_node_cycle(self):
        deps = {"A": ["B"], "B": ["A"]}
        cycle = resolver.detect_cycles(deps)
        self.assertTrue(cycle)
        self.assertIn("A", cycle)
        self.assertIn("B", cycle)

    def test_three_node_cycle(self):
        deps = {"A": ["B"], "B": ["C"], "C": ["A"]}
        cycle = resolver.detect_cycles(deps)
        self.assertTrue(cycle)


class TestResolve(unittest.TestCase):
    def test_hybrid_happy_path(self):
        tasks = [
            _t("Task 1.1", 1),
            _t("Task 2.1", 2),
            _t("Task 2.2", 2, depends=["Task 1.1"]),
        ]
        result = resolver.resolve(tasks, mode="hybrid")
        self.assertEqual(result["Task 1.1"], [])
        self.assertEqual(result["Task 2.1"], ["Task 1.1"])
        self.assertEqual(result["Task 2.2"], ["Task 1.1"])

    def test_resolve_cycle_raises(self):
        tasks = [
            _t("Task 1.1", 1, depends=["Task 2.1"]),
            _t("Task 2.1", 2, depends=["Task 1.1"]),
        ]
        with self.assertRaises(resolver.CycleDetectedError):
            resolver.resolve(tasks, mode="hybrid")


if __name__ == "__main__":
    unittest.main()
