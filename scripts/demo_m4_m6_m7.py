"""Run live M4 + M6 + M7 — dimostrazione comportamento senza LLM.

Cosa fa:
  M4 — routing termico:
    1. simula temperatura alta (CPU 82 °C) in state/timestral_history.json
    2. lancia route_model_key con TASK_ALTA_KW (keyword thread/lock)
    3. verifica: routing decide heavy ✓ ma _thermal_blocked lo declassa a base
    4. simula temperatura OK (CPU 50 °C) → heavy parte normalmente

  M6 — signature cache di code_map.rebuild:
    1. crea progetto temporaneo con 1 file .py
    2. chiama rebuild 3 volte di fila, misura il tempo
    3. confronto con rebuild(force=True)
    4. aggiunge un file → la signature cambia → rebuild rifà il parse

  M7 — isteresi persistente:
    1. processo A: lancia task ALTA → sticky=True scritto su disco
    2. "riavvia processo" (azzera la cache in memoria)
    3. processo B: lancia task MEDIA → deve risultare ALTA (sticky dal disco)
    4. lancia task BASSA → sticky azzerato sul disco

Tutto senza LLM: usa mock per la temperatura, progetti temporanei reali.
"""
from __future__ import annotations

import json
import shutil
import sys
import tempfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import CORE.routing as routing
import CORE.code_map as code_map


# ── Configurazione di prova (stessa del test suite) ──────────────────
CFG = {
    "complexity_routing": {
        "enabled": True,
        "heavy_model": "worker_granite",
    },
    "models": {
        "worker_coder": {"name": "qwen2.5-coder:3b"},
        "worker_granite": {"name": "granite4:7b-a1b-h"},
    },
}
BASE = "worker_coder"
GRANITE_NAME = "granite4:7b-a1b-h"

TASK_ALTA_KW = "task thread con lock e join"  # ADVANCED keyword
TASK_MEDIA = "crea una classe semplice con json"
TASK_BANALE = "stampa ciao mondo"


def section(title: str) -> None:
    print()
    print("=" * 70)
    print(f"  {title}")
    print("=" * 70)


# ── M4: routing termico ─────────────────────────────────────────────
def demo_m4_thermal() -> None:
    section("M4 — Routing termico: heavy bloccato in zona pausa")

    # Reindirizza il file di stato termico a un tempdir
    tmpdir = Path(tempfile.mkdtemp())
    hist_file = tmpdir / "timestral_history.json"
    # ... ma il routing legge da "state/timestral_history.json" (path
    # relativo). Creiamo una dir state/ nel tmpdir e cambiamo cwd.
    orig_cwd = Path.cwd()
    # Ci serve un cwd dove "state/timestral_history.json" possa esistere.
    # Patchiamo _latest_temps per usare il nostro file:
    orig_latest_temps = routing._latest_temps
    state_dir = tmpdir / "state"
    state_dir.mkdir()

    def stub_latest_temps():
        # Legge dal nostro file di stato (come quello vero, ma path our)
        try:
            data = json.loads((state_dir / "timestral_history.json").read_text())
            samples = data.get("samples") or []
            if samples:
                last = samples[-1]
                return (float(last.get("cpu_temp_max") or 0),
                        float(last.get("gpu_temp") or 0))
        except Exception:
            pass
        return (0.0, 0.0)
    routing._latest_temps = stub_latest_temps

    routing.reset_hysteresis()

    try:
        # 1) Sotto soglia → heavy parte
        (state_dir / "timestral_history.json").write_text(json.dumps({
            "samples": [{"cpu_temp_max": 50.0, "gpu_temp": 45.0,
                        "timestamp": time.time()}]
        }))
        print("\n[CPU 50°C / GPU 45°C] sotto soglia → heavy deve partire")
        key, lv, why = routing.route_model_key(
            TASK_ALTA_KW, "", CFG, BASE, {GRANITE_NAME})
        print(f"  → key = {key}")
        print(f"  → livello = {lv}")
        print(f"  → motivazione = {why}")
        assert key == "worker_granite", "Sotto soglia l'heavy deve partire"

        # 2) Sopra soglia CPU (>= 75) → heavy evitato
        (state_dir / "timestral_history.json").write_text(json.dumps({
            "samples": [{"cpu_temp_max": 82.0, "gpu_temp": 0.0,
                        "timestamp": time.time()}]
        }))
        print("\n[CPU 82°C / GPU 0°C] CPU in zona pausa → heavy deve essere evitato")
        key, lv, why = routing.route_model_key(
            TASK_ALTA_KW, "", CFG, BASE, {GRANITE_NAME})
        print(f"  → key = {key}")
        print(f"  → livello = {lv}")
        print(f"  → motivazione = {why}")
        assert key == BASE, "Sopra soglia CPU, l'heavy deve essere evitato"
        assert "termico" in why, "La motivazione deve menzionare il blocco termico"

        # 3) Sopra soglia GPU (>= 80) → heavy evitato
        (state_dir / "timestral_history.json").write_text(json.dumps({
            "samples": [{"cpu_temp_max": 60.0, "gpu_temp": 85.0,
                        "timestamp": time.time()}]
        }))
        print("\n[CPU 60°C / GPU 85°C] GPU in zona pausa → heavy deve essere evitato")
        key, lv, why = routing.route_model_key(
            TASK_ALTA_KW, "", CFG, BASE, {GRANITE_NAME})
        print(f"  → key = {key}")
        print(f"  → livello = {lv}")
        print(f"  → motivazione = {why}")
        assert key == BASE, "Sopra soglia GPU, l'heavy deve essere evitato"

        # 4) Torniamo a temperatura OK → heavy riparte
        (state_dir / "timestral_history.json").write_text(json.dumps({
            "samples": [{"cpu_temp_max": 55.0, "gpu_temp": 50.0,
                        "timestamp": time.time()}]
        }))
        print("\n[CPU 55°C / GPU 50°C] tornati a temperatura OK → heavy riparte")
        key, lv, why = routing.route_model_key(
            TASK_ALTA_KW, "", CFG, BASE, {GRANITE_NAME})
        print(f"  → key = {key}")
        print(f"  → livello = {lv}")
        print(f"  → motivazione = {why}")
        assert key == "worker_granite", "Tornati a temperatura OK l'heavy deve ripartere"

        print("\n✅ M4 PASS: il routing termico declassa l'heavy in zona pausa")
    finally:
        routing._latest_temps = orig_latest_temps
        routing.reset_hysteresis()
        shutil.rmtree(tmpdir, ignore_errors=True)


# ── M6: signature cache ─────────────────────────────────────────────
def demo_m6_cache() -> None:
    section("M6 — Signature cache: rebuild no-op se il progetto non cambia")

    code_map.reset_rebuild_cache()
    proj = Path(tempfile.mkdtemp())
    (proj / "a.py").write_text(
        "def f():\n    return 1\n", encoding="utf-8")
    (proj / "b.py").write_text(
        "def g():\n    return 2\n", encoding="utf-8")

    try:
        # 1) Prima chiamata: cold cache, fa il parse
        t0 = time.perf_counter()
        s1 = code_map.rebuild(proj)
        cold_ms = (time.perf_counter() - t0) * 1000
        print(f"\n1) Prima rebuild (cold cache): {cold_ms:.2f} ms")
        print(f"   files={s1['files']} symbols={s1['symbols']}")

        # 2) Seconda chiamata: signature uguale, cache hit
        t0 = time.perf_counter()
        s2 = code_map.rebuild(proj)
        hot_ms = (time.perf_counter() - t0) * 1000
        print(f"\n2) Seconda rebuild (cache hit): {hot_ms:.2f} ms")
        print(f"   files={s2['files']} symbols={s2['symbols']}")
        speedup = cold_ms / max(hot_ms, 0.001)
        print(f"   speedup ×{speedup:.1f}")
        assert s1 == s2, "Le stats devono essere identiche"
        assert hot_ms < cold_ms, "La cache hit deve essere più veloce"

        # 3) Modifica un file (mtime cambia) → signature cambia → rebuild
        (proj / "a.py").write_text(
            "def f():\n    return 99\n", encoding="utf-8")
        t0 = time.perf_counter()
        s3 = code_map.rebuild(proj)
        rebuild_ms = (time.perf_counter() - t0) * 1000
        print(f"\n3) Modificato a.py → rebuild reale: {rebuild_ms:.2f} ms")
        print(f"   files={s3['files']} symbols={s3['symbols']} (file count invariato)")

        # 4) force=True salta la cache anche se il progetto non è cambiato
        t0 = time.perf_counter()
        s4 = code_map.rebuild(proj, force=True)
        forced_ms = (time.perf_counter() - t0) * 1000
        print(f"\n4) rebuild(force=True): {forced_ms:.2f} ms (cache ignorata)")
        print(f"   files={s4['files']} symbols={s4['symbols']}")

        # 5) Aggiungi un file → signature cambia (count +1)
        (proj / "c.py").write_text(
            "def h():\n    return 3\n", encoding="utf-8")
        s5 = code_map.rebuild(proj)
        print(f"\n5) Aggiunto c.py → rebuild rileva: files={s5['files']} symbols={s5['symbols']}")
        assert s5["files"] == 3, "La signature deve rilevare il nuovo file"

        print("\n✅ M6 PASS: signature cache rende il rebuild no-op se il progetto non cambia")
    finally:
        code_map.reset_rebuild_cache()
        shutil.rmtree(proj, ignore_errors=True)


# ── M7: isteresi persistente ────────────────────────────────────────
def demo_m7_persistent() -> None:
    section("M7 — Isteresi persistente: sopravvive al riavvio del processo")

    # Reindirizza _HYST_FILE a un tempdir per non inquinare state/
    tmpdir = Path(tempfile.mkdtemp())
    orig_file = routing._HYST_FILE
    routing._HYST_FILE = tmpdir / "routing_hysteresis.json"
    # Simula processo fresco
    routing._HYST = {"heavy": False, "loaded": False}

    try:
        # Processo A: task ALTA → imposta sticky heavy, scrive su disco
        print("\n[Processo A] task ALTA (thread+lock) → deve andare heavy e scrivere sticky")
        key, lv, why = routing.route_model_key(
            TASK_ALTA_KW, "", CFG, BASE, {GRANITE_NAME})
        print(f"  → key={key} livello={lv}")
        sticky_file = tmpdir / "routing_hysteresis.json"
        assert sticky_file.exists(), "Il file sticky deve essere stato creato"
        data = json.loads(sticky_file.read_text())
        print(f"  → sticky su disco: {data}")
        assert data["heavy"] is True, "Sticky deve essere True dopo un task alta"

        # Riavvio processo: memoria azzerata
        print("\n[Riavvio processo] memoria azzerata, file sticky ancora presente")
        routing._HYST = {"heavy": False, "loaded": False}

        # Processo B: task MEDIA → deve restare heavy (sticky dal disco)
        print("\n[Processo B] task MEDIA (classe+json) → deve RESTARE heavy (sticky dal disco)")
        key, lv, why = routing.route_model_key(
            TASK_MEDIA, "", CFG, BASE, {GRANITE_NAME})
        print(f"  → key={key} livello={lv}")
        print(f"  → motivazione: {why}")
        assert lv == "alta", "Lo sticky deve mantenere il livello alta per task media"
        assert "isteresi" in why, "La motivazione deve menzionare l'isteresi"

        # Processo B: task BASSA → resetta sticky sul disco
        print("\n[Processo B] task BASSA → deve RESETTARE sticky sul disco")
        key, lv, why = routing.route_model_key(
            TASK_BANALE, "", CFG, BASE, {GRANITE_NAME})
        print(f"  → key={key} livello={lv}")
        data = json.loads(sticky_file.read_text())
        print(f"  → sticky su disco: {data}")
        assert data["heavy"] is False, "Sticky deve essere False dopo un task bassa"

        # Riavvio processo: il file dice heavy=False
        print("\n[Riavvio processo] task MEDIA → deve restare MEDIA (sticky False)")
        routing._HYST = {"heavy": False, "loaded": False}
        key, lv, why = routing.route_model_key(
            TASK_MEDIA, "", CFG, BASE, {GRANITE_NAME})
        print(f"  → key={key} livello={lv}")
        assert lv != "alta", "Dopo reset, un task media non deve diventare heavy"

        print("\n✅ M7 PASS: isteresi persistente tra riavvii processo")
    finally:
        routing._HYST_FILE = orig_file
        routing._HYST = {"heavy": False, "loaded": False}
        routing.reset_hysteresis()
        shutil.rmtree(tmpdir, ignore_errors=True)


# ── Demo "stale sticky" ─────────────────────────────────────────────
def demo_m7_stale() -> None:
    section("M7 — Sub-demo: sticky scaduto (oltre STICKY_MAX_AGE_S) è ignorato")

    tmpdir = Path(tempfile.mkdtemp())
    orig_file = routing._HYST_FILE
    routing._HYST_FILE = tmpdir / "routing_hysteresis.json"
    routing._HYST = {"heavy": False, "loaded": False}

    try:
        sticky = tmpdir / "routing_hysteresis.json"
        # Scrive un file vecchissimo
        old_ts = time.time() - routing.STICKY_MAX_AGE_S - 100
        sticky.write_text(json.dumps({"heavy": True, "ts": old_ts}))
        print(f"\nSticky scritto con ts = {old_ts:.0f} "
              f"({routing.STICKY_MAX_AGE_S + 100}s fa, oltre TTL "
              f"di {routing.STICKY_MAX_AGE_S}s)")
        print("Task MEDIA → deve essere MEDIA, non alta (sticky scaduto)")
        key, lv, why = routing.route_model_key(
            TASK_MEDIA, "", CFG, BASE, {GRANITE_NAME})
        print(f"  → key={key} livello={lv}")
        assert lv != "alta", "Sticky scaduto deve essere ignorato"
        print("\n✅ Sticky scaduto correttamente ignorato")
    finally:
        routing._HYST_FILE = orig_file
        routing._HYST = {"heavy": False, "loaded": False}
        routing.reset_hysteresis()
        shutil.rmtree(tmpdir, ignore_errors=True)


if __name__ == "__main__":
    print("Run live M4 + M6 + M7 — senza LLM, con mock termici e progetti temporanei")
    print(f"Python: {sys.version.split()[0]}")
    print(f"routing module: {routing.__file__}")
    print(f"code_map module: {code_map.__file__}")

    demo_m4_thermal()
    demo_m6_cache()
    demo_m7_persistent()
    demo_m7_stale()

    print()
    print("=" * 70)
    print("  TUTTI I DEMO PASS — M4 + M6 + M7 funzionano end-to-end")
    print("=" * 70)
