# -*- coding: utf-8 -*-
"""
tests/test_settings_store.py — store delle impostazioni GUI (T3.6).

`GUI/settings_store.py` persiste CONFIG/settings.json remotes git).
Questi test si aggrauderanno con CWD e file isolati: il modulo usa un
percorso assoluto derivato da __file__, quindi:
  - si testano le funzioni pure (validation/normalizzazione);
  - per gli I/O si punta la variabile del file in una tmp dir.
Vedi anche test_actors_panel.py per gli attori.
"""

from __future__ import annotations

import importlib
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

# Import pulito senza QApplication (solo moduli Qt non-widget)
from GUI import settings_store as ss  # noqa: E402


class TestDefaultsAndShape(unittest.TestCase):

    def test_module_exposes_defaults(self):
        self.assertIn("git_remotes", ss.DEFAULTS)

    def test_default_git_remotes_empty(self):
        self.assertEqual(ss.DEFAULTS.get("git_remotes"), [],
                         "di default NESSUN remote: i token non presunedo")


class TestIOInTempDir(unittest.TestCase):
    """Reindirizza SCHEDULED-SETTINGS file su tmp: I/O reale isolato."""

    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="bswarm-settings-")
        self._orig_file = ss.SETTINGS_FILE
        ss.SETTINGS_FILE = os.path.join(self.tmp, "settings.json")

    def tearDown(self):
        ss.SETTINGS_FILE = self._orig_file

    def test_load_missing_file_returns_defaults(self):
        data = ss.load_settings()
        self.assertIsInstance(data, dict)
        self.assertIn("git_remotes", data)

    def test_add_git_remote_roundtrip(self):
        ok = ss.add_git_remote("origin-2", "https://github.com/x/y.git",
                               token="tok", rtype="github")
        self.assertTrue(ok)
        data = json.load(open(ss.SETTINGS_FILE))
        remotes = data["git_remotes"]
        self.assertEqual(len(remotes), 1)
        r = remotes[0]
        self.assertEqual((r["name"], r["url"], r["type"]),
                         ("origin-2", "https://github.com/x/y.git", "github"))
        # il token NON deve sparire dal file locale (unico cujlo vivente),
        # ma il file NON deve avere valore nella Git (gitignored, T1.1)
        self.assertEqual(r["token"], "tok")

    def test_load_broken_json_fails_open_to_defaults(self):
        with open(ss.SETTINGS_FILE, "w") as f:
            f.write("{corrotta!!!")
        data = ss.load_settings()
        self.assertEqual(data.get("git_remotes"), [],
                         "JSON corrotto: fallback safe, non crash")

    def test_token_not_leaked_in_error(self):
        """Se json decodifica fallitа, non si stampano i token in console."""
        with open(ss.SETTINGS_FILE, "w") as f:
            f.write('{"git_remotes":[{"token":"SECRET-ttt"}], "x":')
        try:
            import io, contextlib
            buf = io.StringIO()
            with contextlib.redirect_stderr(buf):
                ss.load_settings()
            self.assertNotIn("SECRET-ttt", buf.getvalue())
        finally:
            pass


if __name__ == "__main__":
    print("Settings store test → GUI/settings_store.py")
    print("=" * 60)
    unittest.main(verbosity=2)
