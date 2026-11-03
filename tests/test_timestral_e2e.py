# -*- coding: utf-8 -*-
"""
tests/test_timestral_e2e.py — I6: integrazione end-to-end Timestral.

Tutto REALE tranne i sensori: Orchestrator (via __new__), il vero
`TimestralGatekeeper` con soglie da actors.json-like, il vero
`TaskQueue` su SQLite temporaneo e il vero `_thermal_gate_pass`
(come lo chiama `_tick`).

Flusso verificato:
  task reale nel DB → sample CPU calda (sopra soglia) →
  `_thermal_gate_pass()` False → task `thermal_paused` nel DB →
  sample ancora sopra la soglia di ripresa (isteresi) → pausa resta →
  sample freddo → gate True → task riaccodato `pending`.

Zero token LLM, zero Ollama.
"""

from __future__ import annotations

import json
import logging
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from CORE.orchestrator import Orchestrator, TaskQueue  # noqa: E402
from MONITORING.thermal_manager import TimestralGatekeeper  # noqa: E402

PAUSE_CPU = 50.0      # soglia bassa per scattare subito nei test
RESUME_TEMP = 45.0


def _sample(cpu: float) -> SimpleNamespace:
    """Sample finto (stessa interfaccia di ThermalSample)."""
    return SimpleNamespace(cpu_temp_max=cpu, gpu_temp=0.0,
                           tokens_per_sec=None)


class TestTimestralE2E(unittest.TestCase):
    """I6: il caso reale task-in-coda → pausa termica → ripresa."""

    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="bswarm-timestral-e2e-")
        self.queue = TaskQueue(Path(self.tmp) / "tasks", logging.getLogger("test"))

        orch = Orchestrator.__new__(Orchestrator)
        orch.thermal_gate = TimestralGatekeeper(
            pause_cpu=PAUSE_CPU, resume_temp=RESUME_TEMP)
        orch.timestral = SimpleNamespace(last_sample=None,
                                         get_advice=lambda: None)
        orch.check_only_if_gpu = False
        orch.pause_decision_model_too = False
        orch.queue = self.queue
        orch.log = MagicMock()
        self.orch = orch
        orch._no_gpu_logged = False

    def tearDown(self):
        import shutil
        shutil.rmtree(self.tmp, ignore_errors=True)

    def _add_task(self, title: str) -> str:
        return self.queue.add({
            "title": title, "description": "test",
            "context": json.dumps({"lang": "it"}),  # la coda non serializza
            "type": "generic", "source": "e2e-timestral",
        })

    def _status(self, task_id: str):
        with self.queue._get_conn() as conn:
            row = conn.execute(
                "SELECT status FROM tasks WHERE id = ?", (task_id,)
            ).fetchone()
        return row[0] if row else None

    def test_hot_sample_pauses_tasks_in_db(self):
        """Sample caldo → gate False → task realmente 'thermal_paused'."""
        task_id = self._add_task("task che va in pausa termica")
        self.assertEqual(self._status(task_id), "pending")

        self.orch.timestral.last_sample = _sample(60.0)   # > 50
        self.assertIs(self.orch._thermal_gate_pass(), False)
        self.assertEqual(self._status(task_id), "thermal_paused")

    def test_hysteresis_then_resume_recues_tasks(self):
        """Caldo → pausa; tiepido (sopra resume) → resta in pausa;
        freddo → ripresa e task tornano 'pending'."""
        tid_hot = self._add_task("pausa con temp alta")

        self.orch.timestral.last_sample = _sample(60.0)
        self.orch._thermal_gate_pass()
        self.assertEqual(self._status(tid_hot), "thermal_paused")

        # un task arrivato a coda ferma DURANTE la pausa non viene toccato:
        # resta 'pending' finché la ripresa (o il tick) non lo prende
        tid_cold = self._add_task("task aggiunto durante la pausa")
        self.assertEqual(self._status(tid_cold), "pending")
        # il task aggiunto a coda ferma durante la pausa NON viene toccato
        # (pause_thermal è idempotente e non tocca i task confluentes dopo)
        self.assertEqual(self._status(tid_cold), "pending")

        # isteresi: 47 (sopra la soglia di ripresa 45) → gate ancora False,
        # la pausa resta attiva
        self.orch.timestral.last_sample = _sample(47.0)
        self.assertIs(self.orch._thermal_gate_pass(), False)
        self.assertEqual(self._status(tid_hot), "thermal_paused")

        # freddo: 40 < 45 → gate True → resume riaccoda
        self.orch.timestral.last_sample = _sample(40.0)
        self.assertIs(self.orch._thermal_gate_pass(), True)
        self.assertEqual(self._status(tid_hot), "pending")

    def test_cold_sample_never_pauses(self):
        """Tutto freddo: gate sempre pass, nessun tocco alla coda."""
        task_id = self._add_task("task sereno")
        for cpu in (20.0, 40.0, 44.9):
            self.orch.timestral.last_sample = _sample(cpu)
            self.assertIs(self.orch._thermal_gate_pass(), True)
        self.assertEqual(self._status(task_id), "pending")


if __name__ == "__main__":
    print("Timestral E2E (I6) → CORE/orchestrator.py gate+queue reali")
    print("=" * 60)
    unittest.main(verbosity=2)
