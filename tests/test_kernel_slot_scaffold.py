"""
test_kernel_slot_scaffold.py — todo 'Scaffold deterministico SLOT' (driver Linux).

Nessun compilatore, modulo o insmod: solo generazione da template e gate API
contro la whitelist ricavata dagli header reali. Se gli header mancano i test
vengono saltati: il tool in produzione si ferma (fail closed).
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools import kernel_slot_scaffold as kss  # noqa: E402

VERSION = os.uname().release
pytestmark = pytest.mark.skipif(
    not (kss.header_root(VERSION) / "include/linux/module.h").is_file(),
    reason="kernel headers non disponibili")


def test_generazione_deterministica_e_solo_slot(tmp_path):
    first = kss.generate("demo_drv", tmp_path / "a", VERSION)
    kss.generate("demo_drv", tmp_path / "b", VERSION)
    assert first["unknown_api"] == []
    assert first["compilato"] is False
    src_a = (tmp_path / "a" / "demo_drv.c").read_text(encoding="utf-8")
    src_b = (tmp_path / "b" / "demo_drv.c").read_text(encoding="utf-8")
    assert src_a == src_b
    for marker in ("SLOT_READ", "SLOT_WRITE", "SLOT_IOCTL",
                   "platform_driver_register", "MODULE_LICENSE"):
        assert marker in src_a
    assert "obj-m += demo_drv.o" in (
        tmp_path / "a" / "Makefile").read_text(encoding="utf-8")


def test_nome_non_valido_rifiutato():
    for bad in ("", "Abc", "a-b", "../x", "a b", "x" * 40):
        with pytest.raises(ValueError):
            kss.validate_name(bad)


def test_gate_api_rileva_simbolo_inventato(tmp_path):
    kss.generate("demo_drv", tmp_path / "scaffold", VERSION)
    src = (tmp_path / "scaffold" / "demo_drv.c").read_text(encoding="utf-8")
    assert kss.check_api(src, "demo_drv", VERSION) == []
    bad = src.replace("return -ENOSYS;", "return allucinazione_kernel();", 1)
    assert "allucinazione_kernel" in kss.check_api(bad, "demo_drv", VERSION)


def test_macro_verificate_dagli_header_reali():
    macros = kss.verified_macros(VERSION)
    assert {"module_init", "module_exit", "MODULE_LICENSE"} <= macros


def test_slots_md_riporta_regole_e_criteri():
    text = kss.slots_markdown("demo_drv")
    for token in ("SLOT_READ", "SLOT_WRITE", "SLOT_IOCTL",
                  "checkpatch", "sparse", "40 righe"):
        assert token in text
