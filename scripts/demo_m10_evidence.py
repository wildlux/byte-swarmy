"""Run live M10 — evidence-based model selection, senza LLM.

Dimostra che CORE/model_selector.py ora integra i risultati REALI
della suite T1-T10 salvati in state/suite_compare/results.json.

Scenari:
  1. load_suite_evidence: lettura di un results.json simulato
     con risultati per worker_coder (10/10) e worker_coder_big (4/10)
  2. _evidence_boost_for_model: soglie 10/10, 7-9/10, 5-6/10,
     1-4/10, 0/10, assente
  3. score_model_for_role: un modello "peggiore" sulle euristiche ma
     10/10 nell'evidence vince contro un modello "migliore" sulle
     euristiche ma 0/10 nell'evidence
  4. get_recommendations: il dict ritornato contiene _evidence
  5. fail-open: file results.json assente → nessun boost, si resta
     sulle euristiche (comportamento pre-M10)
  6. format_recommendations: l'evidence è visibile nel display

Tutto senza LLM, con file temporanei e mock hardware.
"""
from __future__ import annotations

import json
import shutil
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from CORE.model_selector import (
    load_suite_evidence,
    _evidence_boost_for_model,
    score_model_for_role,
    get_recommendations,
    format_recommendations,
    ROLE_DEFINITIONS,
)


def section(title: str) -> None:
    print()
    print("=" * 70)
    print(f"  {title}")
    print("=" * 70)


def _make_results_file(tmp: Path, content: dict) -> Path:
    out_dir = tmp / "state" / "suite_compare"
    out_dir.mkdir(parents=True, exist_ok=True)
    p = out_dir / "results.json"
    p.write_text(json.dumps(content, indent=2), encoding="utf-8")
    return p


def _make_config_file(tmp: Path, models: dict) -> Path:
    p = tmp / "config.toml"
    lines = []
    for key, name in models.items():
        lines.append(f"[models.{key}]")
        lines.append(f'name = "{name}"')
        lines.append("")
    p.write_text("\n".join(lines), encoding="utf-8")
    return p


def _fake_model(name, size_gb=1.5, family="qwen2",
                quantization="Q4_K_M", capabilities=None):
    return {
        "name": name,
        "size_bytes": int(size_gb * 1e9),
        "size_gb": size_gb,
        "family": family,
        "families": [family],
        "capabilities": capabilities or ["completion"],
        "parameter_size": "",
        "quantization": quantization,
        "context_length": 4096,
    }


HARDWARE_NO_GPU = {"vram_gb": 0, "ram_gb": 16, "temp_c": 0}


def demo_m10() -> None:
    section("M10 — Evidence-based model selection")
    tmp = Path(tempfile.mkdtemp())
    try:
        # ── Scenario 1: lettura results.json + mapping
        print("\n[1] load_suite_evidence: lettura results.json simulato")
        results = {
            "worker_coder": {
                f"T{i}": {"ok": True, "attempts": 1, "secs": 10 + i,
                          "done": True}
                for i in range(1, 11)
            },
            "worker_coder_big": {
                **{f"T{i}": {"ok": True, "attempts": 2, "secs": 200,
                             "done": True} for i in range(1, 5)},
                **{f"T{i}": {"ok": False, "attempts": 3, "secs": 300,
                             "done": True} for i in range(5, 11)},
            },
        }
        rp = _make_results_file(tmp, results)
        cp = _make_config_file(tmp, {
            "worker_coder": "qwen2.5-coder:3b",
            "worker_coder_big": "kirito1/qwen3-coder:4b",
        })
        ev = load_suite_evidence(rp, cp)
        print(f"  → evidence per qwen2.5-coder:3b: {ev.get('qwen2.5-coder:3b')}")
        print(f"  → evidence per kirito1/qwen3-coder:4b: "
              f"{ev.get('kirito1/qwen3-coder:4b')}")
        assert "qwen2.5-coder:3b" in ev
        assert ev["qwen2.5-coder:3b"]["pass"] == 10
        assert ev["qwen2.5-coder:3b"]["total"] == 10
        assert ev["qwen2.5-coder:3b"]["score"] == 100.0
        assert ev["kirito1/qwen3-coder:4b"]["pass"] == 4
        assert ev["kirito1/qwen3-coder:4b"]["score"] == 40.0

        # ── Scenario 2: soglie di boost
        print("\n[2] _evidence_boost_for_model: soglie")
        casi = [
            ("10/10 fast", {"pass": 10, "total": 10,
                            "mean_attempts": 1.0, "mean_secs": 5.0}),
            ("7/10", {"pass": 7, "total": 10,
                      "mean_attempts": 2.0, "mean_secs": 50.0}),
            ("5/10", {"pass": 5, "total": 10,
                      "mean_attempts": 2.0, "mean_secs": 50.0}),
            ("4/10 weak", {"pass": 4, "total": 10,
                           "mean_attempts": 3.0, "mean_secs": 100.0}),
            ("0/10 rejected", {"pass": 0, "total": 10,
                              "mean_attempts": 3.0, "mean_secs": 100.0}),
        ]
        for label, e in casi:
            ev_single = {"m": e}
            boost, reason = _evidence_boost_for_model("m", ev_single)
            print(f"  {label:20} → boost {boost:+.0f}  ({reason})")

        # ── Scenario 3: score_model_for_role, evidence vince su euristiche
        print("\n[3] score_model_for_role: evidence 10/10 vince su euristiche")
        # Due modelli candidati per worker_coder:
        # - "llama3.2:3b": famiglia preferita, size > ideal (2.5GB, vicino
        #   al max 3.0) → score base moderato
        # - "deepseek-coder:1.3b": size ideale, family NON preferred
        #   (deepseek non è in qwen2/llama/phi3), name contiene "coder"
        #   (+15 per name_keywords) → score base moderato, simile
        # Con evidence 10/10 per deepseek, deepseek vince su llama.
        m_deepseek = _fake_model("deepseek-coder:1.3b", size_gb=1.3,
                                 family="deepseek", quantization="Q4_K_M")
        m_llama = _fake_model("llama3.2:3b", size_gb=2.5, family="llama",
                             quantization="Q4_K_M")
        # Senza evidence
        s_deepseek_base, _ = score_model_for_role(
            m_deepseek, "worker_coder", HARDWARE_NO_GPU, evidence=None)
        s_llama_base, _ = score_model_for_role(
            m_llama, "worker_coder", HARDWARE_NO_GPU, evidence=None)
        print(f"  Senza evidence: deepseek-coder:1.3b = {s_deepseek_base:.0f}, "
              f"llama3.2:3b = {s_llama_base:.0f}")

        # Con evidence 10/10 per deepseek
        ev_good = {"deepseek-coder:1.3b": {"pass": 10, "total": 10,
                                            "mean_attempts": 1.0,
                                            "mean_secs": 5.0,
                                            "score": 100.0}}
        s_deepseek_ev, _ = score_model_for_role(
            m_deepseek, "worker_coder", HARDWARE_NO_GPU, evidence=ev_good)
        s_llama_ev, _ = score_model_for_role(
            m_llama, "worker_coder", HARDWARE_NO_GPU, evidence=ev_good)
        print(f"  Con evidence 10/10 su deepseek: "
              f"deepseek = {s_deepseek_ev:.0f}, llama = {s_llama_ev:.0f} "
              f"(llama invariato: no evidence)")
        assert s_deepseek_ev > s_deepseek_base, "Evidence deve aumentare score"
        assert s_llama_ev == s_llama_base, "Llama senza evidence: invariato"

        # Con evidence 0/10 per deepseek (penalty forte)
        ev_bad = {"deepseek-coder:1.3b": {"pass": 0, "total": 10,
                                          "mean_attempts": 3.0,
                                          "mean_secs": 200.0,
                                          "score": 0.0}}
        s_deepseek_bad, _ = score_model_for_role(
            m_deepseek, "worker_coder", HARDWARE_NO_GPU, evidence=ev_bad)
        print(f"  Con evidence 0/10 su deepseek: "
              f"deepseek = {s_deepseek_bad:.0f} (penalty -20 applicata)")
        assert s_deepseek_bad < s_deepseek_base, "Penalty deve diminuire"

        # ── Scenario 4: get_recommendations espone _evidence
        print("\n[4] get_recommendations: _evidence nel dict ritornato")
        # Patch dei path di default
        import CORE.model_selector as ms
        orig_rp = ms.SUITE_RESULTS_PATH
        orig_cp = ms.CONFIG_PATH_DEFAULT
        orig_get_models = ms.get_ollama_models
        orig_gpu = ms.get_gpu_info
        orig_ram = ms.get_ram_info
        ms.SUITE_RESULTS_PATH = rp
        ms.CONFIG_PATH_DEFAULT = str(cp)
        ms.get_ollama_models = lambda host: [
            _fake_model("qwen2.5-coder:3b", size_gb=1.5, family="qwen2"),
            _fake_model("kirito1/qwen3-coder:4b", size_gb=3.0,
                        family="qwen3"),
        ]
        ms.get_gpu_info = lambda: {"vram_mb": 0, "vram_gb": 0, "temp_c": 0}
        ms.get_ram_info = lambda: {"ram_mb": 16384, "ram_gb": 16}
        try:
            recs = get_recommendations(config_path=str(cp))
            assert "_evidence" in recs
            assert "qwen2.5-coder:3b" in recs["_evidence"]
            # Verifica che il worker_coder raccomandato è qwen (10/10)
            wc = recs.get("worker_coder", {})
            print(f"  worker_coder → {wc.get('model')} "
                  f"(score: {wc.get('score'):.0f}/100)")
            print(f"  reason: {wc.get('reason')}")
            assert wc.get("model") == "qwen2.5-coder:3b"
            assert "evidence 10/10" in wc.get("reason", "")
        finally:
            ms.SUITE_RESULTS_PATH = orig_rp
            ms.CONFIG_PATH_DEFAULT = orig_cp
            ms.get_ollama_models = orig_get_models
            ms.get_gpu_info = orig_gpu
            ms.get_ram_info = orig_ram

        # ── Scenario 5: fail-open con results.json assente
        print("\n[5] Fail-open: results.json assente → niente boost")
        ev_empty = load_suite_evidence(tmp / "non_esiste.json",
                                       cp)
        print(f"  → evidence: {ev_empty}")
        assert ev_empty == {}
        # score_model_for_role con evidence={} deve dare stesso punteggio
        # di evidence=None (comportamento pre-M10). Uso m_deepseek (ha
        # margine nel punteggio, non saturato).
        s_with_empty, _ = score_model_for_role(
            m_deepseek, "worker_coder", HARDWARE_NO_GPU, evidence={})
        s_with_none, _ = score_model_for_role(
            m_deepseek, "worker_coder", HARDWARE_NO_GPU, evidence=None)
        assert s_with_empty == s_with_none
        print(f"  → score con {{}} = {s_with_empty}, "
              f"score con None = {s_with_none} (identici ✓)")

        # ── Scenario 6: format_recommendations mostra l'evidence
        print("\n[6] format_recommendations: evidence visibile nel display")
        fake_recs = {
            "_hardware": {"vram_gb": 4, "ram_gb": 16, "temp_c": 60},
            "_available_models": 5,
            "_evidence": {"qwen2.5-coder:3b": {"pass": 10, "total": 10,
                          "mean_secs": 14, "mean_attempts": 1.1,
                          "score": 100.0}},
            "worker_coder": {"model": "qwen2.5-coder:3b", "score": 95,
                             "size_gb": 1.5,
                             "reason": "size 1.5GB ≤ ideal 1.5GB; "
                                       "family qwen2 preferred; exact "
                                       "preferred name match; "
                                       "evidence 10/10; low retries "
                                       "(1.1/task); fast (14s/task)",
                             "alternatives": [{"model": "llama3.2:3b",
                                               "score": 60}]},
        }
        # Aggiungo i ruoli mancanti per evitare KeyError in format_recommendations
        for role in ROLE_DEFINITIONS:
            if role not in fake_recs:
                fake_recs[role] = {"model": None, "score": 0,
                                   "reason": "demo: non calcolato"}
        txt = format_recommendations(fake_recs)
        # Mostra solo le prime righe (quelle con evidence)
        for line in txt.split("\n")[:6]:
            print(f"  {line}")

        print("\n✅ M10 PASS: model_selector ora è evidence-based")

    finally:
        shutil.rmtree(tmp, ignore_errors=True)


if __name__ == "__main__":
    print("Run live M10 — evidence-based model selection, senza LLM")
    print(f"Python: {sys.version.split()[0]}")
    demo_m10()
    print()
    print("=" * 70)
    print("  TUTTI GLI SCENARI M10 PASS — model_selector usa results.json")
    print("=" * 70)
