"""Test Cycle 65 — Generazione STADIALE dei test (regola termica).

Regola: mai generazioni LLM lunghe e monolitiche (surriscaldano il
portatile). Prima lo SCHELETRO (classe/funzioni vuote) verificato con
`pytest --collect-only`, poi SOLO i corpi. L'implementazione completa
mai in una sola generazione.

Nessun Ollama: modelli finti con risposte a coda.
"""

import sys
from pathlib import Path
from unittest.mock import MagicMock

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from CORE.test_generator import TestGenerator  # noqa: E402


class _L:
    def info(self, *a, **k):
        pass

    def warning(self, *a, **k):
        pass

    def error(self, *a, **k):
        pass

    def debug(self, *a, **k):
        pass


def _queue_models(*responses):
    """Fake models: risposte in coda + log dei prompt ricevuti."""
    m = MagicMock()
    calls = []

    def _side(*args, **kwargs):
        calls.append(kwargs.get("prompt", ""))
        return responses[len(calls) - 1]

    m.call.side_effect = _side
    m.prompts = calls
    return m


def _make_module(tmp_path):
    """Modulo sorgente con 1 funzione pubblica."""
    mod = tmp_path / "calcolo.py"
    mod.write_text("def somma(a, b):\n    return a + b\n", encoding="utf-8")
    return mod


SKELETON = (
    "import sys\n"
    "sys.path.insert(0, '{tmp}')\n"
    "from calcolo import somma\n\n"
    "def test_somma():\n    pass\n"
)
FULL = (
    "import sys\n"
    "sys.path.insert(0, '{tmp}')\n"
    "from calcolo import somma\n\n"
    "def test_somma():\n    assert somma(2, 3) == 5\n"
)


def test_stadio1_scheletro_poi_stadio2_corpi(tmp_path):
    """Flusso stadiale: 2 chiamate BREVI, la seconda riceve lo scheletro
    verificato e deve riempire solo i corpi."""
    mod = _make_module(tmp_path)
    skel = SKELETON.format(tmp=str(tmp_path))
    full = FULL.format(tmp=str(tmp_path))
    models = _queue_models(skel, full)
    tg = TestGenerator(tmp_path, models, _L())

    res = tg.generate_and_verify(str(mod), mod.read_text(encoding="utf-8"))

    assert res.startswith("OK"), f"atteso OK, ottenuto: {res}"
    # 2 stadi = 2 chiamate LLM brevi (mai 1 generazione monolitica)
    assert len(models.prompts) == 2, f"chiamate: {len(models.prompts)}"
    # Stadio 1 chiede lo scheletro vuoto
    assert "SCHELETRO" in models.prompts[0]
    assert "NIENTE corpi" in models.prompts[0]
    # Stadio 2 riceve lo scheletro verificato
    assert "SCHELETRO:" in models.prompts[1]
    assert "def test_somma" in models.prompts[1]
    # Il file finale contiene i corpi (non lo scheletro)
    tf = tmp_path / "tests" / "test_calcolo_regression.py"
    assert tf.exists()
    assert "assert somma(2, 3) == 5" in tf.read_text(encoding="utf-8")


def test_collect_check_scova_import_rotto_allo_stadio_1(tmp_path):
    """Scheletro con import rotto → errore ALLO STADIO 1, senza pagare
    la generazione dei corpi (il guasto più comune su 3B)."""
    mod = _make_module(tmp_path)
    bad_skel = (
        "from modulo_inesistente import somma\n\n"
        "def test_somma():\n    pass\n"
    )
    models = _queue_models(bad_skel, "mai usato")
    tg = TestGenerator(tmp_path, models, _L())

    res = tg.generate_and_verify(str(mod), mod.read_text(encoding="utf-8"))

    assert res.startswith("ERROR"), f"atteso ERROR, ottenuto: {res}"
    assert "scheletro test non valido" in res
    # SOLO 1 chiamata LLM: lo stadio 2 non è mai partito
    assert len(models.prompts) == 1, f"chiamate: {len(models.prompts)}"
    # Il file di test rotto non resta nel progetto utente
    assert not (tmp_path / "tests" / "test_calcolo_regression.py").exists()


def test_stadio2_altera_struttura_rifiutato(tmp_path):
    """Lo stadio 2 non può rinominare/rimuovere i test dello scheletro
    verificato."""
    mod = _make_module(tmp_path)
    skel = SKELETON.format(tmp=str(tmp_path))
    renamed = FULL.format(tmp=str(tmp_path)).replace(
        "def test_somma", "def test_somma_modificata")
    models = _queue_models(skel, renamed)
    tg = TestGenerator(tmp_path, models, _L())

    res = tg.generate_and_verify(str(mod), mod.read_text(encoding="utf-8"))

    assert res.startswith("ERROR"), res
    assert "alterato la struttura" in res
    assert not (tmp_path / "tests" / "test_calcolo_regression.py").exists()


def test_stadio2_fallito_file_rimosso(tmp_path):
    """Errore LLM allo stadio 2 → ERROR pulito, nessun file mezzo scritto."""
    mod = _make_module(tmp_path)
    skel = SKELETON.format(tmp=str(tmp_path))

    models = _queue_models(skel)  # coda: 1a chiamata OK, 2a → IndexError

    def _side(*args, **kwargs):
        models.prompts.append(kwargs.get("prompt", ""))
        try:
            return models.responses[len(models.prompts) - 1]
        except IndexError:
            raise RuntimeError("ollama giù allo stadio 2")

    models.responses = [skel]
    models.call.side_effect = _side
    tg = TestGenerator(tmp_path, models, _L())

    res = tg.generate_and_verify(str(mod), mod.read_text(encoding="utf-8"))

    assert res.startswith("ERROR"), res
    assert "stadio 2" in res
    assert not (tmp_path / "tests" / "test_calcolo_regression.py").exists()


def test_scheletro_vuoto_errore_immediato(tmp_path):
    """Stadio 1 con risposta vuota → ERROR senza scrivere nulla."""
    mod = _make_module(tmp_path)
    models = _queue_models("   ")
    tg = TestGenerator(tmp_path, models, _L())

    res = tg.generate_and_verify(str(mod), mod.read_text(encoding="utf-8"))

    assert res.startswith("ERROR"), res
    assert "scheletro vuoto" in res
    assert len(models.prompts) == 1


if __name__ == "__main__":
    import pytest
    sys.exit(pytest.main([__file__, "-q"]))
