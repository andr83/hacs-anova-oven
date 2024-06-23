"""Support for Anova Sensors."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field

from homeassistant import config_entries
from homeassistant.components.climate.const import ClimateEntityFeature
from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.const import (
    CONF_TEMPERATURE_UNIT,
    PERCENTAGE,
    UnitOfPower,
    UnitOfTime,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import StateType

from .const import DOMAIN, AnovaUnitOfTemperature
from .coordinator import AnovaCoordinator
from .entity import AnovaOvenDescriptionEntity
from .precision_oven import APOSensor


@dataclass(frozen=True)
class AnovaOvenSensorEntityDescriptionMixin:
    """Describes the mixin variables for anova sensors."""

    value_fn: Callable[[APOSensor], float | int | str]
    extra_state_attributes: dict[str, Callable[[APOSensor], float | int | str]] = field(
        default_factory=dict
    )


@dataclass(frozen=True)
class AnovaOvenSensorEntityDescription(
    SensorEntityDescription, AnovaOvenSensorEntityDescriptionMixin
):
    """Describes a Anova sensor."""


def sensor_descriptions(
    unit_of_temperature: AnovaUnitOfTemperature,
) -> list[SensorEntityDescription]:  # noqa: D103
    def temp_getter(x):
        return x.celsius

    match unit_of_temperature:
        case AnovaUnitOfTemperature.FAHRENHEIT:

            def temp_getter(x):
                return x.fahrenheit

    return [
        AnovaOvenSensorEntityDescription(
            key="mode",
            translation_key="mode",
            value_fn=lambda data: data.sensor.mode,
            extra_state_attributes={"raw_stages": lambda s: s.raw_stages},
        ),
        # AnovaOvenSensorEntityDescription(
        #     key="bulb_mode",
        #     translation_key="bulb_mode",
        #     value_fn=lambda data: data.sensor.nodes.temperature_bulbs.mode
        # ),
        AnovaOvenSensorEntityDescription(
            key="temperature",
            translation_key="temperature",
            native_unit_of_measurement=unit_of_temperature,
            device_class=SensorDeviceClass.TEMPERATURE,
            state_class=SensorStateClass.MEASUREMENT,
            value_fn=lambda data: temp_getter(
                data.sensor.nodes.temperature_bulbs.temperature
            ),
            extra_state_attributes={},
        ),
        AnovaOvenSensorEntityDescription(
            key="target_temperature",
            translation_key="target_temperature",
            native_unit_of_measurement=unit_of_temperature,
            device_class=SensorDeviceClass.TEMPERATURE,
            state_class=SensorStateClass.MEASUREMENT,
            value_fn=lambda data: temp_getter(
                data.sensor.nodes.temperature_bulbs.target_temperature
            ),
            extra_state_attributes={},
        ),
        AnovaOvenSensorEntityDescription(
            key="temperature_probe",
            translation_key="temperature_probe",
            native_unit_of_measurement=unit_of_temperature,
            device_class=SensorDeviceClass.TEMPERATURE,
            state_class=SensorStateClass.MEASUREMENT,
            value_fn=lambda data: temp_getter(
                data.sensor.nodes.temperature_probe.temperature
            )
            if data.sensor.nodes.temperature_probe
            and data.sensor.nodes.temperature_probe.temperature
            else None,
            extra_state_attributes={},
        ),
        AnovaOvenSensorEntityDescription(
            key="target_temperature_probe",
            translation_key="target_temperature_probe",
            native_unit_of_measurement=unit_of_temperature,
            device_class=SensorDeviceClass.TEMPERATURE,
            state_class=SensorStateClass.MEASUREMENT,
            value_fn=lambda data: temp_getter(
                data.sensor.nodes.temperature_probe.target_temperature
            )
            if data.sensor.nodes.temperature_probe
            and data.sensor.nodes.temperature_probe.target_temperature
            else None,
            extra_state_attributes={},
        ),
        AnovaOvenSensorEntityDescription(
            key="rear_watts",
            device_class=SensorDeviceClass.POWER,
            native_unit_of_measurement=UnitOfPower.WATT,
            state_class=SensorStateClass.MEASUREMENT,
            translation_key="rear_watts",
            value_fn=lambda data: data.sensor.nodes.rear_heating.watts,
            extra_state_attributes={},
        ),
        AnovaOvenSensorEntityDescription(
            key="bottom_watts",
            device_class=SensorDeviceClass.POWER,
            native_unit_of_measurement=UnitOfPower.WATT,
            state_class=SensorStateClass.MEASUREMENT,
            translation_key="bottom_watts",
            value_fn=lambda data: data.sensor.nodes.bottom_heating.watts,
            extra_state_attributes={},
        ),
        AnovaOvenSensorEntityDescription(
            key="top_watts",
            device_class=SensorDeviceClass.POWER,
            native_unit_of_measurement=UnitOfPower.WATT,
            state_class=SensorStateClass.MEASUREMENT,
            translation_key="top_watts",
            value_fn=lambda data: data.sensor.nodes.top_heating.watts,
            extra_state_attributes={},
        ),
        AnovaOvenSensorEntityDescription(
            key="fan_speed",
            device_class=SensorDeviceClass.POWER_FACTOR,
            native_unit_of_measurement=PERCENTAGE,
            state_class=SensorStateClass.MEASUREMENT,
            translation_key="fan_speed",
            value_fn=lambda data: data.sensor.nodes.fan_speed,
            extra_state_attributes={},
        ),
        AnovaOvenSensorEntityDescription(
            key="steam_generator_mode",
            translation_key="steam_generator_mode",
            value_fn=lambda data: data.sensor.nodes.steam_generator.mode,
            extra_state_attributes={},
        ),
        AnovaOvenSensorEntityDescription(
            key="relative_humidity",
            device_class=SensorDeviceClass.HUMIDITY,
            native_unit_of_measurement=PERCENTAGE,
            state_class=SensorStateClass.MEASUREMENT,
            translation_key="relative_humidity",
            value_fn=lambda data: data.sensor.nodes.steam_generator.relative_humidity,
            extra_state_attributes={},
        ),
        AnovaOvenSensorEntityDescription(
            key="target_humidity",
            device_class=SensorDeviceClass.HUMIDITY,
            native_unit_of_measurement=PERCENTAGE,
            state_class=SensorStateClass.MEASUREMENT,
            translation_key="target_humidity",
            value_fn=lambda data: data.sensor.nodes.steam_generator.target_humidity,
            extra_state_attributes={},
        ),
        AnovaOvenSensorEntityDescription(
            key="cook_time",
            state_class=SensorStateClass.TOTAL_INCREASING,
            native_unit_of_measurement=UnitOfTime.SECONDS,
            icon="mdi:clock-outline",
            translation_key="cook_time",
            device_class=SensorDeviceClass.DURATION,
            value_fn=lambda data: data.sensor.nodes.cook.seconds_elapsed,
            extra_state_attributes={},
        ),
        AnovaOvenSensorEntityDescription(
            key="timer",
            state_class=SensorStateClass.TOTAL_INCREASING,
            native_unit_of_measurement=UnitOfTime.SECONDS,
            icon="mdi:clock-outline",
            translation_key="timer",
            device_class=SensorDeviceClass.DURATION,
            value_fn=lambda data: data.sensor.nodes.timer.current,
            extra_state_attributes={},
        ),
        AnovaOvenSensorEntityDescription(
            key="timer_initial",
            state_class=SensorStateClass.TOTAL,
            native_unit_of_measurement=UnitOfTime.SECONDS,
            icon="mdi:clock-outline",
            translation_key="timer_initial",
            device_class=SensorDeviceClass.DURATION,
            value_fn=lambda data: data.sensor.nodes.timer.initial,
            extra_state_attributes={},
        ),
        AnovaOvenSensorEntityDescription(
            key="timer_mode",
            translation_key="timer_mode",
            value_fn=lambda data: data.sensor.nodes.timer.mode,
            extra_state_attributes={},
        ),
        AnovaOvenSensorEntityDescription(
            key="active_stage",
            state_class=SensorStateClass.MEASUREMENT,
            translation_key="active_stage",
            value_fn=lambda data: data.stages.active,
            extra_state_attributes={},
        ),
        AnovaOvenSensorEntityDescription(
            key="stages_count",
            state_class=SensorStateClass.MEASUREMENT,
            translation_key="stages_count",
            value_fn=lambda data: data.stages.count,
            extra_state_attributes={},
        ),
    ]


async def async_setup_entry(
    hass: HomeAssistant,
    entry: config_entries.ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Anova device."""
    coordinator: AnovaCoordinator = hass.data[DOMAIN][entry.entry_id]
    unit_of_temperature = AnovaUnitOfTemperature(
        entry.options.get(CONF_TEMPERATURE_UNIT, AnovaUnitOfTemperature.CELSIUS)
    )
    async_add_entities(
        AnovaOvenSensor(device[0], coordinator, description)
        for device in coordinator.devices.items()
        for description in sensor_descriptions(unit_of_temperature)
    )


class AnovaOvenSensor(AnovaOvenDescriptionEntity, SensorEntity):
    """A sensor using Anova coordinator."""

    entity_description: AnovaOvenSensorEntityDescription

    @property
    def supported_features(self):
        match self.native_unit_of_measurement:
            case AnovaUnitOfTemperature.CELSIUS:
                return ClimateEntityFeature.TARGET_TEMPERATURE
            case AnovaUnitOfTemperature.FAHRENHEIT:
                return ClimateEntityFeature.TARGET_HUMIDITY

    @property
    def native_value(self) -> StateType:
        """Return the state."""
        if state := self.coordinator.devices[self.cooker_id].state:
            if hasattr(self.entity_description, "extra_state_attributes"):
                for k, getter in self.entity_description.extra_state_attributes.items():
                    self._attr_extra_state_attributes[k] = getter(state)
            return self.entity_description.value_fn(state)
        return None
