"""software_security_panel.py — Pannello per verificare l'integrità anti-manomissione del codice.

Estratto da GUI/control_center.py per ridurre il monolite.

Caratteristiche:
  - Salva una baseline di hash SHA256 dei file critici in
    CONFIG/security_baseline.json (al primo avvio o su richiesta)
  - Confronta l'hash attuale con la baseline per rilevare modifiche
    non autorizzate ai file di CORE/SAFETY/SECURITY
  - Verifica permessi dei file (non world-writable)
  - Elenca file modificati dopo la baseline
"""

from __future__ import annotations

import os
import json

from PyQt6.QtWidgets import (
    QFrame, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QPlainTextEdit,
    QMessageBox,
)
from PyQt6.QtCore import Qt

from GUI.search_bar import SearchBar


class SoftwareSecurityPanel(QFrame):
    """Pannello per verificare l'integrità anti-manomissione del codice.

    Caratteristiche:
      - Salva una baseline di hash SHA256 dei file critici in
        CONFIG/security_baseline.json (al primo avvio o su richiesta)
      - Confronta l'hash attuale con la baseline per rilevare modifiche
        non autorizzate ai file di CORE/SAFETY/SECURITY
      - Verifica permessi dei file (non world-writable)
      - Elenca file modificati dopo la baseline
    """

    BASELINE_FILE = os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        "CONFIG", "security_baseline.json"
    )

    # Cartelle i cui file .py sono considerati "critici" per la sicurezza
    WATCHED_DIRS = ("CORE", "SAFETY", "GUI")

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("security_panel")

        lay = QVBoxLayout(self)
        lay.setContentsMargins(12, 10, 12, 10)
        lay.setSpacing(8)

        # Header
        head = QHBoxLayout()
        head.setSpacing(8)
        head.addWidget(QLabel(
            "<b>Verifica anti-manomissione codice, permessi file, hash baseline</b>"
        ))
        head.addStretch()

        self.scan_btn = QPushButton("🔍 Scansiona ora")
        self.scan_btn.setStyleSheet(
            "QPushButton { background:#2563eb; color:#ffffff; border:none; "
            "padding:8px 14px; border-radius:6px; font-weight:bold; font-size:11px; }"
            "QPushButton:hover { background:#1d4ed8; }"
        )
        self.scan_btn.clicked.connect(self._scan)
        head.addWidget(self.scan_btn)

        self.save_btn = QPushButton("💾 Salva baseline")
        self.save_btn.setStyleSheet(
            "QPushButton { background:#f59e0b; color:#ffffff; border:none; "
            "padding:8px 14px; border-radius:6px; font-weight:bold; font-size:11px; }"
            "QPushButton:hover { background:#d97706; }"
        )
        self.save_btn.setToolTip(
            "Salva l'hash SHA256 attuale di tutti i file come stato fidato. "
            "Le future scansioni confronteranno con questa baseline."
        )
        self.save_btn.clicked.connect(self._save_baseline)
        head.addWidget(self.save_btn)
        lay.addLayout(head)

        # ── Barra di ricerca nel contenuto ────────────────────────────
        self.search_bar = SearchBar(
            None, parent=self,
            placeholder="🔍 Cerca nei risultati…  (Enter = successivo, Shift+Enter = precedente)"
        )
        lay.addWidget(self.search_bar)

        # Output
        self.output = QPlainTextEdit()
        self.output.setReadOnly(True)
        self.output.setPlaceholderText(
            "Clicca 'Scansiona ora' per verificare che i file di CORE/SAFETY/GUI "
            "non siano stati manomessi dopo l'ultima baseline.\n"
            "Salva baseline la prima volta."
        )
        self.output.setStyleSheet(
            "font-family:'JetBrains Mono','Consolas',monospace; "
            "font-size:11px; padding:8px;"
        )
        self.search_bar.target = self.output
        lay.addWidget(self.output, stretch=1)

    def _base_dir(self):
        return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

    def _hash_dir(self) -> dict:
        """Calcola SHA256 di tutti i .py nelle cartelle watched."""
        base = self._base_dir()
        out = {}
        for sub in self.WATCHED_DIRS:
            d = os.path.join(base, sub)
            if not os.path.isdir(d):
                continue
            for fname in sorted(os.listdir(d)):
                if not fname.endswith(".py"):
                    continue
                path = os.path.join(d, fname)
                rel = f"{sub}/{fname}"
                try:
                    import hashlib
                    with open(path, "rb") as f:
                        out[rel] = hashlib.sha256(f.read()).hexdigest()
                except OSError:
                    out[rel] = None
        return out

    def _load_baseline(self) -> dict:
        if not os.path.exists(self.BASELINE_FILE):
            return {}
        try:
            import json as _json
            with open(self.BASELINE_FILE, "r", encoding="utf-8") as f:
                return _json.load(f).get("hashes", {})
        except Exception:
            return {}

    def _save_baseline(self):
        """Salva la baseline di hash attuale."""
        hashes = self._hash_dir()
        if not hashes:
            QMessageBox.warning(self, "Nessun file",
                "Nessun file Python trovato in CORE/SAFETY/GUI da salvare.")
            return
        import time
        os.makedirs(os.path.dirname(self.BASELINE_FILE), exist_ok=True)
        data = {
            "saved_at": time.strftime("%Y-%m-%d %H:%M:%S"),
            "saved_by": os.environ.get("USER", "unknown"),
            "hashes": hashes,
        }
        try:
            with open(self.BASELINE_FILE, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
            self.output.clear()
            self.output.appendPlainText(
                f"✅ Baseline salvata in {self.BASELINE_FILE}\n"
                f"   File monitorati: {len(hashes)}\n"
                f"   Salvata il: {data['saved_at']}\n"
                f"   Utente: {data['saved_by']}\n"
            )
        except OSError as e:
            QMessageBox.critical(self, "Errore", f"Impossibile salvare baseline: {e}")

    def _scan(self):
        """Scansiona i file e confronta con la baseline."""
        self.output.clear()
        self.output.appendPlainText("════════════════════════════════════════════")
        self.output.appendPlainText("  🛡️  SICUREZZA DEL SOFTWARE & ANTI-MANOMISSIONE")
        self.output.appendPlainText("════════════════════════════════════════════\n")

        current = self._hash_dir()
        baseline = self._load_baseline()

        if not baseline:
            self.output.appendPlainText("⚠️  Nessuna baseline trovata.")
            self.output.appendPlainText("    Clicca '💾 Salva baseline' per creare lo stato fidato.")
            self.output.appendPlainText("    Fino ad allora, tutti gli hash attuali verranno")
            self.output.appendPlainText("    salvati come 'nuovi' (nessun confronto possibile).\n")

        # ── 1. Hash file per file ──────────────────────────────────────
        self.output.appendPlainText("─── Hash SHA256 dei file critici ───")
        for rel, h in sorted(current.items()):
            short_h = (h or "errore")[:16]
            if not baseline:
                self.output.appendPlainText(f"  • {rel:40s} sha256:{short_h}...")
            else:
                base_h = baseline.get(rel)
                if base_h is None:
                    self.output.appendPlainText(f"  + {rel:40s} NUOVO (non in baseline) sha256:{short_h}...")
                elif base_h == h:
                    self.output.appendPlainText(f"  ✓ {rel:40s} sha256:{short_h}...")
                else:
                    self.output.appendPlainText(f"  ✗ {rel:40s} MODIFICATO — base:{(base_h or '')[:12]}... curr:{short_h}...")
        self.output.appendPlainText("")

        # ── 2. File rimossi (in baseline ma non più esistenti) ─────────
        if baseline:
            removed = [r for r in baseline if r not in current]
            if removed:
                self.output.appendPlainText("─── File rimossi dalla baseline ───")
                for rel in removed:
                    self.output.appendPlainText(f"  - {rel:40s} eliminato o spostato")
                self.output.appendPlainText("")

        # ── 3. Permessi file (no world-writable) ──────────────────────
        self.output.appendPlainText("─── Permessi file (no world-writable) ───")
        base = self._base_dir()
        import stat
        bad_perms = 0
        for rel in current:
            path = os.path.join(base, rel)
            try:
                mode = os.stat(path).st_mode
                if mode & stat.S_IWOTH:
                    self.output.appendPlainText(f"  ⚠️  {rel} è WORLD-WRITABLE (permessi {oct(mode & 0o777)})")
                    bad_perms += 1
            except OSError:
                pass
        if bad_perms == 0:
            self.output.appendPlainText(f"  ✓  Tutti i file hanno permessi corretti (no world-writable)")
        self.output.appendPlainText("")

        # ── 4. Riepilogo ───────────────────────────────────────────────
        modified = 0
        new = 0
        removed_n = 0
        if baseline:
            for rel, h in current.items():
                base_h = baseline.get(rel)
                if base_h is None:
                    new += 1
                elif base_h != h:
                    modified += 1
            removed_n = len([r for r in baseline if r not in current])

        self.output.appendPlainText("════════════════════════════════════════════")
        self.output.appendPlainText(f"  File monitorati:   {len(current)}")
        self.output.appendPlainText(f"  File modificati:   {modified}")
        self.output.appendPlainText(f"  File nuovi:        {new}")
        self.output.appendPlainText(f"  File rimossi:      {removed_n}")
        self.output.appendPlainText(f"  Permessi anomali:  {bad_perms}")
        status = "✅ SICURO" if (modified == 0 and bad_perms == 0) else "❌ MANOMESSO"
        self.output.appendPlainText(f"  Stato:             {status}")
        self.output.appendPlainText("════════════════════════════════════════════")
