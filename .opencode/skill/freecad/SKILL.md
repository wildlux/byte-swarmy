---
name: freecad
description: Skill per usare FreeCAD: script Python (PartDesign/Build) per generare geometrie, import/export STEP/STL. Usa quando serve modellazione CAD via script.
---

# FreeCAD — skill per generazione CAD via script

Flusso: **specifica → script FreeCAD → esecuzione → export**.

## 1. Scopo

- Generare o modificare geometrie FreeCAD tramite script Python.

## 2. Workflow

1. Scrivere lo script per il Workbench PartDesign/Build.
2. Eseguire headless (`FreeCADCmd -c "import ..."`).
3. Export STEP/STL.

## 3. Quality gates

- Una operazione per script.
- Versione FreeCAD dichiarata.

## 4. Comandi chiave

```bash
FreeCADCmd -c "import MyScript"
```
