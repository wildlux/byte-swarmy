---
id: py-refactor-rename
title: Refactoring multi-file (rename symbol across project)
keywords: refactoring, rinomina, rename, multi-file, tutti i file, aggiorna, riferimenti, references
---
# Recipe: Refactoring multi-file (rename a symbol across the project)

USE THIS SKILL WHEN: the task asks to rename a class/function/method/symbol
in ALL files of the project (or in "tutti i file", "tutto il progetto").

STEPS (follow strictly, in order, ONE action per step):
1. Find the symbol's references across the project with find_references.
2. Read each file that contains the symbol (read_file or read_file_slice)
   BEFORE patching — never patch a file you haven't read.
3. patch_code each file: replace the OLD symbol with the NEW one. Use
   the SMALLEST old_text that uniquely identifies the symbol line (es.
   `class Statistiche` instead of the whole file). One patch per
   occurrence if needed.
4. After ALL files are patched, verify the tests still pass: the
   test files (test_*.py) should NOT need patching if the rename is
   consistent — they import the symbol and call it, so updating the
   symbol's definition + every NON-test use is enough.
5. done=true with a result like "Rinominato X in Y in N file (M
   modifiche totali)".

WORKFLOW (one JSON action per step, as the system expects):

  step 1: {"thought":"cerco riferimenti al simbolo","action":"find_references","args":["{{ OLD SYMBOL }}"],"done":false}
  step 2: {"thought":"leggo il file principale","action":"read_file","args":["{{ FILE WHERE THE SYMBOL IS DEFINED }}"],"done":false}
  step 3..N: {"thought":"patch del file X, occorrenza Y","action":"patch_code","args":["{{ FILE }}","{{ OLD TEXT }}","{{ NEW TEXT }}"],"done":false}
  last: {"thought":"fatto","action":"none","args":[],"done":true,"result":"Rinominato {{ OLD }} in {{ NEW }} in N file (M modifiche)"}

RULES:
- NEVER read a file called `main.py` FIRST unless the task EXPLICITLY
  names it. The default "Read main.py" of small models is WRONG for
  refactoring: you don't know which file holds the symbol until you
  `find_references` it. ALWAYS start with find_references.
- The task names the OLD symbol AND the NEW symbol. Write them down
  in the first thought and never confuse them.
- Files to patch = files returned by find_references. If a file
  appears in the references, it MUST be patched. Do not skip any.
- patch_code args are [path, old_text, new_text]. old_text must match
  EXACTLY a unique substring of the file (case-sensitive, spaces
  included). Use the SMALLEST unique substring to avoid mismatch.
- For a class rename, two patches are usually needed in the file
  that USES the class: one for `from X import OLD` and one for the
  call site `OLD()`. Find them with find_references output.
- Do NOT redefine the symbol with write_file — use patch_code to
  preserve everything else in the file.
- If find_references returns ZERO results, the symbol name is wrong
  or missing: STOP with done=true and result "Symbol X not found,
  refactoring aborted" (honest failure beats guessing).
- After all patches, do NOT run the tests via run_test_suite unless
  the task explicitly asks for it. The system's gate will verify
  them; if they fail, the correction loop will tell you.
- 5 to 8 steps are typical for a 2-3 file project. If you go past
  step 8 without finishing, STOP and done=true with an honest
  result of what was changed and what was not.
- Do NOT loop on list_files: if list_files returned the file list
  once, use that result. Repeating list_files with the same args
  triggers the circuit breaker and wastes steps.
