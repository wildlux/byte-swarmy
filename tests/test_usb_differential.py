# -*- coding: utf-8 -*-
"""
tests/test_usb_differential.py — M11: diff tra catture USB + scoring.

Catture fabbricate: prima e dopo un "aggiornamento" di prova; verifica
endpoint nuovi, request vendor nuove (rischio HIGH), salti di frequenza,
payload medio, tipo changed e rischio low su bus identici.
"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from CORE.usb_differential import diff_captures, explain_diff  # noqa: E402

SETUP_GET_STRING = bytes([0x80, 0x06, 0x03, 0x03, 0x09, 0x04, 0x00, 0xFF])
SETUP_VENDOR_NEW = bytes([0x40, 0xB0, 0x00, 0x00, 0x00, 0x00, 0x40, 0x00])


def ev(ep, direction, ttype, payload_len=0, setup=None, ts=1.0):
    e = {"ts": ts, "ep": ep, "dir": direction, "type": ttype,
         "payload_len": payload_len}
    if setup is not None:
        e["setup"] = setup
    return e


class TestDiff(unittest.TestCase):

    def test_identical_captures_low_risk(self):
        base = [ev(1, "IN", "interrupt", 32, ts=1.1),
                ev(0, "OUT", "control", 0, SETUP_GET_STRING.hex()),
                ev(2, "OUT", "bulk", 64)]
        d = diff_captures(base, [dict(x) for x in base])
        self.assertEqual(d["risk"], "low")
        self.assertEqual(d["risk_reasons"], [])
        self.assertEqual(d["new_endpoints"], [])
        self.assertEqual(d["new_setup_requests"], [])

    def test_new_vendor_request_high_risk(self):
        before = [ev(0, "OUT", "control", 0, SETUP_GET_STRING.hex())]
        after = [ev(0, "OUT", "control", 0, SETUP_GET_STRING.hex()),
                 ev(0, "OUT", "control", 0, SETUP_VENDOR_NEW.hex())]
        d = diff_captures(before, after)
        self.assertEqual(d["risk"], "high")
        self.assertTrue(any("vendor" in x for x in d["risk_reasons"]))
        self.assertEqual(d["new_setup_requests"][0]["request"],
                         "vendor:VENDOR(0xb0)")

    def test_new_data_endpoint_medium_risk(self):
        before = [ev(0, "OUT", "control")]
        after = [ev(0, "OUT", "control"),
                 ev(3, "OUT", "bulk", 512)]
        d = diff_captures(before, after)
        self.assertEqual(d["risk"], "medium")
        self.assertEqual(
            d["new_endpoints"],
            [{"ep": 3, "dir": "OUT", "type": "bulk"}])

    def test_frequency_jump_x5_detected(self):
        base_req = {"setup": SETUP_GET_STRING.hex()}
        before = [ev(0, "OUT", "control", 0, base_req["setup"]) for _ in range(1)]
        # dopo: la stessa richiesta diventa 6 volte più frequente (x6 > x5)
        after = [ev(0, "OUT", "control", 0, base_req["setup"])
                 for _ in range(6)]
        d = diff_captures(before, after)
        self.assertIn("standard:GET_DESCRIPTOR", d["frequency_changes"])
        self.assertEqual(d["frequency_changes"]["standard:GET_DESCRIPTOR"],
                         {"from": 1, "to": 6})
        self.assertEqual(d["risk"], "medium")

    def test_payload_avg_growth_detected(self):
        before = [ev(2, "OUT", "bulk", 64) for _ in range(4)]
        after = [ev(2, "OUT", "bulk", 200) for _ in range(4)]
        d = diff_captures(before, after)
        self.assertIn("2/OUT", d["payload_increase"])
        self.assertGreater(
            d["payload_increase"]["2/OUT"]["avg_after"],
            2 * d["payload_increase"]["2/OUT"]["avg_before"])

    def test_type_change(self):
        before = [ev(5, "IN", "bulk", 8)]
        after = [ev(5, "IN", "interrupt", 8)]
        d = diff_captures(before, after)
        self.assertEqual(d["type_changes"],
                         [{"ep": 5, "dir": "IN", "from": "bulk",
                           "to": "interrupt"}])
        self.assertEqual(d["risk"], "medium")

    def test_gone_endpoint(self):
        before = [ev(4, "IN", "interrupt", 0)]
        after = []
        d = diff_captures(before, after)
        self.assertEqual(d["gone_endpoints"],
                         [{"ep": 4, "dir": "IN", "type": "interrupt"}])

    def test_empty_inputs(self):
        d = diff_captures([], [])
        self.assertEqual(d["risk"], "low")
        self.assertEqual(d["before"]["events"], 0)

    def test_explain_diff_readable(self):
        before = [ev(0, "OUT", "control")]
        after = [ev(0, "OUT", "control"),
                 ev(0, "OUT", "control", 0, SETUP_VENDOR_NEW.hex())]
        text = explain_diff(diff_captures(before, after))
        self.assertIn("RISCHIO: HIGH", text)
        self.assertIn("vendor", text)


if __name__ == "__main__":
    print("USB differential test (M11) → CORE/usb_differential.py")
    print("=" * 60)
    unittest.main(verbosity=2)
