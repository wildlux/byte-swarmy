---
name: qr-code
description: Skill per creare codici QR da testo o URL: generazione via libreria Python (qrcode), output PNG/SVG. Usa quando serve un codice QR.
---

# QR Code — skill per generazione QR

Flusso: **contenuto → generazione → verifica**.

## 1. Scopo

- Generare codici QR per URL o testo.

## 2. Workflow

1. Scegliere il contenuto (URL o testo).
2. Generare il QR con la libreria Python `qrcode`.
3. Salvare in PNG o SVG.

## 3. Quality gates

- Contenuti UTF-8.
- Dimensione coerente con il contenuto.

## 4. Comandi chiave

```bash
python - <<'PY'
import qrcode
img = qrcode.make("https://example.com")
img.save("/tmp/qrcode.png")
PY
```
