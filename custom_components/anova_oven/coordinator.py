"""Support for Anova Coordinators."""

import logging
from asyncio import Task, sleep

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_ACCESS_TOKEN
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import device_registry
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from .api import AnovaOvenApi, AnovaOvenUpdateListener
from .const import CONF_REFRESH_TOKEN, DOMAIN, EVENT_COOK_TARGET_REACHED
from .precision_oven import AnovaPrecisionOven, APOState, Target

_LOGGER = logging.getLogger(__name__)


class AnovaCoordinator(DataUpdateCoordinator[APOState], AnovaOvenUpdateListener):
    """Anova custom coordinator."""

    def __init__(
        self,
        api: AnovaOvenApi,
        hass: HomeAssistant,
        entry: ConfigEntry,
        devices: list[AnovaPrecisionOven],
    ) -> None:
        """Set up Anova Coordinator."""
        super().__init__(
            hass,
            name="Anova Precision Oven",
            logger=_LOGGER,
        )
        assert self.config_entry is not None
        api.add_listener(self)
        self.api: AnovaOvenApi = api
        self.hass: HomeAssistant = hass
        self.entry: ConfigEntry = entry
        self.devices = {d.cooker_id: d for d in devices}
        self._task: Task | None = None

    @callback
    async def async_setup(self) -> None:
        # """Set the firmware version info."""
        # self.device_info = DeviceInfo(
        #     identifiers={(DOMAIN, self.device_unique_id)},
        #     name="Anova Precision Oven",
        #     manufacturer="Anova",
        #     model="Precision Oven",
        #     sw_version=firmware_version,
        # )
        self._task = self.entry.async_create_background_task(
            hass=self.hass, target=self.api.run(), name="Anova Oven WS Task"
        )
        await sleep(5)

    async def on_state(self, device: AnovaPrecisionOven, state: APOState):
        self.devices[device.cooker_id] = device
        self.async_set_updated_data(state)

    async def on_new_device(self, device: AnovaPrecisionOven):
        self.devices[device.cooker_id] = device
        self.async_set_updated_data(None)

    async def on_new_token(self, access_token: str, refresh_token: str):
        self.hass.config_entries.async_update_entry(
            entry=self.entry,
            data=self.entry.data
            | {CONF_ACCESS_TOKEN: access_token, CONF_REFRESH_TOKEN: refresh_token},
        )
        self.entry = self.hass.config_entries.async_get_entry(self.entry.entry_id)

    async def on_target_reached(self, device: AnovaPrecisionOven, target: Target):
        dr = device_registry.async_get(self.hass)
        d = dr.async_get_device(identifiers={(DOMAIN, device.cooker_id)})
        event_data = {
            "device_id": d.id,
            "type": "cook_target_reached",
        }
        self.hass.bus.async_fire(EVENT_COOK_TARGET_REACHED, event_data)
