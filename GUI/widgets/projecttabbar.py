"""
ProjectTabBar — estratto da GUI/control_center.py.
"""

from PyQt6.QtWidgets import (
    QWidget, QFrame, QVBoxLayout, QHBoxLayout, QGridLayout,
    QLabel, QPushButton, QTabBar, QStackedWidget, QTextEdit,
    QGraphicsView, QGraphicsScene, QGraphicsRectItem, QGraphicsTextItem,
    QSizePolicy, QSpacerItem, QMessageBox,
)
from PyQt6.QtCore import Qt, pyqtSignal, QPropertyAnimation, QEasingCurve, QUrl
from PyQt6.QtGui import QColor, QPalette, QPixmap, QFont, QBrush, QPen, QPainter, QCursor, QDesktopServices


class ProjectTabBar(QTabBar):
    """Barra dei progetti aperti in alto (quella arancione/gialla).

    Prima era vuota: nessun tab veniva aggiunto e l'utente vedeva solo il
    pulsante della cartella accanto. Ora carica automaticamente:
      • il progetto corrente (byte-swarmy);
      • ogni sottocartella di ``project/`` (i task prodotti dai worker);
      • un tab "+" che apre un QFileDialog per aggiungere un nuovo progetto.
    """

    # Segnale emesso quando un nuovo progetto viene aggiunto via "+"
    project_added = pyqtSignal(str)
    # Emette il path (assoluto) della cartella quando si seleziona un tab
    current_project_changed = pyqtSignal(str)

    def __init__(self):
        super().__init__()
        self.setDrawBase(False)
        self.setTabsClosable(True)
        self.setMovable(True)
        self.setExpanding(False)
        # Tronca il testo dei tab troppo lunghi con "…" invece di allargare il tab
        self.setElideMode(Qt.TextElideMode.ElideRight)
        # Click su un tab → se è il "+", apri QFileDialog
        self.tabBarClicked.connect(self._on_tab_clicked)
        self.tabCloseRequested.connect(self._on_tab_close_requested)
        # Cambio tab → emetti current_project_changed con path della cartella
        self.currentChanged.connect(self._on_current_changed)
        self._load_open_projects()

    def _load_open_projects(self):
        """Popola i tab con i progetti aperti (cartelle sotto project/).

        Carica **solo** le sottocartelle reali di ``project/`` come tab —
        niente più tab hardcoded "🐝 byte-swarmy" (la cartella root non è un
        progetto caricabile, l'utente lo ha confermato). Se ``project/`` è
        vuoto, si parte direttamente dal tab ``➕``.
        """
        import os
        base = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        projects_dir = os.path.join(base, "project")

        # Tab intermedi — SOLO sottocartelle reali di project/.
        # Ignora file (come .gitkeep, main.py) e cartelle nascoste.
        if os.path.isdir(projects_dir):
            try:
                all_entries = sorted(
                    e for e in os.listdir(projects_dir)
                    if e.startswith("PR_")
                    and os.path.isdir(os.path.join(projects_dir, e))
                    and not e.startswith(".")
                    and e != "__pycache__"
                    and e != ".git"
                    and e != ".venv"
                )
            except OSError:
                all_entries = []
            # Persistenza progetti aperti
            import json
            state_file = os.path.join(base, "state", "open_projects.json")
            open_list = None
            if os.path.exists(state_file):
                try:
                    open_list = json.loads(open(state_file, encoding="utf-8").read())
                    if not isinstance(open_list, list):
                        open_list = None
                except Exception:
                    open_list = None
            if open_list is None:
                open_list = list(all_entries)
                try:
                    os.makedirs(os.path.dirname(state_file), exist_ok=True)
                    with open(state_file, "w", encoding="utf-8") as f:
                        json.dump(open_list, f)
                except Exception:
                    pass
            entries = [e for e in all_entries if e in (open_list or [])]
            for name in entries:
                # Mostra nella scheda il nome SENZA il prefisso "PR_"
                # (regola interna: il prefisso resta solo sul disco).
                display_name = name[3:] if name.startswith("PR_") else name
                # Tronca il nome se troppo lungo per evitare tab troppo larghi.
                # Il nome completo resta nel tooltip.
                if len(display_name) > 15:
                    display_name = display_name[:12] + "..."
                if self._find_tab(display_name) < 0:
                    idx = self.addTab("📁 " + display_name)
                    self.setTabToolTip(idx, name[3:] if name.startswith("PR_") else name)
                    # Salva il path reale (con "PR_") per ricostruirlo
                    # correttamente in _path_for_tab.
                    if not hasattr(self, "_tab_paths"):
                        self._tab_paths = {}
                    self._tab_paths[idx] = os.path.join(projects_dir, name)
                    # Sostituisci la × di default con un QPushButton custom
                    # che ha 15px di margine sinistro (dal testo) e 15px di
                    # margine destro (dal bordo). Il CSS di QTabBar::close-button
                    # è notoriamente buggy in Qt, setTabButton è affidabile.
                    self._install_custom_close_button(idx)

        # Tab finale — "+" per aggiungere un nuovo progetto (non chiudibile).
        # Se non ci sono progetti reali, il ➕ è l'unico tab oltre a nessuno.
        self._plus_index = self.count()
        self.addTab("➕")
        # Nascondi la × dal tab ➕ (ha senso: il + non si "chiude", si clicca)
        self._hide_close_button(self._plus_index)
        # Seleziona il primo tab reale (se esiste), altrimenti il ➕
        if self.count() > 1:
            self.setCurrentIndex(0)
        else:
            self.setCurrentIndex(self._plus_index)

    def _install_custom_close_button(self, index: int):
        """Installa un QPushButton personalizzato come close-button del tab.

        A differenza del close-button di default di Qt (che ignora i margini
        del CSS), questo widget ha controllo pixel-perfect:
          - 15px di margine sinistro (tra testo e ×)
          - 15px di margine destro (tra × e bordo del tab)
        Il click emette tabCloseRequested come il button di default.
        """
        # Larghezza totale: 8px sx + 16px (× icona) + 8px dx = 32px.
        btn = QPushButton("✕")
        btn.setFixedSize(32, 24)
        btn.setCursor(Qt.CursorShape.PointingHandCursor)
        btn.setToolTip("Chiudi questo progetto")
        # setContentsMargins funziona SEMPRE (a differenza del CSS close-button):
        # 8px a sinistra (tra testo e ×) + 8px a destra (tra × e bordo).
        btn.setContentsMargins(8, 0, 8, 0)
        btn.setStyleSheet(
            "QPushButton {"
            "  background:transparent; border:none; "
            "  font-size:13px; font-weight:bold; padding:0;"
            "  margin:0;"
            "}"
            "QPushButton:hover {"
            "  background:#fee2e2; color:#dc2626; border-radius:3px;"
            "}"
        )
        # Click sul pulsante → risolvi l'index AL MOMENTO del click (non al
        # momento della creazione): i tab sono movibili/riordinabili e un index
        # catturato in anticipo chiuderebbe la scheda sbagliata.
        btn.clicked.connect(self._on_close_button_clicked)
        try:
            self.setTabButton(
                index,
                QTabBar.ButtonPosition.RightSide,
                btn,
            )
        except Exception:
            try:
                self.setTabButton(
                    index,
                    QTabBar.ButtonPosition.LeftSide,
                    btn,
                )
            except Exception:
                pass

    def _hide_close_button(self, index: int):
        """Rimuove il pulsante di chiusura (×) da un tab specifico."""
        try:
            self.setTabButton(
                index,
                QTabBar.ButtonPosition.RightSide,
                None,
            )
        except Exception:
            # Su alcuni platform plugin il RightSide non esiste; prova LeftSide
            try:
                self.setTabButton(
                    index,
                    QTabBar.ButtonPosition.LeftSide,
                    None,
                )
            except Exception:
                pass

    def _on_close_button_clicked(self):
        """Risolvi dinamicamente il tab a cui appartiene il pulsante ✕
        cliccato: evita di chiudere la scheda sbagliata dopo riordinamenti."""
        sender = self.sender()
        for i in range(self.count()):
            if (self.tabButton(i, QTabBar.ButtonPosition.RightSide) is sender
                    or self.tabButton(i, QTabBar.ButtonPosition.LeftSide) is sender):
                if not self._is_plus_tab(i):
                    self.tabCloseRequested.emit(i)
                return

    def _is_plus_tab(self, index: int) -> bool:
        return index == getattr(self, "_plus_index", -1)

    def _on_tab_clicked(self, index: int):
        """Apri il QFileDialog se l'utente clicca il tab '+'."""
        if self._is_plus_tab(index):
            self._open_new_project_dialog()

    def _on_current_changed(self, index: int):
        """Emette current_project_changed quando l'utente cambia tab.

        La sidebar 'Archivio progetto' ascolta questo segnale per aggiornare
        il file tree alla cartella del progetto appena selezionato.
        """
        if self._is_plus_tab(index):
            # Il "+" non ha una cartella associata — non emettere
            return
        path = self._path_for_tab(index)
        if path:
            self.current_project_changed.emit(path)

    def _path_for_tab(self, index: int) -> str:
        """Ricostruisce il path assoluto della cartella associata al tab.

        Per i tab ``📁 name`` corrisponde a ``project/name``, ma potrebbe
        anche essere un path assoluto salvato dal QFileDialog (in tal caso
        cerchiamo in ``_tab_paths``).
        """
        import os
        if index < 0 or index >= self.count():
            return ""
        text = self.tabText(index)
        # Salva/recupera path espliciti per tab aperti via QFileDialog
        if not hasattr(self, "_tab_paths"):
            self._tab_paths = {}
        if index in self._tab_paths:
            return self._tab_paths[index]
        # Tab del tipo "📁 name" → project/name
        base = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        projects_dir = os.path.join(base, "project")
        if text.startswith("📁 "):
            name = text[2:]
            candidate = os.path.join(projects_dir, name)
            if os.path.isdir(candidate):
                return candidate
            # Le schede nascondono il prefisso "PR_": prova ad aggiungerlo
            # per ricostruire il path reale della cartella su disco.
            candidate_pr = os.path.join(projects_dir, "PR_" + name)
            if os.path.isdir(candidate_pr):
                return candidate_pr
            # Se name contiene path separatori (cartella esterna)
            if os.path.isdir(name):
                return name
        return ""

    def _on_tab_close_requested(self, index: int):
        """Chiude un tab progetto (qualsuale tab reale tranne il '+')."""
        if self._is_plus_tab(index):
            return  # Il "+" non si chiude
        # Persisti la chiusura: rimuovi dalla lista open_projects.json
        try:
            import os, json
            base = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            state_file = os.path.join(base, "state", "open_projects.json")
            name = self.tabText(index).replace("📁 ", "", 1).strip()
            # Ricostruisci il nome su disco (con prefisso PR_)
            disk_name = name if name.startswith("PR_") else "PR_" + name
            if os.path.exists(state_file):
                data = json.loads(open(state_file, encoding="utf-8").read())
                if isinstance(data, list) and disk_name in data:
                    data.remove(disk_name)
                    with open(state_file, "w", encoding="utf-8") as f:
                        json.dump(data, f)
        except Exception:
            pass
        # Tutti i tab 📁 ... sono chiudibili (nessun tab hardcoded protetto)
        self.removeTab(index)
        # L'indice del "+" è sceso di 1
        self._plus_index = self.count() - 1
        # Se non ci sono più tab reali, sposta la selezione sul ➕
        if self.count() == 1:
            self.setCurrentIndex(0)

    def _open_new_project_dialog(self):
        """Apre un dialog per aggiungere un progetto.

        Chiede (opzionalmente) il link di un repository GitHub/GitLab da
        clonare e la cartella in cui salvare il progetto; se non viene
        fornito un link, permette di scegliere una cartella locale esistente.
        """
        from PyQt6.QtWidgets import (
            QFileDialog, QInputDialog, QMessageBox,
        )
        import os
        import subprocess

        base = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        projects_dir = os.path.join(base, "project")
        start_dir = projects_dir if os.path.isdir(projects_dir) else os.path.expanduser("~")

        # 1) Link repository (opzionale)
        url, ok = QInputDialog.getText(
            None,
            "Nuovo progetto — Repository",
            "Link del repository (GitHub/GitLab) da clonare:\n"
            "(lascia vuoto per scegliere una cartella locale esistente)",
        )
        if not ok:
            self.setCurrentIndex(0)
            return
        url = (url or "").strip()

        folder = None
        if url:
            # 2) Cartella in cui salvare/clonare
            parent = QFileDialog.getExistingDirectory(
                None,
                "Scegli la cartella in cui salvare il progetto clonato",
                start_dir,
                QFileDialog.Option.ShowDirsOnly | QFileDialog.Option.DontResolveSymlinks,
            )
            if not parent:
                self.setCurrentIndex(0)
                return
            # nome progetto dal basename dell'URL (senza .git)
            name = url.rstrip("/").rsplit("/", 1)[-1]
            if name.endswith(".git"):
                name = name[:-4]
            if not name:
                name = "progetto"
            target = os.path.join(parent, name)
            if os.path.exists(target):
                r = QMessageBox.question(
                    None, "Cartella esistente",
                    f"La cartella '{target}' esiste già.\n"
                    "Vuoi aprirla come progetto invece di clonare?",
                    QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                )
                if r != QMessageBox.StandardButton.Yes:
                    self.setCurrentIndex(0)
                    return
            else:
                # clona
                try:
                    proc = subprocess.run(
                        ["git", "clone", url, target],
                        capture_output=True, text=True, timeout=300,
                    )
                except FileNotFoundError:
                    QMessageBox.critical(
                        None, "git non trovato",
                        "Il comando 'git' non è disponibile sul sistema.\n"
                        "Installa git oppure clona manualmente la repo.",
                    )
                    self.setCurrentIndex(0)
                    return
                except subprocess.TimeoutExpired:
                    QMessageBox.critical(
                        None, "Timeout",
                        "Il clone ha superato i 5 minuti. Riprova o clona manualmente.",
                    )
                    self.setCurrentIndex(0)
                    return
                if proc.returncode != 0:
                    QMessageBox.critical(
                        None, "Clone fallito",
                        f"git clone ha restituito errore:\n{proc.stderr.strip()[:500]}",
                    )
                    self.setCurrentIndex(0)
                    return
            folder = target
        else:
            # Nessun link: scegli cartella locale esistente (comportamento originale)
            folder = QFileDialog.getExistingDirectory(
                None,
                "Apri progetto — scegli cartella",
                start_dir,
                QFileDialog.Option.ShowDirsOnly | QFileDialog.Option.DontResolveSymlinks,
            )
            if not folder:
                self.setCurrentIndex(0)
                return

        name = os.path.basename(folder.rstrip("/"))
        if not name:
            name = folder

        # Se è già aperto, selezionalo
        existing = self._find_tab(name)
        if existing >= 0:
            self.setCurrentIndex(existing)
            return

        # Aggiungi il nuovo tab PRIMA del "+" (in modo che resti sempre l'ultimo)
        new_idx = self._plus_index
        self.insertTab(new_idx, "📁 " + name)
        self._plus_index = self.count() - 1
        # Installa il close-button custom (15px dx + 15px sx) sul nuovo tab
        self._install_custom_close_button(new_idx)
        # Salva il path assoluto del nuovo tab per poter aggiornare la sidebar
        if not hasattr(self, "_tab_paths"):
            self._tab_paths = {}
        self._tab_paths[new_idx] = folder
        # Persisti il nuovo progetto nella lista open
        try:
            import os, json
            base = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            state_file = os.path.join(base, "state", "open_projects.json")
            name = os.path.basename(folder.rstrip("/"))
            os.makedirs(os.path.dirname(state_file), exist_ok=True)
            data = []
            if os.path.exists(state_file):
                try:
                    data = json.loads(open(state_file, encoding="utf-8").read())
                    if not isinstance(data, list):
                        data = []
                except Exception:
                    data = []
            if name not in data:
                data.append(name)
            with open(state_file, "w", encoding="utf-8") as f:
                json.dump(data, f)
        except Exception:
            pass
        self.setCurrentIndex(new_idx)

        # Emette segnale/opzionalmente callback: il nome della cartella aperta
        # è disponibile per il ControlCenter (per impostare il working dir).
        if hasattr(self, "project_added"):
            self.project_added.emit(folder)

    def _find_tab(self, name: str) -> int:
        for i in range(self.count()):
            txt = self.tabText(i)
            if txt == name or txt.endswith(" " + name):
                return i
        return -1

    def refresh(self):
        """Ricarica i progetti aperti (utile dopo aver creato/eliminato task)."""
        # Rimuovi tutti i tab e ricarica
        while self.count() > 0:
            self.removeTab(0)
        self._load_open_projects()

    def add_project(self, name: str):
        """Aggiunge un progetto ai tab (se non già presente)."""
        if self._find_tab(name) < 0:
            # Inserisci prima del "+"
            new_idx = getattr(self, "_plus_index", self.count())
            self.insertTab(new_idx, "📁 " + name)
            self._plus_index = self.count() - 1
            self.setCurrentIndex(new_idx)


def _is_junk_project_path(rel: str) -> bool:
    """True per percorsi interni da NON mostrare come 'codice prodotto':
    .git/.venv/nascosti, __pycache__, .pyc — il commit del task tocca
    .git/objects DURANTE la finestra temporale e prima inquinava la lista
    ('Apri risultato' apriva project/.git/objects/12/)."""
    parts = Path(rel).parts
    if any(pp.startswith(".") or pp == "__pycache__" for pp in parts):
        return True
    return rel.endswith(".pyc")


def build_run_command(file_path):
    """Flusso utente 3: comando per eseguire il codice generato dal task
    FUORI dal sandbox (è codice dell'utente, sulla sua macchina).

    .py → python3 | .sh → bash | .c/.cpp → compila in /tmp ed esegui.
    Ritorna None per estensioni non eseguibili direttamente (es. .html:
    il chiamante lo apre nel browser).
    """
    from shlex import quote as _q
    ext = file_path.suffix.lower()
    fp = str(file_path)
    if ext == ".py":
        return ["python3", fp]
    if ext == ".sh":
        return ["bash", fp]
    if ext == ".c":
        return ["bash", "-c", f"gcc {_q(fp)} -o /tmp/bswarm_run && /tmp/bswarm_run"]
    if ext == ".cpp":
        return ["bash", "-c", f"g++ {_q(fp)} -o /tmp/bswarm_run && /tmp/bswarm_run"]
    return None






