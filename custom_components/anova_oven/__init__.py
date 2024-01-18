"""The Anova Precision Oven integration."""
from __future__ import annotations

from homeassistant.const import ATTR_DEVICE_ID, CONF_ACCESS_TOKEN, CONF_DEVICES
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers import aiohttp_client
from homeassistant.helpers import device_registry
from homeassistant.helpers.typing import ConfigType

import uuid
import dataclasses

from .const import DOMAIN, CONF_APP_KEY, CONF_REFRESH_TOKEN, PLATFORM
from .util import to_fahrenheit
from .api import AnovaOvenApi
from .coordinator import AnovaCoordinator
from .precision_oven import AnovaPrecisionOven, APOCommand, APOStage
from .models import AnovaOvenData


PLATFORMS: list[Platform] = [Platform.SENSOR, Platform.BINARY_SENSOR]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Anova Precision Oven from a config entry."""
    hass.data.setdefault(DOMAIN, {})
    devices = [
        AnovaPrecisionOven(
            cooker_id=device[0],
            type=device[1],
        )
        for device in entry.data[CONF_DEVICES]
    ]
    api = AnovaOvenApi(
        session=aiohttp_client.async_get_clientsession(hass),
        app_key=entry.data[CONF_APP_KEY],
        access_token=entry.data[CONF_ACCESS_TOKEN],
        refresh_token=entry.data[CONF_REFRESH_TOKEN],
        existing_devices=devices,
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
        if timer and probe:
            raise ValueError("Only probe or timer can be setup at one.")
        if call.data["sous_vide"] and call.data["target_temperature"] > 100:
            raise ValueError(
                "Target temprature could not exceed 100°C in souse vide mode."
            )
        preheat_stage = APOStage(
            step_type="stage",
            id=f"{PLATFORM}-{uuid.uuid4()}",
            title="",
            description="",
            type="preheat",
            user_action_required=False,
            temperature_bulbs=APOStage.TemperatureBulbs(
                dry=APOStage.TemperatureBulb(
                    setpoint=APOStage.TemperatureSetpoint(
                        celsius=call.data["target_temperature"],
                        fahrenheit=to_fahrenheit(call.data["target_temperature"]),
                    )
                )
                if not call.data["sous_vide"]
                else None,
                wet=APOStage.TemperatureBulb(
                    setpoint=APOStage.TemperatureSetpoint(
                        celsius=call.data["target_temperature"],
                        fahrenheit=to_fahrenheit(call.data["target_temperature"]),
                    )
                )
                if call.data["sous_vide"]
                else None,
                mode="wet" if call.data["sous_vide"] else "dry",
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
                mode="relative-humidity",
                relative_humidity=APOStage.SteamGenerators.Setpoint(setpoint=100),
            ),
            probe_added=call.data.get("temperature_probe") is not None,
            temperature_probe=APOStage.Probe(
                setpoint=APOStage.TemperatureSetpoint(
                    celsius=call.data["temperature_probe"],
                    fahrenheit=to_fahrenheit(call.data["temperature_probe"]),
                )
            )
            if call.data.get("temperature_probe")
            else None,
            timer_added=timer is not None,
            timer=APOStage.Timer(
                initial=timer["hours"] * 3600 + timer["minutes"] * 60 + timer["seconds"]
            )
            if timer
            else None,
        )
        cook_stage = dataclasses.replace(
            preheat_stage,
            id=f"{PLATFORM}-{uuid.uuid4()}",
            type="cook",
        )
        await api.send_command(
            APOCommand(
                command="CMD_APO_START",
                request_id=str(uuid.uuid4()),
                payload=APOCommand.Payload(
                    payload=APOCommand.APOStartPayload(
                        cook_id=f"{PLATFORM}-{uuid.uuid4()}",
                        stages=[preheat_stage, cook_stage],
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
