"""HidrateSpark integration for Home Assistant."""

from __future__ import annotations

import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant

from .const import (
    CONF_ADDRESS,
    CONF_BOTTLE_NAME,
    CONF_NAME_PREFIX,
    CONF_SERIAL_NUMBER,
    CONF_SIZE_ML,
    DEFAULT_NAME_PREFIX,
    DEFAULT_SIZE_ML,
    DOMAIN,
)
from .coordinator import HidrateSparkCoordinator

_LOGGER = logging.getLogger(__name__)

PLATFORMS: list[Platform] = [
    Platform.BINARY_SENSOR,
    Platform.BUTTON,
    Platform.SENSOR,
]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up HidrateSpark from a config entry."""
    address: str = entry.data[CONF_ADDRESS]
    bottle_name: str = entry.data.get(CONF_BOTTLE_NAME) or entry.title
    name: str = bottle_name or entry.data.get(CONF_NAME_PREFIX, DEFAULT_NAME_PREFIX)
    serial_number: str | None = entry.data.get(CONF_SERIAL_NUMBER)
    size_ml: int = entry.options.get(
        CONF_SIZE_ML, entry.data.get(CONF_SIZE_ML, DEFAULT_SIZE_ML)
    )

    coordinator = HidrateSparkCoordinator(
        hass=hass,
        entry=entry,
        address=address,
        bottle_name=bottle_name,
        name=name,
        serial_number=serial_number,
        size_ml=size_ml,
    )
    await coordinator.async_start()

    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = coordinator
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    entry.async_on_unload(entry.add_update_listener(_async_options_updated))
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        coordinator: HidrateSparkCoordinator = hass.data[DOMAIN].pop(entry.entry_id)
        await coordinator.async_stop()
    return unload_ok


async def _async_options_updated(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Reload the entry when options change (e.g. bottle size)."""
    await hass.config_entries.async_reload(entry.entry_id)
