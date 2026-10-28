#!/usr/bin/env python3
"""
add_live_activity.py — Aggiunge un pannello "Live Activity" alla GUI.

Mostra in tempo reale:
- Task in esecuzione (ID, modello, step X/N)
- Ultimo tool chiamato + risultato
- Pensiero (thought) del LLM
- Spinner animato + timer

Patch:
1. gui.py: aggiunge classe LiveActivityPanel + inserimento in TaskQueueTab
2. orchestrator.py: logga i thoughts (così la GUI può mostrarli)
"""
import re
import shutil
from pathlib import Path

GUI_FILE = Path("gui.py")
GUI_BACKUP = Path("gui.py.bak.liveactivity")
ORCH_FILE = Path("orchestrator.py")
ORCH_BACKUP = Path("orchestrator.py.bak.liveactivity")


# ====================================================================
# 1. Classe LiveActivityPanel da inserire in gui.py
# ====================================================================

LIVE_ACTIVITY_CLASS = '''

# ====================================================================
# LIVE ACTIVITY PANEL — feedback real-time sull'attività del modello
# ====================================================================

class LiveActivityPanel(QWidget):
    """Pannello che mostra in tempo reale cosa sta facendo l'orchestratore.

    Mostra: task attivo, modello, step X/N, ultimo tool, pensiero LLM,
    spinner animato, tempo trascorso.
    """

    SPINNER_FRAMES = ["⠋", "⠙", "⠹", "⠸", "⠼", "⠴", "⠦", "⠧", "⠇", "⠏"]

    def __init__(self, parent=None):
        super().__init__(parent)
        self._spinner_idx = 0
        self._start_time = None
        self._last_task_id = None
        self._build_ui()

        # Timer aggiornamento dati (1.5s)
        self.timer = QTimer(self)
        self.timer.timeout.connect(self._refresh)
        self.timer.start(1500)

        # Timer animazione spinner (120ms)
        self.spinner_timer = QTimer(self)
        self.spinner_timer.timeout.connect(self._animate_spinner)

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        group = QGroupBox("⚡ Attività Live")
        gl = QVBoxLayout(group)
        gl.setSpacing(3)
        gl.setContentsMargins(8, 6, 8, 6)

        # Riga 1: status + spinner
        row1 = QHBoxLayout()
        self.status_label = QLabel("○ In attesa")
        self.status_label.setStyleSheet(
            "font-weight: bold; color: #666; font-size: 10pt;"
        )
        row1.addWidget(self.status_label)
        row1.addStretch()
        self.spinner_label = QLabel("")
        self.spinner_label.setStyleSheet(
            "font-size: 14pt; color: #007acc;"
        )
        row1.addWidget(self.spinner_label)
        gl.addLayout(row1)

        # Riga 2: dettagli (task, modello, step, tool)
        self.details_label = QLabel(
            "L'orchestratore controlla la coda. Nessun task in esecuzione."
        )
        self.details_label.setStyleSheet(
            "color: #999; font-family: monospace; font-size: 9pt;"
        )
        self.details_label.setWordWrap(True)
        gl.addWidget(self.details_label)

        # Riga 3: pensiero del LLM
        self.thought_label = QLabel("")
        self.thought_label.setStyleSheet(
            "color: #7ab8e6; font-style: italic; font-size: 9pt; "
            "padding: 2px 0;"
        )
        self.thought_label.setWordWrap(True)
        gl.addWidget(self.thought_label)

        layout.addWidget(group)

    def _refresh(self) -> None:
        """Aggiorna leggendo coda + log."""
        tasks = load_tasks()
        running = [t for t in tasks if t.get("status") == "running"]

        if not running:
            self._show_idle()
            return

        task = running[0]
        task_id = task.get("id", "?")

        # Reset timer se è un nuovo task
        if task_id != self._last_task_id:
            self._start_time = time.time()
            self._last_task_id = task_id

        elapsed = int(time.time() - (self._start_time or time.time()))

        # Tail del log
        log_lines = self._tail_log(LOG_FILE, 150)

        # Parse: step, tool, thought più recenti
        worker_id = None
        step_info = ""
        tool_info = ""
        thought = ""

        for line in reversed(log_lines):
            if not step_info:
                m = re.search(r'\\[(worker-[\\w-]+)\\] step (\\d+)/(\\d+)', line)
                if m:
                    worker_id = m.group(1)
                    step_info = f"Step {m.group(2)}/{m.group(3)}"

            if not tool_info:
                m = re.search(
                    r'\\[(worker-[\\w-]+)\\] tool (\\w+)\\(([^)]*)\\) -> (.*)',
                    line,
                )
                if m:
                    if not worker_id:
                        worker_id = m.group(1)
                    tool_info = (
                        f"🔧 {m.group(2)}({m.group(3)[:25]}) → "
                        f"{m.group(4)[:70]}"
                    )

            if not thought:
                m = re.search(r'\\[(worker-[\\w-]+)\\] thought: (.*)', line)
                if m:
                    if not worker_id:
                        worker_id = m.group(1)
                    thought = m.group(1)[:180]

            if step_info and tool_info and thought:
                break

        # Nome modello dal config
        model_name = worker_id or "?"
        if worker_id:
            try:
                with open(CONFIG_FILE, "rb") as f:
                    cfg = tomllib.load(f)
                key = worker_id.replace("worker-", "worker_")
                model_name = (
                    cfg.get("models", {})
                    .get(key, {})
                    .get("name", worker_id)
                )
            except Exception:
                pass

        # Aggiorna UI
        self.status_label.setText(f"⏳ Elaborazione ({elapsed}s)")
        self.status_label.setStyleSheet(
            "font-weight: bold; color: #007acc; font-size: 10pt;"
        )

        details_parts = [f"Task: {task_id}", f"Modello: {model_name}"]
        if step_info:
            details_parts.append(step_info)
        details = " | ".join(details_parts)
        if tool_info:
            details += f"\\n{tool_info}"
        self.details_label.setText(details)

        if thought:
            self.thought_label.setText(f"💭 {thought}")
        else:
            self.thought_label.setText("💭 (in attesa del primo pensiero...)")

        # Avvia spinner
        if not self.spinner_timer.isActive():
            self.spinner_timer.start(120)

    def _show_idle(self) -> None:
        self._start_time = None
        self._last_task_id = None
        self.status_label.setText("○ In attesa")
        self.status_label.setStyleSheet(
            "font-weight: bold; color: #666; font-size: 10pt;"
        )
        self.details_label.setText(
            "L'orchestratore controlla la coda. Nessun task in esecuzione."
        )
        self.thought_label.setText("")
        self.spinner_label.setText("")
        if self.spinner_timer.isActive():
            self.spinner_timer.stop()

    def _animate_spinner(self) -> None:
        self.spinner_label.setText(self.SPINNER_FRAMES[self._spinner_idx])
        self._spinner_idx = (self._spinner_idx + 1) % len(self.SPINNER_FRAMES)

    def _tail_log(self, path: Path, n: int = 100) -> list:
        try:
            with open(path, "r", encoding="utf-8", errors="replace") as f:
                lines = f.readlines()
            return lines[-n:]
        except Exception:
            return []
'''


# ====================================================================
# 2. Inserimento in TaskQueueTab._build_ui
# ====================================================================

GUI_INSERT_POINT = """        layout.addWidget(self.stats_label)
 
        # Tabella
        self.table = QTableWidget(0, 6)"""

GUI_INSERT_NEW = """        layout.addWidget(self.stats_label)

        # 🆕 Live Activity Panel
        self.live_activity = LiveActivityPanel()
        layout.addWidget(self.live_activity)

        # Tabella
        self.table = QTableWidget(0, 6)"""


# ====================================================================
# 3. Patch orchestrator.py: logga i thoughts
# ====================================================================

ORCH_SEARCH = '''            self.memory.add_event({"type": "thought", "content": action.get("thought", "")[:200]})'''

ORCH_REPLACE = '''            self.memory.add_event({"type": "thought", "content": action.get("thought", "")[:200]})
            self.log.info(f"[{self.agent_id}] thought: {action.get('thought', '')[:200]}")'''


# ====================================================================
# Esecuzione patch
# ====================================================================

def patch_gui() -> bool:
    """Patch gui.py: aggiunge LiveActivityPanel. Ritorna True se OK."""
    if not GUI_FILE.exists():
        print(f"❌ {GUI_FILE} non trovato")
        return False

    content = GUI_FILE.read_text()
    modified = False

    # Backup
    if not GUI_BACKUP.exists():
        shutil.copy2(GUI_FILE, GUI_BACKUP)
        print(f"✓ Backup gui.py: {GUI_BACKUP}")

    # 1. Aggiungi classe LiveActivityPanel (prima di TaskQueueTab)
    if "class LiveActivityPanel" in content:
        print("ℹ  LiveActivityPanel già presente in gui.py, skip")
    else:
        insert_before = "# ====================================================================\n# TASK TABLE TAB"
        if insert_before not in content:
            print("❌ Punto di inserimento 'TASK TABLE TAB' non trovato")
            return False
        content = content.replace(
            insert_before,
            LIVE_ACTIVITY_CLASS + "\n\n" + insert_before,
            1,
        )
        modified = True
        print("✓ Aggiunta classe LiveActivityPanel")

    # 2. Inserisci panel in _build_ui
    if "self.live_activity = LiveActivityPanel()" in content:
        print("ℹ  LiveActivityPanel già inserito in _build_ui, skip")
    elif GUI_INSERT_POINT in content:
        content = content.replace(GUI_INSERT_POINT, GUI_INSERT_NEW, 1)
        modified = True
        print("✓ Inserito LiveActivityPanel in TaskQueueTab._build_ui")
    else:
        print("❌ Punto di inserimento in _build_ui non trovato")
        print("  Cerca: layout.addWidget(self.stats_label) seguito da # Tabella")
        return False

    if modified:
        GUI_FILE.write_text(content)
        print(f"✓ gui.py aggiornato")
    return True


def patch_orchestrator() -> bool:
    """Patch orchestrator.py: logga thoughts. Ritorna True se OK."""
    if not ORCH_FILE.exists():
        print(f"❌ {ORCH_FILE} non trovato")
        return False

    content = ORCH_FILE.read_text()

    if "thought:" in content and "] thought:" in content:
        print("ℹ  Patch thoughts già applicata in orchestrator.py, skip")
        return True

    if ORCH_SEARCH not in content:
        print("❌ Pattern per patch thoughts non trovato in orchestrator.py")
        return False

    if not ORCH_BACKUP.exists():
        shutil.copy2(ORCH_FILE, ORCH_BACKUP)
        print(f"✓ Backup orchestrator.py: {ORCH_BACKUP}")

    content = content.replace(ORCH_SEARCH, ORCH_REPLACE, 1)
    ORCH_FILE.write_text(content)
    print("✓ Patch thoughts applicata a orchestrator.py")
    return True


def main():
    print("=" * 60)
    print("PATCH: Live Activity Panel")
    print("=" * 60)

    ok1 = patch_gui()
    print()
    ok2 = patch_orchestrator()

    print()
    print("=" * 60)
    if ok1 and ok2:
        print("✓ TUTTE LE PATCH APPLICATE")
        print()
        print("Per testare:")
        print("  1. python -c \"import gui; print('OK')\"")
        print("  2. ./avvia.sh")
        print("  3. Aggiungi un task e guarda il pannello Live Activity")
        print()
        print("Per ripristinare:")
        print(f"  cp {GUI_BACKUP} {GUI_FILE}")
        print(f"  cp {ORCH_BACKUP} {ORCH_FILE}")
    else:
        print("⚠  Alcune patch non sono state applicate. Leggi i messaggi sopra.")
    print("=" * 60)


if __name__ == "__main__":
    main()
