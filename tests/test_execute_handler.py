"""Test deterministic per CORE/execute_handler.py (no LLM, no I/O reale)."""
import unittest

from CORE.execute_handler import handle_execute_task, parse_execute_commands


class ParseTests(unittest.TestCase):
    def test_gcc_compile_and_run(self):
        desc = ("Crea project/hello.c. Compila con gcc project/hello.c -o "
                "project/hello e verifica l'output.")
        steps = parse_execute_commands(desc)
        self.assertEqual(len(steps), 2)
        self.assertEqual(steps[0]["kind"], "compile")
        self.assertEqual(steps[0]["cmd"], "gcc project/hello.c -o project/hello")
        self.assertEqual(steps[1]["kind"], "run")
        self.assertEqual(steps[1]["cmd"], "project/hello")

    def test_python_script(self):
        steps = parse_execute_commands("esegui python3 project/main.py e stampa")
        self.assertEqual(len(steps), 1)
        self.assertEqual(steps[0]["kind"], "run")
        self.assertEqual(steps[0]["cmd"], "python3 project/main.py")

    def test_cpp(self):
        steps = parse_execute_commands("g++ project/main.cpp -o project/app")
        self.assertEqual(steps[0]["cmd"], "g++ project/main.cpp -o project/app")

    def test_compile_comes_first_even_if_written_after(self):
        desc = "esegui project/app. Per il build: gcc project/a.c -o project/app"
        steps = parse_execute_commands(desc)
        self.assertEqual(steps[0]["kind"], "compile")
        self.assertEqual(steps[1]["kind"], "run")

    def test_no_commands_recognized(self):
        self.assertEqual(parse_execute_commands("fai qualcosa di bello"), [])
        self.assertEqual(parse_execute_commands(""), [])
        # esecuzione generica senza .py: non riconosciuta di proposito
        self.assertEqual(parse_execute_commands("python project/nonfile"), [])


class HandleTests(unittest.TestCase):
    def test_success_flow(self):
        outputs = {
            "gcc project/hello.c -o project/hello": "",
            "project/hello": "Hello from BYTE-SWARMY!",
        }

        def fake_run(cmd):
            return outputs[cmd]

        task = {"description": "gcc project/hello.c -o project/hello"}
        result = handle_execute_task(task, fake_run)
        self.assertTrue(result.startswith("execute OK"))
        self.assertIn("compilazione project/hello.c -> project/hello -> OK", result)
        self.assertIn("Hello from BYTE-SWARMY!", result)

    def test_failure_propagates_error(self):
        logs = {
            "gcc project/bad.c -o project/bad": "ERROR: exit 1: undefined reference",
        }
        task = {"description": "gcc project/bad.c -o project/bad ed esegui"}

        def fake_run(cmd):
            return logs.get(cmd, "ok")

        result = handle_execute_task(task, fake_run)
        self.assertTrue(result.startswith("ERROR"))
        self.assertIn("compilazione", result)
        self.assertIn("undefined reference", result)

    def test_no_commands_gives_guidance(self):
        task = {"description": "pretend che sia tutto automatico"}
        result = handle_execute_task(task, lambda cmd: "ok")
        self.assertTrue(result.startswith("ERROR"))
        self.assertIn("gcc project/main.c -o project/main", result)

    def test_output_is_truncated(self):
        task = {"description": "python3 project/big.py"}

        def fake_run(cmd):
            return "x" * 10_000

        result = handle_execute_task(task, fake_run)
        self.assertLessEqual(len(result), len("execute OK\n") + 2 + 2000)


if __name__ == "__main__":
    unittest.main()
