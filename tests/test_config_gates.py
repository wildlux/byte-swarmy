"""test_config_gates.py — lock offline dei vincoli di configurazione documentati.

Verifica che la config COMMITTATA rispetti le regole operative: corsia veloce
OFF, best-of-N neutrale, gate termico attivo, num_ctx allineati, remote senza
token, credenziali non tracciate e permessi 0600. Nessun LLM, rete o scrittura.
"""
from __future__ import annotations

import stat
import subprocess
import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CONFIG = ROOT / "CONFIG" / "config.toml"


def _cfg() -> dict:
    return tomllib.loads(CONFIG.read_text(encoding="utf-8"))


def _git(*args: str) -> str:
    return subprocess.run(
        ["git", *args], cwd=ROOT, check=True, capture_output=True,
        text=True).stdout.strip()


def test_fast_lane_resta_disattivata():
    assert _cfg()["fast_lane"]["enabled"] is False


def test_best_of_n_neutrale():
    assert _cfg()["orchestrator"]["best_of_n"] == 1


def test_gate_termico_attivo_e_num_ctx_allineati():
    cfg = _cfg()
    assert cfg["thermal"]["enabled"] is True
    planner = cfg["models"]["planner"]["num_ctx"]
    orchestrator = cfg["models"]["orchestrator"]["num_ctx"]
    assert planner == orchestrator == 2048


def test_remote_github_senza_token():
    url = _git("remote", "get-url", "origin")
    assert url.startswith("git@github.com:")
    for marker in ("https://", "ghp_", "github_pat_", "x-access-token"):
        assert marker not in url
    assert url.endswith("wildlux/byte-swarmy.git")


def test_credenziali_non_tracciate_e_permessi_stretti():
    tracked = _git("ls-files").splitlines()
    for name in tracked:
        assert not name.endswith("cloud_api.json"), name
        assert not name.endswith(".git-credentials"), name
    for rel in ("state/cloud_api.json", "data/state/cloud_api.json"):
        path = ROOT / rel
        if path.is_file():
            assert stat.S_IMODE(path.stat().st_mode) == 0o600, rel


def test_config_senza_segreti_in_chiaro():
    text = CONFIG.read_text(encoding="utf-8")
    for marker in ("ghp_", "github_pat_", "sk-", "-----BEGIN", "password ="):
        assert marker not in text
