"""HidrateSpark sensors."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import PERCENTAGE, EntityCategory, UnitOfVolume
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN, ML_PER_FLUID_OUNCE
from .coordinator import HidrateSparkCoordinator
from .entity import HidrateSparkEntity


SENSORS: tuple[SensorEntityDescription, ...] = (
    SensorEntityDescription(
        key="battery",
        translation_key="battery",
        device_class=SensorDeviceClass.BATTERY,
        native_unit_of_measurement=PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    SensorEntityDescription(
        key="water_today",
        translation_key="water_today",
        native_unit_of_measurement=UnitOfVolume.FLUID_OUNCES,
        device_class=SensorDeviceClass.VOLUME,
        state_class=SensorStateClass.TOTAL_INCREASING,
        suggested_display_precision=2,
    ),
    SensorEntityDescription(
        key="water_lifetime",
        translation_key="water_lifetime",
        native_unit_of_measurement=UnitOfVolume.FLUID_OUNCES,
        device_class=SensorDeviceClass.VOLUME,
        state_class=SensorStateClass.TOTAL_INCREASING,
        suggested_display_precision=2,
    ),
    SensorEntityDescription(
        key="current_fill",
        translation_key="current_fill",
        native_unit_of_measurement=UnitOfVolume.FLUID_OUNCES,
        device_class=SensorDeviceClass.VOLUME_STORAGE,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=2,
    ),
    SensorEntityDescription(
        key="current_fill_pct",
        translation_key="current_fill_pct",
        native_unit_of_measurement=PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SensorEntityDescription(
        key="last_sip_volume",
        translation_key="last_sip_volume",
        native_unit_of_measurement=UnitOfVolume.FLUID_OUNCES,
        device_class=SensorDeviceClass.VOLUME_STORAGE,
        suggested_display_precision=2,
    ),
    SensorEntityDescription(
        key="last_sip_percent_raw",
        translation_key="last_sip_percent_raw",
        native_unit_of_measurement=PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
    ),
    SensorEntityDescription(
        key="last_reported_total_raw",
        translation_key="last_reported_total_raw",
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
    ),
    SensorEntityDescription(
        key="last_sip_time",
        translation_key="last_sip_time",
        device_class=SensorDeviceClass.TIMESTAMP,
    ),
    SensorEntityDescription(
        key="last_update_time",
        translation_key="last_update_time",
        device_class=SensorDeviceClass.TIMESTAMP,
    ),
    SensorEntityDescription(
        key="serial_number",
        translation_key="serial_number",
        icon="mdi:identifier",
    ),
    SensorEntityDescription(
        key="sips_today",
        translation_key="sips_today",
        state_class=SensorStateClass.TOTAL_INCREASING,
        icon="mdi:cup-water",
    ),
    SensorEntityDescription(
        key="refills_today",
        translation_key="refills_today",
        state_class=SensorStateClass.TOTAL_INCREASING,
        icon="mdi:water-pump",
    ),
    SensorEntityDescription(
        key="weight_raw",
        translation_key="weight_raw",
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
    ),
    SensorEntityDescription(
        key="weight_empty_raw",
        translation_key="weight_empty_raw",
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
    ),
    SensorEntityDescription(
        key="weight_full_raw",
        translation_key="weight_full_raw",
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
    ),
    SensorEntityDescription(
        key="raw_units_per_ml",
        translation_key="raw_units_per_ml",
        native_unit_of_measurement="raw/mL",
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=3,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    coordinator: HidrateSparkCoordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities(HidrateSparkSensor(coordinator, desc) for desc in SENSORS)


class HidrateSparkSensor(HidrateSparkEntity, SensorEntity):
    """A single sensor reading from the bottle's coordinator state."""

    entity_description: SensorEntityDescription

    def __init__(
        self,
        coordinator: HidrateSparkCoordinator,
        description: SensorEntityDescription,
    ) -> None:
        super().__init__(coordinator, description.key)
        self.entity_description = description

    @property
    def native_value(self) -> Any:
        state = self._coordinator.state
        key = self.entity_description.key
        if key == "battery":
            return self._coordinator.battery_pct
        if key == "water_today":
            return _ml_to_fl_oz(state.total_today_ml)
        if key == "water_lifetime":
            return _ml_to_fl_oz(state.lifetime_total_ml)
        if key == "current_fill":
            return _ml_to_fl_oz(state.current_fill_ml)
        if key == "current_fill_pct":
            return state.current_fill_pct
        if key == "last_sip_volume":
            return _ml_to_fl_oz(state.last_sip.volume_ml) if state.last_sip else None
        if key == "last_sip_percent_raw":
            return self._coordinator.last_sip_percent
        if key == "last_reported_total_raw":
            return self._coordinator.last_reported_total_raw
        if key == "last_sip_time":
            if state.last_sip is None:
                return None
            return datetime.fromtimestamp(state.last_sip.timestamp, tz=timezone.utc)
        if key == "last_update_time":
            if self._coordinator.last_update_ts is None:
                return None
            return datetime.fromtimestamp(
                self._coordinator.last_update_ts, tz=timezone.utc
            )
        if key == "serial_number":
            return self._coordinator.serial_number
        if key == "sips_today":
            return state.sips_today
        if key == "refills_today":
            return state.refills_today
        if key == "weight_raw":
            return state.weight_raw
        if key == "weight_empty_raw":
            return state.weight_empty_raw
        if key == "weight_full_raw":
            return state.weight_full_raw
        if key == "raw_units_per_ml":
            return round(state.raw_units_per_ml, 3)
        return None

    @property
    def available(self) -> bool:
        # Live-only readings (battery, raw weight) become unavailable when
        # the bottle is disconnected. Cached/accumulated values (totals,
        # current fill, last sip) remain meaningful across disconnects.
        if self.entity_description.key in (
            "battery",
            "weight_raw",
            "last_sip_percent_raw",
            "last_reported_total_raw",
        ):
            return self._coordinator.connected
        if self.entity_description.key in ("weight_empty_raw", "weight_full_raw"):
            return self.native_value is not None
        return True


def _ml_to_fl_oz(value_ml: int | float) -> float:
    return round(value_ml / ML_PER_FLUID_OUNCE, 2)
