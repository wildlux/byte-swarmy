# 🔬 API Fidelity Eval (E2)

**Verdetto**: ✅ PASS — 0 simboli indefiniti, 0 ref non validi. Zero LLM, zero rete.

| Caso | Modulo | Simboli | Verificati | Indefiniti | Esito |
|---|---|---:|---:|---|---|
| json-01 | `json` | 3 | 3 | 0 | ✅ |
<!-- json-01: JSONEncoder, dumps, loads -->
| csv-01 | `csv` | 4 | 4 | 0 | ✅ |
<!-- csv-01: DictWriter, QUOTE_MINIMAL, excel, reader -->

| Ref | Firme | Mancanti | Esito |
|---|---:|---|---|
| `GUI/refs/csv_api.md` | 14 | 0 | ✅ |
| `GUI/refs/json_api.md` | 8 | 0 | ✅ |

Gate: `api_lookup(strict=True)` è lo stesso usato dal worker; i ref sono generati da `tools/gen_api_refs.py` e validati da `tools/validate_refs.py`.
