---
id: py-unittest
title: Python unittest test file (single file)
keywords: unittest, test unitari, testcase, asserzioni, verifica automatica, test
---
# Recipe: unittest test file (single file)

STEPS (follow in order):
1. Create project/main.py using the TEMPLATE below.
2. Replace ONLY the {{...}} placeholders. Do NOT add extra features.
3. done=true with a one-line result.

TEMPLATE (keep every line that has no {{...}} exactly as-is):
```python
import unittest


def somma(a, b):
    """Restituisce la somma di due numeri."""
    return a + b


def sottrazione(a, b):
    """Restituisce la differenza tra due numeri."""
    return a - b


def moltiplicazione(a, b):
    """Restituisce il prodotto di due numeri."""
    return a * b


class TestFunzioni(unittest.TestCase):
    def test_somma(self):
        self.assertEqual(somma(2, 3), 5)

    def test_sottrazione(self):
        self.assertEqual(sottrazione(5, 3), 2)

    def test_moltiplicazione(self):
        self.assertEqual(moltiplicazione(3, 4), 12)


if __name__ == "__main__":
    # Esegui i test e conta quelli passati
    suite = unittest.TestLoader().loadTestsFromTestCase(TestFunzioni)
    result = unittest.TextTestRunner(verbosity=0).run(suite)
    passed = result.testsRun - len(result.failures) - len(result.errors)
    print(f"TEST_PASSATI={passed}")
```

RULES:
- ONE file only: project/main.py. Standard library only.
- Test class inherits unittest.TestCase; methods start with test_.
- Cover BOTH the success case AND the error case when the function can
  fail (assertRaises).
- One assert per concept: assertEqual, assertTrue, assertRaises.
- ALWAYS include the `if __name__ == "__main__"` block that runs the
  tests and prints TEST_PASSATI=N (N = numero di test passati).
- Do NOT use `unittest.main()` alone — it doesn't print TEST_PASSATI.
