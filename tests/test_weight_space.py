"""Test per lo scaricamento pesi HF e l'harness weight-space (estremamente beta).

Tutti offline: nessuna chiamata di rete, nessuna ollama reale, nessuna
esecuzione di codice generato.
"""
import pytest
from pathlib import Path

from CORE import hf_weights as hw


class TestParseHfLink:
    def test_pagina_modello(self):
        info = hw.parse_hf_link("https://huggingface.co/RikiyaT/Qwen3.5-0.8B-weight-space-programming")
        assert info["repo_id"] == "RikiyaT/Qwen3.5-0.8B-weight-space-programming"
        assert info["revision"] == "main"
        assert info["filename"] == ""

    def test_blob_file(self):
        info = hw.parse_hf_link(
            "https://huggingface.co/OWNER/REPO/blob/main/model-q4_0.gguf")
        assert info["filename"] == "model-q4_0.gguf"
        assert info["revision"] == "main"

    def test_resolve_con_query(self):
        info = hw.parse_hf_link(
            "https://huggingface.co/OWNER/REPO/resolve/main/a.gguf?download=true")
        assert info["filename"] == "a.gguf"

    def test_id_corto(self):
        info = hw.parse_hf_link("OWNER/REPO")
        assert info["repo_id"] == "OWNER/REPO"

    def test_link_invalido(self):
        with pytest.raises(ValueError):
            hw.parse_hf_link("https://github.com/x/y")
        with pytest.raises(ValueError):
            hw.parse_hf_link("")
        with pytest.raises(ValueError):
            hw.parse_hf_link("https://huggingface.co/solounocazzo")


class TestPickGguf:
    files = [
        {"path": "model.safetensors", "size": 5_000_000_000},
        {"path": "README.md", "size": 1024},
        {"path": "model.Q8_0.gguf", "size": 900_000_000},
        {"path": "model.Q4_K_M.gguf", "size": 450_000_000},
        {"path": "model.Q4_K_S.gguf", "size": 420_000_000},
    ]

    def test_preferisce_q4(self):
        assert hw.pick_gguf(self.files)["path"] == "model.Q4_K_M.gguf"

    def test_budget_ram(self):
        # se il file Q4 supera il budget, si passa al successivo ranked
        big = [f for f in self.files if f["path"] != "model.Q8_0.gguf"]
        chosen = hw.pick_gguf(big, max_gb=0.1)
        assert chosen["path"].endswith(".gguf")

    def test_nessun_gguf(self):
        assert hw.pick_gguf([{"path": "model.safetensors", "size": 1}]) is None


class TestSanitizeAndRegistry:
    def test_nome_modello_ollama(self):
        name = hw.sanitized_model_name("RikiyaT/Qwen3.5-0.8B-weight-space-programming",
                                       "model.Q4_K_M.gguf")
        assert name == "hfw_qwen3.5-0.8b-weight-space-programming"
        assert all(c.islower() or c.isdigit() or c in "._-" for c in name)

    def test_human_size(self):
        assert hw.human_size(450_000_000).endswith("MB")
        assert hw.human_size(0) == "0.0 B"


class TestRepetitionMetrics:
    from CORE import weight_space_harness as h

    def test_output_in_loop(self):
        malato = "\n".join(["i = 0"] + ['        print("ciao")'] * 14)
        m = self.h.repetition_metrics(malato)
        assert m["loops_like"] is True
        assert m["duplicate_line_ratio"] > 0.5
        assert 0 <= m["tail_selfsimilarity"] <= 1

    def test_output_normale(self):
        pulito = "\n".join(f"print({i} * {i + 1})" for i in range(12))
        m = self.h.repetition_metrics(pulito)
        assert m["loops_like"] is False

    def test_output_corti_senza_falsi_loop(self):
        assert self.h.repetition_metrics("print(1)")["loops_like"] is False


class TestHarnessChecks:
    from CORE import weight_space_harness as h

    def test_expected_number(self):
        assert self.h._expected_number("RISULTATO: 5050", 5050)
        assert not self.h._expected_number("RISULTATO: 5049", 5050)
        assert self.h._expected_number("RISULTATO: 5050\nRISULTATO: 5051", 5051)

    def test_fizzbuzz_check(self):
        prob = self.h.PROBLEMS[1]
        out = "\n".join(["1", "Fizz", "Buzz", "Fizz", "5", "FizzBuzz", "7", "8"])
        assert prob["check"](out) is True
        assert prob["check"]("Fizz solo") is False

    def test_fix_infinite_loop_check(self):
        prob = self.h.PROBLEMS[4]
        ok = prob["check"](
            "    i = 0\n    while i < 10:\n        print(i)\n        i += 1")
        bad = prob["check"]("    while i < 10:\n        print(i)")
        assert ok is True and bad is False

    def test_run_harness_con_fake(self, tmp_path):
        """End-to-end offline: generate_fn finti, senza ollama né codice eseguito."""
        self.h.REPORT_DIR = tmp_path

        def fake(prompt):
            if "1 a 100" in prompt:
                return "for i in ... \nRISULTATO: 5050"
            return "\n".join(["linea unica"] * 25)  # simula loop

        report = self.h.run_harness("fake:1b", generate_fn=fake)
        assert report["total"] == len(self.h.PROBLEMS)
        assert report["passed"] >= 1
        assert report["loops_detected"] is True
        assert report["score"] <= 1.0
        assert Path(report["saved_to"]).exists()

    def test_format_report(self, tmp_path):
        self.h.REPORT_DIR = tmp_path
        report = self.h.run_harness("demo", generate_fn=lambda p: "RISULTATO: 5050")
        txt = self.h.format_report(report)
        assert "MODELLO:" in txt and "VERDETTO:" in txt
