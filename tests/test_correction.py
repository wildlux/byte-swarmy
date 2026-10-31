"""Test Task 2 — Post-execution feedback loop (retry con prompt corretto).

DoD: il prompt di correzione viene costruito (path anonimizzati, errore
limitato), il task va in 'pending' fino a 3 retry e al 4° fallimento
diventa 'failed_definitively' senza loop infiniti.
"""
import logging
import tempfile
import unittest
from pathlib import Path

from CORE.correction import (
    build_correction_prompt,
    limit_error,
    sanitize_paths,
)
from CORE.orchestrator import TaskQueue


class CorrectionPromptTests(unittest.TestCase):
    def test_sanitize_paths(self):
        s = sanitize_paths("errore in /home/wildlux/Desktop/byte-swarmy/project/x.c")
        self.assertNotIn("/home/wildlux", s)
        self.assertIn("[PATH]/Desktop/byte-swarmy/project/x.c", s)

    def test_limit_error_frames_and_chars(self):
        many_frames = "\n".join(f"frame {i}" for i in range(50))
        out = limit_error(many_frames)
        self.assertLessEqual(out.count("\n"), 4)        # 5 max frame
        self.assertLessEqual(len(out), 500)

    def test_prompt_is_directive_and_sectioned(self):
        p = build_correction_prompt("hello task",
                                    "int main(){retunr 0;}",
                                    "error: expected ';'")
        self.assertTrue(p.startswith("Correggi il seguente errore"))
        self.assertIn("## TASK ORIGINALE", p)
        self.assertIn("## ERRORE", p)
        self.assertIn("## CODICE PRECEDENTE", p)

    def test_no_absolute_paths_in_prompt(self):
        stderr = ('Traceback (most recent call last):\n'
                  '  File "/home/wildlux/temp/app.py", line 1, in <module>\n'
                  '    import lib\n'
                  'NameError: no module')
        p = build_correction_prompt("t", "c", stderr)
        self.assertNotIn("/home/wildlux", p)


class RetryLoopTests(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="bswarm-t2-"))
        self.queue = TaskQueue(self.tmp, logging.getLogger("t"))

    def _add(self) -> str:
        return self.queue.add({
            "title": "hello",
            "description": "compila hello.c",
            "type": "execute",
        })

    def test_three_retries_then_pending(self):
        tid = self._add()
        for attempt in range(1, 4):
            status = self.queue.fail_with_correction(
                tid, "ERROR: errore di sintassi",
                f"Correggi il seguente errore #{attempt}",
            )
            self.assertEqual(status, "pending")

        # il prompt e' stato sovrascritto con l'ultimo correzione
        with self.queue._get_conn() as conn:
            conn.row_factory = None
            row = conn.execute(
                "SELECT description, attempts, status FROM tasks WHERE id = ?",
                (tid,),
            ).fetchone()
        self.assertIn("errore #3", str(row[0]))
        self.assertEqual(row[1], 3)
        self.assertEqual(row[2], "pending")

        # il task viene ripescato dal loop
        t = self.queue.next_pending()
        self.assertIsNotNone(t)
        self.assertIn("errore #3", t["description"])

    def test_fourth_failure_marks_definitive(self):
        tid = self._add()
        for _ in range(3):
            self.queue.fail_with_correction(tid, "e", "c")
        status = self.queue.fail_with_correction(tid, "e4", "c4")
        self.assertEqual(status, TaskQueue.STATUS_FINAL)

        with self.queue._get_conn() as conn:
            row = conn.execute(
                "SELECT status, attempts, last_error FROM tasks WHERE id = ?",
                (tid,),
            ).fetchone()
        self.assertEqual(row[0], "failed_definitively")
        self.assertEqual(row[1], 4)
        self.assertIn("e4", row[2])

        # non ripesca piu' nulla di definitivo: loop terminato
        self.assertIsNone(self.queue.next_pending())   # solo questo task
        # NB: next_pending viene applicato a 'pending'/'retry' non definitivi

    def test_status_setter(self):
        tid = self._add()
        self.queue.set_status(tid, "thermal_paused")
        with self.queue._get_conn() as conn:
            row = conn.execute(
                "SELECT status FROM tasks WHERE id = ?", (tid,)
            ).fetchone()
        self.assertEqual(row[0], "thermal_paused")


if __name__ == "__main__":
    unittest.main()
