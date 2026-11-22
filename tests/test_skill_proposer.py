"""
test_skill_proposer.py — Test unit di M8 (memoria dei fallimenti → skill
suggerite).

Senza LLM: classificazione firme, contatori persistenti, soglia, bozze,
approvazione/rifiuto, fail-open.
"""

from __future__ import annotations

import contextlib
import io
import shutil
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import CORE.skill_proposer as sp  # noqa: E402


class TestSkillProposer(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.tmp, ignore_errors=True)
        # redirige storage su tmp
        sp.PROPOSALS_DIR = self.tmp / "skill_proposals"
        sp.FAILURES_FILE = self.tmp / "skill_proposals" / "failures.json"
        sp.SKILLS_DIR = self.tmp / "skills"
        sp.SKILLS_DIR.mkdir(parents=True, exist_ok=True)
        # una skill base fittizia per i test di approvazione
        (sp.SKILLS_DIR / "py-cli-script.md").write_text(
            "---\nid: py-cli-script\n---\n# base\n", encoding="utf-8")

    def test_classify_failure_firme(self):
        self.assertEqual(sp.classify_failure("EOFError: EOF when reading a line",
                                            "x = input()"), "input_interattivo")
        self.assertEqual(sp.classify_failure("STATIC CHECK: {{...}} leftover",
                                            "print({{ MARKER }})"), "placeholder_copiato")
        self.assertEqual(sp.classify_failure("SyntaxError: expected 'except' or 'finally' block",
                                            "try:\n    pass"), "try_senza_except")
        self.assertEqual(sp.classify_failure("RUNTIME ERROR: output atteso mancante: SOMMA=5",
                                            "print('x')"), "marker_mancante")
        self.assertEqual(sp.classify_failure("AttributeError: 'function' object has no attribute 'media'",
                                            ""), "classe_senza_istanza")
        self.assertEqual(sp.classify_failure("NameError: name 'foo' is not defined",
                                            ""), "nome_inedito")
        self.assertEqual(sp.classify_failure("RUNTIME ERROR: timeout (loop infinito)",
                                            "while True: print(next(iter(x)))"), "loop_infinito")
        self.assertEqual(sp.classify_failure("PyCompileError: ... The output should print...",
                                            "Okay let's tackle"), "prosa_senza_fence")
        self.assertEqual(sp.classify_failure("qualcosa di ignoto", ""), "generico")

    def test_record_failure_incrementa(self):
        sp.record_failure("input_interattivo", "t1", "EOFError")
        sp.record_failure("input_interattivo", "t2", "EOFError")
        data = sp._load_failures()
        self.assertEqual(data["counts"]["input_interattivo"], 2)

    def test_soglia_crea_bozza(self):
        for i in range(2):
            sp.record_failure("input_interattivo", f"t{i}", "EOFError")
        # terza occorrenza → bozza
        pid = sp.record_failure("input_interattivo", "t2", "EOFError")
        self.assertIsNotNone(pid)
        props = sp.pending_proposals()
        self.assertEqual(len(props), 1)
        self.assertEqual(props[0]["signature"], "input_interattivo")
        self.assertTrue(Path(props[0]["path"]).exists())

    def test_sotto_soglia_niente_bozza(self):
        sp.record_failure("input_interattivo", "t1", "EOFError")
        self.assertEqual(sp.pending_proposals(), [])

    def test_approve_sposta_in_skills(self):
        for i in range(3):
            sp.record_failure("input_interattivo", f"t{i}", "EOFError")
        pid = sp.pending_proposals()[0]["id"]
        self.assertTrue(sp.approve_proposal(pid))
        # file spostato in SKILLS/
        self.assertTrue((sp.SKILLS_DIR / "py-cli-script.md").exists())
        # backup creato
        self.assertTrue((sp.SKILLS_DIR / "py-cli-script.backup.md").exists())
        # stato aggiornato
        data = sp._load_failures()
        prop = list(data["proposals"].values())[0]
        self.assertEqual(prop["status"], "approved")
        self.assertEqual(sp.pending_proposals(), [])

    def test_reject_cancella_e_resetta(self):
        for i in range(3):
            sp.record_failure("input_interattivo", f"t{i}", "EOFError")
        pid = sp.pending_proposals()[0]["id"]
        self.assertTrue(sp.reject_proposal(pid))
        # file cancellato
        self.assertFalse(Path(sp._load_failures()["proposals"]["input_interattivo"]["path"]).exists())
        # contatore resettato
        self.assertEqual(sp._load_failures()["counts"]["input_interattivo"], 0)
        self.assertEqual(sp.pending_proposals(), [])

    def test_fail_open_non_solleva(self):
        # firma sconosciuta → normalizzata a 'generico', mai eccezione
        try:
            sp.record_failure("firma_che_non_esiste", "t", "err")
        except Exception as e:
            self.fail(f"record_failure ha sollevato: {e}")
        # dir inesistente → fail-open
        sp.PROPOSALS_DIR = Path("/proc/nonexistent/deep")
        sp.FAILURES_FILE = sp.PROPOSALS_DIR / "failures.json"
        try:
            sp.record_failure("generico", "t", "err")
        except Exception as e:
            self.fail(f"record_failure (dir inesistente) ha sollevato: {e}")

    def test_pending_proposals_ignora_gestite(self):
        for i in range(3):
            sp.record_failure("input_interattivo", f"t{i}", "EOFError")
        pid = sp.pending_proposals()[0]["id"]
        sp.reject_proposal(pid)
        self.assertEqual(sp.pending_proposals(), [])

    # --- B2 (2026-11-22): gate verde = approvazione, rosso = bozza ------
    def _draft(self):
        for i in range(3):
            sp.record_failure("input_interattivo", f"t{i}", "EOFError")
        return sp.pending_proposals()[0]

    def test_gate_verde_autoapprova_con_backup_e_report(self):
        prop = self._draft()
        approved = [sp.record_skill_usage("input_interattivo", True)
                    for _ in range(3)]
        self.assertEqual(approved[-1], prop["id"])
        self.assertTrue((sp.SKILLS_DIR / "py-cli-script.md").exists())
        backup = sp.SKILLS_DIR / "py-cli-script.backup.md"
        self.assertTrue(backup.exists())
        data = sp._load_failures()
        info = data["proposals"]["input_interattivo"]
        self.assertEqual(info["status"], "approved")
        self.assertEqual(info["mode"], "auto")
        self.assertEqual(info["backup"], str(backup))
        self.assertTrue(data["gate_reports"][prop["id"]]["ok"])
        report = sp.gate_report(prop["id"])
        self.assertTrue(report.ok)
        self.assertIn("VERDE", report.markdown())
        self.assertEqual(sp.pending_proposals(), [])

    def test_gate_rosso_mantiene_bozza_e_scrive_report(self):
        prop = self._draft()
        path = Path(prop["path"])
        path.write_text(path.read_text(encoding="utf-8").replace(
            "## Template concreto", "## Template rimosso"), encoding="utf-8")
        base_before = (sp.SKILLS_DIR / "py-cli-script.md").read_text(
            encoding="utf-8")

        approved = [sp.record_skill_usage("input_interattivo", True)
                    for _ in range(3)]

        self.assertEqual(approved, [None, None, None])
        self.assertEqual(len(sp.pending_proposals()), 1)
        self.assertEqual(sp._load_failures()["proposals"]["input_interattivo"]["status"],
                         "pending")
        self.assertEqual((sp.SKILLS_DIR / "py-cli-script.md").read_text(
            encoding="utf-8"), base_before)  # nessuna sovrascrittura
        report = sp.gate_report(prop["id"])
        self.assertFalse(report.ok)
        self.assertTrue(any(r.startswith("sezioni:") for r in report.reasons()))
        self.assertIn("ROSSO", report.markdown())

    def test_gate_rifiuta_codice_pericoloso_e_sintassi_invalida(self):
        good = ("# REGOLA APPRESA\n\n## Regola\n"
                + "x" * 60 + "\n\n## Template concreto\n\n"
                "```python\nprint('ok')\n```\n")
        bad_eval = good.replace("print('ok')", "eval(input('x'))")
        bad_syntax = good.replace("print('ok')", "def x(:")

        p = self.tmp / "candidato.md"
        p.write_text(good, encoding="utf-8")
        self.assertTrue(sp.gate_proposal(str(p)).ok)
        p.write_text(bad_eval, encoding="utf-8")
        reasons = sp.gate_proposal(str(p)).reasons()
        self.assertTrue(any("chiamata vietata" in r for r in reasons))
        p.write_text(bad_syntax, encoding="utf-8")
        reasons = sp.gate_proposal(str(p)).reasons()
        self.assertTrue(any("sintassi non valida" in r for r in reasons))

    def test_gate_file_mancante_e_fail_open(self):
        report = sp.gate_proposal(str(self.tmp / "inesistente.md"))
        self.assertFalse(report.ok)
        self.assertIn("mancante", report.reasons()[0])
        self.assertIsNone(sp.gate_report("id-mai-valutato"))

    def test_fallimento_blocca_autoapprovazione(self):
        self._draft()
        outcomes = [sp.record_skill_usage("input_interattivo", True),
                    sp.record_skill_usage("input_interattivo", True),
                    sp.record_skill_usage("input_interattivo", False),
                    sp.record_skill_usage("input_interattivo", True),
                    sp.record_skill_usage("input_interattivo", True)]
        self.assertEqual(outcomes, [None] * 5)
        self.assertEqual(len(sp.pending_proposals()), 1)

    def test_cli_gate_stampa_report(self):
        prop = self._draft()
        for _ in range(3):
            sp.record_skill_usage("input_interattivo", True)
        buf = io.StringIO()
        with mock.patch.object(sys, "argv", ["skill_proposer", "--gate",
                                             prop["id"]]):
            with contextlib.redirect_stdout(buf):
                code = sp._cli()
        self.assertEqual(code, 0)
        self.assertIn("VERDE", buf.getvalue())


if __name__ == "__main__":
    unittest.main(verbosity=2)
