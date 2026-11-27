# 🧠 A/B memoria / contesto (E4)

**Modalità**: DRY-RUN (solver finto — NON è un verdetto reale) — task set `5e6051bfc33d` (10 task congelati).

**Gate termico**: N/A (dry-run) — live richiede `fan_rpm > 0` e `temp_c <= 60` in `data/state/fan_verified.json`.

| Soglia (fissata prima del live) | Valore |
|---|---:|
| with-context minimo | 0.60 |
| delta minimo (with − without) | 0.20 |
| GO / NO-GO / INCONCLUSIVE | GO / NO-GO / INCONCLUSIVE |

| Braccio | Passati | Totale | Tasso |
|---|---:|---:|---:|
| `with_context` | 8 | 10 | 0.80 |
| `without_context` | 0 | 10 | 0.00 |

Delta: **0.80** — verdetto harness (simulato): **GO**.

| Task | Braccio | Contesto (char) | Esito |
|---|---|---:|---|
| `mem-01` | `with_context` | 53 | ✅ |
| `mem-02` | `with_context` | 47 | ✅ |
| `mem-03` | `with_context` | 50 | ✅ |
| `mem-04` | `with_context` | 61 | ✅ |
| `mem-05` | `with_context` | 56 | ✅ |
| `mem-06` | `with_context` | 54 | ✅ |
| `mem-07` | `with_context` | 53 | ✅ |
| `mem-08` | `with_context` | 58 | ✅ |
| `mem-09` | `with_context` | 27 | ❌ |
| `mem-10` | `with_context` | 27 | ❌ |
| `mem-01` | `without_context` | 0 | ❌ |
| `mem-02` | `without_context` | 0 | ❌ |
| `mem-03` | `without_context` | 0 | ❌ |
| `mem-04` | `without_context` | 0 | ❌ |
| `mem-05` | `without_context` | 0 | ❌ |
| `mem-06` | `without_context` | 0 | ❌ |
| `mem-07` | `without_context` | 0 | ❌ |
| `mem-08` | `without_context` | 0 | ❌ |
| `mem-09` | `without_context` | 0 | ❌ |
| `mem-10` | `without_context` | 0 | ❌ |

⚠️ Il dry-run valida solo l'harness: il verdetto sull'impatto reale della memoria arriva da 10 task con LLM live, 🔒 bloccato finché le ventole non sono verificate. Non usare questi numeri per alzare l'asse Memoria/contesto del radar.
