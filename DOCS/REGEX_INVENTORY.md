# Inventario delle espressioni regolari — baseline 2026-11-22

Generato dal test deterministico `tests/test_regex_inventory.py` (AST, zero LLM,
zero import dei moduli scansionati). Per **vedere tutte le regex**:

```bash
.venv/bin/python -m pytest tests/test_regex_inventory.py -q -s
```

## Conteggi

| Voce | Valore |
|---|---|
| Pattern nel registro centralizzato (`DEFAULT_PATTERNS` + `LANG_HINTS`) | 24 |
| Usages con pattern letterale in `CORE/`, `GUI/`, `tools/` | 130 |
| File sorgente Python scansionati | 148 |
| Pattern invalidi o vuoti | 0 |
| Duplicati nel registro centralizzato | 0 |

## Cosa copre

| Sorgente | Metodo |
|---|---|
| `CORE/regex_controller.py` | registro `DEFAULT_PATTERNS` + `LANG_HINTS`, letto direttamente |
| Chiamate `re.compile/search/match/findall/finditer/sub/subn/split/fullmatch` | AST: solo pattern **letterali**, con flag `re.I`/`re.M`/... risolti |
| `RegexController.add('nome', r'pattern')` | AST: secondo argomento letterale |
| Alias (`import re as ...`, `from re import compile as ...`) | risolti dall'AST |

## Limiti dichiarati

- I pattern costruiti a runtime (variabili, f-string, concatenazioni) **non sono
  visibili** all'inventario: per quelli serve la traccia a runtime, non un test
  statico.
- I duplicati tra usages sono ammessi e conteggiati: sono normali (es. validazioni
  identiche in moduli diversi). Sono considerati un difetto solo nel registro
  centralizzato, dove ogni pattern dovrebbe avere un solo nome.
- Cartelle escluse: `__pycache__`, `.git`, `.venv`, `data`, `state`, `node_modules`,
  `build`, `dist` — nessun dato o ambiente viene scansionato.

## Gate associati

| Gate | Esito |
|---|---|
| `pytest tests/test_regex_inventory.py -q` | 4 passed |
| compilazione di ogni pattern | 0 invalidi |
| registro senza duplicati | 0 duplicati |

Il test è **solo lettura**: non riscrive nessuna regex. Eventuali correzioni
sono una sessione separata, con anteprima e gate deterministici.
