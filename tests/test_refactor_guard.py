"""
test_refactor_guard.py — E1: gate deterministico per refactoring.
8 refactoring atomici devono restare verdi; 4 casi negativi devono essere
bloccati. Nessun LLM, nessuna rete: i file sono temporanei.
"""
from __future__ import annotations

import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from tools.refactor_guard import check_refactor  # noqa: E402

BEFORE = '''"""Modulo di esempio."""
FACTOR = 2


def area(width, height):
    """Area del rettangolo."""
    return width * height


def label(name):
    return "item:" + name


if __name__ == "__main__":
    print(area(FACTOR, 3), label("x"))
'''

# 8 trasformazioni atomiche: nessuna cambia API pubblica o output.
AFTER_CASES = [
    ("type hints", BEFORE.replace("def area(width, height):",
                                  "def area(width: int, height: int) -> int:")
     .replace("def label(name):", "def label(name: str) -> str:")),
    ("docstring", BEFORE.replace('    return "item:" + name',
                                '    """Etichetta l\'elemento."""\n'
                                '    return "item:" + name')),
    ("helper privato", BEFORE.replace(
        "def area(width, height):\n    \"\"\"Area del rettangolo.\"\"\"\n"
        "    return width * height",
        "def _mul(a, b):\n    return a * b\n\n\ndef area(width, height):\n"
        "    \"\"\"Area del rettangolo.\"\"\"\n    return _mul(width, height)")),
    ("rinomina locali", BEFORE.replace(
        "    return width * height", "    w, h = width, height\n    return w * h")),
    ("f-string", BEFORE.replace('return "item:" + name',
                                'return f"item:{name}"')),
    ("costante", BEFORE.replace('FACTOR = 2',
                                'FACTOR = 2\nPREFIX = "item:"')
     .replace('return "item:" + name', 'return PREFIX + name')),
    ("stdout esplicito", BEFORE.replace(
        '    print(area(FACTOR, 3), label("x"))',
        '    import sys\n    sys.stdout.write(area(FACTOR, 3).__str__()'
        ' + " " + label("x") + "\\n")')),
    ("__all__", BEFORE.replace('FACTOR = 2',
                               'FACTOR = 2\n__all__ = ["area", "label"]')),
]


def _write(tmp, name, text):
    p = tmp / name
    p.write_text(text, encoding="utf-8")
    return p


def test_otto_refactoring_atomici_restano_verdi():
    with tempfile.TemporaryDirectory() as d:
        tmp = Path(d)
        before = _write(tmp, "before.py", BEFORE)
        for name, after_src in AFTER_CASES:
            after = _write(tmp, "after.py", after_src)
            report = check_refactor(before, after)
            assert report.status == "OK", (name, report.to_dict())
            assert not report.blocking, name
            assert report.behavior_ok, name


def test_comportamento_cambiato_blocca():
    with tempfile.TemporaryDirectory() as d:
        tmp = Path(d)
        before = _write(tmp, "before.py", BEFORE)
        after = _write(tmp, "after.py", BEFORE.replace("FACTOR = 2",
                                                       "FACTOR = 3"))
        report = check_refactor(before, after)
        assert report.status == "FAIL"
        assert not report.behavior_ok
        assert "COMPORTAMENTO CAMBIATO" in report.behavior_diff


def test_api_pubblica_rimossa_blocca():
    with tempfile.TemporaryDirectory() as d:
        tmp = Path(d)
        before = _write(tmp, "before.py", BEFORE)
        after = _write(tmp, "after.py", BEFORE.replace("def label(name):",
                                                       "def describe(name):")
                       .replace('label("x")', 'describe("x")'))
        report = check_refactor(before, after)
        assert report.status == "FAIL"
        assert any(c.kind in ("removed", "changed") for c in report.blocking)


def test_sintassi_invalida_e_file_mancante_bloccano():
    with tempfile.TemporaryDirectory() as d:
        tmp = Path(d)
        before = _write(tmp, "before.py", BEFORE)
        after = _write(tmp, "after.py", "def area(:\n")
        assert check_refactor(before, after).status == "FAIL"
        assert check_refactor(before, tmp / "assente.py").status == "FAIL"


def test_snapshot_non_conclusivo_e_warn_fail_open():
    src = BEFORE.replace('    print(area(FACTOR, 3), label("x"))',
                         '    raise SystemExit("non eseguibile")')
    with tempfile.TemporaryDirectory() as d:
        tmp = Path(d)
        before = _write(tmp, "before.py", src)
        after = _write(tmp, "after.py", src)
        report = check_refactor(before, after)
        assert report.status == "WARN"
        assert report.behavior_conclusive is False


def test_report_markdown_e_json():
    with tempfile.TemporaryDirectory() as d:
        tmp = Path(d)
        before = _write(tmp, "before.py", BEFORE)
        after = _write(tmp, "after.py", AFTER_CASES[0][1])
        report = check_refactor(before, after)
        md = report.markdown()
        assert "Refactor Guard" in md
        assert "`OK`" in md
        data = report.to_dict()
        assert data["status"] == "OK"
        assert data["api_changes"] == []
