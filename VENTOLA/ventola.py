#!/usr/bin/env python3
"""🌀 Ventole — controllo semplice ventole notebook HP via nbfc + pkexec.

Uso:
    .venv/bin/python tools/fan_control_qt.py

- La temperatura è letta dai sensori (nessun permesso richiesto).
- I comandi root passano da `pkexec`: KDE apre il suo dialog password
  (polkit). Nessun terminale, nessun sudo pre-configurato.
- Bottoni: MAX 100% · AUTO (profilo nbfc) · OFF 0% · Stop servizio.
- Stato best-effort: se il servizio non gira, mostra un messaggio,
  mai crash.
"""

import glob
import sys
from pathlib import Path

from PyQt6.QtCore import QProcess, QTimer
from PyQt6.QtWidgets import (
    QApplication, QGridLayout, QHBoxLayout, QLabel, QPushButton,
    QVBoxLayout, QWidget,
)


def cpu_temp() -> float:
    """Temp CPU VERA (°C): coretemp (per-core max). B0D4 satura a
    100.0 e non è usabile come numero primario (vedi hottest_zone)."""
    vals = []
    for d in glob.glob("/sys/class/hwmon/hwmon*"):
        try:
            if Path(d, "name").read_text().strip() != "coretemp":
                continue
            for p in glob.glob(f"{d}/temp*_input"):
                vals.append(float(Path(p).read_text().strip()) / 1000.0)
        except (OSError, ValueError):
            continue
    return max(vals) if vals else 0.0


def cpu_core_temp() -> float:
    """Temp CPU VERA (°C): max per-core di coretemp (dinamica).

    Cycle 74: B0D4 SATURA a 100.0°C esatti sotto carico (misurato:
    GPU 38°C, CPU max 63°C, B0D4 100.0) → il numero max-zone sembra
    bloccato nella GUI. Il numero primario mostrato è questo.
    """
    vals = []
    for d in glob.glob("/sys/class/hwmon/hwmon*"):
        try:
            if Path(d, "name").read_text().strip() != "coretemp":
                continue
            for p in glob.glob(f"{d}/temp*_input"):
                vals.append(float(Path(p).read_text().strip()) / 1000.0)
        except (OSError, ValueError):
            continue
    return max(vals) if vals else 0.0


def hottest_zone() -> tuple[float, str]:
    """(temp, nome) della zona termica più calda (per la riga secondaria)."""
    best = (0.0, "?")
    for z in glob.glob("/sys/class/thermal/thermal_zone*"):
        try:
            t = float(Path(z, "temp").read_text().strip()) / 1000.0
            name = Path(z, "type").read_text().strip()
            if t > best[0]:
                best = (t, name)
        except (OSError, ValueError):
            continue
    return best


def max_temp() -> float:
    """Compatibilità: alias di cpu_temp (fonte vera)."""
    return cpu_temp()


def root_cmd(sh: str) -> list:
    """Comando con privilegi via pkexec (dialog password di KDE)."""
    return ["pkexec", "sh", "-c", sh]


class FanControl(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("🌀 Ventole — nbfc")
        self._proc: QProcess | None = None

        lay = QVBoxLayout(self)
        lay.setSpacing(10)

        self.temp = QLabel("🌡️ …")
        self.temp.setStyleSheet("font-size: 34px; font-weight: 600;")
        lay.addWidget(self.temp)

        self.state = QLabel("…")
        self.state.setStyleSheet("color: gray;")
        lay.addWidget(self.state)

        grid = QGridLayout()
        self.btn_max = QPushButton("🌀 MAX 100%")
        self.btn_auto = QPushButton("🌙 AUTO")
        self.btn_off = QPushButton("⛔ OFF 0%")
        self.btn_stop = QPushButton("🛑 Stop servizio")
        for b in (self.btn_max, self.btn_auto, self.btn_off, self.btn_stop):
            b.setMinimumHeight(44)
        grid.addWidget(self.btn_max, 0, 0)
        grid.addWidget(self.btn_auto, 0, 1)
        grid.addWidget(self.btn_off, 1, 0)
        grid.addWidget(self.btn_stop, 1, 1)
        lay.addLayout(grid)

        self.msg = QLabel("Pronto. Ti chiede la password al primo comando.")
        self.msg.setWordWrap(True)
        lay.addWidget(self.msg)

        self.btn_max.clicked.connect(lambda: self._run("start & set", True))
        self.btn_auto.clicked.connect(lambda: self._run("start & auto", True))
        self.btn_off.clicked.connect(lambda: self._run("start & off", True))
        self.btn_stop.clicked.connect(lambda: self._run("stop", True))

        self.t = QTimer(self)  # UN solo timer (disciplina byte-swarmy)
        self.t.timeout.connect(self._tick)
        self.t.start(2000)
        self._tick()

    # ------------------------------------------------------------------
    def _tick(self) -> None:
        cpu = cpu_core_temp()
        hot, hot_name = hottest_zone()
        # Primario: CPU vera (dinamica — B0D4 satura e sembrerebbe bloccato)
        self.temp.setText(f"🌡️ CPU {cpu:.1f}°C")
        if cpu >= 80:
            self.temp.setStyleSheet(
                "font-size: 34px; font-weight: 600; color: #b91c1c;")
        elif cpu >= 60:
            self.temp.setStyleSheet(
                "font-size: 34px; font-weight: 600; color: #b45309;")
        else:
            self.temp.setStyleSheet(
                "font-size: 34px; font-weight: 600; color: #15803d;")
        # Secondario: la zona più calda (trasparenza, niente nascosto)
        warn = ""
        if hot >= 95.0 and cpu < 80:
            warn = " — ⚠️ satura (sensore DPTF noto difettoso)"
        self.state.setText(
            f"zona più calda: {hot_name} {hot:.1f}°C{warn}")

    def _run(self, what: str, _root: bool) -> None:
        cmds = {
            "start & set": "nbfc start && nbfc set -s 100",
            "start & auto": "nbfc start && nbfc set -a",
            "start & off": "nbfc start && nbfc set -s 0",
            "stop": "nbfc stop",
        }
        cmd = root_cmd(cmds[what])
        if self._proc is not None and self._proc.state() != QProcess.ProcessState.NotRunning:
            self.msg.setText("⏳ Un comando è già in corso…")
            return
        p = QProcess(self)
        p.finished.connect(
            lambda code, _s, w=what: self._done(code, w))
        self._proc = p
        for b in (self.btn_max, self.btn_auto, self.btn_off, self.btn_stop):
            b.setEnabled(False)
        self.msg.setText("🔐 Autorizza nel dialog di KDE…")
        p.start(cmd[0], cmd[1:])

    def _done(self, code: int, what: str) -> None:
        for b in (self.btn_max, self.btn_auto, self.btn_off, self.btn_stop):
            b.setEnabled(True)
        labels = {
            "start & set": "Ventole al 100%",
            "start & auto": "Controllo automatico",
            "start & off": "Ventole spente",
            "stop": "Servizio nbfc fermato",
        }
        if code == 0:
            self.msg.setText(f"✅ {labels[what]}")
            self.state.setText(labels[what])
        elif code in (126, 127):
            self.msg.setText("❌ Autorizzazione annullata o pkexec assente.")
        else:
            self.msg.setText(f"❌ Comando fallito (exit {code}). "
                             "Servizio già attivo? Controlla `nbfc status`.")


if __name__ == "__main__":
    app = QApplication(sys.argv)
    w = FanControl()
    w.show()
    sys.exit(app.exec())
