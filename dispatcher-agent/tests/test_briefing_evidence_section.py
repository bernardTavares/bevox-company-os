"""Test for "Como reportar fechamento" section in briefing template.

Background: T-0165 ficou blocked por test_inconclusive em AC1 ("LayoutPosition
suporta 9 posições") porque executor reportou só "introduced LayoutPosition
with the 9 typed positions" sem enumerar literalmente. Drafter haiku é
conservador e não pôde validar. Solução: ensinar executor a citar evidência
explícita por AC no log final.
"""
import unittest

from lib import briefing


class TestEvidenceReportingSection(unittest.TestCase):
    def _task(self):
        return {
            "id": "T-0001",
            "title": "Sample",
            "epic_id": "e1",
            "wave_ref": "e1/sample",
            "dispatch_payload": {
                "goal": "do thing",
                "acceptance_criteria": ["AC1"],
            },
        }

    def test_evidence_section_present(self):
        """Briefing inclui instruções de como reportar evidência citável."""
        out = briefing.render_briefing(self._task(), "Read,Write,Bash")
        self.assertIn("Como reportar fechamento", out)
        self.assertIn("tester-agent valida cada AC", out)

    def test_evidence_section_warns_about_inconclusive(self):
        """Seção alerta sobre risco de inconclusive."""
        out = briefing.render_briefing(self._task(), "Read,Write,Bash")
        self.assertIn("inconclusive", out)
        self.assertIn("blocked", out)

    def test_evidence_section_lists_evidence_types(self):
        """Seção cobre 5 tipos de evidência: tipos, refs, code changes, commands, AC numerado."""
        out = briefing.render_briefing(self._task(), "Read,Write,Bash")
        self.assertIn("Tipos/enums", out)
        self.assertIn("Funcoes/constantes/refs", out)
        self.assertIn("Code changes", out)
        self.assertIn("Commands rodados", out)
        self.assertIn("AC numerado", out)

    def test_evidence_section_has_concrete_example(self):
        """Seção mostra exemplo concreto com path:line + enum literal."""
        out = briefing.render_briefing(self._task(), "Read,Write,Bash")
        # Concrete example with `path:line` pattern
        self.assertIn("AC1", out)
        # Example shows literal enum values
        self.assertIn("'top-left'", out)
        # Example shows path:line citation
        self.assertIn("types/scene.ts:", out)

    def test_evidence_section_before_tools_block(self):
        """Seção aparece ANTES do bloco 'Tools permitidas' (ordem importa)."""
        out = briefing.render_briefing(self._task(), "Read,Write,Bash")
        idx_evidence = out.find("Como reportar fechamento")
        idx_tools = out.find("Tools permitidas")
        self.assertGreater(idx_evidence, 0)
        self.assertGreater(idx_tools, idx_evidence,
                           "Tools permitidas deve vir DEPOIS de Como reportar fechamento")


if __name__ == "__main__":
    unittest.main()
