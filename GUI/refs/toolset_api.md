# ToolSet API — cheat sheet (byte-swarmy)

I tool disponibili al worker (CORE/tools.py). Tutti operano dentro `project/`.
Path sempre relativi a project_root (es. "CORE/worker.py", non "/home/...").

## Lettura
- `read_file(path)` → str: legge un file (max max_file_size_readable byte)
- `read_file_slice(path, start_line, end_line)` → str: max 200 righe (1-based)
- `read_document(path)` → str: .txt/.md/.py/.json/.csv/.pdf (via pdftotext)
- `list_files(path="")` → lista file nella dir
- `search(pattern, include="*")` → grep

## Scrittura
- `write_file(path, content)` → str: scrittura atomica (tmp + rename)
  - Bloccata su file protetti (requirements.txt, .gitignore, config.toml, ...)
  - Bloccata su shrink sospetto (>500 byte -> <20%)
  - AST scanner blocca codice pericoloso (os.system, eval, ...)
  - Gate anti-escape-artifact su QUALSIASI file
- `patch_code(path, old_text, new_text)` → str: sostituisce UNA occorrenza
  esatta di old_text. Fallisce se old_text non trovato esattamente.
- `delete_file(path)` → str: cancella un file singolo (no dir)
- `move_file(path, new_path)` → str: rinomina/sposta (no overwrite)

## Analisi
- `analyze_project()` → str: struttura del progetto
- `find_references(symbol)` → str: chi usa il simbodo
- `analyze_complexity(path)` → str
- `get_call_graph(symbol)` → str
- `extract_method(path, start, end, new_name)` → str
- `lint_code(path)` → str: py_compile + bandit + mypy

## Git
- `git_status()`, `git_diff(ref)`, `git_log(n)`, `git_branch()`
- `git_commit(msg)`, `git_merge(branch)`, `git_pull()`, `git_push()`

## Test & bash
- `run_test_suite()` → str: report pytest (PASS/FAIL/ERR)
- `run_bash(cmd)` → str: comando shell in sandbox
- `list_tools()` → dict: tool disponibili

## Diario
- `diary_llm(...)` → str

## Errori comuni del worker
- Scrivere `main.py` invece di `VENTOLA/hello_qt.py` → path sbagliato
- `write_file` su file protetto → usa `patch_code`
- `write_file` con shrink sospetto → usa `patch_code` o modifica a mano
- Ignorare il file target della task → LEGGI PRIMA (disciplina)
- Creare file nuovi quando la task dice "modifica" → VIETATO
- `patch_code` con old_text non esatto → fallisce; copia ESATTAMENTE

## Regola d'oro
Lavora su UN solo file per task. Leggi prima, modifica con il cambiamento
minimo, rileggi per verifica. Non creare file nuovi se la task dice
"modifica".
