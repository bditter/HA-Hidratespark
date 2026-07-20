"""Name-based identity and rotating-MAC coordinator behavior."""

import datetime as _dt
import importlib.util
import os
import sys
import types
import unittest


def _install_stubs():
    def mod(name):
        m = types.ModuleType(name)
        sys.modules[name] = m
        return m

    ha = mod("homeassistant")
    components = mod("homeassistant.components")
    bluetooth = mod("homeassistant.components.bluetooth")

    class BluetoothCallbackMatcher:
        def __init__(self, **kwargs):
            self.kwargs = kwargs

    class BluetoothScanningMode:
        PASSIVE = "passive"

    bluetooth.BluetoothCallbackMatcher = BluetoothCallbackMatcher
    bluetooth.BluetoothScanningMode = BluetoothScanningMode
    bluetooth.BluetoothChange = object
    bluetooth.BluetoothServiceInfoBleak = object
    bluetooth.async_discovered_service_info = lambda hass: hass.discovered
    bluetooth.async_ble_device_from_address = lambda *a, **k: None
    bluetooth.async_register_callback = lambda *a, **k: (lambda: None)
    components.bluetooth = bluetooth
    ha.components = components

    config_entries = mod("homeassistant.config_entries")
    config_entries.ConfigEntry = object

    core = mod("homeassistant.core")
    core.CALLBACK_TYPE = object
    core.HomeAssistant = object
    core.callback = lambda fn: fn

    helpers = mod("homeassistant.helpers")
    dispatcher = mod("homeassistant.helpers.dispatcher")
    dispatcher.async_dispatcher_send = lambda *a, **k: None
    storage = mod("homeassistant.helpers.storage")

    class Store:
        def __init__(self, *a, **k):
            pass

    storage.Store = Store
    helpers.dispatcher = dispatcher
    helpers.storage = storage
    ha.helpers = helpers

    util = mod("homeassistant.util")
    dtm = mod("homeassistant.util.dt")
    dtm.now = lambda: _dt.datetime.now(_dt.timezone.utc)
    dtm.as_local = lambda d: d
    util.dt = dtm
    ha.util = util

    bleak = mod("bleak")

    class BleakClient:
        ...

    bleak.BleakClient = BleakClient
    backends = mod("bleak.backends")
    device = mod("bleak.backends.device")
    device.BLEDevice = object
    bleak.backends = backends
    backends.device = device

    brc = mod("bleak_retry_connector")
    brc.BleakClientWithServiceCache = object

    async def establish_connection(*a, **k):
        raise RuntimeError("not used")

    brc.establish_connection = establish_connection


def _load_modules():
    _install_stubs()
    base = os.path.join(os.path.dirname(__file__), "..", "custom_components", "ha_hidratespark")
    pkg = types.ModuleType("hsp")
    pkg.__path__ = [base]
    sys.modules["hsp"] = pkg

    def load(sub):
        spec = importlib.util.spec_from_file_location(
            f"hsp.{sub}", os.path.join(base, f"{sub}.py")
        )
        m = importlib.util.module_from_spec(spec)
        sys.modules[f"hsp.{sub}"] = m
        spec.loader.exec_module(m)
        return m

    for sub in ("const", "identity", "state", "ble"):
        load(sub)
    return load("coordinator")


class ServiceInfo:
    def __init__(self, name, address, service_uuids=None):
        self.name = name
        self.address = address
        self.service_uuids = service_uuids or []


class ConfigEntries:
    def __init__(self):
        self.updated = None

    def async_update_entry(self, entry, *, data):
        self.updated = data
        entry.data = data
        return True


class Hass:
    def __init__(self):
        self.discovered = []
        self.config_entries = ConfigEntries()


class Entry:
    def __init__(self):
        self.entry_id = "entry-1"
        self.data = {"address": "AA:AA:AA:AA:AA:AA", "bottle_name": "h2oBottle"}


class MacRotationTest(unittest.TestCase):
    def test_advertisement_matches_configured_bottle_name(self):
        coordinator = _load_modules()
        const = sys.modules["hsp.const"]
        c = coordinator.HidrateSparkCoordinator(
            Hass(), Entry(), "AA:AA:AA:AA:AA:AA", "h2oBottle", "h2oBottle", 591
        )

        self.assertTrue(
            c._advertisement_matches_bottle(
                ServiceInfo("h2oBottle", "BB:BB:BB:BB:BB:BB", [const.SERVICE_REF])
            )
        )
        self.assertTrue(
            c._advertisement_matches_bottle(
                ServiceInfo("h2oBottle", "BB:BB:BB:BB:BB:BB")
            )
        )
        self.assertFalse(
            c._advertisement_matches_bottle(
                ServiceInfo("otherBottle", "BB:BB:BB:BB:BB:BB", [const.SERVICE_REF])
            )
        )

    def test_rotated_mac_updates_entry_and_client_address(self):
        coordinator = _load_modules()
        hass = Hass()
        entry = Entry()
        c = coordinator.HidrateSparkCoordinator(
            hass, entry, "AA:AA:AA:AA:AA:AA", "h2oBottle", "h2oBottle", 591
        )
        client = types.SimpleNamespace(address=c.address, force_syncs=0)

        def request_force_sync():
            client.force_syncs += 1

        client.request_force_sync = request_force_sync
        c._client = client

        c._on_advertisement(
            ServiceInfo("h2oBottle", "BB:BB:BB:BB:BB:BB"),
            None,
        )

        self.assertEqual(c.address, "BB:BB:BB:BB:BB:BB")
        self.assertEqual(client.address, "BB:BB:BB:BB:BB:BB")
        self.assertEqual(client.force_syncs, 1)
        self.assertEqual(entry.data["address"], "BB:BB:BB:BB:BB:BB")
        self.assertEqual(entry.data["bottle_name"], "h2oBottle")


if __name__ == "__main__":
    unittest.main(verbosity=2)
