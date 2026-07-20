"""Calibration buttons for HidrateSpark bottles."""

from __future__ import annotations

from homeassistant.components.button import ButtonEntity, ButtonEntityDescription
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN
from .coordinator import HidrateSparkCoordinator
from .entity import HidrateSparkEntity


BUTTONS: tuple[ButtonEntityDescription, ...] = (
    ButtonEntityDescription(
        key="calibrate_full",
        translation_key="calibrate_full",
        entity_category=EntityCategory.CONFIG,
    ),
    ButtonEntityDescription(
        key="calibrate_empty",
        translation_key="calibrate_empty",
        entity_category=EntityCategory.CONFIG,
    ),
    ButtonEntityDescription(
        key="reset_totals",
        translation_key="reset_totals",
        entity_category=EntityCategory.CONFIG,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    coordinator: HidrateSparkCoordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities(HidrateSparkButton(coordinator, desc) for desc in BUTTONS)


class HidrateSparkButton(HidrateSparkEntity, ButtonEntity):
    """A calibration action for the bottle."""

    entity_description: ButtonEntityDescription

    def __init__(
        self,
        coordinator: HidrateSparkCoordinator,
        description: ButtonEntityDescription,
    ) -> None:
        super().__init__(coordinator, description.key)
        self.entity_description = description

    async def async_press(self) -> None:
        if self.entity_description.key == "calibrate_full":
            await self._coordinator.async_calibrate_full()
            return
        if self.entity_description.key == "calibrate_empty":
            await self._coordinator.async_calibrate_empty()
            return
        if self.entity_description.key == "reset_totals":
            await self._coordinator.async_reset_totals()

    @property
    def available(self) -> bool:
        if self.entity_description.key == "reset_totals":
            return True
        return (
            self._coordinator.connected
            and self._coordinator.state.weight_raw is not None
        )
