"""Config flow for Anova Precision Oven integration."""

from __future__ import annotations

import asyncio
import logging
from typing import Any

import voluptuous as vol
from homeassistant import config_entries
from homeassistant.const import (
    CONF_ACCESS_TOKEN,
    CONF_DEVICES,
    CONF_TEMPERATURE_UNIT,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.data_entry_flow import FlowResult
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .api import AnovaOvenApi
from .const import CONF_APP_KEY, CONF_REFRESH_TOKEN, DOMAIN, AnovaUnitOfTemperature
from .exceptions import InvalidAuth, NoDevicesFound
from .precision_oven import AnovaPrecisionOven

_LOGGER = logging.getLogger(__name__)


# TODO adjust the data schema to the data that you need
STEP_USER_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_APP_KEY): str,
        vol.Required(CONF_ACCESS_TOKEN): str,
        vol.Required(CONF_REFRESH_TOKEN): str,
        vol.Required(
            CONF_TEMPERATURE_UNIT, default=AnovaUnitOfTemperature.CELSIUS
        ): vol.All(vol.Coerce(str), vol.In([e.value for e in AnovaUnitOfTemperature])),
    }
)

STEP_OPTIONS_SCHEMA = vol.Schema(
    {
        vol.Optional(
            CONF_TEMPERATURE_UNIT, default=AnovaUnitOfTemperature.CELSIUS
        ): vol.All(vol.Coerce(str), vol.In([e.value for e in AnovaUnitOfTemperature])),
    }
)


async def validate_input(hass: HomeAssistant, data: dict[str, Any]) -> dict[str, Any]:
    """Validate the user input allows us to connect.

    Data has the keys from STEP_USER_DATA_SCHEMA with values provided by the user.
    """
    # TODO validate the data can be used to set up a connection.

    # If your PyPI package is not built with async, pass your methods
    # to the executor:
    # await hass.async_add_executor_job(
    #     your_validate_func, data[CONF_USERNAME], data[CONF_PASSWORD]
    # )

    api = AnovaOvenApi(
        session=async_get_clientsession(hass),
        app_key=data[CONF_APP_KEY],
        access_token=data[CONF_ACCESS_TOKEN],
        refresh_token=data[CONF_REFRESH_TOKEN],
    )

    devices = []
    async with asyncio.TaskGroup() as tg:
        tg.create_task(api.run())
        devices = await api.get_devices()
        await api.stop()
    return devices


class ConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Anova Precision Oven."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle the initial step."""
        errors: dict[str, str] = {}
        if user_input is not None:
            try:
                devices = await validate_input(self.hass, user_input)
            except InvalidAuth:
                errors["base"] = "invalid_auth"
            except NoDevicesFound:
                errors["base"] = "no_devices_found"
            except Exception:  # pylint: disable=broad-except
                _LOGGER.exception("Unexpected exception")
                errors["base"] = "unknown"
            else:
                # We store device list in config flow in order to persist found devices on restart, as the Anova api get_devices does not return any devices that are offline.
                device_list = serialize_device_list(devices)
                return self.async_create_entry(
                    title="Anova Oven",
                    data={
                        CONF_APP_KEY: user_input[CONF_APP_KEY],
                        CONF_ACCESS_TOKEN: user_input[CONF_ACCESS_TOKEN],
                        CONF_REFRESH_TOKEN: user_input[CONF_REFRESH_TOKEN],
                        CONF_DEVICES: device_list,
                    },
                    options={
                        CONF_TEMPERATURE_UNIT: user_input[CONF_TEMPERATURE_UNIT],
                    },
                )

        return self.async_show_form(
            step_id="user", data_schema=STEP_USER_DATA_SCHEMA, errors=errors
        )

    @staticmethod
    @callback
    def async_get_options_flow(
        config_entry: config_entries.ConfigEntry,
    ) -> config_entries.OptionsFlow:
        """Create the options flow."""
        return AnovaOvenOptionsFlowHandler(config_entry)


class AnovaOvenOptionsFlowHandler(config_entries.OptionsFlowWithConfigEntry):
    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Manage the options."""
        if user_input is not None:
            entry = self.async_create_entry(title="", data=user_input)
            return entry

        return self.async_show_form(
            step_id="init",
            data_schema=self.add_suggested_values_to_schema(
                STEP_OPTIONS_SCHEMA, self.config_entry.options
            ),
        )


def serialize_device_list(devices: list[AnovaPrecisionOven]) -> list[tuple[str, str]]:
    """Turn the device list into a serializable list that can be reconstructed."""
    return [(device.cooker_id, device.type) for device in devices]
