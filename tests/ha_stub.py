"""Lightweight test harness for the integration's pure logic.

These tests intentionally avoid a full Home Assistant install: state.py only
needs a thin slice of HA (a Store for persistence and dt_util for timezone),
which is stubbed here, and the integration package is loaded synthetically so
relative imports resolve. This keeps the unit tests runnable with bare
``python3`` in CI without pulling the whole HA test stack.
"""

import datetime as _dt
import importlib.util
import os
import sys
import types

# HA's configured "local" timezone, fixed for deterministic tests.
TZ = _dt.timezone(_dt.timedelta(hours=1))
_NOW = {"dt": _dt.datetime(2026, 6, 18, 12, 0, 0, tzinfo=TZ)}


def set_now(dt):
    """Set the value dt_util.now() returns inside the code under test."""
    _NOW["dt"] = dt


def local_ts(y, mo, d, h, mi, s=0):
    """Unix timestamp for a wall-clock time in the fixed local zone."""
    return _dt.datetime(y, mo, d, h, mi, s, tzinfo=TZ).timestamp()


class HomeAssistant:  # stub
    ...


class _Store:
    """In-memory stand-in for homeassistant.helpers.storage.Store."""

    def __init__(self, *a, **k):
        self._data = None

    async def async_load(self):
        return self._data

    async def async_save(self, data):
        self._data = data


def _install_ha_stubs():
    def mod(name):
        m = types.ModuleType(name)
        sys.modules[name] = m
        return m

    ha = mod("homeassistant")
    core = mod("homeassistant.core")
    core.HomeAssistant = HomeAssistant
    helpers = mod("homeassistant.helpers")
    storage = mod("homeassistant.helpers.storage")
    storage.Store = _Store
    util = mod("homeassistant.util")
    dtm = mod("homeassistant.util.dt")
    dtm.now = lambda: _NOW["dt"]
    dtm.as_local = lambda d: d.astimezone(TZ)
    util.dt = dtm
    ha.core, ha.helpers, ha.util, helpers.storage = core, helpers, util, storage


def load_state():
    """Return the integration's `state` module with HA stubbed out."""
    _install_ha_stubs()
    base = os.path.join(
        os.path.dirname(__file__),
        "..",
        "custom_components",
        "ha_hidratespark",
    )
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

    load("const")
    return load("state")
