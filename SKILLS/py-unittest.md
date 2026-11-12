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


def {{ FUNCTION }}({{ PARAMS }}):
    """{{ WHAT IT COMPUTES }}"""
    return {{ COMPUTATION }}


class Test{{ NAME }}(unittest.TestCase):
    def test_{{ SUCCESS CASE }}(self):
        self.assertEqual({{ FUNCTION }}({{ ARGS }}), {{ EXPECTED }})

    def test_{{ ERROR CASE }}(self):
        with self.assertRaises({{ ERROR TYPE }}):
            {{ CALL THAT MUST RAISE }}


if __name__ == "__main__":
    unittest.main()
```

RULES:
- ONE file only: project/main.py. Standard library only.
- Test class inherits unittest.TestCase; methods start with test_.
- Cover BOTH the success case AND the error case when the function can
  fail (assertRaises).
- One assert per concept: assertEqual, assertTrue, assertRaises.
- Run with `unittest.main()` under the __main__ guard.
