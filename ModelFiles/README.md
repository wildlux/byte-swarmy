# ModelFiles — varianti Ollama per Byte-Swarmy

Ogni file qui dentro è un Modelfile che crea una variante di un modello
Ollama con parametri fissi ottimizzati per l'hardware di destinazione.

## Come usarli

```bash
# Dalla root del progetto:
ollama create <nome-modello> -f ./ModelFiles/<file>

# Esempi:
ollama create qwen3-8k -f ./ModelFiles/Modelfile
ollama create qwen3.5-4k-gpu -f ./ModelFiles/Modelfile-qwen4k
```

## Varianti disponibili

| File | Base | num_ctx | num_gpu | Note |
|---|---|---|---|---|
| `Modelfile` | qwen3:8b | 8192 | auto | Batch 512, 4 thread. Per compiti generali. |
| `Modelfile-qwen4k` | qwen3.5-4k | 4096 | 256 (tutto su GPU) | Forza GPU, disattiva thinking. Per hardware 4 GB VRAM. |

## Aggiungere una nuova variante

1. Crea un file `Modelfile-<nome>` in questa cartella.
2. Usa `FROM <modello-base>` e imposta i parametri con `PARAMETER`.
3. Registra con `ollama create <nome> -f ./ModelFiles/Modelfile-<nome>`.
4. Aggiorna la tabella sopra.
5. Aggiungi il modello al blocco `models` in `~/.config/opencode/opencode.json`.

## Note

- I parametri sono **fissi**: non vengono modificati a runtime. Ogni variante è un modello a sé.
- Non committare modelli scaricati (`.ollama/`): solo i Modelfile (testo) vanno nel repo.
- Per hardware con più VRAM, crea varianti con `num_ctx` più alto (es. 16384, 32768).
EOF
echo done