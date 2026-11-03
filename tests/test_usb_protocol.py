# -*- coding: utf-8 -*-
"""
tests/test_usb_protocol.py — M10: parser descrittori/setup USB.

Catture fabbricate (nessun hardware necessario): decode_setup seguendo
la spec §9.3, parser `lsusb -v` su un output REALISTICO troncato,
describe_event/summarize su eventi usbmon-like.
"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from CORE.usb_protocol import (  # noqa: E402
    decode_setup, describe_event, describe_setup,
    parse_lsusb_descriptors, summarize,
)


LSUSB_SAMPLE = """
Device Descriptor:
  bcdUSB               2.00
  idVendor           0x046d Logitech
  idProduct          0xc52b Unifying Receiver
  bcdDevice           24.07
  iManufacturer           1  Logitech
  iProduct                2  USB Receiver
  bDeviceClass            0
  Config: 1
 Interface Descriptor:
  bInterfaceNumber   1
 Interface Descriptor:
  bInterfaceNumber   2
  Endpoint Descriptor:
    bEndpointAddress     0x81  EP 1 IN
    bmAttributes            3
      Interrupt
    wMaxPacketSize     0x0020  1x 32 bytes
    bInterval               1
  Endpoint Descriptor:
    bEndpointAddress     0x02  EP 2 OUT
    bmAttributes            2
      Bulk
    wMaxPacketSize     0x0040  1x 64 bytes
    bInterval               0
"""

# setup: bmRequestType=0x80 (IN, standard, device), bRequest=0x06
# (GET_DESCRIPTOR), wValue=0x0303 (STRING idx 3), wIndex=0x0409 (en-US,
# little-endian: 09 04), wLength=255 (little-endian: FF 00)
SETUP_GET_STRING = bytes([0x80, 0x06, 0x03, 0x03, 0x09, 0x04, 0xFF, 0x00])
# SET_CONFIGURATION: bmRequestType=0x00, bRequest=0x09, wValue=1
SETUP_SET_CONF = bytes([0x00, 0x09, 0x01, 0x00, 0x00, 0x00, 0x00, 0x00])
# vendor request 0xB0: bm=0x40 (OUT, type=vendor(bits6..5), recipient device)
SETUP_VENDOR = bytes([0x40, 0xB0, 0x00, 0x00, 0x00, 0x00, 0x40, 0x00])


class TestDecodeSetup(unittest.TestCase):

    def test_get_descriptor_string(self):
        d = decode_setup(SETUP_GET_STRING)
        self.assertEqual(d["direction"], "IN")
        self.assertEqual(d["type"], "standard")
        self.assertEqual(d["recipient"], "device")
        self.assertEqual(d["name"], "GET_DESCRIPTOR")
        self.assertEqual(d["descriptor_type"], "STRING")
        self.assertEqual(d["descriptor_index"], 3)
        self.assertEqual(d["string_langid"], "0x0409")
        self.assertEqual(d["wLength"], 255)

    def test_set_configuration(self):
        d = decode_setup(SETUP_SET_CONF)
        self.assertEqual(d["name"], "SET_CONFIGURATION")
        self.assertEqual(d["configuration_value"], 1)
        self.assertEqual(d["direction"], "OUT")

    def test_vendor_request(self):
        d = decode_setup(SETUP_VENDOR)
        self.assertEqual(d["type"], "vendor")
        self.assertEqual(d["name"], "VENDOR(0xb0)")
        self.assertEqual(d["wLength"], 64)

    def test_bad_length_raises(self):
        for bad in (b"", b"\x00" * 7, b"\x00" * 9):
            with self.assertRaises(ValueError):
                decode_setup(bad)

    def test_reserved_type(self):
        # bm=0x60 → tipo (bits 6..5) = 3 (riservato), recipient=device
        raw = bytes([0x60, 0x00, 0, 0, 0, 0, 0, 0])
        d = decode_setup(raw)
        self.assertTrue(d["type"].startswith("reserved"))
        self.assertEqual(d["recipient"], "device")
        self.assertEqual(d["direction"], "OUT")

    def test_describe_setup_human(self):
        s = describe_setup(SETUP_GET_STRING)
        self.assertIn("GET_DESCRIPTOR", s)
        self.assertIn("STRING(3)", s)
        self.assertIn("IN", s)


class TestLsusbParser(unittest.TestCase):

    def setUp(self):
        self.dev = parse_lsusb_descriptors(LSUSB_SAMPLE)

    def test_identity_fields(self):
        self.assertEqual(self.dev["idVendor"], 0x046D)
        self.assertEqual(self.dev["idProduct"], 0xC52B)
        self.assertEqual(self.dev["product"], "USB Receiver")
        self.assertEqual(self.dev["manufacturer"], "Logitech")

    def test_endpoints_parsed(self):
        eps = self.dev["endpoints"]
        self.assertEqual(len(eps), 2)
        ep_in = next(e for e in eps if e["direction"] == "IN")
        self.assertEqual(ep_in["endpoint"], 1)
        self.assertEqual(ep_in["type"], "interrupt")
        self.assertEqual(ep_in["max_packet_size"], 32)
        ep_out = next(e for e in eps if e["direction"] == "OUT")
        self.assertEqual(ep_out["type"], "bulk")
        self.assertEqual(ep_out["max_packet_size"], 64)
        self.assertEqual(ep_out["address"], "0x02")

    def test_interfaces_found(self):
        nums = sorted(i["number"] for i in self.dev["interfaces"])
        self.assertEqual(nums, [1, 2])

    def test_garbage_input_is_empty_not_crash(self):
        d = parse_lsusb_descriptors("")
        self.assertEqual(d["endpoints"], [])
        d2 = parse_lsusb_descriptors("### righe random senza chiavi\n123\n")
        self.assertEqual(d2["endpoints"], [])


class TestEvents(unittest.TestCase):

    EV_IN = {"ts": 1.00001, "ep": 1, "dir": "IN", "type": "interrupt",
             "payload_len": 32, "data": "01" * 32}
    EV_SETUP = {"ts": 2.0, "ep": 0, "dir": "OUT", "type": "control",
                "payload_len": 0, "setup": SETUP_GET_STRING.hex()}

    def test_describe_event_line(self):
        line = describe_event(self.EV_IN)
        self.assertIn("EP1", line)
        self.assertIn("IN", line)
        self.assertIn("interrupt", line)
        self.assertIn("32B", line)

    def test_describe_event_with_setup(self):
        line = describe_event(self.EV_SETUP)
        self.assertIn("setup=GET_DESCRIPTOR", line)

    def test_describe_event_malformed_setup_no_crash(self):
        ev = dict(self.EV_SETUP)
        ev["setup"] = "zzyy"
        line = describe_event(ev)
        self.assertIn("<malformato>", line)

    def test_describe_event_missing_fields(self):
        line = describe_event({})
        self.assertTrue(line)   # mai crash, sempre una riga

    def test_summarize_stats(self):
        events = [self.EV_IN, self.EV_SETUP, self.EV_IN]
        s = summarize(events)
        self.assertEqual(s["events"], 3)
        self.assertEqual(s["dirs"]["IN"], 2)
        self.assertEqual(s["types"]["interrupt"], 2)
        self.assertEqual(s["setup_requests"].get("standard:GET_DESCRIPTOR"), 1)
        self.assertEqual(s["max_payload"], 32)

    def test_summarize_empty(self):
        s = summarize([])
        self.assertEqual(s["events"], 0)


if __name__ == "__main__":
    print("USB protocol test (M10) → CORE/usb_protocol.py")
    print("=" * 60)
    unittest.main(verbosity=2)
