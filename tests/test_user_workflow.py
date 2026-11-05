# -*- coding: utf-8 -*-
"""
tests/test_user_workflow.py — workflow utente end-to-end della GUI.

Offscreen (QT_QPA_PLATFORM=offscreen). Verifica che il workflow utente
sia COMPLETAMENTE collegato, senza parti morte:

1. CONNETTIVITÀ: ogni QPushButton/QToolButton abilitato deve avere almeno
   un receiver sul segnale clicked — altrimenti è un pulsante "morto"
   (l'utente lo preme e non succede niente). Whitelist documentata per
   le eccezioni note (pulsanti interni Qt, azioni via altri segnali).
2. CARD → PANNELLO: ogni card (plancia + strumenti) apre il suo pannello
   nel detail_stack e il back_btn della pagina riporta alla Plancia.
3. TOUR VISIVO: ogni pagina viene renderizzata con grab(). Con env
   BSWARM_WORKFLOW_SHOTS=1 salva un PNG per pagina in EXPORT/workflow_shots/
   (revisione manuale del workflow).
4. CLICK SICURI: solo i pulsanti affidabili (zoom, aggiorna) vengono
   clickati davvero; gli esegui_*/deploy NON vengono clickati (lanciano
   processi reali) ma è verificata la loro connessione.

Esecuzione:
    .venv/bin/python -m pytest tests/test_user_workflow.py -v
    BSWARM_WORKFLOW_SHOTS=1 .venv/bin/python -m pytest tests/test_user_workflow.py -v
"""

from __future__ import annotations

import os
import sys
import unittest
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from PyQt6.QtWidgets import QApplication, QPushButton, QToolButton  # noqa: E402

from GUI.control_center import ControlCenter  # noqa: E402

_app = QApplication.instance() or QApplication(
    sys.argv[:1] + ["test_user_workflow"])

# Pulsanti interni di Qt (scrollbar): collegati da Qt stesso, non dal codice
# GUI. Il conteggio receiver può risultare 0 ma il comportamento è reale.
QT_INTERNAL = {"ScrollLeftButton", "ScrollRightButton"}

# Pulsanti con collegamento via segnali DIVERSI da clicked (es. pressed,
# toggled) o senza handler per scelta di design. Ogni voce va motivata.
KNOWN_UNCONNECTED = {
    # (vuoto: aggiungere qui, con motivazione, se l'audit trova eccezioni reali)
}

# Pulsanti sicuri da clickare davvero: non aprono dialog modali, non
# lanciano processi, non modificano dati.
SAFE_CLICKS = {
    "code_zoom_in", "code_zoom_out", "code_zoom_reset",  # zoom codice
    "aggiorna",                                           # refresh UI
}

_WIN = None


def _window() -> ControlCenter:
    """Istanza singola condivisa tra i test (costruzione è costosa)."""
    global _WIN
    if _WIN is None:
        _WIN = ControlCenter()
        _WIN.show()
        _app.processEvents()
    return _WIN


def _all_buttons(win) -> list:
    return (win.findChildren(QPushButton)
            + win.findChildren(QToolButton))


class TestButtonConnectivity(unittest.TestCase):
    """Nessun pulsante morto: ogni bottone abilitato deve ascoltare qualcuno."""

    def test_every_enabled_button_has_receiver(self):
        win = _window()
        dead = []
        for b in _all_buttons(win):
            if not b.isEnabled():
                continue
            name = (b.objectName()
                    or (b.text().strip()[:40] if b.text().strip() else "")
                    or type(b).__name__)
            if name in QT_INTERNAL or name in KNOWN_UNCONNECTED:
                continue
            if b.receivers(b.clicked) == 0:
                page = self._page_of(win, b)
                dead.append(f"{name} ({page})")
        self.assertEqual(
            dead, [],
            f"pulsanti senza receiver su clicked (workflow morto): {dead}")

    @staticmethod
    def _page_of(win, btn) -> str:
        """Nome della pagina (dettaglio) che contiene il pulsante."""
        p = btn.parent()
        while p is not None:
            if p.objectName() or type(p).__name__ != "QWidget":
                if p.objectName():
                    return p.objectName()
            p = p.parent()
        return "?"


class TestCardsOpenPanels(unittest.TestCase):
    """Card → pannello: nessuna card scollegata dal suo detail page."""

    def test_every_card_opens_its_panel(self):
        center = _window().center
        all_cards = {**center.cards, **center.tools_cards}
        # Ogni panel_pages deve essere raggiungibile da una card
        self.assertEqual(
            set(all_cards.keys()), set(center.panel_pages.keys()),
            "card e panel_pages disallineati: "
            f"solo-card={set(all_cards) - set(center.panel_pages)} "
            f"solo-pannello={set(center.panel_pages) - set(all_cards)}")

        for key, card in all_cards.items():
            with self.subTest(card=key):
                center.open_panel(key)
                _app.processEvents()
                self.assertEqual(center.main_stack.currentIndex(), 1,
                                 f"card '{key}': main_stack non cambia")
                self.assertIs(center.detail_stack.currentWidget(),
                              center.panel_pages[key],
                              f"card '{key}': pannello sbagliato nel detail_stack")

    def test_back_button_returns_to_plancia(self):
        center = _window().center
        for key, page in center.panel_pages.items():
            with self.subTest(panel=key):
                center.open_panel(key)
                _app.processEvents()
                backs = [b for b in page.findChildren(QPushButton)
                         if b.objectName() == "back_btn"]
                self.assertTrue(
                    backs, f"pannello '{key}': nessun back_btn nella pagina")
                backs[0].click()
                _app.processEvents()
                self.assertEqual(
                    center.main_stack.currentIndex(), 0,
                    f"pannello '{key}': back_btn non torna alla Plancia")


class TestPageTour(unittest.TestCase):
    """Tour visivo: ogni pagina renderizza senza crash; PNG opzionali."""

    def test_every_page_renders(self):
        win = _window()
        center = win.center
        shots_dir = None
        if os.environ.get("BSWARM_WORKFLOW_SHOTS", "").strip() == "1":
            shots_dir = ROOT / "EXPORT" / "workflow_shots"
            shots_dir.mkdir(parents=True, exist_ok=True)

        tour = [("plancia", 0, None)]
        tour += [(k, 1, center.panel_pages[k]) for k in center.panel_pages]

        for name, main_idx, page in tour:
            with self.subTest(page=name):
                center.main_stack.setCurrentIndex(main_idx)
                if page is not None:
                    center.detail_stack.setCurrentWidget(page)
                _app.processEvents()
                pm = win.grab()
                self.assertFalse(pm.isNull(), f"pagina '{name}': grab nullo")
                self.assertGreater(pm.width(), 100, f"pagina '{name}': troppo piccola")
                if shots_dir is not None:
                    pm.save(str(shots_dir / f"{name}.png"))

        center.back_to_main()
        _app.processEvents()

    def test_safe_buttons_click(self):
        win = _window()
        center = win.center
        clicked = 0
        for b in _all_buttons(win):
            if b.objectName() in SAFE_CLICKS and b.isEnabled():
                b.click()          # non deve lanciare nulla di crashabile
                _app.processEvents()
                clicked += 1
        self.assertGreaterEqual(clicked, 3,
                                f"pulsanti sicuri clickati: {clicked} (attesi >= 3)")


class TestToolbarToggle(unittest.TestCase):
    """Il pulsante ▶/⏸ della toolbar è collegato e fa la pausa REALE."""

    def test_toggle_pauses_and_resumes(self):
        center = _window()
        btn = center.device_panel.toggle_btn
        flag = ROOT / "state" / "pause.flag"
        self.assertEqual(btn.text(), "▶",
                         "stato iniziale atteso: orchestratore attivo")
        try:
            btn.click()
            _app.processEvents()
            self.assertEqual(btn.text(), "⏸", "dopo 1° click: in pausa")
            self.assertTrue(flag.exists(),
                            "dopo 1° click deve esistere state/pause.flag")

            btn.click()
            _app.processEvents()
            self.assertEqual(btn.text(), "▶", "dopo 2° click: ripreso")
            self.assertFalse(flag.exists(),
                             "dopo 2° click il flag deve essere rimosso")
        finally:
            flag.unlink(missing_ok=True)
            if btn.text() != "▶":
                btn.click()
                _app.processEvents()


if __name__ == "__main__":
    unittest.main(verbosity=2)
