# Hardware Detection — BYTE-SWARMY

Auto-rilevamento hardware per ottimizzare Worker paralleli, keep_alive modelli
e strategia CPU/GPU. Compatibile con Apple Silicon, NVIDIA, AMD e solo CPU.

## Architettura

```
Avvio byte-swarmy
       ↓
[CORE/hardware_detector.py] — detect()
       ↓
Rileva: GPU type, RAM, VRAM, bandwidth, unified vs dedicated
       ↓
Seleziona strategia ottimale (STRATEGIES dict)
       ↓
[CORE/ollama_client.py] — usa keep_alive suggerito per _unload()
       ↓
[GUI/hardware_panel.py] — mostra profilo + strategia all'utente
```

## 6 profili hardware supportati

| # | Hardware | RAM/VRAM | Strategia | Workers | Keep alive | Modelli in RAM |
|---|----------|----------|-----------|---------|------------|----------------|
| 1 | Apple M3/M4 Max | ≥32GB unified | `unified_parallel` | 4 | 600s | 4 |
| 2 | Apple M1/M2/M3 base | 16GB unified | `unified_light` | 2 | 300s | 2 |
| 3 | NVIDIA RTX 4090 | ≥20GB VRAM | `nvidia_dual` | 2 | 300s | 2 |
| 4 | NVIDIA RTX 3060/4060 | 8-20GB VRAM | `nvidia_cpu_split` | 2 | 60s | 2 |
| 5 | AMD Radeon RX 7800+ | ≥16GB VRAM | `amd_dual` | 2 | 300s | 2 |
| 6 | Solo CPU | any | `cpu_only` | 1 | 0s | 1 |

## Strategie dettagliate

### `unified_parallel` — Apple Silicon ≥32GB
**Quando**: Mac M1/M2/M3/M4 Max o Ultra con 32GB+ memoria unificata.
**Comportamento**: 4 Worker paralleli, 4 modelli caricati simultaneamente in
RAM unificata (zero context switch), keep_alive 10 minuti.
**Vantaggio**: bandwidth 400 GB/s permette context switch istantanei (~100ms
vs 5s su PCIe).

### `unified_light` — Apple Silicon 16GB
**Quando**: Mac base (M1/M2/M3) con 16GB memoria unificata.
**Comportamento**: 2 Worker paralleli, 2 modelli simultanei, keep_alive 5 min.
**Limitazione**: RAM limitata non permette 4 modelli grandi simultanei.

### `nvidia_dual` — NVIDIA ≥20GB VRAM
**Quando**: RTX 4090 (24GB), RTX 5090 (32GB), A100 (40-80GB), H100 (80GB).
**Comportamento**: 2 Worker su GPU, 2 modelli su VRAM dedicata, keep_alive 5 min.
**Limitazione**: VRAM dedicata richiede copy via PCIe (~20 GB/s) ma una volta
caricati i modelli, l'inference è velocissimo.

### `nvidia_cpu_split` — NVIDIA 8-20GB VRAM
**Quando**: RTX 3060 (12GB), RTX 4060 (8GB), RTX 4070 (12GB).
**Comportamento**: 1 Worker su GPU + 1 Worker su CPU, keep_alive breve (60s).
**Strategia**: sfrutta GPU per inference veloce e CPU per task paralleli.

### `amd_dual` — AMD ROCm ≥16GB VRAM
**Quando**: Radeon RX 7800 XT (16GB), RX 7900 XTX (24GB), Instinct MI250/MI300.
**Comportamento**: 2 Worker su GPU AMD, 2 modelli su VRAM, keep_alive 5 min.
**Requisito**: ROCm installato e `rocm-smi` disponibile nel PATH.

### `cpu_only` — Solo CPU
**Quando**: nessuna GPU rilevata, o GPU entry-level (<8GB VRAM).
**Comportamento**: 1 Worker, 1 modello alla volta, keep_alive 0 (scarica subito
per liberare RAM).
**Fallback**: è il default sicuro quando il rilevamento fallisce.

## File coinvolti

| File | Ruolo |
|------|-------|
| `CORE/hardware_detector.py` | Rilevamento + selezione strategia (modulo principale) |
| `CORE/ollama_client.py` | Usa `get_keep_alive_override()` per decidere keep_alive |
| `GUI/hardware_panel.py` | Pannello GUI "Hardware & Modelli" nella Plancia |
| `GUI/control_center.py` | Card "🖥️ Hardware & Modelli" nella Plancia |
| `CONFIG/config.toml` | Sezione `[hardware]` con mode=auto o override manuali |

## Configurazione

### Modalità auto (default, raccomandata)
```toml
[hardware]
mode = "auto"
```
byte-swarmy rileva l'hardware al boot e applica la strategia ottimale.

### Override manuale
```toml
[hardware]
mode = "manual"
worker_count = 2
keep_alive_sec = 300
strategy = "unified_light"
```
Utile per testing o per forzare una strategia specifica.

## API Python

```python
from CORE.hardware_detector import detect, get_profile, get_keep_alive_override

# Rileva una volta (cached)
profile = get_profile()
print(profile.gpu_type)        # "apple_metal" | "nvidia_cuda" | "amd_rocm" | "none"
print(profile.memory_unified)  # True per Apple Silicon
print(profile.strategy)        # "unified_parallel" | ...
print(profile.worker_count)    # 1-4
print(profile.keep_alive_sec)  # 0-600
print(profile.summary)         # one-line summary

# Forza refresh (es. dopo aver collegato GPU esterna)
profile = get_profile(force_refresh=True)

# Keep alive per ModelClient (tiene conto di config override)
keep_alive = get_keep_alive_override(config)
```

## CLI di test

```bash
# Rileva e mostra profilo
python -m CORE.hardware_detector

# Output JSON
python -m CORE.hardware_detector --json

# Mostra dati grezzi di rilevamento
python -m CORE.hardware_detector --verbose
```

## Test con mock (per CI)

Il modulo è testato con mock per simulare tutti i 6 profili hardware:
- `tests/test_hardware_detector.py` (da creare) — mocka `platform.system()` e
  `subprocess.run()` per simulare Apple/NVIDIA/AMD/CPU.

Esempio di test con mock:
```python
from unittest.mock import patch, MagicMock
from CORE import hardware_detector as hd

with patch('platform.system', return_value='Darwin'), \
     patch('subprocess.run') as mock_run:
    mock_run.return_value = MagicMock(
        returncode=0,
        stdout='Chip: Apple M3 Max\nMemory: 64 GB\n',
        stderr='',
    )
    profile = hd.detect()
    assert profile.gpu_type == 'apple_metal'
    assert profile.strategy == 'unified_parallel'
    assert profile.worker_count == 4
```

## Estensioni future

1. **Multi-GPU NVIDIA**: rilevare più GPU (NVLink) e distribuire modelli su più VRAM
2. **Apple Ultra**: rilevare M1/M2/M3 Ultra (2 chip, 800 GB/s bandwidth)
3. **Dynamic rebalancing**: monitorare RAM/VRAM in tempo reale e ridurre
   worker_count se la memoria si satura
4. **Ollama ps integration**: leggere `ollama ps` per vedere quali modelli sono
   già caricati e ottimizzare keep_alive di conseguenza
5. **User override GUI**: pannello per cambiare strategia senza editare config

## Troubleshooting

### "GPU type: none" ma ho una GPU
- **Apple**: assicurati che `system_profiler` sia nel PATH (default su macOS)
- **NVIDIA**: installa `nvidia-smi` (pacchetto `nvidia-utils` su Linux)
- **AMD**: installa ROCm (`rocm-smi` deve essere nel PATH)

### Thermal Routing (M4 — Fase 8)
Il routing per complessità consulta lo stato termico prima di scegliere il modello heavy:
- Se CPU ≥ 75°C o GPU ≥ 80°C → l'heavy viene evitato, si resta sul base.
- Lezione della suite comparativa: il 4B muore di throttling (300s timeout), il 3B regge.
- Campione fresco da `state/timestral_history.json` (GUI, <120s) o lettura diretta `/sys` (CLI).
- Fail-open: se la lettura termica fallisce, l'heavy parte comunque.
- Configurabile: `[complexity_routing] thermal_guard = true/false`.

### Strategy sbagliata
Forza manualmente in `CONFIG/config.toml`:
```toml
[hardware]
mode = "manual"
strategy = "unified_parallel"  # o altra strategia valida
```

### Cambio hardware a runtime
Click su "🔄 Rileva hardware di nuovo" nel pannello GUI, oppure riavvia byte-swarmy.
Il rilevamento è cached nella sessione, ma `force_refresh=True` rilancia.
