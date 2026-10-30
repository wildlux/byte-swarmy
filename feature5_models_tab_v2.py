#!/usr/bin/env python3
"""feature5_models_tab_v2.py — Versione con save_and_restart corretto."""
import re
import shutil
from pathlib import Path

GUI_FILE = Path("GUI/main_window.py")
BACKUP = Path("GUI/main_window.py.bak.modelstab2")


# Metodo save_and_restart corretto (senza stringa multilinea in subprocess)
SAVE_METHOD = '''    def save_and_restart(self) -> None:
        """Salva le selezioni nel config.toml e riavvia l'orchestratore."""
        reply = QMessageBox.question(
            self, "Conferma salvataggio",
            "Salvare i modelli selezionati nel config.toml e riavviare l'orchestratore?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.Yes
        )
        if reply != QMessageBox.StandardButton.Yes:
            return
        
        self.status_label.setText("Salvataggio...")
        
        try:
            import tomllib
            import tomli_w
            import shutil
            import os
            import signal
            import time
            import subprocess
            import sys
            
            config_path = Path("CONFIG/config.toml")
            backup = config_path.with_suffix(".toml.bak.modelsel")
            shutil.copy2(config_path, backup)
            
            with open(config_path, "rb") as f:
                cfg = tomllib.load(f)
            
            models_cfg = cfg.get("models", {})
            role_to_section = {
                "orchestrator": "orchestrator",
                "planner": "planner",
                "worker_coder": "worker_coder",
                "worker_general": "worker_general",
                "embedding": "embedding",
            }
            for role, section in role_to_section.items():
                combo = self.role_combos[role]
                model_name = combo.currentData()
                if model_name:
                    if section not in models_cfg:
                        models_cfg[section] = {}
                    models_cfg[section]["name"] = model_name
            
            dec_combo = self.role_combos["decision"]
            dec_model = dec_combo.currentData()
            if dec_model:
                decision_cfg = cfg.get("decision_models", {})
                for k, v in decision_cfg.items():
                    if isinstance(v, dict) and "enabled" in v:
                        v["enabled"] = (v.get("name") == dec_model)
                if not any(
                    isinstance(v, dict) and v.get("name") == dec_model
                    for v in decision_cfg.values()
                ):
                    section_name = dec_model.split(":")[0].replace("-", "_").replace(".", "_")
                    decision_cfg[section_name] = {
                        "name": dec_model,
                        "enabled": True,
                        "temperature": 0.1,
                        "num_ctx": 4096,
                    }
                    decision_cfg["active"] = section_name
                else:
                    for k, v in decision_cfg.items():
                        if isinstance(v, dict) and v.get("name") == dec_model:
                            decision_cfg["active"] = k
                            break
                cfg["decision_models"] = decision_cfg
            
            cfg["models"] = models_cfg
            
            with open(config_path, "wb") as f:
                tomli_w.dump(cfg, f)
            
            self.status_label.setText("✓ Config salvato. Riavvio orchestratore...")
            
            # Riavvia orchestratore
            pid_file = Path("state/orchestrator.pid")
            if pid_file.exists():
                try:
                    pid = int(pid_file.read_text().strip())
                    os.kill(pid, signal.SIGTERM)
                except Exception:
                    pass
            time.sleep(2)
            subprocess.Popen(
                [sys.executable, "-m", "SAFETY.watchdog"],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                start_new_session=True,
            )
            
            self.status_label.setText("✓ Orchestratore riavviato con nuovi modelli!")
            
        except Exception as e:
            self.status_label.setText(f"❌ Errore: {e}")
            import traceback
            QMessageBox.critical(self, "Errore", traceback.format_exc())
'''


def main():
    if not GUI_FILE.exists():
        return 1
    
    content = GUI_FILE.read_text()
    
    if "class ModelsTab" in content:
        print("ℹ  ModelsTab già presente, rimuovo prima di riapplicare")
        # Ripristina backup se esiste
        if BACKUP.exists():
            shutil.copy2(BACKUP, GUI_FILE)
            content = GUI_FILE.read_text()
        elif Path("GUI/main_window.py.bak.modelstab").exists():
            shutil.copy2("GUI/main_window.py.bak.modelstab", GUI_FILE)
            content = GUI_FILE.read_text()
    
    shutil.copy2(GUI_FILE, BACKUP)
    
    # 1. Aggiungi la classe ModelsTab (senza save_and_restart difettoso)
    # Carica la classe da file separato se serve, per ora la incollo qui semplificata
    models_tab_class = _get_models_tab_class()
    
    insert_point = "class MainWindow(QMainWindow):"
    if insert_point not in content:
        print("❌ MainWindow non trovata")
        return 1
    
    content = content.replace(
        insert_point,
        models_tab_class + "\n\n" + insert_point,
        1
    )
    print("✓ Classe ModelsTab aggiunta")
    
    # 2. Aggiungi il tab
    if 'self.tabs.addTab(self.task_tab, "Coda Task")' in content and 'self.models_tab' not in content:
        content = content.replace(
            'self.tests_tab = TestsTab()',
            'self.tests_tab = TestsTab()\n        self.models_tab = ModelsTab()',
            1
        )
        content = content.replace(
            'self.tabs.addTab(self.task_tab, "Coda Task")',
            'self.tabs.addTab(self.task_tab, "Coda Task")\n        self.tabs.addTab(self.models_tab, "Modelli")',
            1
        )
        print("✓ Tab 'Modelli' aggiunto")
    
    GUI_FILE.write_text(content)
    
    try:
        compile(content, "main_window.py", "exec")
        print("✓ Verifica sintassi OK")
    except SyntaxError as e:
        print(f"❌ Errore sintassi: {e}")
        shutil.copy2(BACKUP, GUI_FILE)
        return 1
    
    print()
    print("✓ FEATURE 5 v2 COMPLETATA")
    print("Riavvia:")
    print("  ./ferma.sh && pkill -f 'python.*gui' 2>/dev/null; sleep 1")
    print("  ./avvia.sh --gui")
    return 0


def _get_models_tab_class() -> str:
    """Restituisce la classe ModelsTab completa con save_and_restart corretto."""
    return '''

# ====================================================================
# MODELS TAB — selettore modelli LLM con auto-selezione intelligente
# ====================================================================

class ModelsTab(QWidget):
    """Tab per selezionare e configurare i modelli LLM per ogni ruolo."""
    
    ROLES = [
        ("orchestrator", "Orchestrator (decisioni veloci)"),
        ("planner", "Planner (pianificazione task)"),
        ("worker_coder", "Worker Coder (generazione codice)"),
        ("worker_general", "Worker General (task generali)"),
        ("embedding", "Embedding (ricerca semantica)"),
        ("decision", "Decision (scomposizione task generici)"),
    ]
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self._recommendations = {}
        self._available_models = []
        self.role_combos = {}
        self.role_test_buttons = {}
        self.role_info_labels = {}
        self._build_ui()
        QTimer.singleShot(1000, self.refresh_models)
    
    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        
        header = QLabel(
            "<h2>🤖 Selezione Modelli LLM</h2>"
            "<p>Configura quali modelli Ollama usare per ogni ruolo. "
            "Clicca <b>Auto-Select</b> per scegliere automaticamente "
            "i modelli migliori in base al tuo hardware.</p>"
        )
        header.setWordWrap(True)
        header.setStyleSheet("padding: 8px; background: #1f1f1f; border-radius: 4px;")
        layout.addWidget(header)
        
        toolbar = QHBoxLayout()
        btn_refresh = QPushButton("🔄 Refresh modelli")
        btn_refresh.clicked.connect(self.refresh_models)
        btn_auto = QPushButton("🎯 Auto-Select")
        btn_auto.setStyleSheet("background-color: #28a745; color: white; font-weight: bold; padding: 8px 16px;")
        btn_auto.clicked.connect(self.auto_select)
        btn_save = QPushButton("💾 Save & Restart")
        btn_save.setStyleSheet("background-color: #007acc; color: white; font-weight: bold; padding: 8px 16px;")
        btn_save.clicked.connect(self.save_and_restart)
        
        self.status_label = QLabel("Caricamento modelli...")
        self.status_label.setStyleSheet("color: #999; padding: 0 10px;")
        
        toolbar.addWidget(btn_refresh)
        toolbar.addWidget(btn_auto)
        toolbar.addStretch()
        toolbar.addWidget(self.status_label)
        toolbar.addWidget(btn_save)
        layout.addLayout(toolbar)
        
        self.hw_label = QLabel("Hardware: caricamento...")
        self.hw_label.setStyleSheet("padding: 6px; background: #252525; font-family: monospace; color: #50fa7b; border-radius: 3px;")
        layout.addWidget(self.hw_label)
        
        roles_group = QGroupBox("Configurazione ruoli")
        roles_layout = QVBoxLayout(roles_group)
        
        for role_key, role_label in self.ROLES:
            row = QHBoxLayout()
            label = QLabel(f"<b>{role_label}</b>")
            label.setMinimumWidth(280)
            row.addWidget(label)
            
            combo = QComboBox()
            combo.setMinimumWidth(300)
            combo.currentTextChanged.connect(lambda text, r=role_key: self._on_role_changed(r, text))
            self.role_combos[role_key] = combo
            row.addWidget(combo, stretch=1)
            
            btn_test = QPushButton("🧪 Test")
            btn_test.setMaximumWidth(80)
            btn_test.clicked.connect(lambda checked, r=role_key: self._test_model(r))
            self.role_test_buttons[role_key] = btn_test
            row.addWidget(btn_test)
            
            info = QLabel("—")
            info.setMinimumWidth(200)
            info.setStyleSheet("color: #999; font-size: 9pt;")
            self.role_info_labels[role_key] = info
            row.addWidget(info)
            
            roles_layout.addLayout(row)
        
        layout.addWidget(roles_group)
        
        results_group = QGroupBox("📋 Dettagli Auto-Select")
        results_layout = QVBoxLayout(results_group)
        self.results_text = QPlainTextEdit()
        self.results_text.setReadOnly(True)
        self.results_text.setMaximumHeight(200)
        font = QFont("Monospace")
        font.setStyleHint(QFont.StyleHint.Monospace)
        font.setPointSize(9)
        self.results_text.setFont(font)
        self.results_text.setPlaceholderText("Clicca 'Auto-Select' per vedere le raccomandazioni dettagliate...")
        results_layout.addWidget(self.results_text)
        layout.addWidget(results_group)
        
        layout.addStretch()
    
    def refresh_models(self) -> None:
        """Ricarica la lista modelli da Ollama e popola le ComboBox."""
        self.status_label.setText("Caricamento modelli...")
        try:
            from CORE.model_selector import get_ollama_models, get_gpu_info, get_ram_info
            models = get_ollama_models()
            self._available_models = models
            
            gpu = get_gpu_info()
            ram = get_ram_info()
            self.hw_label.setText(
                f"Hardware: VRAM {gpu['vram_gb']:.1f}GB | "
                f"RAM {ram['ram_gb']:.1f}GB | "
                f"GPU {gpu['temp_c']:.0f}°C | "
                f"Modelli disponibili: {len(models)}"
            )
            
            for role_key, combo in self.role_combos.items():
                current = combo.currentText()
                combo.clear()
                combo.addItem("— (nessuno) —", "")
                for m in sorted(models, key=lambda x: x["size_gb"]):
                    label = f"{m['name']} ({m['size_gb']:.1f}GB, {m.get('family', '?')})"
                    combo.addItem(label, m["name"])
                if current:
                    for i in range(combo.count()):
                        if current in combo.itemText(i):
                            combo.setCurrentIndex(i)
                            break
            
            self.status_label.setText(f"✓ {len(models)} modelli caricati")
        except Exception as e:
            self.status_label.setText(f"❌ Errore: {e}")
    
    def _on_role_changed(self, role: str, text: str) -> None:
        if not text or text.startswith("—"):
            self.role_info_labels[role].setText("—")
            return
        model_name = text.split(" (")[0] if " (" in text else text
        model = next((m for m in self._available_models if m["name"] == model_name), None)
        if not model:
            return
        rec = self._recommendations.get(role, {})
        score = rec.get("score", 0) if rec.get("model") == model_name else 0
        info_text = f"{model['size_gb']:.1f}GB | {model.get('family', '?')}"
        if score > 0:
            info_text += f" | score: {score:.0f}/100"
        self.role_info_labels[role].setText(info_text)
    
    def auto_select(self) -> None:
        """Esegue l'algoritmo di auto-selezione e mostra i risultati."""
        self.status_label.setText("Esecuzione auto-select...")
        try:
            from CORE.model_selector import get_recommendations, format_recommendations
            recs = get_recommendations()
            self._recommendations = recs
            self.results_text.setPlainText(format_recommendations(recs))
            for role_key, _ in self.ROLES:
                rec = recs.get(role_key, {})
                model_name = rec.get("model")
                if model_name:
                    combo = self.role_combos[role_key]
                    for i in range(combo.count()):
                        if model_name in combo.itemText(i):
                            combo.setCurrentIndex(i)
                            break
                    self._on_role_changed(role_key, combo.currentText())
            self.status_label.setText("✓ Auto-select completato. Clicca 'Save & Restart' per applicare.")
        except Exception as e:
            self.status_label.setText(f"❌ Auto-select fallito: {e}")
            import traceback
            self.results_text.setPlainText(traceback.format_exc())
    
    def _test_model(self, role: str) -> None:
        """Testa il modello selezionato con 'hello'."""
        combo = self.role_combos[role]
        model_name = combo.currentData()
        if not model_name:
            self.role_info_labels[role].setText("❌ Nessun modello selezionato")
            return
        btn = self.role_test_buttons[role]
        btn.setText("⏳...")
        btn.setEnabled(False)
        self.role_info_labels[role].setText(f"Testando {model_name}...")
        QApplication.processEvents()
        try:
            import json
            import urllib.request
            import time
            start = time.time()
            payload = {
                "model": model_name,
                "messages": [{"role": "user", "content": "Say hello in one word"}],
                "stream": False,
                "options": {"num_predict": 20},
            }
            data = json.dumps(payload).encode("utf-8")
            req = urllib.request.Request(
                "http://localhost:11434/api/chat",
                data=data,
                headers={"Content-Type": "application/json"},
                method="POST",
            )
            with urllib.request.urlopen(req, timeout=30) as resp:
                result = json.loads(resp.read().decode("utf-8"))
            elapsed = time.time() - start
            content = result.get("message", {}).get("content", "").strip()[:50]
            eval_count = result.get("eval_count", 0)
            tps = eval_count / elapsed if elapsed > 0 else 0
            self.role_info_labels[role].setText(f"✓ {elapsed:.1f}s | {tps:.1f} tok/s | \\"{content}\\"")
            self.role_info_labels[role].setStyleSheet("color: #50fa7b; font-size: 9pt;")
        except Exception as e:
            self.role_info_labels[role].setText(f"❌ {str(e)[:60]}")
            self.role_info_labels[role].setStyleSheet("color: #ff5555; font-size: 9pt;")
        finally:
            btn.setText("🧪 Test")
            btn.setEnabled(True)
    
''' + SAVE_METHOD + "\n"


if __name__ == "__main__":
    raise SystemExit(main())
