"""Coordinator binding the BLE protocol to Home Assistant entities.

This is what makes ESPHome Bluetooth proxies work: we obtain the BLEDevice via
homeassistant.components.bluetooth.async_ble_device_from_address() — which
transparently returns a proxy-backed device when the bottle is in range of an
ESPHome proxy and not a local adapter — and feed it to bleak-retry-connector.
The same code path also drives a directly-attached USB/onboard adapter.
"""

from __future__ import annotations

import asyncio
import logging
import time
from typing import Optional

from homeassistant.components import bluetooth
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import CALLBACK_TYPE, HomeAssistant, callback
from homeassistant.helpers.dispatcher import async_dispatcher_send

from .ble import BottleClient
from .const import (
    CONF_ADDRESS,
    CONF_BOTTLE_NAME,
    CONF_SERIAL_NUMBER,
    DEFAULT_NAME_PREFIX,
    DOMAIN,
    SERVICE_REF,
)
from .identity import normalize_bottle_name
from .state import BottleState, Sip

_LOGGER = logging.getLogger(__name__)

SIGNAL_UPDATE = f"{DOMAIN}_update_{{entry_id}}"


class HidrateSparkCoordinator:
    """Owns the BLE client, the persisted state, and broadcasts updates."""

    def __init__(
        self,
        hass: HomeAssistant,
        entry: ConfigEntry,
        address: str,
        bottle_name: str,
        name: str,
        serial_number: str | None,
        size_ml: int,
    ) -> None:
        self.hass = hass
        self.entry = entry
        self.address = address.upper()
        self.bottle_name = bottle_name
        self.bottle_id = normalize_bottle_name(bottle_name) or self.address
        self.name = name
        self.serial_number = serial_number
        self.state = BottleState(hass, entry.entry_id, size_ml)

        self._client: Optional[BottleClient] = None
        self._task: Optional[asyncio.Task] = None
        self._unsub_advert: Optional[CALLBACK_TYPE] = None
        self._battery_pct: Optional[int] = None
        self.last_update_ts: Optional[float] = None
        self._connected = False
        self.last_error: Optional[str] = None

    @property
    def signal(self) -> str:
        return SIGNAL_UPDATE.format(entry_id=self.entry.entry_id)

    @property
    def battery_pct(self) -> Optional[int]:
        return self._battery_pct

    @property
    def connected(self) -> bool:
        return self._connected

    @property
    def device_name(self) -> str:
        """Return the Home Assistant device display name."""
        return self.serial_number or self.name or "HidrateSpark"

    # ---------------------------------------------------------------- lifecycle

    async def async_start(self) -> None:
        await self.state.async_load()
        self._refresh_address_from_discovery()

        self._client = BottleClient(
            address=self.address,
            name=self.name,
            size_ml=self.state.bottle_size_ml,
            on_sip=self._handle_sip,
            on_battery=self._handle_battery,
            on_serial=self._handle_serial,
            on_status=self._handle_status,
            on_refill=self._handle_refill,
            on_weight=self._handle_weight,
            ble_device_provider=self._get_ble_device,
            anchor_exists=lambda: self.state.weight_full_raw is not None,
        )

        # Wake the BLE loop whenever HA sees a fresh advertisement for the bottle.
        self._unsub_advert = bluetooth.async_register_callback(
            self.hass,
            self._on_advertisement,
            bluetooth.BluetoothCallbackMatcher(connectable=True),
            bluetooth.BluetoothScanningMode.PASSIVE,
        )

        self._task = self.hass.async_create_background_task(
            self._client.run(), name=f"hidratespark-{self.address}"
        )

    async def async_stop(self) -> None:
        if self._unsub_advert is not None:
            self._unsub_advert()
            self._unsub_advert = None
        if self._client is not None:
            await self._client.stop()
        if self._task is not None:
            try:
                await asyncio.wait_for(self._task, timeout=5.0)
            except (asyncio.TimeoutError, asyncio.CancelledError):
                self._task.cancel()
        await self.state.async_save()

    def request_force_sync(self) -> None:
        if self._client is not None:
            self._client.request_force_sync()

    async def async_calibrate_full(self) -> bool:
        """Set the full-bottle calibration from the latest stable raw weight."""
        if not self.state.calibrate_full():
            return False
        await self.state.async_save()
        self._notify()
        return True

    async def async_calibrate_empty(self) -> bool:
        """Set the empty-bottle calibration from the latest stable raw weight."""
        if not self.state.calibrate_empty():
            return False
        await self.state.async_save()
        self._notify()
        return True

    async def async_reset_totals(self) -> None:
        """Clear accumulated water, sip, and refill totals."""
        self.state.reset_totals()
        await self.state.async_save()
        self._notify()

    # ------------------------------------------------------- BLE device lookup

    def _get_ble_device(self):
        """Return the most current BLEDevice (proxy or local) for the bottle."""
        self._refresh_address_from_discovery()
        device = bluetooth.async_ble_device_from_address(
            self.hass, self.address, connectable=True
        )
        if device is None:
            _LOGGER.debug(
                "no BLE device available for %s at %s",
                self.bottle_name,
                self.address,
            )
        return device

    def _refresh_address_from_discovery(self) -> None:
        """Adopt the latest advertised MAC for this bottle name, if HA has one."""
        for info in bluetooth.async_discovered_service_info(self.hass):
            if self._advertisement_matches_bottle(info):
                self._set_current_address(info.address)
                return

    def _advertisement_matches_bottle(
        self, service_info: bluetooth.BluetoothServiceInfoBleak
    ) -> bool:
        """Return True when an advertisement belongs to this configured bottle."""
        advertised_name = normalize_bottle_name(service_info.name)
        if advertised_name != self.bottle_id:
            return False
        advertised_services = {u.lower() for u in service_info.service_uuids or []}
        if SERVICE_REF.lower() in advertised_services:
            return True
        return bool(
            service_info.name
            and service_info.name.lower().startswith(DEFAULT_NAME_PREFIX)
        )

    def _set_current_address(self, address: str) -> bool:
        """Update the mutable MAC address used for BLE connections."""
        new_address = address.upper()
        if new_address == self.address:
            return False

        old_address = self.address
        self.address = new_address
        if self._client is not None:
            self._client.address = new_address

        data = dict(self.entry.data)
        data[CONF_ADDRESS] = new_address
        data[CONF_BOTTLE_NAME] = self.bottle_name
        self.hass.config_entries.async_update_entry(self.entry, data=data)
        _LOGGER.info(
            "bottle %s rotated MAC from %s to %s",
            self.bottle_name,
            old_address,
            new_address,
        )
        if self._client is not None:
            self._client.request_force_sync()
        return True

    @callback
    def _on_advertisement(
        self,
        service_info: bluetooth.BluetoothServiceInfoBleak,
        change: bluetooth.BluetoothChange,
    ) -> None:
        # Just nudge the run loop — the BLE client picks up the latest device on
        # its next iteration. We don't drive connect/disconnect from here.
        if not self._advertisement_matches_bottle(service_info):
            return
        _LOGGER.debug(
            "matched advertisement for %s at %s",
            self.bottle_name,
            service_info.address,
        )
        address_changed = self._set_current_address(service_info.address)
        if self._client is not None and not self._connected and not address_changed:
            self._client.request_force_sync()

    # ---------------------------------------------------------- BLE callbacks

    async def _handle_sip(
        self, timestamp: float, volume_ml: int, total_reported_ml: int
    ) -> None:
        self._mark_data_update()
        if self.state.add_sip(
            Sip(
                timestamp=timestamp,
                volume_ml=volume_ml,
                reported_total_ml=total_reported_ml,
            )
        ):
            await self.state.async_save()
        self._notify()

    async def _handle_battery(self, pct: int) -> None:
        self._mark_data_update()
        if pct == self._battery_pct:
            self._notify()
            return
        self._battery_pct = pct
        self._notify()

    async def _handle_serial(self, serial_number: str) -> None:
        self._mark_data_update()
        if serial_number == self.serial_number:
            self._notify()
            return
        self.serial_number = serial_number
        data = dict(self.entry.data)
        data[CONF_SERIAL_NUMBER] = serial_number
        self.hass.config_entries.async_update_entry(self.entry, data=data)
        self._notify()

    async def _handle_status(self, connected: bool, error: Optional[str]) -> None:
        if connected != self._connected:
            self._connected = connected
        self.last_error = error
        self._notify()

    async def _handle_refill(self, source: str, weight_full_raw: Optional[int]) -> None:
        self._mark_data_update()
        self.state.refill(source, weight_full_raw)
        await self.state.async_save()
        self._notify()

    async def _handle_weight(self, raw: int, _low_byte: int) -> None:
        self._mark_data_update()
        fill_changed = self.state.update_fill_from_weight(raw)
        if fill_changed:
            # Persist sparingly — fill changes happen often. Only on real change.
            await self.state.async_save()
        # Always notify so the live raw-weight reading refreshes even before a
        # calibration anchor exists (update_fill_from_weight returns False once
        # an anchor is set and fill is unchanged, but it still records the
        # latest stable raw reading).
        self._notify()

    def _mark_data_update(self) -> None:
        self.last_update_ts = time.time()

    @callback
    def _notify(self) -> None:
        async_dispatcher_send(self.hass, self.signal)
