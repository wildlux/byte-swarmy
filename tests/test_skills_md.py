"""Test: le skill operative (.opencode/skill/*/SKILL.md) sono ben formate.

Covers: presenza almeno una skill, frontmatter name+description, e presenza
di almeno un raggruppamento di sezione Markdown nel body.
"""

import re
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

SKILLS_DIR = ROOT / ".opencode" / "skill"


def _skill_files() -> list:
    if not SKILLS_DIR.is_dir():
        return []
    return sorted(SKILLS_DIR.glob("*/SKILL.md"))


class TestSkillsMd(unittest.TestCase):
    def test_almeno_un_skill_riguardata(self):
        self.assertTrue(
            _skill_files(),
            "nessuna skill trovata in .opencode/skill/",
        )

    def test_ogni_skill_ha_frontmatter_name_e_description(self):
        files = _skill_files()
        self.assertTrue(files)
        for f in files:
            text = f.read_text(encoding="utf-8")
            m = re.match(r"^---\s*\n(.*?)\n---\s*\n", text, re.DOTALL)
            self.assertIsNotNone(m, f"{f}: frontmatter mancante")
            fm = m.group(1)
            self.assertIn("name:", fm, f"{f}: frontmatter senza name")
            self.assertIn(
                "description:", fm, f"{f}: frontmatter senza description",
            )

    def test_ogni_skill_ha_almeno_un_raggruppamento_sezionale(self):
        files = _skill_files()
        self.assertTrue(files)
        for f in files:
            text = f.read_text(encoding="utf-8")
            self.assertIn("## ", text, f"{f}: nessun heading di sezione")


if __name__ == "__main__":
    unittest.main()
