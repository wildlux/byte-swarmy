"""test_suite_panel.py — Pannello "Test Suite" per la Plancia di Controllo.

Esegue la suite di test del progetto, un file alla volta (processo
dedicato per file via QProcess), con timeout per file e risultato
consolidato salvato in ``state/test_suite/results.json``.

Perché per-file: il runner unico (``tests/run_tests.py``) discovera anche
i test e2e/LLM che aspettano Ollama e si appendono; qui i file e2e sono
esclusi di default (checkbox opt-in) e ogni file ha un timeout proprio,
così un file bloccato non blocca mai la suite.

Stile: identico agli altri pannelli (hardware_panel.py) — header con
"← Indietro alla Plancia (Backspace)", scroll, QGroupBox, token tema via
set_prop/set_banner/token_color (niente colori hardcoded non sincronizzati).
"""
from __future__ import annotations

import re
import sys
import time
from pathlib import Path

from PyQt6.QtCore import QProcess, QProcessEnvironment, Qt, QTimer
from PyQt6.QtWidgets import (
    QCheckBox, QGroupBox, QHBoxLayout, QLabel, QListWidget, QListWidgetItem,
    QPlainTextEdit, QProgressBar, QPushButton, QScrollArea, QVBoxLayout,
    QWidget, QFrame,
)

from GUI.theme.theme import set_prop as _theme_prop
from GUI.theme.theme import set_banner as _theme_banner
from GUI.theme.theme import token_color as _token_color

_BASE = Path(__file__).resolve().parent.parent
RESULTS_REL = "state/test_suite/results.json"

# Timeout per file: i test unit sono rapidi; i file e2e (opt-in) possono
# aspettare Ollama quindi hanno un budget molto più alto.
DEFAULT_TIMEOUT_S = 120
E2E_TIMEOUT_S = 600

# File che richiedono Ollama / sono end-to-end: esclusi di default.
_E2E_HINTS = ("e2e", "live", "swarm", "workflow")
_E2E_EXPLICIT = {"test_timestral_full.py"}


def is_e2e_file(name: str) -> bool:
    """True se il file di test è e2e/LLM (escluso di default dalla suite)."""
    if name in _E2E_EXPLICIT:
        return True
    stem = name[len("test_"):-len(".py")] if name.startswith("test_") else name
    return any(h in stem for h in _E2E_HINTS)


def discover_test_files(include_e2e: bool = False) -> tuple[list[str], list[str]]:
    """Ritorna (files_da_eseguire, files_esclusi) ordinati, solo top-level
    ``tests/test_*.py``. I file e2e/LLM sono esclusi a meno di opt-in.
    """
    files = sorted(p.name for p in (_BASE / "tests").glob("test_*.py"))
    e2e = [f for f in files if is_e2e_file(f)]
    if include_e2e:
        return files, []
    return [f for f in files if f not in e2e], e2e


# ── Parsing output (pytest -q e unittest verbose) ────────────────────
_PX_PASSED = re.compile(r"(\d+) passed")
_PX_FAILED = re.compile(r"(\d+) failed")
_PX_ERROR = re.compile(r"(\d+) error")
_PX_SKIPPED = re.compile(r"(\d+) skipped")
_UT_RAN = re.compile(r"Ran (\d+) tests? in ([\d.]+)s")


def parse_test_output(text: str, exit_code: int) -> dict:
    """Estrae (status, counts) dall'output del runner di un file.

    Supporta pytest -q ("12 passed, 1 failed in 2.3s") e unittest verbose
    ("Ran N tests ... OK/FAILED"). Exit code 5 di pytest = nessun test
    raccolto → SKIP.
    """
    counts = {"passed": 0, "failed": 0, "errors": 0, "skipped": 0}
    for pat, key in ((_PX_PASSED, "passed"), (_PX_FAILED, "failed"),
                     (_PX_ERROR, "errors"), (_PX_SKIPPED, "skipped")):
        m = pat.search(text)
        if m:
            counts[key] = int(m.group(1))
    m = _UT_RAN.search(text)
    if m:
        total = int(m.group(1))
        if total and not any(counts.values()):
            counts["passed"] = total
        if "FAILED" not in text:
            counts["failed"] = 0
            counts["errors"] = 0
    if exit_code == 0:
        status = "PASS"
    elif exit_code == 5:  # pytest: no tests collected
        status = "SKIP"
    else:
        status = "FAIL"
    return {"status": status, "counts": counts}


_STATUS_EMOJI = {"PASS": "✅", "FAIL": "❌", "ERROR": "💥", "SKIP": "⏭"}


def _output_tail(text: str, max_chars: int = 4000) -> str:
    """Coda dell'output (la parte utile: riepilogo/traceback finale)."""
    text = (text or "").strip()
    return text[-max_chars:]


class TestSuitePanel(QWidget):
    """Pannello "Test Suite": runner per-file con timeout + risultato JSON."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("test_suite_panel")
        self._proc: QProcess | None = None
        self._timer: QTimer | None = None
        self._queue: list[Path] = []
        self._results: list[dict] = []
        self._excluded: list[str] = []
        self._current_file = ""
        self._t0 = 0.0
        self._timed_out = False
        self._stopping = False
        self._build_ui()
        self._load_saved()

    # ──────────────────────────────────────────────────────────────────
    # UI
    # ──────────────────────────────────────────────────────────────────
    def _build_ui(self):
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setStyleSheet(
            "QScrollArea { background:transparent; border:none; }")

        content = QWidget()
        content.setObjectName("panelScrollContent")
        content.setStyleSheet(
            "QWidget#panelScrollContent { background: transparent; }")
        outer = QVBoxLayout(content)
        outer.setContentsMargins(20, 16, 20, 16)
        outer.setSpacing(14)

        # Header: Indietro + titolo (stile identico agli altri pannelli)
        head = QHBoxLayout()
        head.setSpacing(10)
        back = QPushButton("← Indietro alla Plancia (Backspace)")
        back.setObjectName("back_btn")
        back.clicked.connect(self._back_to_main)
        head.addWidget(back)
        head.addStretch()
        title = QLabel("<b style='font-size:18px;'>🧪 Test Suite</b>")
        head.addWidget(title)
        head.addStretch()
        outer.addLayout(head)

        expl = QLabel(
            "Esegue la suite di test un file alla volta (processo dedicato "
            "per file, timeout per file): un test bloccato non blocca mai "
            "la suite. I file e2e/LLM sono esclusi di default perché "
            "aspettano Ollama (lenti); abilitali con la checkbox per "
            "eseguirli comunque. Il risultato è salvato in "
            "state/test_suite/results.json."
        )
        expl.setWordWrap(True)
        expl.setStyleSheet("font-size:11px;")
        _theme_prop(expl, "role", "muted")
        outer.addWidget(expl)

        # Controlli: esegui / ferma / opt-in e2e
        controls = QHBoxLayout()
        controls.setSpacing(10)
        self.run_btn = QPushButton("▶ Esegui suite")
        _theme_prop(self.run_btn, "role", "primary")
        self.run_btn.clicked.connect(self._run)
        controls.addWidget(self.run_btn)
        self.stop_btn = QPushButton("⏹ Ferma")
        _theme_prop(self.stop_btn, "role", "danger")
        self.stop_btn.setEnabled(False)
        self.stop_btn.clicked.connect(self._stop)
        controls.addWidget(self.stop_btn)
        controls.addStretch()
        self.e2e_cb = QCheckBox("Includi test e2e/LLM (richiedono Ollama)")
        self.e2e_cb.setToolTip(
            "I test e2e eseguono il modello reale: minuti, non secondi.")
        controls.addWidget(self.e2e_cb)
        outer.addLayout(controls)

        # Progresso
        self.progress = QProgressBar()
        self.progress.setRange(0, 1)
        self.progress.setValue(0)
        outer.addWidget(self.progress)

        self.status_lbl = QLabel("Inattivo — risultato ultimo run qui sotto.")
        self.status_lbl.setStyleSheet("font-size:11px;")
        _theme_prop(self.status_lbl, "role", "muted")
        outer.addWidget(self.status_lbl)

        # Riepilogo
        self.summary_box = QGroupBox("📊 Risultato")
        s_lay = QVBoxLayout(self.summary_box)
        s_lay.setSpacing(8)
        s_lay.setContentsMargins(14, 14, 14, 14)
        self.badge_lbl = QLabel("—")
        self.badge_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.badge_lbl.setStyleSheet(
            "padding:8px; font-size:14px; font-weight:bold;")
        s_lay.addWidget(self.badge_lbl)
        grid_data = [
            ("files_ok", "File OK"),
            ("files_ko", "File KO"),
            ("passed", "Test pass"),
            ("failed", "Test fail"),
            ("errors", "Test error"),
            ("skipped", "Test skip"),
            ("duration_s", "Durata"),
        ]
        self.summary_labels: dict[str, QLabel] = {}
        for key, text in grid_data:
            row = QHBoxLayout()
            lbl = QLabel(f"<b>{text}:</b>")
            lbl.setStyleSheet("font-size:12px;")
            _theme_prop(lbl, "role", "muted")
            lbl.setFixedWidth(160)
            row.addWidget(lbl)
            val = QLabel("—")
            val.setStyleSheet("font-size:12px;")
            row.addWidget(val, stretch=1)
            self.summary_labels[key] = val
            s_lay.addLayout(row)
        outer.addWidget(self.summary_box)

        # Risultati per file
        list_box = QGroupBox("📁 Risultati per file")
        l_lay = QVBoxLayout(list_box)
        l_lay.setContentsMargins(10, 10, 10, 10)
        self.list = QListWidget()
        self.list.itemSelectionChanged.connect(self._on_selected)
        self.list.setStyleSheet(
            "font-family:'JetBrains Mono','Consolas',monospace; "
            "font-size:11px;")
        self.list.setMinimumHeight(180)
        l_lay.addWidget(self.list, stretch=1)
        outer.addWidget(list_box, stretch=1)

        # Output del file selezionato
        det_box = QGroupBox("🖨️ Output del file selezionato")
        d_lay = QVBoxLayout(det_box)
        d_lay.setContentsMargins(10, 10, 10, 10)
        self.detail = QPlainTextEdit()
        self.detail.setReadOnly(True)
        self.detail.setMaximumBlockCount(400)
        self.detail.setStyleSheet(
            "font-family:'JetBrains Mono','Consolas',monospace; "
            "font-size:10.5px;")
        self.detail.setPlaceholderText(
            "Seleziona un file nella lista per vedere la coda del suo output…")
        self.detail.setMaximumHeight(200)
        d_lay.addWidget(self.detail)
        outer.addWidget(det_box)

        # Log esecuzione
        log_box = QGroupBox("📜 Log esecuzione")
        g_lay = QVBoxLayout(log_box)
        g_lay.setContentsMargins(10, 10, 10, 10)
        self.log = QPlainTextEdit()
        self.log.setReadOnly(True)
        self.log.setMaximumBlockCount(300)
        self.log.setStyleSheet(
            "font-family:'JetBrains Mono','Consolas',monospace; "
            "font-size:10.5px;")
        self.log.setPlaceholderText("Il log dell'esecuzione apparirà qui…")
        self.log.setMaximumHeight(150)
        g_lay.addWidget(self.log)
        outer.addWidget(log_box)

        outer.addStretch()
        scroll.setWidget(content)

        main_lay = QVBoxLayout(self)
        main_lay.setContentsMargins(0, 0, 0, 0)
        main_lay.setSpacing(0)
        main_lay.addWidget(scroll)

    # ──────────────────────────────────────────────────────────────────
    # Runner (QProcess sequenziale, timeout per file)
    # ──────────────────────────────────────────────────────────────────
    def _run(self):
        if self._proc is not None:
            return
        include_e2e = self.e2e_cb.isChecked()
        files, excluded = discover_test_files(include_e2e)
        if not files:
            self._log("⚠ Nessun file di test trovato in tests/.")
            return
        self._results = []
        self._excluded = excluded
        self._queue = [_BASE / "tests" / f for f in files]
        self._stopping = False
        self._timed_out = False
        self.list.clear()
        self.detail.clear()
        self.log.clear()
        self.progress.setRange(0, len(self._queue))
        self.progress.setValue(0)
        self.run_btn.setEnabled(False)
        self.stop_btn.setEnabled(True)
        self._log(f"▶ Suite avviata: {len(files)} file "
                  f"({len(excluded)} e2e/LLM esclusi, timeout "
                  f"{DEFAULT_TIMEOUT_S}s per file).")
        self._next()

    def _next(self):
        if not self._queue:
            self._finalize()
            return
        path = self._queue.pop(0)
        self._current_file = path.name
        timeout = (E2E_TIMEOUT_S if is_e2e_file(path.name)
                   else DEFAULT_TIMEOUT_S)
        self._log(f"[{self._now()}] ▶ {path.name} (timeout {timeout}s)")
        self.status_lbl.setText(f"Esecuzione: {path.name} …")
        proc = QProcess(self)
        proc.setProcessChannelMode(QProcess.ProcessChannelMode.MergedChannels)
        env = QProcessEnvironment.systemEnvironment()
        # offscreen: i test non devono aprire finestre sul desktop reale
        env.insert("QT_QPA_PLATFORM", "offscreen")
        env.insert("PYTHONUNBUFFERED", "1")
        proc.setProcessEnvironment(env)
        proc.setWorkingDirectory(str(_BASE))
        prog = sys.executable
        args = ["-m", "pytest", "-q", "--no-header", "-p", "no:cacheprovider",
                "--tb=short", str(path)]
        proc.finished.connect(self._on_finished)
        self._proc = proc
        self._t0 = time.monotonic()
        proc.start(prog, args)
        self._timer = QTimer(self)
        self._timer.setSingleShot(True)
        self._timer.timeout.connect(self._on_timeout)
        self._timer.start(timeout * 1000)

    def _on_timeout(self):
        self._timed_out = True
        if self._proc is not None:
            self._log(f"[{self._now()}] ⏱ Timeout: kill del processo "
                      f"{self._current_file}")
            self._proc.kill()

    def _on_finished(self, exit_code, exit_status):
        if self._proc is None:
            return
        proc, self._proc = self._proc, None
        if self._timer is not None:
            self._timer.stop()
            self._timer.deleteLater()
            self._timer = None
        out = bytes(proc.readAllStandardOutput()).decode(
            errors="replace")
        dur = round(time.monotonic() - self._t0, 1)
        name = self._current_file
        timed_out, self._timed_out = self._timed_out, False

        if timed_out:
            record = {"file": name, "status": "ERROR",
                      "counts": {"passed": 0, "failed": 0, "errors": 0,
                                 "skipped": 0},
                      "duration_s": dur,
                      "detail": _output_tail(out) +
                      f"\n[TIMEOUT] file bloccato oltre il budget; "
                      f"processo terminato."}
        elif self._stopping:
            record = {"file": name, "status": "SKIP",
                      "counts": {"passed": 0, "failed": 0, "errors": 0,
                                 "skipped": 0},
                      "duration_s": dur,
                      "detail": "run interrotto dall'utente"}
        elif exit_status == QProcess.ExitStatus.CrashExit and \
                "passed" not in out and "OK" not in out:
            record = {"file": name, "status": "ERROR",
                      "counts": {"passed": 0, "failed": 0, "errors": 0,
                                 "skipped": 0},
                      "duration_s": dur,
                      "detail": _output_tail(out) +
                      f"\n[CRASH] il processo è morto (exit {exit_code})."}
        else:
            parsed = parse_test_output(out, exit_code)
            record = {"file": name, "status": parsed["status"],
                      "counts": parsed["counts"], "duration_s": dur,
                      "detail": _output_tail(out)}

        self._results.append(record)
        self._append_list_row(record)
        c = record["counts"]
        self._log(f"[{self._now()}] {record['status']:<5} {name} — "
                  f"{c['passed']} pass, {c['failed']} fail, "
                  f"{c['errors']} err ({dur}s)")
        self.progress.setValue(self.progress.value() + 1)
        if not self._queue and self._stopping:
            self._finalize()
        else:
            self._next()

    def _stop(self):
        if self._proc is None:
            return
        self._stopping = True
        self._queue.clear()
        self._log(f"[{self._now()}] ⏹ Stop richiesto: fermo il file "
                  f"corrente e chiudo la suite.")
        self._proc.kill()

    # ──────────────────────────────────────────────────────────────────
    # Risultati
    # ──────────────────────────────────────────────────────────────────
    def _finalize(self):
        self.run_btn.setEnabled(True)
        self.stop_btn.setEnabled(False)
        self.progress.setRange(0, 1)
        self.progress.setValue(1)
        res = self._results
        files_ok = sum(1 for r in res if r["status"] == "PASS")
        files_ko = sum(1 for r in res if r["status"] in ("FAIL", "ERROR"))
        tot = {"passed": 0, "failed": 0, "errors": 0, "skipped": 0}
        dur = 0.0
        for r in res:
            for k in tot:
                tot[k] += r["counts"].get(k, 0)
            dur += r["duration_s"]
        skipped_files = sum(1 for r in res if r["status"] == "SKIP")
        report = {
            "generated_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
            "include_e2e": self.e2e_cb.isChecked(),
            "excluded_files": list(self._excluded),
            "summary": {
                "files_total": len(res), "files_ok": files_ok,
                "files_ko": files_ko, "files_skipped": skipped_files,
                "passed": tot["passed"], "failed": tot["failed"],
                "errors": tot["errors"], "skipped": tot["skipped"],
                "duration_s": round(dur, 1),
            },
            "files": res,
        }
        ok = files_ko == 0 and len(res) > 0
        self._apply_summary(report, ok)
        try:
            from CORE.state_repository import save_json
            saved = save_json(RESULTS_REL, report)
        except Exception:
            saved = False
        self._log(f"[{self._now()}] "
                  + (f"{'✅' if ok else '❌'} Suite completata in "
                     f"{dur:.1f}s — risultato salvato in {RESULTS_REL}."
                     if saved else
                     f"⚠ Suite completata ma salvataggio JSON fallito."))
        self.status_lbl.setText(
            "Completato — risultato salvato in state/test_suite/results.json."
            if saved else "Completato (salvataggio JSON fallito).")

    def _apply_summary(self, report: dict, ok: bool):
        s = report["summary"]
        self.summary_labels["files_ok"].setText(str(s["files_ok"]))
        self.summary_labels["files_ko"].setText(str(s["files_ko"]))
        self.summary_labels["passed"].setText(str(s["passed"]))
        self.summary_labels["failed"].setText(str(s["failed"]))
        self.summary_labels["errors"].setText(str(s["errors"]))
        self.summary_labels["skipped"].setText(str(s["skipped"]))
        self.summary_labels["duration_s"].setText(f"{s['duration_s']}s")
        if ok:
            tok, txt = "ok", (f"✅ TUTTO OK — {s['files_ok']} file, "
                              f"{s['passed']} test pass")
        elif s.get("files_total", 0) == 0:
            tok, txt = "muted", "— nessun risultato —"
        else:
            tok, txt = "alert", (f"❌ {s['files_ko']} file KO — "
                                 f"{s['failed']} fail, {s['errors']} error")
        color = _token_color(tok) or "#8f99ab"
        self.badge_lbl.setText(txt)
        # rgba() esplicita: in QSS Qt l'hex a 8 cifre è #AARRGGBB
        h = color.lstrip("#")
        r, g, b = int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)
        self.badge_lbl.setStyleSheet(
            f"background:rgba({r},{g},{b},0.10); "
            f"border:2px solid rgba({r},{g},{b},0.55); border-radius:8px; "
            f"padding:8px; font-size:14px; font-weight:bold; "
            f"color:{color};")

    def _append_list_row(self, record: dict):
        c = record["counts"]
        emoji = _STATUS_EMOJI.get(record["status"], "•")
        item = QListWidgetItem(
            f"{emoji} {record['file']} — {c['passed']} pass, "
            f"{c['failed']} fail, {c['errors']} err "
            f"({record['duration_s']}s)")
        item.setData(Qt.ItemDataRole.UserRole, len(self._results) - 1)
        self.list.addItem(item)

    def _on_selected(self):
        items = self.list.selectedItems()
        if not items:
            return
        idx = items[0].data(Qt.ItemDataRole.UserRole)
        if isinstance(idx, int) and 0 <= idx < len(self._results):
            self.detail.setPlainText(self._results[idx].get("detail") or "—")

    def _load_saved(self):
        """Mostra il risultato dell'ultimo run salvato, se esiste."""
        try:
            from CORE.state_repository import load_json
            report = load_json(RESULTS_REL)
        except Exception:
            report = None
        if not isinstance(report, dict) or "summary" not in report:
            return
        self._results = list(report.get("files") or [])
        self._excluded = list(report.get("excluded_files") or [])
        for r in self._results:
            self._append_list_row(r)
        files_ok = sum(1 for r in self._results if r["status"] == "PASS")
        files_ko = sum(1 for r in self._results
                       if r["status"] in ("FAIL", "ERROR"))
        self._apply_summary(
            report, files_ko == 0 and files_ok > 0)
        self._log(f"Ultimo run: {report.get('generated_at', '?')} "
                  f"(caricato da {RESULTS_REL})")

    # ──────────────────────────────────────────────────────────────────
    def _log(self, line: str):
        self.log.appendPlainText(line)

    @staticmethod
    def _now() -> str:
        return time.strftime("%H:%M:%S")

    def _back_to_main(self):
        """Torna alla plancia di controllo (come hardware_panel)."""
        p = self.parent()
        while p and not hasattr(p, "back_to_main"):
            p = p.parent()
        if p and hasattr(p, "back_to_main"):
            p.back_to_main()


__all__ = ["TestSuitePanel", "discover_test_files", "is_e2e_file",
           "parse_test_output"]
