---
name: svg-studio
description: Skill per la creazione di diagrammi/schemi grafici in SVG con strumenti open source (Inkscape, Krita) e validazione dei file SVG per l'apertura nei programmi liberi. Usa quando serve un diagramma SVG da aprire in Inkscape/Krita o da generare programmaticamente.
---

# SVG Studio — diagrammi e schemi in SVG con strumenti liberi

Flusso: **progettazione → generazione SVG → validazione → export/compat**.

## 1. Scopo
- Generare diagrammi (architetture, flussi, timeline, grafici) in SVG.
- Usare strumenti open source: Inkscape (CLI), Krita, oppure generazione programmatica.
- I file SVG devono essere **aperti** in Inkscape/Krita (compatibilità SVG standard).

## 2. Workflow
1. Progettare diagramma (componenti, relazioni, stile).
2. Generare SVG (script Python/XML o Inkscape CLI).
3. Validare: XML ben formato, viewBox, percorsi/chiusure, dimensioni.
4. Esportare/compatibilità: Inkscape/Krita aprono SVG; conversioni a PNG/PDF se serve.

## 3. Tipi di diagramma supportati

- **Box + freccia**: `rect` + `marker` arrow tra due box.
- **Box + linea**: `rect` + `line` (senza marker) tra due box.
- **Misto**: più box connessi da connessioni **freccia** e/o **linea** (straight
  line), sia singole sia combinate.
- Coordinamento: sorgente/destinazione come anchor (`x1/y1/x2/y2` per linee,
  `cx/cy` o punti di ancoraggio per marker).

## 4. Quality gates
- SVG ben formato (nessun tag non chiuso).
- viewBox dichiarato.
- Testo leggibile, scale coerenti.

## 5. Comandi chiave
```bash
inkscape /tmp/diagram.svg --export-type=png --export-filename=/tmp/diagram.png
python - <<'PY'
# generazione SVG programmatica
import xml.etree.ElementTree as ET
svg = ET.Element("svg", {"xmlns": "http://www.w3.org/2000/svg", "viewBox": "0 0 100 100"})
ET.SubElement(svg, "rect", {"width": "100", "height": "100"})
ET.ElementTree(svg).write("/tmp/diagram.svg")
PY
```
