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

import logging
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


class TestThemeLiveSwitch(unittest.TestCase):
    """Il tema scelto (10+ temi) si applica LIVE e resta persistito."""

    def test_combo_has_light_and_dark_groups(self):
        panel = _window().center.panel_pages["config"]
        combo = panel.theme_combo
        headers = [combo.itemText(i) for i in range(combo.count())
                   if combo.itemData(i) is None
                   and combo.itemText(i).startswith("—")]
        self.assertEqual(headers, ["— Temi chiari —", "— Temi scuri —"])

    def test_switch_via_combo_applies_live(self):
        """Percorso utente reale: selezione nel combo → QSS live + persist."""
        from GUI import settings_store as store
        from GUI.theme import theme as T
        win = _window()
        center = win.center
        panel = center.panel_pages["config"]
        saved = store.get_theme()
        other = next(t for t in T.available_themes() if t != saved)
        try:
            pos = panel.theme_combo.findData(other)
            self.assertGreaterEqual(pos, 0)
            panel.theme_combo.setCurrentIndex(pos)   # camino utente reale
            _app.processEvents()
            # Il QSS applicato è tema + regole di layout (_window_chrome)
            self.assertTrue(
                win.styleSheet().startswith(T.load_stylesheet(other)),
                "il QSS della finestra deve cambiare subito")
            self.assertEqual(store.get_theme(), other,
                             "il tema scelto deve persistere per nome")
        finally:
            store.set_theme(saved)
            center._apply_theme_live(saved)
            _app.processEvents()


    def test_inverted_light_themes_exist_and_classify_light(self):
        """I temi chiari generati per inversione esistono e sono 'light'."""
        from GUI.theme import theme as T
        expected = {"light_dark", "light_dracula", "light_hacker",
                    "light_neon", "light_nord", "light_pink", "light_solar",
                    "light_venom_blue", "light_venom_green"}
        self.assertTrue(expected.issubset(set(T.available_themes())),
                        "mancano i temi chiari generati per inversione")
        for t in expected:
            self.assertEqual(T.theme_kind(t), "light", t)

    def test_dark_themes_leave_no_white_panels(self):
        """Regression: nei temi scuri nessuna zona deve restare bianca.

        Colpisce gli stylesheet inline light-only (drawer #fafafa, main_scroll
        #ffffff, ecc.) che sovrascrivono il QSS del tema.
        """
        from GUI import settings_store as store
        from GUI.theme import theme as T

        def _lum(c):
            return (0.2126 * c.red() + 0.7152 * c.green()
                    + 0.0722 * c.blue()) / 255.0

        # su finestra 1450x900: drawer, header, albero, lista task, gap
        # tra i widget al centro, toolbar, pulsante ape.
        spots = [(60, 300), (140, 95), (140, 250), (140, 600),
                 (900, 430), (700, 20), (96, 32)]
        win = _window()
        saved = store.get_theme()
        white = []
        try:
            for theme in T.available_themes():
                if T.theme_kind(theme) != "dark":
                    continue
                win.center._apply_theme_live(theme)
                _app.processEvents()
                img = win.grab().toImage()
                for x, y in spots:
                    if _lum(img.pixelColor(x, y)) > 0.85:
                        white.append(f"{theme}@({x},{y})")
        finally:
            win.center._apply_theme_live(saved)
            _app.processEvents()
        self.assertEqual(white, [], f"zone bianche nei temi scuri: {white}")


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


class TestSmallModelFixes(unittest.TestCase):
    """I modelli piccoli devono riuscire a salvare e i task a ritentare."""

    def test_parse_action_accepts_python_literal(self):
        """Risposte dict Python-style (apici singoli, true/false) si parsano."""
        from CORE.orchestrator import Worker
        raw = ("{'thought':'t','action':'write_file',"
               "'args':['project/main.py','print(1)'],'done':false}")
        a = Worker._parse_action(None, raw)
        self.assertIsNotNone(a, "dict Python-style deve essere accettato")
        self.assertEqual(a["action"], "write_file")
        self.assertEqual(a["args"][0], "project/main.py")

    def test_parse_action_json_still_works(self):
        from CORE.orchestrator import Worker
        a = Worker._parse_action(
            None, '{"thought":"t","action":"analyze_project","args":[],"done":false}')
        self.assertIsNotNone(a)
        self.assertEqual(a["action"], "analyze_project")

    def test_envelope_path_content_becomes_write_file(self):
        """tool(path, code) del modello → write_file (gate AST resta attivo)."""
        from CORE.orchestrator import _looks_like_file_path
        self.assertTrue(_looks_like_file_path("project/main.py"))
        self.assertTrue(_looks_like_file_path("README.md"))
        self.assertFalse(_looks_like_file_path("analyze_project"))
        self.assertFalse(_looks_like_file_path("def fib():\n    pass"))

    def test_task_retry_cooldown_and_limit(self):
        """Retry configurabile: cooldown blocca il ripescaggio, limite ritardi."""
        import tempfile, shutil as _sh
        from CORE.orchestrator import TaskQueue
        tmp = Path(tempfile.mkdtemp(prefix="bswarm_queue_"))
        try:
            log = logging.getLogger("test_retry")
            log.addHandler(logging.NullHandler())
            q = TaskQueue(tmp, log)
            q.RETRY_LIMIT = 2                     # configurabile
            # NB: senza "id" esplicito — add() usa setdefault e ritorna
            # l'id generato; passandone uno custom il tid non combacia.
            tid = q.add({"title": "t", "description": "d",
                         "status": "pending", "attempts": 0})
            q.update_task(tid, status="running")
            # 1° fallimento con cooldown 60s: NON ripescabile subito
            st = q.fail_with_correction(tid, "err1", "fix1", cooldown_sec=60)
            self.assertEqual(st, "pending")
            self.assertIsNone(q.next_pending(),
                              "cooldown: il task non deve essere ripescato")
            # senza cooldown: ripescabile
            q.update_task(tid, status="running")
            st = q.fail_with_correction(tid, "err2", "fix2", cooldown_sec=0)
            self.assertEqual(st, "pending")
            self.assertIsNotNone(q.next_pending())
            # oltre il limite (2): definitivo
            q.update_task(tid, status="running")
            st = q.fail_with_correction(tid, "err3", "fix3")
            self.assertEqual(st, "failed_definitively")
        finally:
            _sh.rmtree(tmp, ignore_errors=True)


class TestNewShortcuts(unittest.TestCase):
    """CPU/GPU cliccabili → Attori; ESC chiude i crediti; '/' → comando."""

    def test_device_row_click_opens_actors_panel(self):
        win = _window()
        win.center.back_to_main()
        _app.processEvents()
        row = win.device_panel.cpu_box
        row.mousePressEvent(None)          # handler installato dalla patch
        _app.processEvents()
        self.assertEqual(win.center.main_stack.currentIndex(), 1)
        self.assertIs(win.center.detail_stack.currentWidget(),
                      win.center.panel_pages["modelli"])
        win.center.back_to_main()

    def test_esc_closes_credits(self):
        from PyQt6.QtCore import QEvent, Qt as _Qt
        from PyQt6.QtGui import QKeyEvent
        win = _window()
        win._show_credits()
        _app.processEvents()
        self.assertIsNotNone(win._credits_overlay)
        ev = QKeyEvent(QEvent.Type.KeyPress, _Qt.Key.Key_Escape,
                       _Qt.KeyboardModifier.NoModifier)
        win.center.eventFilter(win, ev)    # filtro app-level
        _app.processEvents()
        self.assertIsNone(win._credits_overlay,
                          "ESC deve chiudere i ringraziamenti")

    def test_slash_focuses_command_input(self):
        from PyQt6.QtCore import Qt as _Qt
        from PyQt6.QtTest import QTest
        win = _window()
        win.center.back_to_main()
        _app.processEvents()
        win.cmd_input.clear()
        QTest.keyClick(win, _Qt.Key.Key_Slash)
        _app.processEvents()
        self.assertTrue(win.cmd_input.hasFocus(),
                        "'/' deve portare il focus sul campo comando in basso")


class TestSmallWindowFixes(unittest.TestCase):
    """Finestra piccola: crediti clampati, editor → massimizzazione prevedibile."""

    def test_credits_fit_small_window(self):
        """Overlay crediti (1180x600) si ridimensiona se la finestra è più
        piccola — prima veniva tagliato ai bordi."""
        win = _window()
        win.showNormal()
        win.resize(1000, 700)
        _app.processEvents()
        try:
            win._show_credits()
            _app.processEvents()
            ov = win._credits_overlay
            self.assertIsNotNone(ov)
            self.assertLessEqual(ov.width(), win.width(),
                                 "overlay più largo della finestra: tagliato")
            self.assertLessEqual(ov.height(), win.height(),
                                 "overlay più alto della finestra: tagliato")
        finally:
            win._close_credits()
            _app.processEvents()

    def test_editor_dock_maximizes_instead_of_jump(self):
        """Aprire un documento su finestra stretta massimizza la finestra
        (prevedibile) invece del salto di dimensione imposto da Qt."""
        from PyQt6.QtWidgets import QWidget
        win = _window()
        win.showNormal()
        win.resize(1000, 700)
        _app.processEvents()
        col = QWidget()
        col.setMinimumWidth(500)
        try:
            win.center.attach_editor_column(col)
            _app.processEvents()
            self.assertTrue(win.isMaximized(),
                            "dock su finestra stretta deve massimizzare")
        finally:
            win.center.detach_editor_column()
            _app.processEvents()


class TestTaskDetailsCode(unittest.TestCase):
    """Il dialog Dettagli Task mostra i file prodotti (navigabili)."""

    def test_collect_task_files_by_mtime_fallback(self):
        """File creati in project/ nell'intervallo di vita del task → trovati."""
        import sqlite3
        import shutil
        import time as _time
        from GUI.control_center import FileTreeDrawer

        root = ROOT
        now = _time.time()
        probe = root / "project" / "TEST_dialog_probe"
        probe.mkdir(exist_ok=True)
        (probe / "main.py").write_text("print('x')\n")
        (probe / "avvia.sh").write_text("#!/bin/bash\ntrue\n")
        con = sqlite3.connect(root / "tasks" / "queue.db")
        tid = "dialog-probe-test"
        con.execute("DELETE FROM tasks WHERE id=?", (tid,))
        con.commit(); con.close()
        task = {"id": tid, "started_at": now - 5, "completed_at": now}
        try:
            files = FileTreeDrawer._collect_task_files(task, str(root))
            ours = {f for f in files if f.startswith("TEST_dialog_probe/")}
            # subset: la finestra ±120s può includere file di test adiacenti
            self.assertLessEqual({"TEST_dialog_probe/main.py",
                                  "TEST_dialog_probe/avvia.sh"}, ours)
        finally:
            shutil.rmtree(probe, ignore_errors=True)

    def test_collect_unknown_task_is_empty(self):
        from GUI.control_center import FileTreeDrawer
        task = {"id": "task-inesistente-xyz", "started_at": 0,
                "completed_at": 0}
        files = FileTreeDrawer._collect_task_files(task, str(ROOT))
        ours = [f for f in files if "dialog_probe" in f]
        self.assertEqual(ours, [])


class TestRunGeneratedCodeAndEscalation(unittest.TestCase):
    """Flusso 3 (eseguire il codice generato) + escalation LLM sui fallimenti."""

    def test_build_run_command_by_extension(self):
        from GUI.control_center import build_run_command
        f = ROOT / "project" / "x"
        self.assertEqual(build_run_command(f / "main.py"),
                         ["python3", str(f / "main.py")])
        self.assertEqual(build_run_command(f / "avvia.sh"),
                         ["bash", str(f / "avvia.sh")])
        self.assertEqual(build_run_command(f / "prog.c")[0], "bash")
        self.assertIn("gcc", build_run_command(f / "prog.c")[2])
        self.assertIn("g++", build_run_command(f / "prog.cpp")[2])
        self.assertIsNone(build_run_command(f / "README.md"))

    def test_escalation_suggestion_by_weight(self):
        from CORE.orchestrator import suggest_escalation
        self.assertIn("medium", suggest_escalation("light"))
        self.assertIn("qwen2.5:3b", suggest_escalation("light"))
        self.assertIn("heavy", suggest_escalation("medium"))
        self.assertIn("llama3:8b", suggest_escalation("medium"))
        self.assertIn("peso massimo", suggest_escalation("heavy"))


class TestTaskFileJunkFilter(unittest.TestCase):
    """'Apri risultato' non deve più finire in project/.git/objects/12/."""

    def test_git_and_pycache_excluded(self):
        import shutil as _sh
        import time as _time
        from GUI.control_center import FileTreeDrawer
        probe = ROOT / "project" / "TEST_dialog_probe"
        probe.mkdir(exist_ok=True)
        # spazzatura: oggetti git toccati dal commit del task + pycache
        junk = probe / ".git" / "objects" / "12"
        junk.mkdir(parents=True, exist_ok=True)
        (junk / "abc123").write_text("blob")
        pyc_dir = probe / "__pycache__"
        pyc_dir.mkdir(parents=True, exist_ok=True)
        (pyc_dir / "main.cpython-314.pyc").write_text("junk")
        (probe / "main.py").write_text("print('x')\n")
        (probe / "avvia.sh").write_text("#!/bin/bash\ntrue\n")
        task = {"id": "dialog-probe-junk", "started_at": _time.time() - 5,
                "completed_at": _time.time()}
        try:
            files = FileTreeDrawer._collect_task_files(task, str(ROOT))
            ours = [f for f in files if f.startswith("TEST_dialog_probe/")]
            self.assertEqual(ours, ["TEST_dialog_probe/main.py",
                                    "TEST_dialog_probe/avvia.sh"],
                             "solo i file reali, niente .git/pycache")
        finally:
            _sh.rmtree(probe, ignore_errors=True)
