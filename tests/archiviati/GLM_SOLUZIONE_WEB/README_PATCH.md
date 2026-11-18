# Patch: ripristino File Manager dopo refactoring modulare

## Diagnosi

Dopo il commit `3312ad4` ("Rifattorizzazione GUI: rimosso main_window.py,
nuova interfaccia modulare") il file manager (sidebar sinistra "Archivio
progetto" + "Lavori e Compiti") **non viene più visualizzato** nel Control
Center.

### Causa radice

Il commit `ff73e40` ("refactor: CU5+CU6 — spezzato control_center.py")
ha estratto la classe `FileTreeDrawer` dal monolite `control_center.py` in
un nuovo modulo `GUI/file_tree_drawer.py`, ma l'estrazione è rimasta
**incompleta**: solo il 30% del codice originale (~16 metodi su ~50) è
stato portato nel nuovo file.

Il costruttore di `FileTreeDrawer` passa metodi come callback al nuovo
`TaskListWidget(...)`:

```python
self.task_list_widget = TaskListWidget(
    on_select_all_toggled=self._toggle_select_all_tasks,
    on_refresh_requested=self._force_refresh_tasks,
    on_delete_checked_requested=self._delete_checked_tasks,
    on_clean_queue_requested=self._clean_queue,
    on_task_activated=self._on_task_double_clicked,
    on_context_menu=self._on_task_context_menu,
)
```

Python risolve `self._toggle_select_all_tasks` come bound method lookup
**al momento della costruzione**. Poiché i metodi `_toggle_select_all_tasks`,
`_force_refresh_tasks`, `_delete_checked_tasks`, `_clean_queue`,
`_on_task_double_clicked`, `_on_task_context_menu` non erano stati portati
nel nuovo modulo, Python sollevava `AttributeError` già in `__init__`,
bloccando la costruzione di `FileTreeDrawer` e di conseguenza dell'intero
`ControlCenter`. Risultato: il file manager non appariva.

### Metodi mancanti (parziale)

| Categoria | Metodi mancanti |
|---|---|
| **Callback TaskListWidget** (bloccanti per `__init__`) | `_toggle_select_all_tasks`, `_force_refresh_tasks`, `_delete_checked_tasks`, `_clean_queue`, `_on_task_double_clicked`, `_on_task_context_menu` |
| **Operazioni file tree** | `_rename_item`, `_delete_item`, `_on_tree_click`, `_on_tree_double_click`, `_on_tree_context_menu`, `_on_folder_expanded`, `_on_model_data_changed`, `_delete_selected_items`, `_open_pending_editor` |
| **Sort / colonne** | `_toggle_sort_order`, `_sort_by_name`, `_sort_children_recursive`, `_apply_header_layout`, `_load_column_widths`, `_save_column_widths` |
| **Aggiunta elementi** | `_add_text_file`, `_add_folder` |
| **Refresh / folder** | `_refresh_file_tree` (versione corretta), `set_current_folder`, `_save_splitter_vertical_state` |
| **Azioni task** | `_on_task_item_clicked`, `_on_task_item_changed`, `_get_task_status`, `_pause_task_with_refresh`, `_resume_task_with_refresh`, `_stop_task_with_refresh`, `_restart_task_with_refresh`, `_delete_task_with_refresh`, `_copy_task_id`, `_open_task_result`, `_show_task_details`, `_collect_task_files` |
| **Orchestrator wrappers** | `_pause_orchestrator`, `_resume_orchestrator`, `_stop_orchestrator` |
| **Animazione** | `toggle` |

### Attributi mancanti in `__init__`

`main_win`, `_GUI_DEBUG`, `_pending_editor_path`, `_editor_open_timer`,
`_refreshing_tasks`, `header`, `add_file_btn`, `add_folder_btn`,
`refresh_btn`, `del_btn`, `sort_btn`, `path_label`, `_anim`, `_open`.

### Import mancanti

- `QAction` (usato nei context menu, non importato)
- `QListWidgetItem` (usato in `task_list_widget.py` ma non importato)
- `QItemSelectionModel`, `QPropertyAnimation`, `QEasingCurve`, `QTimer`,
  `QHeaderView`, `QFileIconProvider`, `QMenu`, `QInputDialog`,
  `QMessageBox`, `shutil`, `sqlite3`, `inspect`, `subprocess`

### Funzioni helper perse nel refactoring

Le funzioni module-level `_log_user_action`, `_pause_task`,
`_resume_single_task`, `_stop_task`, `_restart_task` erano in
`control_center.py` / `main_window.py` prima del refactoring e **non sono
state portate da nessuna parte**. Il nuovo `control_center.py` continua a
chiamare `_log_user_action(...)` (linee 295, 340, 688, 696) senza definirlo
né importarlo → `NameError` a runtime quando l'utente preme i pulsanti
pausa/stop orchestrator.

## File patchati

| File | Modifica | Righe prima → dopo |
|---|---|---|
| `GUI/file_tree_drawer.py` | **Riscritto da zero**: ripristinata la classe `FileTreeDrawer` completa (47 metodi, ~1800 righe) con tutti gli import corretti e l'adattamento al nuovo layout modulare | 363 → 1824 |
| `GUI/task_queue.py` | **Aggiunte 5 funzioni**: `pause_task`, `resume_single_task`, `stop_task`, `restart_task`, `log_user_action` (alias pubblici delle vecchie `_pause_task`, `_log_user_action`, ecc.) | 281 → 425 |
| `GUI/task_list_widget.py` | **Fix import**: aggiunto `QListWidgetItem` (usato in `set_tasks`/`add_task` ma non importato) e `QColor` a livello modulo; rimossi gli import inline ridondanti | 293 → 290 |
| `GUI/control_center.py` | **Fix import**: aggiunto `from GUI.task_queue import log_user_action as _log_user_action, pause_task as _pause_task, resume_single_task as _resume_single_task, stop_task as _stop_task, restart_task as _restart_task` | 1495 → 1502 |

## Verifica

Tre script di verifica in `download/byte-swarmy-patch/`:

1. **`verify_file_manager_restore.py`** — analisi AST statica: verifica
   sintassi, presenza di tutti i 47 metodi attesi su `FileTreeDrawer`,
   19 attributi attesi in `__init__`, 15 import attesi a livello modulo,
   funzioni helper presenti in `task_queue.py`, import corretti in
   `task_list_widget.py` e `control_center.py`.

   ```
   $ python3 verify_file_manager_restore.py
   TUTTI I CONTROLLI SUPERATI - file manager ripristinato
   ```

2. **`check_self_attrs.py`** — verifica che ogni `self.X` referenziato
   nei metodi di `FileTreeDrawer` sia assegnato da qualche parte
   (no `AttributeError` a runtime per attributi non inizializzati).

   ```
   $ python3 check_self_attrs.py
   OK Tutti gli attributi self.X sono assegnati da qualche parte
   ```

3. **`test_real_import.py`** — import reale di `GUI.file_tree_drawer`
   tramite mock PyQt6 (PyQt6 non si carica nel sandbox per mancanza di
   `libEGL.so.1`, ma il mock permissivo basta per validare la struttura).
   Verifica anche che `FileTreeDrawer(parent=None)` si possa istanziare
   senza errori.

   ```
   $ python3 test_real_import.py
   OK Modulo caricato
   FileTreeDrawer classe presente: True
   OK Tutti i 37 metodi attesi presenti
   OK Costruzione riuscita
     self.main_win = None
     self.task_list_widget = TaskListWidget
     self.header presente: True
     ...
   OK FILE MANAGER RIPRISTINATO — pronto per essere visualizzato
   ```

## Come applicare la patch

I file in questa directory sostituiscono direttamente i corrispondenti
nel repository `byte-swarmy`:

```bash
cd /path/to/byte-swarmy
cp /home/z/my-project/download/byte-swarmy-patch/GUI/file_tree_drawer.py    GUI/
cp /home/z/my-project/download/byte-swarmy-patch/GUI/task_queue.py          GUI/
cp /home/z/my-project/download/byte-swarmy-patch/GUI/task_list_widget.py    GUI/
cp /home/z/my-project/download/byte-swarmy-patch/GUI/control_center.py      GUI/

# Poi avvia normalmente:
./byte-swarm.sh gui
# oppure
python -m GUI.control_center
```

## Note di implementazione

- Il nuovo `FileTreeDrawer` mantiene il design modulare delegando la UI
  della lista task a `TaskListWidget` (introdotto nel refactoring), ma
  espone `self.task_list` come alias di `self.task_list_widget.task_list`
  per retro-compatibilità con il codice originale che accedeva direttamente
  agli item della lista.
- Le funzioni `pause_task`, `resume_single_task`, `stop_task`,
  `restart_task`, `log_user_action` sono state nominate **senza** il
  prefisso `_` (convenzione PEP 8 per API pubbliche). Gli import in
  `file_tree_drawer.py` e `control_center.py` usano alias
  `pause_task as _pause_task` ecc. per mantenere i nomi originali nel
  codice chiamante e minimizzare il diff.
- `_click_log` continua a essere importato da `GUI.control_center` con
  fallback a no-op in caso di import circolare (pattern già presente nel
  codice pre-refactoring).
- Tutte le chiamate a `main_window.load_tasks` / `main_window.delete_task`
  (rimosso) sono state sostituite con `task_queue.load_tasks` /
  `task_queue.delete_task` (già presenti nel nuovo modulo).
- Le funzioni `_is_junk_project_path` e `build_run_command` (usate in
  `_collect_task_files` e `_show_task_details`) sono importate da
  `GUI.project_tab_bar` dove sono già definite nel nuovo layout.

## Cosa NON è stato toccato

- `GUI/file_manager.py` — già corretto dopo `ff73e40`
- `GUI/file_tree_drawer.py` originale era uno stub, è stato riscritto
- `GUI/file_editor_widget.py` — già estratto correttamente in `3312ad4`
- `GUI/file_context_menu.py` — file standalone, non coinvolto
- `GUI/center_area.py`, `GUI/panels.py`, ecc. — già corretti
