"""Support for Anova Sensors."""
from __future__ import annotations

from typing import Callable, Literal
from dataclasses import dataclass
from enum import StrEnum, auto

from anova_wifi import APCUpdateSensor

from homeassistant import config_entries
from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.const import UnitOfTemperature, UnitOfTime
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import StateType

from .const import DOMAIN
from .entity import AnovaOvenDescriptionEntity
from .coordinator import AnovaCoordinator
from .precision_oven import APOSensor


class FormatType(StrEnum):
    OnOff = auto()
    YesNo = auto()


@dataclass(frozen=True)
class AnovaOvenBinarySensorEntityDescriptionMixin:
    """Describes the mixin variables for anova sensors."""
    format_type: FormatType
    value_fn: Callable[[APOSensor], bool]


@dataclass(frozen=True)
class AnovaOvenBinarySensorEntityDescription(
    SensorEntityDescription, AnovaOvenBinarySensorEntityDescriptionMixin
):
    """Describes a Anova binary sensor."""


SENSOR_DESCRIPTIONS: list[SensorEntityDescription] = [
    AnovaOvenBinarySensorEntityDescription(
        key="sous_vide",
        translation_key="sous_vide",
        format_type=FormatType.OnOff,
        value_fn=lambda data: data.sensor.nodes.temperature_bulbs.mode == 'wet',
    ),
    AnovaOvenBinarySensorEntityDescription(
        key="lamp_on",
        translation_key="lamp_on",
        format_type=FormatType.OnOff,
        value_fn=lambda data: data.sensor.nodes.lamp_on,
    ),
    AnovaOvenBinarySensorEntityDescription(
        key="door_closed",
        translation_key="door_closed",
        format_type=FormatType.YesNo,
        value_fn=lambda data: data.sensor.nodes.door_closed,
    ),
    AnovaOvenBinarySensorEntityDescription(
        key="water_tank_empty",
        translation_key="water_tank_empty",
        format_type=FormatType.YesNo,
        value_fn=lambda data: data.sensor.nodes.water_tank_empty,
    ),
]


async def async_setup_entry(
    hass: HomeAssistant,
    entry: config_entries.ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Anova device."""
    coordinator: AnovaCoordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities(
        AnovaOvenBinarySensor(device[0], coordinator, description)
        for device in coordinator.devices.items()
        for description in SENSOR_DESCRIPTIONS
    )


class AnovaOvenBinarySensor(AnovaOvenDescriptionEntity, SensorEntity):
    """A sensor using Anova coordinator."""

    entity_description: AnovaOvenBinarySensorEntityDescription

    @property
    def native_value(self) -> StateType:
        """Return the state."""
        if state := self.coordinator.devices[self.cooker_id].state:
            is_on = self.entity_description.value_fn(state)
            match self.entity_description.format_type:
                case FormatType.OnOff:
                    return "on" if is_on else "off"
                case FormatType.YesNo:
                    return "yes" if is_on else "no"
        return None
