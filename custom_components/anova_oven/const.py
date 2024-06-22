"""Constants for the Anova Precision Oven integration."""

from enum import IntFlag, StrEnum

DOMAIN = "anova_oven"

PLATFORM = "android"
CONF_APP_KEY = "app_key"
CONF_REFRESH_TOKEN = "refresh_token"

EVENT_COOK_TARGET_REACHED = f"{DOMAIN}.cook_target_reached"


class AnovaUnitOfTemperature(StrEnum):
    """Temperature units."""

    CELSIUS = "°C"
    FAHRENHEIT = "°F"


class TemperatureEntityFeature(IntFlag):
    """Supported features of the climate entity."""

    CELSIUS = 1
    FAHRENHEIT = 2
