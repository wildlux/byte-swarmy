"""test_llm_tuner_wiring.py — Verifica che il tuner sia collegato al ModelClient.

Regressione per l'integrazione di TimestralLLMTuner (prima era un attributo
sempre None, quindi il tuning termico dei parametri LLM era disattivato).
"""
from __future__ import annotations

import logging
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from CORE.ollama_client import ModelClient


def _make_client():
    cfg = {
        "ollama": {"host": "http://localhost:11434", "request_timeout": 30,
                   "first_token_timeout": 60},
        "models": {"worker_coder": {"name": "qwen", "temperature": 0.5,
                                    "num_ctx": 4096, "num_predict": 256}},
    }
    return ModelClient(cfg, logging.getLogger("test"))


def test_tuner_none_usa_config_statica():
    mc = _make_client()
    assert mc.llm_tuner is None
    opts = mc._get_tuned_options("worker_coder", mc.models_cfg["worker_coder"], None)
    assert opts["temperature"] == 0.5  # valore statico, non tuned


def test_tuner_presente_applica_valori_tuned():
    mc = _make_client()

    class FakeTuner:
        def get_params(self, model_key):
            return {"temperature": 0.05, "top_p": 0.7, "top_k": 20,
                    "num_ctx": 1536, "repeat_penalty": 1.35,
                    "repeat_last_n": 128, "num_predict": 200}

    mc.llm_tuner = FakeTuner()
    opts = mc._get_tuned_options("worker_coder", mc.models_cfg["worker_coder"], None)
    assert opts["temperature"] == 0.05
    assert opts["num_ctx"] == 1536
    assert opts["num_predict"] == 200


def test_max_tokens_esplicito_non_sovrascritto_dal_tuner():
    mc = _make_client()

    class FakeTuner:
        def get_params(self, model_key):
            return {"temperature": 0.05, "top_p": 0.7, "top_k": 20,
                    "num_ctx": 1536, "repeat_penalty": 1.35,
                    "repeat_last_n": 128, "num_predict": 200}

    mc.llm_tuner = FakeTuner()
    opts = mc._get_tuned_options("worker_coder", mc.models_cfg["worker_coder"], 999)
    assert opts["num_predict"] == 999  # max_tokens esplicito ha priorità
    assert opts["temperature"] == 0.05
