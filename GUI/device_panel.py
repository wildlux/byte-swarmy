"""device_panel.py — Barra superiore con indicatori CPU/GPU e controlli Git.

Estratto da GUI/control_center.py per ridurre il monolite.
"""

from __future__ import annotations

import os
import subprocess
import time

from PyQt6.QtWidgets import (
    QFrame, QHBoxLayout, QVBoxLayout, QPushButton, QLabel,
    QSizePolicy, QMessageBox,
)
from PyQt6.QtCore import Qt

from GUI import settings_store


class DevicePanel(QFrame):
    """Barra superiore con indicatori CPU/GPU e controlli Git."""

    def __init__(self, control_center=None):
        super().__init__()
        self.setObjectName("device_panel")
        self.setMinimumHeight(56)
        lay = QHBoxLayout(self)
        lay.setContentsMargins(6, 4, 6, 4)
        lay.setSpacing(8)

        devices_col = QVBoxLayout()
        devices_col.setSpacing(2)
        devices_col.setContentsMargins(0, 0, 0, 0)

        self.cpu_box = self._device_row("CPU", "#16a34a", "qwen2.5:1.5b")
        self.gpu_box = self._device_row("GPU", "#2563eb", "—")

        devices_col.addWidget(self.cpu_box)
        devices_col.addWidget(self.gpu_box)
        lay.addLayout(devices_col)

        sep = QFrame()
        sep.setFixedWidth(1)
        sep.setStyleSheet("background:#d0d0d0;")
        lay.addWidget(sep)

        self.git_btn = QPushButton("💾")
        self.git_btn.setMinimumWidth(36)
        self.git_btn.setFixedHeight(46)
        self.git_btn.setObjectName("git_btn")
        self.git_btn.setToolTip("Salva su tutti i remote Git configurati")
        self.git_btn.setStyleSheet(
            "QPushButton#git_btn { background:transparent; color:#6b7280; "
            "font-size:16px; border:1px solid #e5e7eb; border-radius:6px; border:none; }"
            "QPushButton#git_btn:hover { background:#f3f4f6; border-color:#9ca3af; }"
        )
        self.git_btn.clicked.connect(self._do_git_save)
        lay.addWidget(self.git_btn)

        self.pause_btn = QPushButton("▶")
        self.pause_btn.setMinimumWidth(44)
        self.pause_btn.setFixedHeight(46)
        self.pause_btn.setObjectName("primary_btn")
        self.pause_btn.setToolTip("Pausa/Riprendi Orchestratore")
        self.pause_btn.setStyleSheet(
            "QPushButton#primary_btn { background:#16a34a; color:white; "
            "font-weight:bold; font-size:16px; border-radius:6px; border:none; }"
            "QPushButton#primary_btn:hover { background:#15803d; }"
        )
        self.pause_btn.clicked.connect(
            control_center._toggle_orchestrator if control_center else self._toggle_orchestrator
        )
        lay.addWidget(self.pause_btn)

        self.stop_btn = QPushButton("⏹")
        self.stop_btn.setMinimumWidth(44)
        self.stop_btn.setFixedHeight(46)
        self.stop_btn.setObjectName("stop_btn")
        self.stop_btn.setToolTip("Ferma Orchestratore")
        self.stop_btn.setStyleSheet(
            "QPushButton#stop_btn { background:#dc2626; color:white; "
            "font-weight:bold; font-size:16px; border-radius:6px; border:none; }"
            "QPushButton#stop_btn:hover { background:#b91c1c; }"
        )
        self.stop_btn.clicked.connect(
            control_center._stop_orchestrator if control_center else self._stop_orchestrator
        )
        lay.addWidget(self.stop_btn)

        self.git_remotes = self._detect_git_remotes()
        self._update_git_tooltip()

    def _open_actors_panel(self):
        """Le righe CPU/GPU sono cliccabili: portano a Modelli → Attori."""
        p = self.parent()
        while p is not None and not hasattr(p, "center"):
            p = p.parent()
        if p is not None:
            p.center.open_panel("modelli")

    def _detect_git_remotes(self):
        remotes = []
        try:
            result = subprocess.run(
                ["git", "remote", "-v"],
                capture_output=True, text=True, timeout=5
            )
            if result.returncode == 0:
                seen = set()
                for line in result.stdout.strip().split("\n"):
                    if line:
                        name = line.split()[0]
                        if name not in seen:
                            seen.add(name)
                            url = line.split()[1]
                            if "github" in url:
                                remotes.append(("GitHub", name))
                            elif "gitlab" in url:
                                remotes.append(("GitLab", name))
                            else:
                                remotes.append(("Git", name))
        except Exception:
            pass
        if not remotes:
            remotes = [("Git", "origin")]
        return remotes

    def _update_git_tooltip(self):
        names = [r[0] for r in self.git_remotes]
        if len(names) == 1:
            self.git_btn.setToolTip(f"Salva su {names[0]}")
        else:
            self.git_btn.setToolTip(f"Salva su {', '.join(names)}")

    def _do_git_save(self):
        """Salva (push) su tutti i remote Git configurati.

        Implementazione reale:
          1. legge i remote salvati in CONFIG/settings.json (SettingsPanel)
          2. **C1**: apre dialog di conferma con lista dei remote
          3. per ogni remote, inietta il token nell'URL (https://oauth2:TOKEN@...)
          4. fa `git add -A` + `git commit -m "Auto-sync ..."` + `git push REMOTE BRANCH`
          5. **C2**: raccoglie gli errori e mostra dialog di riepilogo

        Se non ci sono remote configurati nel settings store, usa i remote
        git locali (rilevati con `git remote -v`) come fallback.
        """
        import time as _time, os as _os
        from GUI import settings_store as ss

        # 1) Leggi i remote configurati dall'utente nel SettingsPanel
        configured = ss.get_git_remotes()
        # 2) Se vuoti, fallback ai remote git locali (vecchio comportamento)
        if not configured:
            names = [r[0] for r in self.git_remotes]
            print(f"[GIT] Nessun remote configurato in settings. Uso i remote locali: {', '.join(names)}")
            # C1: conferma anche per il fallback ai remote locali
            ok = self._confirm_push(
                title="Salvataggio su Git (remote locali)",
                remote_list=[(n, "(remote git locale)", r) for r, n in self.git_remotes],
            )
            if not ok:
                return
            errors = []
            for rtype, name in self.git_remotes:
                err = self._git_push_one(name, None, branch=None)
                if err:
                    errors.append((name, err))
            # C2: dialog di riepilogo
            self._show_push_summary(
                total=len(self.git_remotes),
                errors=errors,
                remote_list=[(n, "(remote git locale)") for r, n in self.git_remotes],
            )
            return

        # 3) **C1**: dialog di conferma con lista dei remote
        remote_list_for_dialog = []
        env_key_by_type = {
            "github": "BSWARM_GITHUB_TOKEN",
            "gitlab": "BSWARM_GITLAB_TOKEN",
        }
        for r in configured:
            name = r.get("name", "?")
            url = r.get("url", "")
            rtype = r.get("type", "git")
            env_key = env_key_by_type.get(str(rtype).lower())
            env_token = _os.environ.get(env_key, "") if env_key else ""
            source = f"env {env_key}" if env_token else "CONFIG/settings.json"
            remote_list_for_dialog.append((name, url, source))

        ok = self._confirm_push(
            title=f"Salvataggio su {len(configured)} remote Git",
            remote_list=remote_list_for_dialog,
        )
        if not ok:
            print("[GIT] Push annullato dall'utente.")
            return

        # 4) Push su ogni remote + raccoglie errori per C2
        print(f"[GIT] Salvataggio su {len(configured)} remote configurati:")
        errors = []
        for r in configured:
            name = r.get("name", "?")
            url = r.get("url", "")
            token = r.get("token", "")
            rtype = r.get("type", "git")
            # T1.3: il token da env ha SEMPRE priorità su quello salvato
            env_key = env_key_by_type.get(str(rtype).lower())
            env_token = _os.environ.get(env_key, "") if env_key else ""
            if env_token:
                token = env_token
                print(f"  • {name} ({rtype}): {url} [token da env {env_key}]")
            else:
                print(f"  • {name} ({rtype}): {url} [token da CONFIG]")
            err = self._git_push_one(name, url, token=token)
            if err:
                errors.append((name, err))

        # 5) **C2**: dialog di riepilogo
        self._show_push_summary(
            total=len(configured),
            errors=errors,
            remote_list=[(n, u) for n, u, _ in remote_list_for_dialog],
        )

    def _confirm_push(self, title: str, remote_list) -> bool:
        """C1: dialog di conferma prima del push. Ritorna True se l'utente
        conferma, False se annulla.

        ``remote_list`` è una lista di tuple:
          - (name, url, source) — per i remote da CONFIG
          - (name, url, type) — per i remote git locali (compat)
        """
        lines = ["Questa operazione farà:"]
        lines.append("  • git add -A  (tutte le modifiche)")
        lines.append("  • git commit -m \"Auto-sync YYYY-MM-DD HH:MM:SS\"")
        lines.append("  • git push REMOTE BRANCH  (su tutti i remote sotto)")
        lines.append("")
        lines.append(f"Remote ({len(remote_list)}):")
        for entry in remote_list:
            if len(entry) == 3:
                name, url, info = entry
            else:
                name, url = entry
                info = ""
            icon = "🐙" if "github" in str(info).lower() or "github" in url else (
                "🦊" if "gitlab" in url else "📂"
            )
            line = f"  {icon} {name} — {url}"
            if info and info not in ("github", "gitlab", "git"):
                line += f"  [token: {info}]"
            lines.append(line)
        lines.append("")
        lines.append("Vuoi continuare?")
        msg = QMessageBox(self)
        msg.setWindowTitle("Conferma push Git")
        msg.setIcon(QMessageBox.Icon.Question)
        msg.setText("\n".join(lines))
        msg.setStandardButtons(QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
        msg.setDefaultButton(QMessageBox.StandardButton.No)
        return msg.exec() == QMessageBox.StandardButton.Yes

    def _show_push_summary(self, total: int, errors, remote_list):
        """C2: dialog di riepilogo dopo il push.

        - Se 0 errori: dialog informativo "✅ Push completato"
        - Se alcuni errori: dialog di warning con elenco errori
        - Se tutti falliti: dialog critical
        """
        success = total - len(errors)
        if not errors:
            QMessageBox.information(
                self,
                "Push completato",
                f"✅ Push completato con successo su tutti i {total} remote.\n\n"
                + "\n".join(f"  ✓ {n} — {u}" for n, u in remote_list),
            )
            return
        if success == 0:
            icon = QMessageBox.Icon.Critical
            title = "Push fallito su tutti i remote"
            head = f"❌ Tutti i {total} push sono falliti:\n\n"
        else:
            icon = QMessageBox.Icon.Warning
            title = f"Push parziale: {success}/{total} OK"
            head = (f"⚠️ {success}/{total} remote OK, {len(errors)} falliti:\n\n")
        body = head + "\n".join(f"  ✗ {n}: {e[:200]}" for n, e in errors)
        msg = QMessageBox(self)
        msg.setWindowTitle(title)
        msg.setIcon(icon)
        msg.setText(body)
        msg.exec()

    def _git_push_one(self, remote_name: str, url: str | None, token: str = "", branch: str | None = None):
        """Esegue git add + commit + push su un singolo remote.

        Se ``url`` è None, usa il remote locale già configurato in .git/config.

        Se ``token`` è presente, lo inietta nell'URL per il push (https only).

        Ritorna: ``None`` se tutto OK, oppure una stringa con l'errore.
        """
        import os as _os, subprocess as _subprocess, time as _time

        base_dir = _os.path.dirname(_os.path.dirname(_os.path.abspath(__file__)))
        ts = _time.strftime("%Y-%m-%d %H:%M:%S")
        commit_msg = f"Auto-sync {ts}"

        try:
            # 1) git add -A
            r_add = _subprocess.run(
                ["git", "add", "-A"],
                cwd=base_dir, capture_output=True, text=True, timeout=30,
            )
            if r_add.returncode != 0:
                err = f"git add fallito: {r_add.stderr.strip()}"
                print(f"[GIT:{remote_name}] {err}")
                return err

            # 2) git commit -m "Auto-sync ..." (ok anche se nothing to commit)
            r_commit = _subprocess.run(
                ["git", "commit", "-m", commit_msg],
                cwd=base_dir, capture_output=True, text=True, timeout=30,
            )
            if r_commit.returncode != 0 and "nothing to commit" not in r_commit.stdout.lower():
                # "nothing to commit" non è un errore: push OK anche senza modifiche
                err = f"commit: {r_commit.stdout.strip() or r_commit.stderr.strip()}"
                print(f"[GIT:{remote_name}] {err}")
                return err

            # 3) Determina branch corrente (default main)
            if branch is None:
                r_branch = _subprocess.run(
                    ["git", "rev-parse", "--abbrev-ref", "HEAD"],
                    cwd=base_dir, capture_output=True, text=True, timeout=5,
                )
                branch = r_branch.stdout.strip() or "main"

            # 4) Se url + token forniti, inietta il token per il push
            push_url = None
            if url and token and url.startswith("https://"):
                push_url = url.replace("https://", f"https://oauth2:{token}@")
            elif url and token and url.startswith("http://"):
                push_url = url.replace("http://", f"http://oauth2:{token}@")

            if push_url:
                # Push diretto usando URL con token
                r_push = _subprocess.run(
                    ["git", "push", push_url, branch],
                    cwd=base_dir, capture_output=True, text=True, timeout=120,
                )
            else:
                # Push usando il remote locale già configurato
                r_push = _subprocess.run(
                    ["git", "push", remote_name, branch],
                    cwd=base_dir, capture_output=True, text=True, timeout=120,
                )

            if r_push.returncode == 0:
                print(f"[GIT:{remote_name}] ✓ push OK ({branch})")
                return None  # success
            else:
                err = r_push.stderr.strip() or r_push.stdout.strip()
                print(f"[GIT:{remote_name}] ✗ push fallito: {err}")
                return err

        except _subprocess.TimeoutExpired:
            err = "timeout (push > 120s)"
            print(f"[GIT:{remote_name}] ✗ {err}")
            return err
        except FileNotFoundError:
            err = "git non trovato (subprocess)"
            print(f"[GIT:{remote_name}] ✗ {err}")
            return err
        except Exception as e:
            err = f"{type(e).__name__}: {e}"
            print(f"[GIT:{remote_name}] ✗ {err}")
            return err

    def _device_row(self, name, color, model_name):
        row = QFrame()
        row.setObjectName(f"{name.lower()}_row")
        row.setMinimumHeight(24)
        row.setStyleSheet(
            f"QFrame#{name.lower()}_row {{ border:1px solid {color}44; "
            f"border-radius:4px; }}"
        )
        # Cliccabile → apre "Modelli → Attori" per scegliere gli LLM
        row.setCursor(Qt.CursorShape.PointingHandCursor)
        row.setToolTip(f"{name}: clicca per configurare i modelli (Modelli → Attori)")
        row.mousePressEvent = lambda e: self._open_actors_panel()
        lay = QHBoxLayout(row)
        lay.setContentsMargins(6, 2, 6, 2)
        lay.setSpacing(6)

        lbl = QLabel(name)
        lbl.setStyleSheet(f"color:{color}; font-size:12px; font-weight:bold;")
        lbl.setMinimumWidth(40)
        lbl.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        lay.addWidget(lbl)

        model_lbl = QLabel(model_name)
        model_lbl.setStyleSheet("font-size:10px;")
        model_lbl.setMinimumWidth(190)
        model_lbl.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        model_lbl.setTextInteractionFlags(Qt.TextInteractionFlag.NoTextInteraction)
        # Tronca con elipsis se troppo lungo, così non spinge i valori a destra
        from PyQt6.QtCore import Qt as _Qt
        model_lbl.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Preferred)
        lay.addWidget(model_lbl)

        temp_lbl = QLabel("-")
        tok_lbl = QLabel("-")
        kv_lbl = QLabel("-")
        mem_lbl = QLabel("-")
        bus_lbl = QLabel("-")

        for w in (temp_lbl, tok_lbl, kv_lbl, mem_lbl, bus_lbl):
            w.setStyleSheet("font-size:11px; font-weight:500;")
            w.setMinimumWidth(42)
            w.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
            lay.addWidget(w)

        # Tooltip sui valori altrimenti criptici (2.1G, 65%, 800M…)
        temp_lbl.setToolTip("Temperatura del dispositivo (°C)")
        tok_lbl.setToolTip("Token generati al secondo (tok/s)")
        kv_lbl.setToolTip("Dimensione cache KV del modello (memoria occupata)")
        mem_lbl.setToolTip("Uso memoria RAM del dispositivo (%)")
        bus_lbl.setToolTip("Larghezza di banda bus / VRAM")

        row._temp = temp_lbl
        row._tok = tok_lbl
        row._kv = kv_lbl
        row._mem = mem_lbl
        row._bus = bus_lbl
        row._model = model_lbl
        return row
