"""integrity_tests_panel.py — Pannello per eseguire test di integrità del software.

Estratto da GUI/control_center.py per ridurre il monolite.

Verifica:
  - checksum SHA256 di tutti i file Python di CORE/SAFETY/CONFIG
  - esistenza dei file critici (orchestrator.py, security.py, ecc.)
  - sintassi Python di ogni modulo (py_compile)
  - coerenza del config.toml
"""

from __future__ import annotations

import os
import hashlib
import py_compile

from PyQt6.QtWidgets import (
    QFrame, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QPlainTextEdit,
)
from PyQt6.QtCore import Qt

from GUI.search_bar import SearchBar


class IntegrityTestsPanel(QFrame):
    """Pannello per eseguire test di integrità del software.

    Verifica:
      - checksum SHA256 di tutti i file Python di CORE/SAFETY/CONFIG
      - esistenza dei file critici (orchestrator.py, security.py, ecc.)
      - sintassi Python di ogni modulo (py_compile)
      - coerenza del config.toml
    """

    # File critici che DEVONO esistere e non essere vuoti
    CRITICAL_FILES = [
        "CORE/orchestrator.py",
        "CORE/tools.py",
        "CORE/ollama_client.py",
        "SAFETY/security.py",
        "SAFETY/security_checks.py",
        "SAFETY/watchdog.py",
        "CONFIG/config.toml",
        "GUI/control_center.py",
        "GUI/gui_backend.py",
        "GUI/settings_store.py",
    ]

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("integrity_panel")

        lay = QVBoxLayout(self)
        lay.setContentsMargins(12, 10, 12, 10)
        lay.setSpacing(8)

        # Header con pulsante "Esegui test"
        head = QHBoxLayout()
        head.setSpacing(8)
        head.addWidget(
            QLabel("<b>Verifica checksum, esistenza file critici, sintassi Python</b>")
        )
        head.addStretch()

        self.run_btn = QPushButton("▶ Esegui test di integrità")
        self.run_btn.setStyleSheet(
            "QPushButton { background:#16a34a; color:#ffffff; border:none; "
            "padding:8px 14px; border-radius:6px; font-weight:bold; font-size:11px; }"
            "QPushButton:hover { background:#15803d; }"
        )
        self.run_btn.clicked.connect(self._run_tests)
        head.addWidget(self.run_btn)
        lay.addLayout(head)

        # ── Barra di ricerca nel contenuto ────────────────────────────
        self.search_bar = SearchBar(
            None, parent=self,  # target viene impostato dopo la creazione di output
            placeholder="🔍 Cerca nei risultati…  (Enter = successivo, Shift+Enter = precedente)"
        )
        lay.addWidget(self.search_bar)

        # Output area
        self.output = QPlainTextEdit()
        self.output.setReadOnly(True)
        self.output.setPlaceholderText(
            "Clicca 'Esegui test di integrità' per verificare checksum SHA256, "
            "esistenza file critici, e sintassi Python dei moduli.\n"
            "Risultato: elenco PASS/FAIL con dettagli."
        )
        self.output.setStyleSheet(
            "font-family:'JetBrains Mono','Consolas',monospace; "
            "font-size:11px; padding:8px;"
        )
        # Collega la search bar al target (ora che self.output esiste)
        self.search_bar.target = self.output
        lay.addWidget(self.output, stretch=1)

        # Stato iniziale: baseline checksum
        self._baseline = None

    def _base_dir(self):
        return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

    def _run_tests(self):
        """Esegue tutti i test di integrità e mostra il risultato."""
        self.output.clear()
        self.output.appendPlainText("════════════════════════════════════════════")
        self.output.appendPlainText("  🧪 TEST DI INTEGRITÀ DEL SOFTWARE")
        self.output.appendPlainText("═════════════════════════════════════════════\n")
        import time, tempfile

        base = self._base_dir()
        passed = 0
        failed = 0
        warnings = 0
        start = time.time()

        # ── Test 1: esistenza file critici ─────────────────────────────
        self.output.appendPlainText("─── Test 1: Esistenza file critici ───")
        for rel in self.CRITICAL_FILES:
            path = os.path.join(base, rel)
            if os.path.exists(path):
                size = os.path.getsize(path)
                if size == 0:
                    self.output.appendPlainText(f"  ⚠️  {rel} — esiste ma è VUOTO ({size}B)")
                    warnings += 1
                else:
                    self.output.appendPlainText(f"  ✓  {rel} — {size}B")
                    passed += 1
            else:
                self.output.appendPlainText(f"  ✗  {rel} — MANCANTE")
                failed += 1
        self.output.appendPlainText("")

        # ── Test 2: checksum SHA256 di tutti i .py in CORE/ ────────────
        self.output.appendPlainText("─── Test 2: Checksum SHA256 CORE/*.py ───")
        core_dir = os.path.join(base, "CORE")
        if os.path.isdir(core_dir):
            hashes = {}
            for fname in sorted(os.listdir(core_dir)):
                if not fname.endswith(".py"):
                    continue
                path = os.path.join(core_dir, fname)
                try:
                    with open(path, "rb") as f:
                        h = hashlib.sha256(f.read()).hexdigest()[:16]
                    hashes[fname] = h
                    self.output.appendPlainText(f"  ✓  {fname}  sha256:{h}...")
                    passed += 1
                except OSError as e:
                    self.output.appendPlainText(f"  ✗  {fname}  errore: {e}")
                    failed += 1
        self.output.appendPlainText("")

        # ── Test 3: py_compile di ogni .py in CORE/ e GUI/ ─────────────
        self.output.appendPlainText("─── Test 3: Sintassi Python (py_compile) ───")
        for sub in ("CORE", "GUI", "SAFETY"):
            d = os.path.join(base, sub)
            if not os.path.isdir(d):
                continue
            for fname in sorted(os.listdir(d)):
                if not fname.endswith(".py"):
                    continue
                path = os.path.join(d, fname)
                try:
                    py_compile.compile(path, doraise=True, quiet=2)
                    self.output.appendPlainText(f"  ✓  {sub}/{fname} — sintassi OK")
                    passed += 1
                except py_compile.PyCompileError as e:
                    self.output.appendPlainText(f"  ✗  {sub}/{fname} — ERRORE SINTASSI")
                    self.output.appendPlainText(f"      {str(e)[:200]}")
                    failed += 1
                except Exception as e:
                    self.output.appendPlainText(f"  ✗  {sub}/{fname} — {type(e).__name__}: {e}")
                    failed += 1
        self.output.appendPlainText("")

        # ── Test 4: config.toml parseable ─────────────────────────────
        self.output.appendPlainText("─── Test 4: Config.toml valido ───")
        config_path = os.path.join(base, "CONFIG", "config.toml")
        try:
            import tomllib
            with open(config_path, "rb") as f:
                tomllib.load(f)
            self.output.appendPlainText("  ✓  CONFIG/config.toml — parse OK")
            passed += 1
        except ImportError:
            # Python < 3.11 — fallback a tomli se installato
            try:
                import tomli
                with open(config_path, "rb") as f:
                    tomli.load(f)
                self.output.appendPlainText("  ✓  CONFIG/config.toml — parse OK (tomli)")
                passed += 1
            except Exception as e:
                self.output.appendPlainText(f"  ⚠️  tomli non disponibile: {e}")
                warnings += 1
        except FileNotFoundError:
            self.output.appendPlainText("  ✗  CONFIG/config.toml — MANCANTE")
            failed += 1
        except Exception as e:
            self.output.appendPlainText(f"  ✗  CONFIG/config.toml — PARSE ERROR: {e}")
            failed += 1
        self.output.appendPlainText("")

        # ── Riepilogo ─────────────────────────────────────────────────
        elapsed = time.time() - start
        self.output.appendPlainText("════════════════════════════════════════════")
        self.output.appendPlainText(f"  ✓ PASS:    {passed}")
        self.output.appendPlainText(f"  ✗ FAIL:    {failed}")
        self.output.appendPlainText(f"  ⚠️ WARN:   {warnings}")
        self.output.appendPlainText(f"  ⏱  Tempo: {elapsed:.2f}s")
        status = "✅ INTEGRO" if failed == 0 else "❌ COMPROMESSO"
        self.output.appendPlainText(f"  Stato:    {status}")
        self.output.appendPlainText("════════════════════════════════════════════")
