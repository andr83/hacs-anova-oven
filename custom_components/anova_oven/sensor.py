"""Support for Anova Sensors."""
from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from anova_wifi import APCUpdateSensor

from homeassistant import config_entries
from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.const import PERCENTAGE, UnitOfPower, UnitOfTemperature, UnitOfTime
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import StateType

from .const import DOMAIN
from .entity import AnovaOvenDescriptionEntity
from .coordinator import AnovaCoordinator
from .precision_oven import APOSensor


@dataclass(frozen=True)
class AnovaOvenSensorEntityDescriptionMixin:
    """Describes the mixin variables for anova sensors."""

    value_fn: Callable[[APOSensor], float | int | str]


@dataclass(frozen=True)
class AnovaOvenSensorEntityDescription(
    SensorEntityDescription, AnovaOvenSensorEntityDescriptionMixin
):
    """Describes a Anova sensor."""


SENSOR_DESCRIPTIONS: list[SensorEntityDescription] = [
    AnovaOvenSensorEntityDescription(
        key="mode",
        translation_key="mode",
        value_fn=lambda data: data.sensor.mode
    ),
    # AnovaOvenSensorEntityDescription(
    #     key="bulb_mode",
    #     translation_key="bulb_mode",
    #     value_fn=lambda data: data.sensor.nodes.temperature_bulbs.mode
    # ),
    AnovaOvenSensorEntityDescription(
        key="temperature",
        translation_key="temperature",
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda data: data.sensor.nodes.temperature_bulbs.temperature
    ),
    AnovaOvenSensorEntityDescription(
        key="target_temperature",
        translation_key="target_temperature",
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda data: data.sensor.nodes.temperature_bulbs.target_temperature
    ),
    AnovaOvenSensorEntityDescription(
        key="rear_watts",
        device_class=SensorDeviceClass.POWER,
        native_unit_of_measurement=UnitOfPower.WATT,
        state_class=SensorStateClass.MEASUREMENT,
        translation_key="rear_watts",
        value_fn=lambda data: data.sensor.nodes.rear_heating.watts
    ),
    AnovaOvenSensorEntityDescription(
        key="bottom_watts",
        device_class=SensorDeviceClass.POWER,
        native_unit_of_measurement=UnitOfPower.WATT,
        state_class=SensorStateClass.MEASUREMENT,
        translation_key="bottom_watts",
        value_fn=lambda data: data.sensor.nodes.bottom_heating.watts
    ),
    AnovaOvenSensorEntityDescription(
        key="top_watts",
        device_class=SensorDeviceClass.POWER,
        native_unit_of_measurement=UnitOfPower.WATT,
        state_class=SensorStateClass.MEASUREMENT,
        translation_key="top_watts",
        value_fn=lambda data: data.sensor.nodes.top_heating.watts
    ),
    AnovaOvenSensorEntityDescription(
        key="fan_speed",
        device_class=SensorDeviceClass.POWER_FACTOR,
        native_unit_of_measurement=PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        translation_key="fan_speed",
        value_fn=lambda data: data.sensor.nodes.fan_speed
    ),
    AnovaOvenSensorEntityDescription(
        key="steam_generator_mode",
        translation_key="steam_generator_mode",
        value_fn=lambda data: data.sensor.nodes.steam_generator.mode
    ),
    AnovaOvenSensorEntityDescription(
        key="relative_humidity",
        device_class=SensorDeviceClass.HUMIDITY,
        native_unit_of_measurement=PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        translation_key="relative_humidity",
        value_fn=lambda data: data.sensor.nodes.steam_generator.relative_humidity
    ),
    AnovaOvenSensorEntityDescription(
        key="target_humidity",
        device_class=SensorDeviceClass.HUMIDITY,
        native_unit_of_measurement=PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        translation_key="target_humidity",
        value_fn=lambda data: data.sensor.nodes.steam_generator.target_humidity
    ),
    AnovaOvenSensorEntityDescription(
        key="cook_time",
        state_class=SensorStateClass.TOTAL_INCREASING,
        native_unit_of_measurement=UnitOfTime.SECONDS,
        icon="mdi:clock-outline",
        translation_key="cook_time",
        device_class=SensorDeviceClass.DURATION,
        value_fn=lambda data: data.sensor.nodes.cook.seconds_elapsed
    ),
    AnovaOvenSensorEntityDescription(
        key="timer",
        state_class=SensorStateClass.TOTAL_INCREASING,
        native_unit_of_measurement=UnitOfTime.SECONDS,
        icon="mdi:clock-outline",
        translation_key="timer",
        device_class=SensorDeviceClass.DURATION,
        value_fn=lambda data: data.sensor.nodes.timer.current
    ),
    AnovaOvenSensorEntityDescription(
        key="timer_initial",
        state_class=SensorStateClass.TOTAL,
        native_unit_of_measurement=UnitOfTime.SECONDS,
        icon="mdi:clock-outline",
        translation_key="timer_initial",
        device_class=SensorDeviceClass.DURATION,
        value_fn=lambda data: data.sensor.nodes.timer.initial
    ),
    AnovaOvenSensorEntityDescription(
        key="timer_mode",
        translation_key="timer_mode",
        value_fn=lambda data: data.sensor.nodes.timer.mode
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
        AnovaOvenSensor(device[0], coordinator, description)
        for device in coordinator.devices.items()
        for description in SENSOR_DESCRIPTIONS
    )


class AnovaOvenSensor(AnovaOvenDescriptionEntity, SensorEntity):
    """A sensor using Anova coordinator."""

    entity_description: AnovaOvenSensorEntityDescription

    @property
    def native_value(self) -> StateType:
        """Return the state."""
        if state := self.coordinator.devices[self.cooker_id].state:
            return self.entity_description.value_fn(state)
        return None
