"""CORE/subprocess_utils.py — Helper per subprocess con opzioni standard.

Riduce la duplicazione di stdin/stdout/stderr/text/encoding tra moduli.
"""
from __future__ import annotations

import subprocess
from typing import Optional


def run_captured(cmd, *, env=None, cwd=None, timeout=None, shell=False,
                 input_text=None) -> subprocess.CompletedProcess:
    """Esegue un comando catturando stdout/stderr con opzioni standard.

    Wrapper su subprocess.run con stdin=DEVNULL, stdout/stderr=PIPE,
    text=True, encoding utf-8, errors replace.
    """
    kwargs = dict(
        stdin=subprocess.DEVNULL if input_text is None else subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    if env is not None:
        kwargs["env"] = env
    if cwd is not None:
        kwargs["cwd"] = cwd
    if timeout is not None:
        kwargs["timeout"] = timeout
    if shell:
        kwargs["shell"] = True
    if input_text is not None:
        kwargs["input"] = input_text
    return subprocess.run(cmd, **kwargs)
PY
.venv/bin/python -m py_compile CORE/subprocess_utils.py && echo "COMPILE_OK"