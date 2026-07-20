"""Config flow for the HidrateSpark integration.

Discovery sources:
  * Bluetooth — when HA's bluetooth stack (or an ESPHome proxy) sees a bottle
    advertising the HydroSync reference service or a `h2o*` local name, the
    user is offered a one-click "Configure" action.
  * Manual — the user picks from any HidrateSpark candidate currently
    advertising in range, or types its advertised name and current MAC address.
"""

from __future__ import annotations

import logging
from typing import Any

import voluptuous as vol
from homeassistant.components.bluetooth import (
    BluetoothServiceInfoBleak,
    async_discovered_service_info,
)
from homeassistant.config_entries import ConfigFlow, OptionsFlow
from homeassistant.data_entry_flow import FlowResult
from homeassistant.const import CONF_ADDRESS
from homeassistant.core import callback
from homeassistant.helpers import config_validation as cv

from .const import (
    CONF_BOTTLE_NAME,
    CONF_NAME_PREFIX,
    CONF_SIZE_ML,
    DEFAULT_NAME_PREFIX,
    DEFAULT_SIZE_ML,
    DOMAIN,
    SERVICE_REF,
)
from .identity import normalize_bottle_name

_LOGGER = logging.getLogger(__name__)


def _looks_like_bottle(info: BluetoothServiceInfoBleak) -> bool:
    if SERVICE_REF.lower() in {u.lower() for u in info.service_uuids or []}:
        return True
    if info.name and info.name.lower().startswith(DEFAULT_NAME_PREFIX):
        return True
    return False


def _bottle_name(info: BluetoothServiceInfoBleak) -> str | None:
    """Return the advertised bottle name when it can be used as identity."""
    return info.name.strip() if info.name and info.name.strip() else None


class HidrateSparkConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for HidrateSpark."""

    VERSION = 1

    def __init__(self) -> None:
        self._discovery_info: BluetoothServiceInfoBleak | None = None
        self._discovered: dict[str, BluetoothServiceInfoBleak] = {}

    # ----------------------------------------------------------- bluetooth flow

    async def async_step_bluetooth(
        self, discovery_info: BluetoothServiceInfoBleak
    ) -> FlowResult:
        """Handle a bottle discovered via the bluetooth integration."""
        if not _looks_like_bottle(discovery_info):
            return self.async_abort(reason="not_supported")
        bottle_name = _bottle_name(discovery_info)
        bottle_id = normalize_bottle_name(bottle_name)
        if bottle_name is None or bottle_id is None:
            return self.async_abort(reason="not_supported")
        await self.async_set_unique_id(bottle_id)
        self._abort_if_unique_id_configured(
            updates={
                CONF_ADDRESS: discovery_info.address.upper(),
                CONF_BOTTLE_NAME: bottle_name,
            },
            reload_on_update=True,
        )
        self._discovery_info = discovery_info
        self.context["title_placeholders"] = {
            "name": bottle_name,
        }
        return await self.async_step_bluetooth_confirm()

    async def async_step_bluetooth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        assert self._discovery_info is not None
        bottle_name = _bottle_name(self._discovery_info)
        assert bottle_name is not None
        if user_input is not None:
            return self.async_create_entry(
                title=bottle_name,
                data={
                    CONF_ADDRESS: self._discovery_info.address.upper(),
                    CONF_BOTTLE_NAME: bottle_name,
                    CONF_NAME_PREFIX: DEFAULT_NAME_PREFIX,
                },
                options={CONF_SIZE_ML: user_input.get(CONF_SIZE_ML, DEFAULT_SIZE_ML)},
            )
        return self.async_show_form(
            step_id="bluetooth_confirm",
            description_placeholders={
                "name": bottle_name,
            },
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_SIZE_ML, default=DEFAULT_SIZE_ML): vol.All(
                        cv.positive_int, vol.Range(min=100, max=2000)
                    ),
                }
            ),
        )

    # ---------------------------------------------------------------- user flow

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle a manually-initiated flow."""
        if user_input is not None:
            bottle_name = str(user_input[CONF_BOTTLE_NAME]).strip()
            bottle_id = normalize_bottle_name(bottle_name)
            if bottle_id is None:
                return self.async_abort(reason="not_supported")
            discovered = self._discovered.get(bottle_id)
            address = (
                discovered.address
                if discovered is not None
                else user_input[CONF_ADDRESS]
            ).upper()
            await self.async_set_unique_id(bottle_id)
            self._abort_if_unique_id_configured(
                updates={
                    CONF_ADDRESS: address,
                    CONF_BOTTLE_NAME: bottle_name,
                },
                reload_on_update=True,
            )
            return self.async_create_entry(
                title=bottle_name,
                data={
                    CONF_ADDRESS: address,
                    CONF_BOTTLE_NAME: bottle_name,
                    CONF_NAME_PREFIX: DEFAULT_NAME_PREFIX,
                },
                options={CONF_SIZE_ML: user_input.get(CONF_SIZE_ML, DEFAULT_SIZE_ML)},
            )

        # Build a picker from currently-advertising candidates.
        current_bottle_ids = {
            entry.unique_id for entry in self._async_current_entries()
        }
        for info in async_discovered_service_info(self.hass):
            bottle_name = _bottle_name(info)
            bottle_id = normalize_bottle_name(bottle_name)
            if bottle_name is None or bottle_id is None:
                continue
            if bottle_id in current_bottle_ids:
                continue
            if _looks_like_bottle(info):
                self._discovered[bottle_id] = info

        if self._discovered:
            choices = {
                bottle_id: f"{info.name} ({info.address})"
                for bottle_id, info in self._discovered.items()
            }
            schema = vol.Schema(
                {
                    vol.Required(CONF_BOTTLE_NAME): vol.In(choices),
                    vol.Required(CONF_SIZE_ML, default=DEFAULT_SIZE_ML): vol.All(
                        cv.positive_int, vol.Range(min=100, max=2000)
                    ),
                }
            )
        else:
            schema = vol.Schema(
                {
                    vol.Required(CONF_BOTTLE_NAME): str,
                    vol.Required(CONF_ADDRESS): str,
                    vol.Required(CONF_SIZE_ML, default=DEFAULT_SIZE_ML): vol.All(
                        cv.positive_int, vol.Range(min=100, max=2000)
                    ),
                }
            )

        return self.async_show_form(step_id="user", data_schema=schema)

    # ----------------------------------------------------------------- options

    @staticmethod
    @callback
    def async_get_options_flow(config_entry) -> OptionsFlow:
        return HidrateSparkOptionsFlow(config_entry)


class HidrateSparkOptionsFlow(OptionsFlow):
    """Allow the bottle size to be tuned after setup."""

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        if user_input is not None:
            return self.async_create_entry(title="", data=user_input)
        current = self.config_entry.options.get(
            CONF_SIZE_ML, self.config_entry.data.get(CONF_SIZE_ML, DEFAULT_SIZE_ML)
        )
        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_SIZE_ML, default=current): vol.All(
                        cv.positive_int, vol.Range(min=100, max=2000)
                    ),
                }
            ),
        )
