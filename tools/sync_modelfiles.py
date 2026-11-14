#!/usr/bin/env python3
"""tools/sync_modelfiles.py — Sincronizza i Modelfile con i modelli Ollama installati.

Scansiona i modelli disponibili su Ollama (/api/tags) e verifica quali
non hanno ancora una variante in ModelFiles/. Per ogni modello mancante,
genera un Modelfile di base con parametri sensati basati sulla dimensione
del modello e sulla VRAM disponibile.

Uso:
    python tools/sync_modelfiles.py [--create] [--dry-run] [--host http://localhost:11434]

    --dry-run     mostra cosa farebbe senza scrivere nulla
    --create      dopo aver generato i Modelfile, esegue 'ollama create'
                  per ogni variante (richiede Ollama avviato)
    --host        host Ollama (default: http://localhost:11434)
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import urllib.request
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
MODELFILES_DIR = BASE_DIR / "ModelFiles"

# Parametri base per categoria di dimensione modello (VRAM 4GB)
PARAMS = {
    "tiny":   {"num_ctx": 4096, "num_predict": 512,  "num_gpu": 256, "temperature": 0.1},
    "small":  {"num_ctx": 4096, "num_predict": 1024, "num_gpu": 256, "temperature": 0.2},
    "medium": {"num_ctx": 2048, "num_predict": 512,  "num_gpu": 256, "temperature": 0.2},
    "large":  {"num_ctx": 2048, "num_predict": 256,  "num_gpu": 256, "temperature": 0.2},
}


def get_ollama_models(host: str) -> list[dict]:
    """Legge i modelli da Ollama /api/tags."""
    try:
        with urllib.request.urlopen(f"{host}/api/tags", timeout=5) as r:
            data = json.loads(r.read())
    except Exception as e:
        print(f"ERRORE: impossibile contattare Ollama su {host}: {e}", file=sys.stderr)
        sys.exit(1)
    models = []
    for m in data.get("models", []):
        details = m.get("details", {})
        models.append({
            "name": m.get("name", ""),
            "size_gb": m.get("size", 0) / 1e9,
            "family": details.get("family", "unknown"),
            "quantization": details.get("quantization_level", "unknown"),
            "context_length": details.get("context_length", 0),
        })
    return models


def categorize(size_gb: float) -> str:
    """Categorizza per dimensione: tiny (<2GB), small (2-4GB), medium (4-8GB), large (>8GB)."""
    if size_gb < 2:
        return "tiny"
    if size_gb < 4:
        return "small"
    if size_gb < 8:
        return "medium"
    return "large"


def sanitize_name(name: str) -> str:
    """Sanitizza il nome modello per il nome file: qwen2.5:7b -> qwen2.5-7b."""
    return name.replace(":", "-").replace("/", "-").lower()


def existing_variants() -> set[str]:
    """Ritorna i nomi dei modelli base già coperti da un Modelfile."""
    variants = set()
    if not MODELFILES_DIR.is_dir():
        return variants
    for path in MODELFILES_DIR.glob("Modelfile*"):
        if path.name == "README.md":
            continue
        try:
            for line in path.read_text(encoding="utf-8").splitlines():
                if line.strip().startswith("FROM "):
                    variants.add(line.strip().split()[1])
        except Exception:
            pass
    return variants


def generate_modelfile(model: dict) -> str:
    """Genera il contenuto di un Modelfile per il modello dato."""
    cat = categorize(model["size_gb"])
    p = PARAMS[cat]
    name = model["name"]
    no_think = "qwen3" in name.lower() or "deepseek-r1" in name.lower()
    lines = [
        f"FROM {name}",
        f"PARAMETER num_ctx {p['num_ctx']}",
        f"PARAMETER num_predict {p['num_predict']}",
        f"PARAMETER num_gpu {p['num_gpu']}",
        f"PARAMETER temperature {p['temperature']}",
        f"PARAMETER num_batch 512",
        f"PARAMETER num_thread 4",
    ]
    if no_think:
        lines.append('SYSTEM "/no_think"')
    lines.append("")
    lines.append(f"# Auto-generato da sync_modelfiles.py — categoria: {cat} ({model['size_gb']:.1f}GB)")
    lines.append(f"# Famiglia: {model['family']} | Quant: {model['quantization']}")
    return "\n".join(lines) + "\n"


def main():
    parser = argparse.ArgumentParser(
        description="Sincronizza Modelfile con i modelli Ollama installati."
    )
    parser.add_argument("--dry-run", action="store_true",
                        help="Mostra cosa farebbe senza scrivere nulla")
    parser.add_argument("--create", action="store_true",
                        help="Esegue 'ollama create' per ogni nuova variante")
    parser.add_argument("--host", default="http://localhost:11434",
                        help="Host Ollama (default: http://localhost:11434)")
    args = parser.parse_args()

    models = get_ollama_models(args.host)
    covered = existing_variants()

    # Filtra modelli già coperti (inclusi i Modelfile esistenti)
    new_models = [m for m in models if m["name"] not in covered]

    if not new_models:
        print("✓ Tutti i modelli hanno già una variante in ModelFiles/.")
        return

    print(f"Modelli senza variante: {len(new_models)}")
    print()

    for m in new_models:
        cat = categorize(m["size_gb"])
        safe = sanitize_name(m["name"])
        out_path = MODELFILES_DIR / f"Modelfile-auto-{safe}"
        content = generate_modelfile(m)

        print(f"  [{cat:6s}] {m['name']:30s} ({m['size_gb']:.1f}GB) → {out_path.name}")
        print(f"          {content.strip().splitlines()[1]}")

        if not args.dry_run:
            MODELFILES_DIR.mkdir(parents=True, exist_ok=True)
            out_path.write_text(content, encoding="utf-8")
            print(f"          ✓ Scritto: {out_path}")

            if args.create:
                variant_name = f"{safe}-opt"
                print(f"          → ollama create {variant_name} -f {out_path}")
                r = subprocess.run(
                    ["ollama", "create", variant_name, "-f", str(out_path)],
                    capture_output=True, text=True,
                )
                if r.returncode == 0:
                    print(f"          ✓ Creato: {variant_name}")
                else:
                    print(f"          ✗ Errore: {r.stderr.strip()}")
        print()

    if args.dry_run:
        print("(dry-run: nessun file scritto)")


if __name__ == "__main__":
    main()