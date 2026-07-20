"""ble.py sip-notify resilience: the inline re-drain is bounded so a record the
firmware never pops can't trap us in a write loop, and frames with a corrupt
(bogus) seconds-ago are dropped rather than recorded as present-time sips.

Self-contained: stubs the HA + bleak surface ble.py imports and drives
_on_data_notify directly. Run: python3 tests/test_sip_redrain.py
"""

import asyncio
import importlib.util
import inspect
import os
import sys
import types
import unittest
from unittest.mock import AsyncMock


def _install_stubs():
    def mod(name):
        m = types.ModuleType(name)
        sys.modules[name] = m
        return m

    # Home Assistant surface (ble.py imports none directly, but const may be
    # pulled via the package; keep it minimal and safe).
    # bleak surface used only for type hints / establish_connection.
    bleak = mod("bleak")

    class BleakClient:  # stub
        ...

    bleak.BleakClient = BleakClient
    backends = mod("bleak.backends")
    device = mod("bleak.backends.device")

    class BLEDevice:  # stub
        ...

    device.BLEDevice = BLEDevice
    bleak.backends = backends
    backends.device = device

    brc = mod("bleak_retry_connector")

    class BleakClientWithServiceCache:  # stub
        ...

    async def establish_connection(*a, **k):  # stub
        raise RuntimeError("not used in unit tests")

    brc.BleakClientWithServiceCache = BleakClientWithServiceCache
    brc.establish_connection = establish_connection


def _load_ble():
    _install_stubs()
    base = os.path.join(
        os.path.dirname(__file__), "..", "custom_components", "ha_hidratespark"
    )
    pkg = types.ModuleType("hsp")
    pkg.__path__ = [base]
    sys.modules["hsp"] = pkg

    def load(sub):
        spec = importlib.util.spec_from_file_location(f"hsp.{sub}", os.path.join(base, f"{sub}.py"))
        m = importlib.util.module_from_spec(spec)
        sys.modules[f"hsp.{sub}"] = m
        spec.loader.exec_module(m)
        return m

    load("const")
    return load("ble")


ble = _load_ble()
MAX = __import__("sys").modules["hsp.const"].MAX_IDENTICAL_SIP_FRAMES


class FakeClient:
    """Counts re-drain writes; always reports connected."""

    def __init__(self):
        self.writes = 0
        self.is_connected = True

    async def write_gatt_char(self, *a, **k):
        self.writes += 1


def make_client():
    kwargs = dict(
        size_ml=946,
        on_sip=AsyncMock(),
        on_battery=AsyncMock(),
        on_serial=AsyncMock(),
        on_status=AsyncMock(),
        on_refill=AsyncMock(),
        on_weight=AsyncMock(),
        ble_device_provider=lambda: None,
    )
    # anchor_exists exists only once the 32oz weight branch is merged in.
    if "anchor_exists" in inspect.signature(ble.BottleClient.__init__).parameters:
        kwargs["anchor_exists"] = lambda: False
    c = ble.BottleClient("AA:BB:CC:DD:EE:FF", "bottle", **kwargs)
    c._connected = True
    c._client = FakeClient()
    c._data_char = "data-char-uuid"
    return c


class ReDrainBoundTest(unittest.TestCase):
    def test_redrain_stops_after_max_identical_frames(self):
        c = make_client()
        frame = bytearray([1, 0])  # remaining=1, short (no sip parsed)

        async def go():
            for _ in range(MAX + 3):
                await c._on_data_notify(None, frame)

        asyncio.run(go())
        self.assertEqual(
            c._client.writes, MAX,
            f"re-drain must stop after {MAX} identical frames, got {c._client.writes}",
        )
        self.assertEqual(c._on_sip.await_count, 0, "short frames must not emit sips")


class CorruptFrameTest(unittest.TestCase):
    def test_bogus_seconds_ago_frame_is_dropped(self):
        c = make_client()
        # 9 bytes; seconds_ago = 0xFFFFFFFF (~136 years) -> bogus
        frame = bytearray([1, 10, 0x00, 0x64, 0x00, 0xFF, 0xFF, 0xFF, 0xFF])
        asyncio.run(c._on_data_notify(None, frame))
        self.assertEqual(c._on_sip.await_count, 0, "corrupt-timestamp frame must be dropped")

    def test_valid_frame_emits_one_sip(self):
        c = make_client()
        # remaining=1, pct=10, total=100, seconds_ago=5 -> volume = round(946*10/100)=95
        frame = bytearray([1, 10, 0x00, 0x64, 0x00, 0x00, 0x00, 0x00, 0x05])
        asyncio.run(c._on_data_notify(None, frame))
        self.assertEqual(c._on_sip.await_count, 1)
        _ts, volume, total = c._on_sip.await_args.args
        self.assertEqual(volume, 95)
        self.assertEqual(total, 100)


if __name__ == "__main__":
    unittest.main(verbosity=2)
