"""Fixture condivise per la suite — Qt sempre offscreen, un solo QApplication.

Il platform viene impostato in fase di import di ``conftest.py``, quindi prima
che i moduli di test importino PyQt6. Elimina i ``QApplication`` duplicati a
livello modulo (causa di abort in ``test_theme_sync.py``).
"""

from __future__ import annotations

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest  # noqa: E402


@pytest.fixture(scope="session", autouse=True)
def qapp():
    """QApplication singleton, riutilizzato da tutti i test GUI."""
    from PyQt6.QtWidgets import QApplication

    app = QApplication.instance() or QApplication([])
    yield app
