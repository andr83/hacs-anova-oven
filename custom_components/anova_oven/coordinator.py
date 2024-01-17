"""Support for Anova Coordinators."""
from asyncio import timeout, Task, create_task, sleep
from datetime import timedelta
import logging
import typing

from .precision_oven import AnovaPrecisionOven, APOState
from .api import AnovaOvenApi, AnovaOvenUpdateListener
from .models import AnovaOvenData
from .const import CONF_APP_KEY, CONF_REFRESH_TOKEN

from homeassistant.const import CONF_ACCESS_TOKEN, CONF_DEVICES
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import DOMAIN

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
            data=self.entry.data | {
                CONF_ACCESS_TOKEN: access_token,
                CONF_REFRESH_TOKEN: refresh_token
            },
        )
        self.entry = self.hass.config_entries.async_get_entry(
            self.entry.entry_id
        )
