"""Base entity for HidrateSpark sensors and binary sensors."""

from __future__ import annotations

from homeassistant.core import callback
from typing import Any

from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity import Entity

from .const import DOMAIN
from .coordinator import HidrateSparkCoordinator


class HidrateSparkEntity(Entity):
    """Common bits for every entity belonging to a bottle."""

    _attr_should_poll = False
    _attr_has_entity_name = True

    def __init__(self, coordinator: HidrateSparkCoordinator, key: str) -> None:
        self._coordinator = coordinator
        self._attr_unique_id = f"{coordinator.bottle_id}_{key}"

    @property
    def device_info(self) -> DeviceInfo:
        info: dict[str, Any] = {
            "identifiers": {(DOMAIN, self._coordinator.bottle_id)},
            "name": self._coordinator.device_name,
            "manufacturer": "HidrateSpark",
            "model": "Smart Water Bottle",
        }
        if self._coordinator.serial_number:
            info["serial_number"] = self._coordinator.serial_number
        return DeviceInfo(**info)

    async def async_added_to_hass(self) -> None:
        self.async_on_remove(
            async_dispatcher_connect(
                self.hass, self._coordinator.signal, self._handle_update
            )
        )

    @callback
    def _handle_update(self) -> None:
        self.async_write_ha_state()

    @property
    def available(self) -> bool:
        return self._coordinator.connected
