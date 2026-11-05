"""hardware_panel.py — Pannello "Hardware & Modelli" per la Plancia.

Mostra il profilo hardware rilevato da CORE/hardware_detector.py:
  - Tipo GPU (Apple Metal / NVIDIA CUDA / AMD ROCm / CPU)
  - Memoria (unificata vs dedicata, RAM/VRAM totale)
  - Bandwidth (GB/s)
  - Strategia auto-suggerita (cpu_only, unified_parallel, nvidia_dual, ecc.)
  - Worker count, keep_alive, modelli in RAM

Pulsante "🔄 Rileva di nuovo" per rieseguire il rilevamento (utile se
si collega una GPU esterna mentre byte-swarmy è in esecuzione).
"""
from __future__ import annotations

from pathlib import Path

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QFrame,
    QGroupBox, QSizePolicy, QPlainTextEdit,
)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QFont

from GUI.theme.theme import set_prop as _theme_prop
from GUI.theme.theme import set_banner as _theme_banner

_BASE = Path(__file__).resolve().parent.parent


class HardwarePanel(QWidget):
    """Pannello 'Hardware & Modelli' per la Plancia di byte-swarmy.

    Mostra il profilo hardware rilevato automaticamente + pulsante
    refresh per rilanciare il rilevamento.
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("hardware_panel")
        self._build_ui()
        self._refresh_profile()

    # ──────────────────────────────────────────────────────────────────
    # UI
    # ──────────────────────────────────────────────────────────────────
    def _build_ui(self):
        outer = QVBoxLayout(self)
        outer.setContentsMargins(20, 16, 20, 16)
        outer.setSpacing(14)

        # Header: pulsante Indietro + titolo (stile dal tema app-level QSS)
        head = QHBoxLayout()
        head.setSpacing(10)
        back = QPushButton("← Indietro alla Plancia (Backspace)")
        back.setObjectName("back_btn")
        back.clicked.connect(self._back_to_main)
        head.addWidget(back)
        head.addStretch()
        title = QLabel("<b style='font-size:18px;'>🖥️ Hardware & Modelli</b>")
        head.addWidget(title)
        head.addStretch()
        outer.addLayout(head)

        # Spiegazione
        expl = QLabel(
            "Rilevamento automatico del tipo di GPU e memoria disponibile. "
            "La strategia ottimale (Worker paralleli, modelli in RAM, keep_alive) "
            "viene scelta in base all'hardware: Apple Silicon (memoria unificata), "
            "NVIDIA CUDA (VRAM dedicata), AMD ROCm, o solo CPU."
        )
        expl.setWordWrap(True)
        # tema: colore dal QSS (role="muted"), solo la dimensione inline
        expl.setStyleSheet("font-size:11px;")
        _theme_prop(expl, "role", "muted")
        outer.addWidget(expl)

        # Pulsante refresh: stile primario dal tema (QPushButton[role="primary"])
        btn_row = QHBoxLayout()
        self.refresh_btn = QPushButton("🔄 Rileva hardware di nuovo")
        _theme_prop(self.refresh_btn, "role", "primary")
        self.refresh_btn.clicked.connect(self._refresh_profile)
        btn_row.addWidget(self.refresh_btn)
        btn_row.addStretch()
        outer.addLayout(btn_row)

        # Box profilo hardware (stile QGroupBox dal tema)
        prof_box = QGroupBox("📊 Profilo hardware rilevato")
        prof_lay = QVBoxLayout(prof_box)
        prof_lay.setSpacing(8)
        prof_lay.setContentsMargins(14, 14, 14, 14)

        # Griglia info hardware (label + valore per riga)
        self.info_labels: dict[str, QLabel] = {}
        info_grid_data = [
            ("platform", "Platform"),
            ("gpu_type", "Tipo GPU"),
            ("gpu_name", "Nome GPU"),
            ("memory_unified", "Memoria unificata"),
            ("ram_total", "RAM totale"),
            ("vram_total", "VRAM totale"),
            ("bandwidth", "Bandwidth"),
            ("cpu_cores", "CPU cores"),
            ("model_size", "Modello configurato"),
            ("model_fits", "Modello in VRAM?"),
        ]
        for key, label_text in info_grid_data:
            row = QHBoxLayout()
            lbl = QLabel(f"<b>{label_text}:</b>")
            lbl.setStyleSheet("font-size:12px;")
            _theme_prop(lbl, "role", "muted")
            lbl.setFixedWidth(160)
            row.addWidget(lbl)
            val = QLabel("—")
            # NB: nessun colore inline — segue il tema (il vecchio
            # #1a1a1a era invisibile nel tema scuro)
            val.setStyleSheet("font-size:12px;")
            row.addWidget(val, stretch=1)
            self.info_labels[key] = val
            prof_lay.addLayout(row)

        outer.addWidget(prof_box)

        # Box strategia suggerita (stile QGroupBox dal tema)
        strat_box = QGroupBox("🎯 Strategia auto-suggerita")
        strat_lay = QVBoxLayout(strat_box)
        strat_lay.setSpacing(8)
        strat_lay.setContentsMargins(14, 14, 14, 14)

        # Badge grande strategia (ricolorato dinamico in _refresh_profile)
        self.strat_badge = QLabel("—")
        self.strat_badge.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.strat_badge.setStyleSheet(
            "padding:16px; font-size:18px; font-weight:bold;"
        )
        strat_lay.addWidget(self.strat_badge)

        # Descrizione strategia
        self.strat_desc = QLabel("—")
        self.strat_desc.setWordWrap(True)
        self.strat_desc.setStyleSheet("font-size:11px; padding:8px;")
        _theme_prop(self.strat_desc, "role", "muted")
        strat_lay.addWidget(self.strat_desc)

        # Parametri strategia
        self.strat_params = QLabel("—")
        self.strat_params.setStyleSheet(
            "padding:10px; font-size:12px;"
        )
        self.strat_params.setWordWrap(True)
        strat_lay.addWidget(self.strat_params)

        outer.addWidget(strat_box)

        # Riepilogo one-line
        self.summary_lbl = QLabel("—")
        self.summary_lbl.setStyleSheet(
            "font-size:11px; font-style:italic; padding:8px;"
        )
        _theme_prop(self.summary_lbl, "role", "muted")
        self.summary_lbl.setWordWrap(True)
        outer.addWidget(self.summary_lbl)

        # Log rilevamento (usa lo spazio vuoto per testo utile)
        log_box = QGroupBox("📜 Log rilevamento")
        log_lay = QVBoxLayout(log_box)
        log_lay.setContentsMargins(10, 10, 10, 10)
        self.hw_log = QPlainTextEdit()
        self.hw_log.setReadOnly(True)
        self.hw_log.setMaximumBlockCount(200)
        self.hw_log.setStyleSheet(
            "font-family:'JetBrains Mono','Consolas',monospace; font-size:10.5px;"
        )
        self.hw_log.setPlaceholderText("Il log del rilevamento apparirà qui...")
        log_lay.addWidget(self.hw_log)
        outer.addWidget(log_box, stretch=1)

    # ──────────────────────────────────────────────────────────────────
    # Handler
    # ──────────────────────────────────────────────────────────────────
    # NB: _group_style() rimosso — i QGroupBox ora prendono lo stile dal
    # tema app-level (QGroupBox nei .qss), così seguono il tema live.

    def _refresh_profile(self):
        """Rileva l'hardware e aggiorna la GUI."""
        try:
            from CORE.hardware_detector import get_profile, STRATEGIES
            # Forza refresh (utile se è stata collegata una GPU esterna)
            profile = get_profile(force_refresh=True)

            # Popola info hardware
            self.info_labels["platform"].setText(profile.platform)
            self.info_labels["gpu_type"].setText(profile.gpu_type)
            self.info_labels["gpu_name"].setText(profile.gpu_name or "—")
            unified_text = "✓ Sì (Apple Silicon)" if profile.memory_unified else "✗ No (dedicata)"
            self.info_labels["memory_unified"].setText(unified_text)
            self.info_labels["ram_total"].setText(f"{profile.ram_total_gb:.1f} GB")
            if profile.vram_total_gb > 0:
                self.info_labels["vram_total"].setText(f"{profile.vram_total_gb:.1f} GB")
            else:
                self.info_labels["vram_total"].setText("— (no GPU)")
            if profile.bandwidth_gbps > 0:
                self.info_labels["bandwidth"].setText(f"{profile.bandwidth_gbps:.0f} GB/s")
            else:
                self.info_labels["bandwidth"].setText("—")
            self.info_labels["cpu_cores"].setText(str(profile.cpu_cores))

            # Nuovi campi: modello configurato + fits VRAM
            if profile.model_size_gb > 0:
                self.info_labels["model_size"].setText(
                    f"{profile.model_size_gb:.1f} GB (modello più grande in actors.json)"
                )
            else:
                self.info_labels["model_size"].setText("— (nessun actors.json)")
            if profile.vram_total_gb > 0:
                fits_text = "✓ Sì — GPU verrà usata" if profile.model_fits_vram else "✗ No — userà CPU"
                color = "#16a34a" if profile.model_fits_vram else "#dc2626"
                self.info_labels["model_fits"].setText(
                    f'<span style="color:{color};font-weight:bold">{fits_text}</span>'
                )
            else:
                self.info_labels["model_fits"].setText("— (no GPU)")

            # Badge strategia
            strat_colors = {
                "unified_parallel": ("#16a34a", "🚀 unified_parallel"),
                "unified_light":    ("#16a34a", "⚡ unified_light"),
                "nvidia_dual":      ("#2563eb", "🎮 nvidia_dual"),
                "nvidia_cpu_split": ("#2563eb", "🔀 nvidia_cpu_split"),
                "nvidia_light":     ("#0891b2", "💡 nvidia_light"),
                "amd_dual":         ("#dc2626", "🎮 amd_dual"),
                "amd_light":        ("#dc2626", "💡 amd_light"),
                "cpu_only":         ("#666666", "💻 cpu_only"),
            }
            color, label = strat_colors.get(
                profile.strategy, ("#666666", profile.strategy))
            self.strat_badge.setText(f"Strategia: {label}")
            self.strat_badge.setStyleSheet(
                f"background:{color}11; border:2px solid {color}; border-radius:8px; "
                f"padding:16px; font-size:18px; font-weight:bold; color:{color};"
            )

            # Descrizione
            self.strat_desc.setText(profile.description)

            # Parametri
            self.strat_params.setText(
                f"<table cellpadding='4' style='font-size:13px;'>"
                f"<tr><td><b>Worker paralleli:</b></td><td>{profile.worker_count}</td></tr>"
                f"<tr><td><b>Keep alive:</b></td><td>{profile.keep_alive_sec}s</td></tr>"
                f"<tr><td><b>Modelli in RAM:</b></td><td>{profile.models_in_ram}</td></tr>"
                f"<tr><td><b>Multi-modello:</b></td><td>"
                f"{'✓ Supportato' if profile.supports_multi_model else '✗ Non supportato'}"
                f"</td></tr>"
                f"<tr><td><b>Worker paralleli:</b></td><td>"
                f"{'✓ Supportato' if profile.supports_parallel_workers else '✗ Non supportato'}"
                f"</td></tr>"
                f"</table>"
            )

            # Summary
            self.summary_lbl.setText(f"📊 {profile.summary}")

            # Log rilevamento (usa lo spazio vuoto per testo utile)
            import time as _t
            self.hw_log.appendPlainText(
                f"[{_t.strftime('%H:%M:%S')}] Rilevamento OK"
            )
            self.hw_log.appendPlainText(
                f"  Piattaforma: {profile.platform}"
            )
            self.hw_log.appendPlainText(
                f"  GPU: {profile.gpu_type} — {profile.gpu_name or '—'}"
            )
            self.hw_log.appendPlainText(
                f"  RAM: {profile.ram_total_gb:.1f} GB  "
                f"VRAM: {profile.vram_total_gb:.1f} GB  "
                f"BW: {profile.bandwidth_gbps:.0f} GB/s"
            )
            self.hw_log.appendPlainText(
                f"  Strategia: {profile.strategy}  "
                f"worker={profile.worker_count}  "
                f"keep_alive={profile.keep_alive_sec}s"
            )
            self.hw_log.appendPlainText(f"  {profile.summary}")
            self.hw_log.appendPlainText("")

        except Exception as e:
            self.strat_badge.setText(f"✗ Errore rilevamento: {e}")
            self.strat_badge.setStyleSheet(
                "padding:16px; font-size:14px; font-weight:bold;"
            )
            _theme_banner(self.strat_badge, "error")
            try:
                import time as _t
                self.hw_log.appendPlainText(
                    f"[{_t.strftime('%H:%M:%S')}] ERRORE: {e}"
                )
            except Exception:
                pass

    def _back_to_main(self):
        """Torna alla plancia di controllo."""
        p = self.parent()
        while p and not hasattr(p, "back_to_main"):
            p = p.parent()
        if p and hasattr(p, "back_to_main"):
            p.back_to_main()
