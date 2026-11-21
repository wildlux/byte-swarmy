---
name: blender
description: Skill per usare Blender: script Python (bpy) per generare mesh e oggetti, esportazione glTF/OBJ/STL, rendering. Usa quando serve asset 3D via script.
---

# Blender — skill per asset 3D via script

Flusso: **specifica → script bpy → esecuzione → export**.

## 1. Scopo

- Generare oggetti 3D in Blender tramite script Python (bpy).

## 2. Workflow

1. Scrivere script bpy (primitive, modifier, materiali).
2. Eseguire headless (`blender -b -P script.py`).
3. Esportare glTF/OBJ/STL.

## 3. Quality gates

- Versione Blender dichiarata.
- Una modifica per script.

## 4. Comandi chiave

```bash
blender -b --python my_script.py
```
