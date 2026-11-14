"""GUI/cc_shutdown.py — Chiusura finestra e terminazione orchestratore.

Estratto da GUI/control_center.py (R3): validazione PID, terminazione
SIGTERM→SIGKILL bloccante, closeEvent con scelta ricordata. Mixin:
comportamento invariato (test in tests/test_close_orchestrator.py).
"""

from __future__ import annotations

import os

from PyQt6.QtWidgets import QApplication, QCheckBox, QMessageBox

from GUI import settings_store


class ShutdownMixin:
    def _orchestrator_pid(self) -> tuple:
        """PID dell'orchestratore da state/orchestrator.pid, con validazione
        di sicurezza (come byte-swarm.sh stop): il processo deve esistere E
        il suo cmdline deve contenere 'orchestrator' o 'watchdog' — così un
        pid file stantio o un pid riutilizzato non fanno terminare processi
        innocenti. Ritorna (pid, alive); (None, False) se non attivo.
        """
        import signal  # noqa: F401  (coerente con il resto del file)
        base = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        pid_file = os.path.join(base, 'state', 'orchestrator.pid')
        try:
            if not os.path.exists(pid_file):
                return None, False
            raw = ""
            with open(pid_file) as _f:
                raw = _f.read().strip()
            if not raw.isdigit():
                return None, False
            pid = int(raw)
            os.kill(pid, 0)  # solleva ProcessLookupError se non esiste
        except ProcessLookupError:
            return None, False
        except PermissionError:
            return None, False
        except Exception:
            return None, False
        # Cmdline check: deve davvero essere l'orchestratore
        try:
            with open(f"/proc/{pid}/cmdline", "rb") as _fh:
                cmdline = _fh.read().decode(errors="replace")
            if "orchestrator" not in cmdline and "watchdog" not in cmdline:
                return None, False  # pid riutilizzato: non toccare
        except Exception:
            pass  # /proc non leggibile: resta "vivo" (solo il nostro pid file)
        return pid, True

    def _terminate_orchestrator_blocking(self, timeout_s: float = 5.0) -> bool:
        """Termina l'orchestratore SINCRONAMENTE, prima che la finestra
        si chiuda. SIGTERM → attesa attiva (poll 0.2 s) → SIGKILL di
        riserva → attesa → rimozione pid file. Ritorna True se il
        processo non è più in esecuzione (o non stava girando).
        """
        import signal, time
        pid, alive = self._orchestrator_pid()
        if pid is None or not alive:
            return True
        base = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        pid_file = os.path.join(base, 'state', 'orchestrator.pid')
        try:
            self.statusBar().showMessage(
                f"⏹ Chiusura orchestratore (PID {pid})...")
            QApplication.processEvents()  # lascia dipingere il messaggio
        except Exception:
            pass
        try:
            os.kill(pid, signal.SIGTERM)
        except Exception:
            pass

        def _wait_dead(limit: float) -> bool:
            deadline = time.monotonic() + limit
            while time.monotonic() < deadline:
                if not self._pid_alive(pid):
                    return True
                time.sleep(0.2)
            return False

        dead = _wait_dead(timeout_s)
        if not dead:
            try:
                os.kill(pid, signal.SIGKILL)
            except Exception:
                pass
            dead = _wait_dead(2.0)
        try:
            if os.path.exists(pid_file):
                os.remove(pid_file)
        except Exception:
            pass
        return dead

    @staticmethod
    def _pid_alive(pid: int) -> bool:
        """True se il processo esiste e NON è zombie.

        Un processo figlio terminato ma non ancora reaped resta in /proc
        come zombie: kill(pid, 0) lo considera vivo — per questo si
        controlla anche lo stato in /proc/PID/stat.
        """
        try:
            os.kill(pid, 0)
        except Exception:
            return False
        try:
            with open(f"/proc/{pid}/stat", "rb") as _fh:
                tail = _fh.read().decode(errors="replace").rpartition(")")[2]
            fields = tail.split()
            return bool(fields) and fields[0] != "Z"
        except Exception:
            return True  # /proc non leggibile: conservativo, assume vivo

    def closeEvent(self, event):
        """Chiusura finestra: se l'orchestratore è attivo, lo termina
        PRIMA di chiudere la finestra (o applica la scelta ricordata
        nelle impostazioni: stop / keep / chiedi ogni volta).
        """
        try:
            pid, alive = self._orchestrator_pid()
            if pid is None or not alive:
                event.accept()
                return
            remembered = settings_store.get_close_action()

            if remembered == "keep":
                event.accept()
                return

            if remembered != "stop":
                box = QMessageBox(self)
                box.setWindowTitle("Chiudi BYTE-SWARMY")
                box.setIcon(QMessageBox.Icon.Question)
                box.setText(
                    "L'orchestratore è ancora attivo in background.\n"
                    "Cosa vuoi fare?")
                btn_stop = box.addButton(
                    "Termina e chiudi",
                    QMessageBox.ButtonRole.AcceptRole)
                btn_stop.setDefault(True)
                btn_keep = box.addButton(
                    "Lascia attivo in background",
                    QMessageBox.ButtonRole.NoRole)
                btn_cancel = box.addButton(
                    "Annulla", QMessageBox.ButtonRole.RejectRole)
                cb = QCheckBox("Ricorda questa scelta")
                box.setCheckBox(cb)
                box.exec()
                clicked = box.clickedButton()
                if clicked is btn_cancel:
                    event.ignore()
                    return
                if cb.isChecked():
                    try:
                        settings_store.set_close_action(
                            "stop" if clicked is btn_stop else "keep")
                    except Exception:
                        pass
                if clicked is not btn_stop:
                    event.accept()
                    return

            ok = self._terminate_orchestrator_blocking()
            if ok:
                self.statusBar().showMessage("⏹ Orchestratore fermato", 3000)
                event.accept()
            else:
                # Non risponde nemmeno a SIGKILL: chiede conferma esplicita
                reply = QMessageBox.question(
                    self, "Chiusura",
                    "L'orchestratore non ha risposto alla terminazione.\n"
                    "Chiudere comunque la finestra (l'orchestratore resta "
                    "attivo)?",
                    QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
                if reply == QMessageBox.StandardButton.Yes:
                    event.accept()
                else:
                    event.ignore()
        except Exception:
            # Fail-open: mai bloccare la chiusura della finestra
            event.accept()
