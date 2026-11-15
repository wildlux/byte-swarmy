"""Test Cycle 47 — furbate A/B/C/F (warmup/keep_alive, sticky scheduling,
audit gate deterministico, watchdog primo token).

Unit test senza rete né Ollama: usano config fake, SQLite temporanea e
file temporanei. I percorsi live (boot reale) sono coperti dal boot smoke.
"""
import time
import tomllib
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent


def _make_client(tmp_path, hardware=None, ollama_extra=None):
    """ModelClient con config minima (nessuna rete: solo parsing config)."""
    from CORE.ollama_client import ModelClient

    cfg = {
        "ollama": {
            "host": "http://localhost:11434",
            "request_timeout": 300,
        },
        "models": {},
    }
    if ollama_extra:
        cfg["ollama"].update(ollama_extra)
    if hardware is not None:
        cfg["hardware"] = hardware
    log = type("L", (), {"info": staticmethod(print),
                         "warning": staticmethod(print),
                         "error": staticmethod(print),
                         "debug": staticmethod(lambda *a, **k: None)})()
    return ModelClient(cfg, log)


class TestKeepAliveExplicit:
    """A: [hardware].keep_alive_sec esplicito rispettato, auto = None."""

    def test_auto_non_manda_keep_alive(self, tmp_path):
        c = _make_client(tmp_path)
        assert c._explicit_keep_alive() is None

    def test_esplicito_ritorna_int(self, tmp_path):
        c = _make_client(tmp_path, hardware={"keep_alive_sec": 600})
        assert c._explicit_keep_alive() == 600

    def test_zero_esplicito_e_zero(self, tmp_path):
        # 0 esplicito = scarica subito (vincolo utente, va rispettato)
        c = _make_client(tmp_path, hardware={"keep_alive_sec": 0})
        assert c._explicit_keep_alive() == 0

    def test_valore_non_valido_auto(self, tmp_path):
        c = _make_client(tmp_path, hardware={"keep_alive_sec": "venti"})
        assert c._explicit_keep_alive() is None


class TestFirstTokenWatchdogConfig:
    """F: parsing [ollama].first_token_timeout + errore tipizzato."""

    def test_default_60(self, tmp_path):
        c = _make_client(tmp_path)
        assert c.first_token_timeout == 60.0

    def test_override_config(self, tmp_path):
        c = _make_client(tmp_path, ollama_extra={"first_token_timeout": 25})
        assert c.first_token_timeout == 25.0

    def test_zero_disattiva(self, tmp_path):
        c = _make_client(tmp_path, ollama_extra={"first_token_timeout": 0})
        assert c.first_token_timeout == 0.0

    def test_primo_token_timeout_importabile(self):
        from CORE.ollama_client import FirstTokenTimeout
        assert issubclass(FirstTokenTimeout, RuntimeError)

    def test_config_reale_ha_il_watchdog(self):
        cfg = tomllib.loads((ROOT / "CONFIG" / "config.toml").read_text())
        assert cfg["ollama"]["first_token_timeout"] == 60


class TestStickyScheduling:
    """B: peek_pending (lettura) + claim_by_id (claim atomico specifico)."""

    def _queue(self, tmp_path):
        from CORE.task_queue import TaskQueue
        log = type("L", (), {"info": staticmethod(print),
                             "warning": staticmethod(print),
                             "error": staticmethod(print),
                             "debug": staticmethod(lambda *a, **k: None)})()
        return TaskQueue(tmp_path / "tasks", log)

    def _add(self, q, title):
        return q.add({"title": title, "description": title,
                      "status": "pending"})

    def test_peek_non_claima(self, tmp_path):
        q = self._queue(tmp_path)
        t1 = self._add(q, "primo")
        self._add(q, "secondo")
        peeked = q.peek_pending(limit=8)
        assert [p["id"] for p in peeked][0] == t1
        # peek non deve alterare lo stato: next_pending deve trovare t1
        got = q.next_pending()
        assert got["id"] == t1

    def test_peek_rispetta_retry_after(self, tmp_path):
        q = self._queue(tmp_path)
        tid = self._add(q, "in cooldown")
        # metto retry_after nel futuro: peek non deve mostrarlo
        q.update_task(tid, retry_after=time.time() + 999)
        assert q.peek_pending() == []

    def test_claim_by_id_prende_quello_giusto(self, tmp_path):
        q = self._queue(tmp_path)
        t1 = self._add(q, "primo")
        t2 = self._add(q, "secondo")
        got = q.claim_by_id(t2)
        assert got is not None and got["id"] == t2
        assert got["status"] == "running"
        # t1 resta pendente
        rest = q.peek_pending()
        assert [p["id"] for p in rest] == [t1]

    def test_claim_by_id_contesa_persa(self, tmp_path):
        q = self._queue(tmp_path)
        tid = self._add(q, "solo")
        first = q.claim_by_id(tid)
        assert first is not None
        # secondo claimatore: None (nessun doppio claim)
        assert q.claim_by_id(tid) is None

    def test_claim_by_id_stato_inesistente(self, tmp_path):
        q = self._queue(tmp_path)
        tid = self._add(q, "x")
        q.mark_done(tid, "fatto")
        assert q.claim_by_id(tid) is None


class _Noop:
    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


def _noop():
    return _Noop()


class TestDeterministicAuditGate:
    """C: AST-check sui file scritti prima dell'audit LLM."""

    def _auditor(self, gate=True):
        from CORE.auditor import AuditWorker
        log = type("L", (), {"info": staticmethod(print),
                             "warning": staticmethod(print),
                             "error": staticmethod(print),
                             "debug": staticmethod(lambda *a, **k: None)})()
        a = AuditWorker(None, log, config={"audit": {"deterministic_gate": gate}})
        return a

    def test_flag_da_config(self):
        assert self._auditor(True).deterministic_gate is True
        a = self._auditor(False)
        assert a.deterministic_gate is False
        # default: senza chiave = OFF (comportamento invariato)
        from CORE.auditor import AuditWorker
        log = type("L", (), {"info": staticmethod(print),
                             "warning": staticmethod(print),
                             "error": staticmethod(print),
                             "debug": staticmethod(lambda *a, **k: None)})()
        assert AuditWorker(None, log).deterministic_gate is False

    def test_py_valido_approve(self, tmp_path):
        started = time.time()
        time.sleep(0.02)
        (tmp_path / "main.py").write_text("x = 1\n", encoding="utf-8")
        det = self._auditor()._deterministic_check(str(tmp_path), started)
        assert det is not None and det["decision"] == "APPROVE"

    def test_syntaxerror_reject_con_riga(self, tmp_path):
        started = time.time()
        time.sleep(0.02)
        (tmp_path / "rotto.py").write_text("def f(:\n  pass\n", encoding="utf-8")
        det = self._auditor()._deterministic_check(str(tmp_path), started)
        assert det["decision"] == "REJECT"
        assert "riga 1" in det["feedback"]

    def test_nessun_file_nessuna_decisione(self, tmp_path):
        started = time.time()
        time.sleep(0.02)
        det = self._auditor()._deterministic_check(str(tmp_path), started)
        assert det is None  # → prosegue con audit LLM come prima

    def test_file_vecchi_ignorati(self, tmp_path):
        vecchio = tmp_path / "vecchio.py"
        vecchio.write_text("x = 1\n", encoding="utf-8")
        import os
        two_days_ago = time.time() - 172800
        os.utime(vecchio, (two_days_ago, two_days_ago))
        det = self._auditor()._deterministic_check(str(tmp_path), time.time() - 60)
        assert det is None

    def test_skip_state_dir(self, tmp_path):
        started = time.time()
        time.sleep(0.02)
        st = tmp_path / "state"
        st.mkdir()
        (st / "streaming.txt").write_text("tok", encoding="utf-8")
        det = self._auditor()._deterministic_check(str(tmp_path), started)
        assert det is None

    def test_started_at_none_gate_off(self, tmp_path):
        (tmp_path / "a.py").write_text("x = 1\n", encoding="utf-8")
        det = self._auditor()._deterministic_check(str(tmp_path), None)
        assert det is None

    def test_config_reale_gate_on(self):
        cfg = tomllib.loads((ROOT / "CONFIG" / "config.toml").read_text())
        assert cfg["audit"]["deterministic_gate"] is True


class TestWarmupConfig:
    """A: warmup_model nel config reale + warmup() valida la chiave."""

    def test_config_reale_warmup_model(self):
        cfg = tomllib.loads((ROOT / "CONFIG" / "config.toml").read_text())
        assert cfg["hardware"]["warmup_model"] == "worker_coder"

    def test_warmup_chiave_sconosciuta(self, tmp_path):
        c = _make_client(tmp_path)
        with pytest.raises(KeyError):
            c.warmup("modello_che_non_esiste")

    def test_config_reale_sticky_on(self):
        cfg = tomllib.loads((ROOT / "CONFIG" / "config.toml").read_text())
        assert cfg["orchestrator"]["sticky_models"] is True


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-q"]))
