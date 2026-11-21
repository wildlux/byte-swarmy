---
name: research-report
description: Ricerca online + scrittura di report (PDF / Excel / Word / ODT via LibreOffice) + disegno di grafici e diagrammi SVG. Usa quando l'utente chiede ricerche, confronti, analisi con fonti esterne, report o deliverable scritti, oppure quando serve generare diagrammi/schemi in SVG.
---

# Research Report — skill unica (ricerca → report → grafici SVG)

Un unico flusso di lavoro per: **ricercare online, scrivere un report in un formato
scritto o quantitativo, e produrre diagrammi/schemi in SVG**.

## 1. Fasi del flusso

1. **Input**: argomento/tipo di report richiesto dall'utente.
2. **Ricerca** (online): fonti (browser, webfetch, websearch), criteri di
   affidabilità, data di pubblicazione, citazioni (URL + titolo + data).
3. **Sintesi**: mappa concettuale, punti salienti, gap, incertezze.
4. **Scrittura report**: struttura standard → conversione in formato target.
5. **Diagrammi/Schemi SVG**: per architetture, flussi, comparazioni, grafici.

## 2. Ricerca online

- Usa `websearch` / `webfetch` / browser per raccogliere fonti; registra URL,
  titolo, data.
- Cita sempre con fonte; separa dati verificati da ipotesi dell'utente.
- Se una fonte è inaffidabile o assente → segnala l'incertezza, non inventare.

## 3. Scrittura del report

Struttura standard: titolo, executive summary, contesto, metodologia,
risultati, analisi, conclusioni, raccomandazioni, appendice fonti.

### Conversioni (via LibreOffice headless — fallback ai formati Python nativi)

- Word/DOCX: da Markdown/HTML → ODT (`pandoc` o python-docx) → `soffice
  --headless --convert-to=docx`; oppure scrivere ODT e convertire.
- Excel/XLSX: `openpyxl` (dati) o ods → `soffice --headless --convert-to=ods`.
- PDF: `soffice --headless --convert-to=pdf file.odt file.pdf` (o da HTML).
- LibreOffice nativo: file sorgente ODT/ODS/ODP → esportazione PDF via CLI.

Comandi base:

```bash
soffice --headless --convert-to=pdf /tmp/report.odt /tmp/report.pdf
soffice --headless --convert-to=ods /tmp/report.ods /tmp/report.xlsx
soffice --headless --convert-to=docx /tmp/report.odt /tmp/report.docx
```

Se LibreOffice non è disponibile: usa i generatori Python nativi
(`python-docx` per DOCX, `openpyxl` per XLSX, `reportlab`/HTML→PDF per PDF).

## 4. Diagrammi / schemi SVG

- Genera SVG deterministico via script (Python con `xml.etree`/stringhe, o
  generatore a mano) per: flussi, architetture, timeline, grafici comparativi.
- Struttura SVG: viewBox, scala, testo leggibile, colori coerenti col report.
- Salva in `EXPORT/` o `/tmp`; verifica che sia XML ben formato.

## 5. Quality gates

- Fonti verificate e citate; date contestuali.
- Niente dati inventati: se non reperibili → "non disponibile".
- Report e diagrammi coerenti (stesso set di dati/fatti).

## 6. Comandi chiave

```bash
soffice --headless --convert-to=pdf input.odt output.pdf
soffice --headless --convert-to=ods input.ods output.xlsx
soffice --headless --convert-to=docx input.odt output.docx
soffice --headless --convert-to=pdf input.html output.pdf
python -c "import openpyxl"   # XLSX
python -c "import docx"       # DOCX
```
