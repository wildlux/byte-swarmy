"""GUI/cc_orchestrator.py — Controlli orchestratore e metriche live.

Estratto da GUI/control_center.py (R3): pausa/ripresa/stop dell'orchestratore,
toggle della toolbar, invio comandi alla coda, barra di completamento e
metriche CPU/GPU/Ollama. Mixin: comportamento invariato.
"""

from __future__ import annotations

import os

from GUI.gui_backend import (
    add_task_to_db, get_cpu_temp, get_gpu_temp, get_metrics,
    get_gpu_freq_mhz, get_gpu_mem_pct, get_ram_pct,
)
from GUI.task_queue import log_user_action as _log_user_action
from INTENT.metrics import estimate_kv_cache_mb


class OrchestratorMixin:
    def _pause_orchestrator(self):
        """Mette in pausa l'orchestratore (crea file state/pause.flag)."""
        try:
            _log_user_action("Sidebar-Orchestratore", "pausa", details="Pausa orchestratore da sidebar")
            import os, time
            base = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            pause_file = os.path.join(base, 'state', 'pause.flag')
            with open(pause_file, 'w') as f:
                f.write(str(time.time()))
            if hasattr(self, '_pause_btn'):
                self._pause_btn.setText("▶ Riprendi")
                self._pause_btn.setStyleSheet("QPushButton { background:#16a34a; color:white; border:none; padding:6px 12px; border-radius:6px; font-weight:bold; }")
                try: self._pause_btn.clicked.disconnect()
                except Exception: pass
                self._pause_btn.clicked.connect(self._resume_orchestrator)
            self.statusBar().showMessage("⏸ Orchestratore in pausa", 3000)
            try:
                self._sync_toggle_icon()
            except Exception:
                pass
        except Exception as e:
            print(f"Errore pausa: {e}")

    def _resume_orchestrator(self):
        """Riprende l'orchestratore."""
        try:
            import os
            base = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            pause_file = os.path.join(base, 'state', 'pause.flag')
            if os.path.exists(pause_file):
                os.remove(pause_file)
            if hasattr(self, '_pause_btn'):
                self._pause_btn.setText("⏸ Pausa")
                self._pause_btn.setStyleSheet("QPushButton { background:#f59e0b; color:white; border:none; padding:6px 12px; border-radius:6px; font-weight:bold; }")
                try: self._pause_btn.clicked.disconnect()
                except Exception: pass
                self._pause_btn.clicked.connect(self._pause_orchestrator)
            self.statusBar().showMessage("▶ Orchestratore ripreso", 3000)
            try:
                self._sync_toggle_icon()
            except Exception:
                pass
        except Exception as e:
            print(f"Errore resume: {e}")

    def _stop_orchestrator(self):
        """Ferma l'orchestratore (kill del processo)."""
        import os, signal
        base = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        pid_file = os.path.join(base, 'state', 'orchestrator.pid')
        try:
            if os.path.exists(pid_file):
                with open(pid_file) as _f:
                    _pid = int(_f.read().strip())
                os.kill(_pid, signal.SIGTERM)
                self.statusBar().showMessage("⏹ Orchestratore fermato", 4000)
                # Rimuovi pause.flag se presente
                pause_file = os.path.join(base, 'state', 'pause.flag')
                if os.path.exists(pause_file):
                    os.remove(pause_file)
                # Reset icona pulsante pausa/riprendi
                btn = self.device_panel.pause_btn
                btn.setText("▶")
                btn.setStyleSheet(
                    "QPushButton#primary_btn { background:#16a34a; color:white; "
                    "font-weight:bold; font-size:16px; border-radius:6px; border:none; }"
                )
            else:
                self.statusBar().showMessage("⚠ Nessun orchestratore in esecuzione", 4000)
        except Exception as e:
            self.statusBar().showMessage(f"⚠ Errore stop: {e}", 5000)

    def _toggle_orchestrator(self):
        """Pausa/Riprendi l'orchestratore (state/pause.flag).

        Pulsante ▶/⏸ della toolbar e voce menu condividono questa logica:
        ▶ (verde) = attivo, click → pausa (⏸ ambra); ⏸ = in pausa,
        click → riprendi (▶ verde).
        """
        import os, time
        btn = self.device_panel.pause_btn
        base = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        pause_file = os.path.join(base, 'state', 'pause.flag')
        pid_file = os.path.join(base, 'state', 'orchestrator.pid')
        running_style = ("QPushButton#primary_btn { background:#16a34a; color:white; "
                         "font-weight:bold; font-size:16px; border-radius:6px; "
                         "border:none; }")
        paused_style = ("QPushButton#primary_btn { background:#f59e0b; color:white; "
                        "font-weight:bold; font-size:14px; border-radius:6px; "
                        "border:none; }")
        # Verifica che l'orchestratore sia effettivamente in esecuzione
        orch_running = False
        try:
            if os.path.exists(pid_file):
                with open(pid_file) as _f:
                    _pid = int(_f.read().strip())
                with open(f"/proc/{_pid}/cmdline", "rb") as _f:
                    _cmd = _f.read().replace(b"\\x00", b" ").decode("utf-8", "replace")
                orch_running = ("orchestrator" in _cmd or "watchdog" in _cmd)
        except Exception:
            orch_running = False
        if not orch_running:
            # Avvia l'orchestratore in background
            try:
                import subprocess as _sp
                python = os.path.join(base, ".venv", "bin", "python")
                if not os.path.exists(python):
                    python = "python3"
                log_path = os.path.join(base, "logs", "byte-swarmy.log")
                os.makedirs(os.path.dirname(log_path), exist_ok=True)
                logf = open(log_path, "a")
                proc = _sp.Popen(
                    [python, "-m", "CORE.orchestrator"],
                    cwd=base,
                    stdout=logf,
                    stderr=logf,
                    start_new_session=True,
                )
                # Scrivi pid file
                with open(pid_file, "w") as _f:
                    _f.write(str(proc.pid))
                # Attendi avvio
                import time as _t
                for _ in range(10):
                    _t.sleep(0.5)
                    if self._is_orchestrator_running():
                        break
                if self._is_orchestrator_running():
                    btn.setText("▶")
                    btn.setStyleSheet(running_style)
                    self.statusBar().showMessage("▶ Orchestratore avviato", 4000)
                else:
                    self.statusBar().showMessage("⚠ Avvio orchestratore fallito: controlla i log", 5000)
            except Exception as e:
                self.statusBar().showMessage(f"⚠ Errore avvio: {e}", 5000)
            return
        try:
            # Stato reale basato sul flag, non sul testo del pulsante
            # (il testo può andare fuori sync dopo pause/resume esterni).
            paused = os.path.exists(pause_file)
            if not paused:
                _log_user_action("Toolbar-Orchestratore", "pausa",
                                 details="Pausa da pulsante ▶ toolbar")
                with open(pause_file, 'w') as f:
                    f.write(str(time.time()))
                btn.setText("⏸")
                btn.setStyleSheet(paused_style)
                self.statusBar().showMessage("⏸ Orchestratore in pausa", 3000)
            else:
                _log_user_action("Toolbar-Orchestratore", "ripreso",
                                 details="Ripresa da pulsante ⏸ toolbar")
                if os.path.exists(pause_file):
                    os.remove(pause_file)
                btn.setText("▶")
                btn.setStyleSheet(running_style)
                self.statusBar().showMessage("▶ Orchestratore ripreso", 3000)
        except Exception as e:
            print(f"Errore toggle orchestratore: {e}")

    def _sync_toggle_icon(self):
        """Allinea l'icona del pulsante ▶/⏸ allo stato reale (pause.flag)."""
        import os
        btn = self.device_panel.pause_btn
        base = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        paused = os.path.exists(os.path.join(base, 'state', 'pause.flag'))
        if paused:
            btn.setText("⏸")
            btn.setStyleSheet(
                "QPushButton#primary_btn { background:#f59e0b; color:white; "
                "font-weight:bold; font-size:14px; border-radius:6px; border:none; }")
        else:
            btn.setText("▶")
            btn.setStyleSheet(
                "QPushButton#primary_btn { background:#16a34a; color:white; "
                "font-weight:bold; font-size:16px; border-radius:6px; border:none; }")

    def _is_orchestrator_running(self) -> bool:
        """True se il processo orchestratore è attivo (via pid file)."""
        import os
        base = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        pid_file = os.path.join(base, "state", "orchestrator.pid")
        try:
            if not os.path.exists(pid_file):
                return False
            with open(pid_file) as _f:
                _pid = int(_f.read().strip())
            with open(f"/proc/{_pid}/cmdline", "rb") as _f:
                _cmd = _f.read().replace(b"\\x00", b" ").decode("utf-8", "replace")
            return ("orchestrator" in _cmd or "watchdog" in _cmd)
        except Exception:
            return False

    def _tick_metrics(self):
        self._cpu_temp = get_cpu_temp()
        self._gpu_temp = get_gpu_temp()

        metrics = get_metrics()
        self._tok_s = metrics.get("tokens_per_sec", 0) if metrics else 0

        # ── Posizione REALE dei modelli (da `ollama ps`) ─────────────
        # Non mostriamo più l'etichetta dell'attore (LLM/Decision) ma
        # DOVE sta effettivamente girando il modello in questo momento:
        #   - 100% GPU  → modello su GPU
        #   - 100% CPU  → modello su CPU
        #   - 80%/20%   → offload parziale
        # Se nessun modello è caricato, mostriamo "(idle)".
        running = self._get_ollama_running_models()
        # running: dict {model_name: {"cpu": int, "gpu": int}}
        # Cerca il modello con uso percentuale più alto per riga
        cpu_model_str = "(idle)"
        gpu_model_str = "(idle)"
        for name, info in running.items():
            cpu_pct = info.get("cpu", 0)
            gpu_pct = info.get("gpu", 0)
            if gpu_pct >= 90:
                # Modello principalmente su GPU
                gpu_model_str = f"{name} ({gpu_pct}%GPU)"
            elif cpu_pct >= 90:
                # Modello principalmente su CPU
                cpu_model_str = f"{name} ({cpu_pct}%CPU)"
            elif cpu_pct > 0 and gpu_pct > 0:
                # Offload parziale: mostra su entrambe le righe
                cpu_model_str = f"{name} ({cpu_pct}%CPU)"
                gpu_model_str = f"{name} ({gpu_pct}%GPU)"
            # Se solo un modello è attivo e sta su GPU, la riga CPU resta (idle)

        cpu = self.device_panel.cpu_box
        cpu._model.setText(cpu_model_str)
        cpu._temp.setText(f"{self._cpu_temp:.0f}°C")
        cpu._tok.setText(f"{self._tok_s:.0f}t/s")

        # Valori reali (non segnaposto hardcoded):
        #   KV cache → stima da context_used + architettura modello
        #   RAM %    → /proc/meminfo
        #   GPU mem %→ nvidia-smi memory.used/memory.total
        #   GPU freq → nvidia-smi clocks.current.graphics
        ram_pct = get_ram_pct()
        gpu_mem_pct = get_gpu_mem_pct()
        gpu_freq = get_gpu_freq_mhz()
        model_name = metrics.get("model", "") if metrics else ""
        ctx = metrics.get("context_used", 0) if metrics else 0
        kv_mb = estimate_kv_cache_mb(ctx, model_name) if ctx > 0 else 0.0

        cpu._kv.setText(f"{kv_mb:.0f}MB" if kv_mb > 0 else "-")
        cpu._mem.setText(f"{ram_pct}%" if ram_pct is not None else "-")
        cpu._bus.setText("-")  # bus CPU non disponibile su questa piattaforma

        gpu = self.device_panel.gpu_box
        gpu._model.setText(gpu_model_str)
        gpu._temp.setText(f"{self._gpu_temp:.0f}°C")
        gpu._kv.setText(f"{kv_mb:.0f}MB" if kv_mb > 0 else "-")
        gpu._mem.setText(f"{gpu_mem_pct}%" if gpu_mem_pct is not None else "-")
        gpu._bus.setText(f"{gpu_freq}M" if gpu_freq is not None else "-")

    def _get_ollama_running_models(self) -> dict:
        """Esegue `ollama ps` e ritorna un dict {model_name: {"cpu": pct, "gpu": pct}}.

        Esempio output ollama ps:
            NAME              SIZE    PROCESSOR           ...
            qwen2.5:1.5b      986 MB  100% GPU            ...
            qwen2.5:7b        4.7 GB  80% CPU / 20% GPU   ...

        Ritorno:
            {"qwen2.5:1.5b": {"cpu": 0, "gpu": 100},
             "qwen2.5:7b":   {"cpu": 80, "gpu": 20}}

        Se ollama non è disponibile o nessun modello è caricato, ritorna {}.
        """
        try:
            import subprocess as _sp
            result = _sp.run(
                ["ollama", "ps"],
                capture_output=True, text=True, timeout=5,
            )
            if result.returncode != 0 or not result.stdout.strip():
                return {}
            lines = result.stdout.strip().split("\n")
            if len(lines) < 2:
                return {}  # solo header, nessun modello
            # Trova l'indice della colonna PROCESSOR dall'header
            header = lines[0].upper()
            proc_idx = header.find("PROCESSOR")
            name_idx = 0  # NAME è sempre la prima colonna
            if proc_idx < 0:
                return {}  # formato inatteso
            running = {}
            for line in lines[1:]:
                if not line.strip():
                    continue
                # Estrai nome modello (primi caratteri fino al primo spazio multiplo)
                parts = line.split(None, 1)
                if not parts:
                    continue
                name = parts[0]
                # Estrai la colonna PROCESSOR
                if len(line) > proc_idx:
                    proc_str = line[proc_idx:].strip()
                else:
                    proc_str = ""
                # Parsifica "100% GPU" o "80% CPU / 20% GPU"
                cpu_pct = 0
                gpu_pct = 0
                import re
                for match in re.finditer(r'(\d+)%\s*(CPU|GPU)', proc_str, re.IGNORECASE):
                    pct = int(match.group(1))
                    kind = match.group(2).upper()
                    if kind == "CPU":
                        cpu_pct = pct
                    elif kind == "GPU":
                        gpu_pct = pct
                if cpu_pct > 0 or gpu_pct > 0:
                    running[name] = {"cpu": cpu_pct, "gpu": gpu_pct}
            return running
        except FileNotFoundError:
            return {}  # ollama non installato
        except Exception:
            return {}  # timeout, parse error, ecc.

    def _send_command(self):
        text = self.cmd_input.text().strip()
        if not text:
            return
        project_path = self.get_current_project_path() if hasattr(self, "get_current_project_path") else None
        project_name = os.path.basename(project_path.rstrip("/")) if project_path else None
        try:
            from GUI.task_queue import add_task
            task = add_task(text, "", "", "code", project_path)
            task_id = task.get("id", "")
        except Exception as e:
            print(f"add_task fallito, fallback globale: {e}")
            try:
                task_id = add_task_to_db(text, project_path=project_path)
            except Exception as e2:
                self.statusBar().showMessage(f"❌ Errore aggiunta task: {e2}", 5000)
                return
        self.cmd_input.clear()
        # Feedback visivo: dove è stato salvato
        where = f"progetto '{project_name}'" if project_name else "coda globale"
        msg = f"✅ Task aggiunto a {where}"
        if task_id:
            msg += f"  (id: {task_id[:18]}…)"
        if not self._is_orchestrator_running():
            msg += "  ⚠ orchestratore NON attivo: il task resta in coda"
        else:
            msg += "  ▶ orchestratore attivo: in elaborazione"
        self.statusBar().showMessage(msg, 6000)
        print(msg)
        # Aggiorna la lista task del drawer/progetto attivo
        try:
            if hasattr(self, "drawer") and self.drawer is not None:
                self.drawer._force_refresh_tasks()
        except Exception as e:
            print(f"refresh task list fallito: {e}")
        # Aggiorna anche il pannello Coda Task del centro (se presente)
        try:
            scheduler = self.center.panel_pages.get("coda") if hasattr(self, "center") else None
            if scheduler is not None and hasattr(scheduler, "refresh"):
                scheduler.refresh()
        except Exception as e:
            print(f"refresh coda panel fallito: {e}")

    def _update_completion_bar(self):
        '''Aggiorna la barra di avanzamento con % task done/total.'''
        try:
            import sqlite3, os
            base = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            db_path = os.path.join(base, "tasks", "queue.db")
            if not os.path.exists(db_path):
                return
            conn = sqlite3.connect(db_path, timeout=3.0)
            project_path = self.get_current_project_path() if hasattr(self, "get_current_project_path") else None
            # Filtro per progetto attivo (se disponibile)
            if project_path:
                proj_filter = " AND project_path = ?"
                proj_params = (project_path,)
            else:
                proj_filter = " AND project_path IS NULL"
                proj_params = ()

            # 1) Task attualmente in esecuzione (in assoluto, per l'animazione)
            running_any = conn.execute(
                "SELECT id, title FROM tasks WHERE status='running' ORDER BY started_at DESC LIMIT 1"
            ).fetchone()
            # Task in esecuzione per il progetto attivo (per il tooltip/dettaglio)
            running = conn.execute(
                "SELECT id, title FROM tasks WHERE status='running'" + proj_filter + " ORDER BY started_at DESC LIMIT 1",
                proj_params,
            ).fetchone()
            target_id = None
            target_title = None
            if running:
                target_id = running[0]
                target_title = running[1]
            elif running_any:
                # C'è un task running ma non del progetto attivo: usa quello per il titolo
                target_id = running_any[0]
                target_title = running_any[1]
            else:
                # 2) Ultimo task top-level con sotto-task
                parents = conn.execute(
                    "SELECT t.id, t.title FROM tasks t "
                    "WHERE t.parent IS NULL AND EXISTS (SELECT 1 FROM tasks c WHERE c.parent=t.id) "
                    + proj_filter.replace(" AND ", " AND t.") + " ORDER BY t.created_at DESC LIMIT 1",
                    proj_params,
                ).fetchone()
                if parents:
                    target_id = parents[0]
                    target_title = parents[1]
                else:
                    # 3) Ultimo task top-level (anche senza sotto-task)
                    last = conn.execute(
                        "SELECT id, title FROM tasks WHERE parent IS NULL" + proj_filter + " ORDER BY created_at DESC LIMIT 1",
                        proj_params,
                    ).fetchone()
                    if last:
                        target_id = last[0]
                        target_title = last[1]

            # Progresso complessivo del progetto attivo (tutti i task)
            proj_total = conn.execute(
                "SELECT COUNT(*) FROM tasks WHERE 1=1" + proj_filter, proj_params
            ).fetchone()[0]
            proj_done = conn.execute(
                "SELECT COUNT(*) FROM tasks WHERE status='done'" + proj_filter, proj_params
            ).fetchone()[0]

            total = proj_total
            done = proj_done

            tot_all = conn.execute("SELECT COUNT(*) FROM tasks").fetchone()[0]
            done_all = conn.execute("SELECT COUNT(*) FROM tasks WHERE status='done'").fetchone()[0]

            # Info sotto-task del task attivo (per tooltip)
            sub_total = 0
            sub_done = 0
            if target_id:
                children = conn.execute(
                    "SELECT status FROM tasks WHERE parent=?", (target_id,)
                ).fetchall()
                if children:
                    sub_total = len(children)
                    sub_done = sum(1 for (s,) in children if s == "done")
                else:
                    st = conn.execute(
                        "SELECT status FROM tasks WHERE id=?", (target_id,)
                    ).fetchone()
                    sub_total = 1
                    sub_done = 1 if (st and st[0] == "done") else 0

            conn.close()

            if hasattr(self, "_completion_bar"):
                # Se c'è un task in esecuzione (qualsiasi progetto) → animazione indeterminata
                # (la barra "carica" per far capire che qualcosa sta succedendo)
                if running_any:
                    self._completion_bar.setRange(0, 0)  # modalità indeterminata
                    self._completion_bar.setFormat("In elaborazione…")
                    self._completion_bar.setToolTip(
                        f"Progetto: {proj_name}\n"
                        f"Task in esecuzione: {target_title or '-'}\n"
                        f"Sotto-task attivi: {sub_done}/{sub_total}\n"
                        f"Totale storico: {done_all}/{tot_all}"
                    )
                else:
                    # Torna a modalità percentuale normale
                    self._completion_bar.setRange(0, 100)
                    pct = int(done * 100 / total) if total > 0 else 0
                    self._completion_bar.setValue(pct)
                    proj_name = os.path.basename((project_path or '').rstrip('/')) or "tutti"
                    # A riposo (nessun task o 0%): mostra "Pronto" e barra vuota
                    if total == 0 or pct == 0:
                        self._completion_bar.setFormat("Pronto")
                        self._completion_bar.setToolTip(
                            f"Progetto: {proj_name}\n"
                            f"Nessun task in coda o tutti completati.\n"
                            f"Totale storico: {done_all}/{tot_all}"
                        )
                    else:
                        self._completion_bar.setFormat(f"{proj_name}: {done}/{total} (%p%)")
                        self._completion_bar.setToolTip(
                            f"Progetto: {proj_name}\n"
                            f"Task completati: {done}/{total} ({pct}%)\n"
                            f"Task attivo: {target_title or '-'}\n"
                            f"Sotto-task attivi: {sub_done}/{sub_total}\n"
                            f"Totale storico: {done_all}/{tot_all}"
                        )
        except Exception:
            pass
