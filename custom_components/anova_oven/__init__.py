"""The Anova Precision Oven integration."""

from __future__ import annotations

import dataclasses
import uuid

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    ATTR_DEVICE_ID,
    CONF_ACCESS_TOKEN,
    CONF_DEVICES,
    CONF_TEMPERATURE_UNIT,
    Platform,
)
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers import aiohttp_client, device_registry
from homeassistant.helpers.typing import ConfigType

from .api import AnovaOvenApi
from .const import (
    CONF_APP_KEY,
    CONF_REFRESH_TOKEN,
    DOMAIN,
    PLATFORM,
    AnovaUnitOfTemperature,
)
from .coordinator import AnovaCoordinator
from .precision_oven import AnovaPrecisionOven, APOCommand, APOStage
from .util import to_celsius, to_fahrenheit

PLATFORMS: list[Platform] = [Platform.SENSOR, Platform.BINARY_SENSOR]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Anova Precision Oven from a config entry."""
    entry.async_on_unload(entry.add_update_listener(update_listener))

    data = entry.data | entry.options

    hass.data.setdefault(DOMAIN, {})
    devices = [
        AnovaPrecisionOven(
            cooker_id=device[0],
            type=device[1],
        )
        for device in data[CONF_DEVICES]
    ]
    api = AnovaOvenApi(
        session=aiohttp_client.async_get_clientsession(hass),
        app_key=data[CONF_APP_KEY],
        access_token=data[CONF_ACCESS_TOKEN],
        refresh_token=data[CONF_REFRESH_TOKEN],
        existing_devices=devices,
        unit_of_temperature=data.get(
            CONF_TEMPERATURE_UNIT, AnovaUnitOfTemperature.CELSIUS
        ),
    )
    coordinator = AnovaCoordinator(api=api, hass=hass, entry=entry, devices=devices)
    await coordinator.async_setup()
    hass.data[DOMAIN][entry.entry_id] = coordinator

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    if unload_ok := await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        hass.data[DOMAIN].pop(entry.entry_id)

    return unload_ok


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up  component."""
    # hass.data[DOMAIN] = {}

    def get_api(device_id) -> tuple[str, AnovaOvenApi]:
        cook_id = None
        api: AnovaOvenApi | None = None
        dr = device_registry.async_get(hass)
        if device := dr.async_get(device_id):
            for ce_key in device.config_entries:
                if ce := hass.data[DOMAIN].get(ce_key):
                    api: AnovaOvenApi = ce.api
                    for k, v in device.identifiers:
                        if k == DOMAIN:
                            cook_id = v
                            break
        if not api or not device_id:
            raise ConfigEntryNotReady("Device is not found or doesn't ready.")
        return cook_id, api

    async def start_cook(call: ServiceCall):
        api: AnovaOvenApi
        cook_id, api = get_api(call.data[ATTR_DEVICE_ID])
        timer = call.data.get("timer")
        probe = call.data.get("temperature_probe")
        uot = api.unit_of_temperature
        if timer and probe:
            raise ValueError("Only probe or timer can be setup at one.")

        if (sous_vide := call.data.get("sous_vide")) is None:
            sous_vide = False

        target_temperature_celsius = None
        target_temperature_fahrenheit = None

        temperature_probe_celsius = None
        temperature_probe_fahrenheit = None

        preheat_required = False
        user_action_required = False

        match call.data.get("timer_mode"):
            case "When Preheated":
                preheat_required = True
            case "Manually":
                preheat_required = True
                user_action_required = True

        match uot:
            case AnovaUnitOfTemperature.CELSIUS:
                if (
                    target_temperature_celsius := call.data.get(
                        "target_temperature_celsius"
                    )
                ) is None:
                    raise ValueError(
                        "This service requires field Target temperature, please enter a valid value."
                    )

                target_temperature_fahrenheit = to_fahrenheit(
                    target_temperature_celsius
                )

                if temperature_probe_celsius := call.data.get(
                    "temperature_probe_celsius"
                ):
                    temperature_probe_fahrenheit = to_fahrenheit(
                        temperature_probe_celsius
                    )
                if sous_vide and target_temperature_celsius > 100:
                    raise ValueError(
                        "Target temprature could not exceed 100°C in souse vide mode."
                    )
            case AnovaUnitOfTemperature.FAHRENHEIT:
                if (
                    target_temperature_fahrenheit := call.data.get(
                        "target_temperature_fahrenheit"
                    )
                ) is None:
                    raise ValueError(
                        "This service requires field Target temperature, please enter a valid value."
                    )
                target_temperature_celsius = to_celsius(target_temperature_fahrenheit)

                if temperature_probe_fahrenheit := call.data.get(
                    "temperature_probe_fahrenheit"
                ):
                    temperature_probe_celsius = to_celsius(temperature_probe_fahrenheit)
                if sous_vide and target_temperature_fahrenheit > 212:
                    raise ValueError(
                        "Target temprature could not exceed 212°F in souse vide mode."
                    )
        preheat_stage = APOStage(
            step_type="stage",
            id=f"{PLATFORM}-{uuid.uuid4()}",
            title="",
            description="",
            type="preheat",
            user_action_required=user_action_required,
            temperature_bulbs=APOStage.TemperatureBulbs(
                dry=APOStage.TemperatureBulb(
                    setpoint=APOStage.TemperatureSetpoint(
                        celsius=target_temperature_celsius,
                        fahrenheit=target_temperature_fahrenheit,
                    )
                )
                if not sous_vide
                else None,
                wet=APOStage.TemperatureBulb(
                    setpoint=APOStage.TemperatureSetpoint(
                        celsius=target_temperature_celsius,
                        fahrenheit=target_temperature_fahrenheit,
                    )
                )
                if sous_vide
                else None,
                mode="wet" if sous_vide else "dry",
            ),
            heating_elements=APOStage.HeatingElements(
                bottom=APOStage.On(on=call.data.get("heating_bottom", False)),
                top=APOStage.On(on=call.data.get("heating_top", False)),
                rear=APOStage.On(on=call.data.get("heating_rear", True)),
            ),
            fan=APOStage.Fan(speed=100),
            vent=APOStage.Vent(open=False),
            rack_position=3,
            steam_generators=APOStage.SteamGenerators(
                mode="relative-humidity" if sous_vide else "steam-percentage",
                relative_humidity=APOStage.SteamGenerators.Setpoint(
                    setpoint=call.data.get("target_humidity", 100 if sous_vide else 0)
                )
                if sous_vide
                else None,
                steam_percentage=APOStage.SteamGenerators.Setpoint(
                    setpoint=call.data.get("target_humidity")
                )
                if not sous_vide
                else None,
            ),
            probe_added=temperature_probe_celsius is not None,
            temperature_probe=APOStage.Probe(
                setpoint=APOStage.TemperatureSetpoint(
                    celsius=temperature_probe_celsius,
                    fahrenheit=temperature_probe_fahrenheit,
                )
            )
            if temperature_probe_celsius is not None
            else None,
        )
        cook_stage = dataclasses.replace(
            preheat_stage,
            id=f"{PLATFORM}-{uuid.uuid4()}",
            type="cook",
            user_action_required=user_action_required,
            timer_added=timer is not None,
            timer=APOStage.Timer(
                initial=timer["hours"] * 3600 + timer["minutes"] * 60 + timer["seconds"]
            )
            if timer
            else None,
        )
        stages = []
        if preheat_required:
            stages.append(preheat_stage)
        stages.append(cook_stage)
        await api.send_command(
            APOCommand(
                command="CMD_APO_START",
                request_id=str(uuid.uuid4()),
                payload=APOCommand.Payload(
                    payload=APOCommand.APOStartPayload(
                        cook_id=f"{PLATFORM}-{uuid.uuid4()}",
                        stages=stages,
                    ),
                    type="CMD_APO_START",
                    id=cook_id,
                ),
            )
        )

    async def stop_cook(call: ServiceCall):
        api: AnovaOvenApi
        cook_id, api = get_api(call.data[ATTR_DEVICE_ID])
        await api.send_command(
            APOCommand(
                command="CMD_APO_STOP",
                request_id=str(uuid.uuid4()),
                payload=APOCommand.Payload(
                    type="CMD_APO_STOP", id=cook_id, payload=None
                ),
            )
        )

    hass.services.async_register(
        DOMAIN,
        "start_cook",
        start_cook,
    )

    hass.services.async_register(
        DOMAIN,
        "stop_cook",
        stop_cook,
    )

    return True


async def update_listener(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Handle options update."""
    await hass.config_entries.async_reload(entry.entry_id)
