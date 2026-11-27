#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""F1 — gate deterministico per scaffold iOS/Android (offline).

Verifica SOLO la struttura dei template e la copertura dei ref curati:

* marker `# SLOT:` presenti e nessun timestamp;
* import e costrutti richiesti presenti nel template;
* simboli usati presenti nel ref `GUI/refs/mobile/*.md`.

NON compila Swift/Kotlin: le toolchain non sono presenti e il live resta
🔒 bloccato termicamente. Nessun LLM, rete o GPU.

Uso:
    .venv/bin/python tools/mobile_scaffold_check.py
    .venv/bin/python tools/mobile_scaffold_check.py --out RAG/DOCS/MOBILE_SCAFFOLD_REPORT.md
    .venv/bin/python tools/mobile_scaffold_check.py --json
"""
from __future__ import annotations

import argparse
import json
import re
import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "RAG" / "DOCS" / "MOBILE_SCAFFOLD_REPORT.md"
TEMPLATES = ROOT / "GUI" / "refs" / "templates"
MOBILE_REFS = ROOT / "GUI" / "refs" / "mobile"

SPECS = {
    "ios": {
        "label": "iOS / SwiftUI",
        "template": "mobile_ios.swift.tpl",
        "ref": "swiftui.md",
        "sdk": "swift",
        "imports": ("import SwiftUI",),
        "markers": ("struct ContentView: View", "var body: some View",
                    "@State"),
        "symbols": ("View", "State", "Text", "VStack", "Button", "padding"),
    },
    "android": {
        "label": "Android / Jetpack Compose",
        "template": "mobile_android.kt.tpl",
        "ref": "android_compose.md",
        "sdk": "kotlinc",
        "imports": (
            "import android.os.Bundle",
            "import androidx.activity.ComponentActivity",
            "import androidx.activity.compose.setContent",
            "import androidx.compose.foundation.layout.Column",
            "import androidx.compose.material3.Button",
            "import androidx.compose.material3.MaterialTheme",
            "import androidx.compose.material3.Surface",
            "import androidx.compose.material3.Text",
            "import androidx.compose.runtime.Composable",
            "import androidx.compose.runtime.mutableStateOf",
            "import androidx.compose.runtime.remember",
        ),
        "markers": ("class MainActivity : ComponentActivity()", "setContent {",
                    "@Composable"),
        "symbols": ("ComponentActivity", "setContent", "MaterialTheme",
                    "Surface", "Column", "Text", "Button", "Composable",
                    "remember", "mutableStateOf"),
    },
}


def check_source(key: str, src: str, ref_text: str) -> dict:
    """Valuta una coppia template/ref senza toccare il filesystem."""
    spec = SPECS[key]
    missing_imports = [line for line in spec["imports"] if line not in src]
    missing_markers = [line for line in spec["markers"] if line not in src]
    missing_refs = [sym for sym in spec["symbols"]
                    if f"`{sym}`" not in ref_text]
    missing_usage = [sym for sym in spec["symbols"] if sym not in src]
    timestamp_free = not re.search(r"\b20\d{2}-\d{2}-\d{2}\b", src)
    issues = []
    if "# SLOT:" not in src:
        issues.append("marker # SLOT: assente")
    if not timestamp_free:
        issues.append("timestamp nel template")
    issues += [f"import mancante: {line}" for line in missing_imports]
    issues += [f"costrutto mancante: {line}" for line in missing_markers]
    issues += [f"simbolo senza ref: {sym}" for sym in missing_refs]
    issues += [f"simbolo non usato: {sym}" for sym in missing_usage]
    return {
        "label": spec["label"],
        "template": spec["template"],
        "ref": spec["ref"],
        "has_slot": "# SLOT:" in src,
        "timestamp_free": timestamp_free,
        "missing_imports": missing_imports,
        "missing_markers": missing_markers,
        "missing_refs": missing_refs,
        "missing_usage": missing_usage,
        "issues": issues,
        "ok": not issues,
    }


def check_all() -> dict:
    results = {}
    for key in sorted(SPECS):
        spec = SPECS[key]
        src = (TEMPLATES / spec["template"]).read_text(encoding="utf-8")
        ref = (MOBILE_REFS / spec["ref"]).read_text(encoding="utf-8")
        row = check_source(key, src, ref)
        row["toolchain"] = shutil.which(spec["sdk"]) or "ASSENTE"
        results[key] = row
    return {
        "platforms": results,
        "ok": all(row["ok"] for row in results.values()),
    }


def _cell(ok: bool) -> str:
    return "✅" if ok else "❌"


def markdown(result: dict) -> str:
    lines = [
        "# 📱 Mobile scaffold — verifica strutturale (F1)",
        "",
        "_Generato deterministicamente da `tools/mobile_scaffold_check.py` "
        "— zero LLM, zero rete, zero GPU, zero timestamp._",
        "",
        "Questo gate verifica **solo struttura e copertura dei ref**. "
        "Non compila Swift/Kotlin e non dimostra che un'app giri su un "
        "dispositivo: per questo l'asse Mobile resta 2/4, non 4/4.",
        "",
        "| Piattaforma | Template | Ref | SLOT | Import | Costrutti | Simboli | Build |",
        "|---|---|---|---|---|---|---|---|",
    ]
    for key in sorted(result["platforms"]):
        row = result["platforms"][key]
        symbols_ok = not row["missing_refs"] and not row["missing_usage"]
        lines.append(
            f"| {row['label']} | `{row['template']}` | `{row['ref']}` | "
            f"{_cell(row['has_slot'])} | "
            f"{_cell(not row['missing_imports'])} | "
            f"{_cell(not row['missing_markers'])} | "
            f"{_cell(symbols_ok)} | "
            f"⚠️ non verificata (`{row['toolchain']}`) |")
    lines += ["", "## Dettagli", ""]
    for key in sorted(result["platforms"]):
        row = result["platforms"][key]
        lines.append(f"### {row['label']} — {'PASS' if row['ok'] else 'FAIL'}")
        lines.append("")
        if row["issues"]:
            lines += [f"- {issue}" for issue in row["issues"]]
        else:
            lines.append("- Nessuna anomalia strutturale rilevata.")
        lines.append("")
    lines += [
        "## Limite onesto",
        "",
        "- `api_lookup(strict=True)` è un gate Python: qui non si applica. "
        "I simboli mobile sono **statici**, verificati solo come presenza "
        "nei ref curati `GUI/refs/mobile/`.",
        "- La build richiede Xcode/iOS SDK e Android SDK, assenti in questo "
        "ambiente. Nessun verdetto di compilabilità.",
        "- Il collaudo con LLM resta 🔒 bloccato finché le ventole non sono "
        "verificate (≤60 °C).",
        "",
    ]
    return "\n".join(lines)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--out", default=str(OUT), help="file Markdown da scrivere")
    ap.add_argument("--json", action="store_true", help="stampa solo JSON")
    args = ap.parse_args(argv)

    result = check_all()
    if args.json:
        print(json.dumps(result, indent=2, ensure_ascii=False))
        return 0 if result["ok"] else 1
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(markdown(result), encoding="utf-8")
    print(f"Report scritto: {out} ({'PASS' if result['ok'] else 'FAIL'})")
    return 0 if result["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
