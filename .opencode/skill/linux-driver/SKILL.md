---
name: linux-driver
description: Skill per sviluppo driver Linux (moduli kernel, char device, platform/I2C/SPI, DMA, IRQ, device tree, regmap, IIO/GPIO/input) con gate deterministici (compilazione contro kernel headers, checkpatch, sparse). Usa quando l'utente chiede driver Linux o kernel module.
---

# Linux Driver — skill per sviluppo driver Linux

Flusso: **specifica → scaffold → codice → gate (compile/checkpatch/sparse) → test (QEMU/module)**.

## 1. Scopo

- Generare/modificare driver Linux (C) con gate deterministici.
- Riferimenti: kernel headers della versione target, device tree, ABI.

## 2. Workflow

1. Identificare il sottosistema (char, platform, I2C, SPI, IIO, GPIO, input, DMA).
2. Scaffold del modulo (Makefile, Kbuild, probe/remove, file_operations):
   `.venv/bin/python tools/kernel_slot_scaffold.py --name NOME --out DIR`
   genera lo scheletro con 3 slot (read/write/ioctl) e verifica le API
   contro la whitelist degli header target (fail closed).
3. Implementare le operazioni (read/write/ioctl, probe, remove, IRQ handler).
4. Gate: `make` contro i kernel headers della versione target.
5. `scripts/checkpatch.pl` + `sparse` per qualità.
6. Test in QEMU o su target reale (insmod/rmmod, dmesg).

## 3. Quality gates

- Compilazione pulita contro i kernel headers target (nessun warning).
- `checkpatch.pl` senza errori.
- `sparse` senza warning.
- Nessuna API allucinata: ogni simbodo kernel deve esistere negli header target;
  dopo il fill degli slot eseguire
  `.venv/bin/python tools/kernel_slot_scaffold.py --check FILE.c`.

## 4. Mappa capitoli (Linux Device Driver Development, 2nd ed.)

| Argomento | Capitolo |
|---|---|
| Kernel module basics | 1-2 |
| Kernel helpers | 3 |
| Character device | 4 |
| Device tree | 5 |
| Platform devices/drivers | 6-7 |
| I2C / SPI | 8-9 |
| Memory / DMA / Regmap | 10-12 |
| IRQ framework | 13 |
| Device model | 14 |
| IIO / GPIO / Input | 15-17 |

## 5. Comandi chiave

```bash
make -C /lib/modules/$(uname -r)/build M=$(pwd) modules
scripts/checkpatch.pl --file driver.c
make C=1 CF="-D__CHECK_ENDIAN__"
sudo insmod driver.ko && dmesg | tail
```
