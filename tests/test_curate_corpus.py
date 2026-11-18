"""Test Fase B — strumenti di curazione del corpus (tools/curate_corpus).

Zero LLM, stato temporaneo. Copre: curate (dedup + filtro done),
collect_task via file jsonl per task.
"""

import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from tools import curate_corpus as cc  # noqa: E402
from CORE import feedback_corpus as fc  # noqa: E402


def _t(task_id, verdict="done", output="x = 1\n", **kw):
    return fc.Triple(
        task_id=task_id, kind=kw.get("kind", "code"), title=task_id,
        description="d", refs=tuple(kw.get("refs") or ()),
        output=output, verdict=verdict, first_try=True, attempts=1,
        model="qwen2.5-coder:3b", reason="", ts=1.0)


class TestCurateCorpus(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="bswarm-curate-"))

    def tearDown(self):
        import shutil
        shutil.rmtree(self.tmp, ignore_errors=True)

    def _seed(self, task_id: str, triples):
        p = fc.task_path(task_id, state_dir=self.tmp)
        p.parent.mkdir(parents=True, exist_ok=True)
        with p.open("w", encoding="utf-8") as f:
            for t in triples:
                f.write(json.dumps(t.to_dict()) + "\n")

    def test_curate_filtro_done_e_dedup(self):
        kept = cc.curate([
            _t("task-1", verdict="done", output="def a():\n    return 1\n"),
            _t("task-1", verdict="done", output="def a():\n    return 1\n"),  # dup
            _t("task-2", verdict="corrected", output="def b():\n    return 2\n"),
        ])
        self.assertEqual(len(kept), 1)
        self.assertEqual(kept[0].task_id, "task-1")

    def test_curate_senza_filtro(self):
        kept = cc.curate([
            _t("task-1", verdict="done"),
            _t("task-2", verdict="corrected"),
        ], only_done=False)
        self.assertEqual(len(kept), 2)

    def test_collect_task_via_file(self):
        self._seed("task-9", [_t("task-9", verdict="done", output="x = 1\n")])
        samples = cc.collect_task("task-9", state_dir=self.tmp)
        self.assertEqual(len(samples), 1)
        self.assertEqual(samples[0].output, "x = 1\n")


if __name__ == "__main__":
    unittest.main()
