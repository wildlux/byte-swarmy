"""
test_behavioral_check.py — Test unit di A2 integrato in run_direct.

Verifica che behavioral_check=True catturi cambiamenti di comportamento.
"""

from __future__ import annotations

import shutil
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from CORE.skill_executor import run_direct  # noqa: E402


class TestBehavioralCheck(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.tmp, ignore_errors=True)

    def _write(self, code: str) -> None:
        (self.tmp / "main.py").write_text(code, encoding="utf-8")

    def test_behavioral_ok(self):
        # Codice originale che stampa 42
        self._write('print("RISULTATO=42")\n')
        # Task che genera lo stesso output
        class FakeClient:
            def call(self, model_key, prompt, system=None):
                return "```python\nprint('RISULTATO=42')\n```"
        res = run_direct({"title": "stampa RISULTATO=42"}, str(self.tmp),
                         client=FakeClient(), max_retries=1,
                         behavioral_check=True)
        self.assertTrue(res["ok"])

    def test_behavioral_divergenza(self):
        # Codice originale che stampa 42
        self._write('print("RISULTATO=42")\n')
        # Task che genera output diverso
        class FakeClient:
            def call(self, model_key, prompt, system=None):
                return "```python\nprint('RISULTATO=99')\n```"
        res = run_direct({"title": "stampa RISULTATO=99"}, str(self.tmp),
                         client=FakeClient(), max_retries=1,
                         behavioral_check=True)
        self.assertFalse(res["ok"])
        self.assertIn("COMPORTAMENTO CAMBIATO", res["error"])

    def test_behavioral_no_snapshot(self):
        # Nessun file esistente → nessuno snapshot → nessuna verifica
        class FakeClient:
            def call(self, model_key, prompt, system=None):
                return "```python\nprint('RISULTATO=42')\n```"
        res = run_direct({"title": "stampa RISULTATO=42"}, str(self.tmp),
                         client=FakeClient(), max_retries=1,
                         behavioral_check=True)
        self.assertTrue(res["ok"])

    def test_behavioral_off_by_default(self):
        self._write('print("RISULTATO=42")\n')
        class FakeClient:
            def call(self, model_key, prompt, system=None):
                return "```python\nprint('RISULTATO=99')\n```"
        res = run_direct({"title": "stampa RISULTATO=99"}, str(self.tmp),
                         client=FakeClient(), max_retries=1)
        # behavioral_check=False di default → non verifica → ok=True
        self.assertTrue(res["ok"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
