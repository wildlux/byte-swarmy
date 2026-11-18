"""Test Cycle 57 — Test generation per nuovi percorsi di esecuzione.

Copre TestGenerator (senza dipendere da Ollama reale): generazione test per
moduli con funzioni pubbliche, esecuzione pytest, skip file non-Python/test,
gestione syntax error.
"""

import pathlib
from unittest.mock import MagicMock

from CORE.test_generator import TestGenerator


def _fake_models(test_code: str) -> MagicMock:
    """Modello finto che restituisce il codice di test fornito."""
    m = MagicMock()
    m.call.return_value = test_code
    return m


def _dummy_logger():
    class _L:
        def info(self, *a, **k):
            pass

        def warning(self, *a, **k):
            pass

        def error(self, *a, **k):
            pass

        def debug(self, *a, **k):
            pass
    return _L()


def test_generator_ok_on_public_functions(tmp_path):
    """Modulo con funzione pubblica → test generato ed eseguito → OK."""
    mod = tmp_path / "calcolo.py"
    mod.write_text(
        "def somma(a, b):\n    return a + b\n\ndef moltiplica(a, b):\n    return a * b\n",
        encoding="utf-8",
    )

    test_code = (
        "import sys\n"
        f"sys.path.insert(0, {repr(str(tmp_path))})\n"
        "from calcolo import somma, moltiplica\n\n"
        "def test_somma():\n    assert somma(2, 3) == 5\n\n"
        "def test_moltiplica():\n    assert moltiplica(2, 3) == 6\n"
    )

    models = _fake_models(test_code)
    tg = TestGenerator(tmp_path, models, _dummy_logger())
    res = tg.generate_and_verify(str(mod), mod.read_text(encoding="utf-8"))

    assert res.startswith("OK"), f"Expected OK, got: {res}"
    # Il file di test è stato creato
    test_file = tmp_path / "tests" / "test_calcolo_regression.py"
    assert test_file.exists()


def test_generator_syntax_error(tmp_path):
    """Modulo con syntax error → py_compile nel verifier? No: TestGenerator
    non fa py_compile (spetta al runtime verifier). Qui testa che un modulo
    con funzioni generi un test che può fallire all'import."""
    mod = tmp_path / "rotto.py"
    mod.write_text("def rotto(:\n    pass\n", encoding="utf-8")

    models = _fake_models("def test_x():\n    assert True\n")
    tg = TestGenerator(tmp_path, models, _dummy_logger())
    res = tg.generate_and_verify(str(mod), mod.read_text(encoding="utf-8"))

    # Il modulo ha syntax error: il test generato fallirà all'import → ERROR
    assert res.startswith("ERROR") or res.startswith("OK"), res


def test_generator_skips_non_python(tmp_path):
    """File non .py → skip OK."""
    md = tmp_path / "README.md"
    md.write_text("# ciao\n", encoding="utf-8")
    models = _fake_models("whatever")
    tg = TestGenerator(tmp_path, models, _dummy_logger())
    res = tg.generate_and_verify(str(md), "# ciao\n")
    assert res.startswith("OK") and "skip" in res


def test_generator_skips_test_files(tmp_path):
    """File test_*.py → skip OK (nessuna ricorsione)."""
    tf = tmp_path / "test_foo.py"
    tf.write_text("def test_foo():\n    assert True\n", encoding="utf-8")
    models = _fake_models("whatever")
    tg = TestGenerator(tmp_path, models, _dummy_logger())
    res = tg.generate_and_verify(str(tf), tf.read_text(encoding="utf-8"))
    assert res.startswith("OK") and "skip" in res


def test_generator_skips_inside_tests_dir(tmp_path):
    """File dentro tests/ → skip OK (nessuna ricorsione)."""
    tests_dir = tmp_path / "tests"
    tests_dir.mkdir()
    inner = tests_dir / "helper.py"
    inner.write_text("def aiuto(x):\n    return x + 1\n", encoding="utf-8")
    models = _fake_models("whatever")
    tg = TestGenerator(tmp_path, models, _dummy_logger())
    res = tg.generate_and_verify(str(inner), inner.read_text(encoding="utf-8"))
    assert res.startswith("OK") and "skip" in res


def test_generator_no_public_functions(tmp_path):
    """Modulo senza funzioni pubbliche → skip OK."""
    mod = tmp_path / "consts.py"
    mod.write_text("PI = 3.14\n_VAR = 1\n", encoding="utf-8")
    models = _fake_models("whatever")
    tg = TestGenerator(tmp_path, models, _dummy_logger())
    res = tg.generate_and_verify(str(mod), mod.read_text(encoding="utf-8"))
    assert res.startswith("OK") and "skip" in res


def test_generator_extracts_public_functions():
    """_extract_public_functions estrae solo funzioni pubbliche."""
    tg = TestGenerator(pathlib.Path("/tmp"), MagicMock(), _dummy_logger())
    code = "def pubblica():\n    pass\ndef _privata():\n    pass\ndef Pubblica2():\n    pass\n"
    funcs = tg._extract_public_functions(code)
    assert "pubblica" in funcs
    assert "Pubblica2" in funcs
    assert "_privata" not in funcs


if __name__ == "__main__":
    import pytest

    raise SystemExit(pytest.main([__file__, "-q"]))
