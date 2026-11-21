---
name: linux-kernel-refs
description: Skill per estrarre e iniettare riferimenti API dal kernel Linux (header C) per ridurre le allucinazioni su API kernel, anche nuove/non in training. Usa quando l'utente chiede driver Linux o kernel module con API specifiche.
---

# Linux Kernel Refs — skill per seguire API kernel corrette (anche nuove)

Flusso: **versione kernel → estrazione header → ref markdown → iniezione nel prompt → gate compile**.

## 1. Scopo

- Ridurre le allucinazioni su API kernel (nomi/firme inesistenti → panic).
- Funziona per API nuove: l'estrazione è deterministica dagli header della versione target.

## 2. Strategie (dal più forte al più debole)

1. **Estrazione dagli header**: `tools/extract_kernel_refs.py` estrae prototipi di funzione dagli header del kernel target → `CORE/refs/linux_kernel_<ver>.md`. Iniettato nel prompt.
2. **Compile gate**: `make -C /lib/modules/$(uname -r)/build M=$(pwd) modules` rifiuta simbodo inesistenti → correction prompt.
3. **checkpatch + sparse**: qualità e warning aggiuntivi.
4. **Correction loop**: fino a 3 retry con prompt di correzione.

## 3. Workflow

1. Identifica la versione kernel target (`uname -r`).
2. Esegui `tools/extract_kernel_refs.py [--subsystem i2c]` per generare il ref.
3. Inietta il ref nel prompt (sezione `## API REFS`).
4. Genera il codice (SLOT: scaffold deterministico + filler 3b).
5. Gate: `make` + `checkpatch.pl` + `sparse`.
6. Test in QEMU o su target.

## 4. Quality gates

- Ogni simbodo kernel usato deve esistere negli header target.
- `make` pulito (0 warning) contro i kernel headers target.
- `checkpatch.pl` senza errori.

## 5. Comandi chiave

```bash
.venv/bin/python tools/extract_kernel_refs.py
.venv/bin/python tools/extract_kernel_refs.py --subsystem i2c
make -C /lib/modules/$(uname -r)/build M=$(pwd) modules
scripts/checkpatch.pl --file driver.c
make C=1 CF="-D__CHECK_ENDIAN__"
```
