"""Base entity for the Anova integration."""
from __future__ import annotations

from homeassistant.helpers.entity import Entity, EntityDescription
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.helpers.device_registry import DeviceInfo

from .coordinator import AnovaCoordinator
from .const import DOMAIN

class AnovaOvenEntity(CoordinatorEntity[AnovaCoordinator], Entity):
    """Defines an Anova entity."""

    _attr_has_entity_name = True

    def __init__(self, cooker_id: str, coordinator: AnovaCoordinator) -> None:
        """Initialize the Anova entity."""
        super().__init__(coordinator)
        self.cooker_id = cooker_id

    @property
    def device_info(self) -> DeviceInfo:
        if device := self.coordinator.devices.get(self.cooker_id):
            return DeviceInfo(
                identifiers={(DOMAIN, self.cooker_id)},
                name="Anova Precision Oven",
                manufacturer="Anova",
                model="Precision Oven",
                sw_version=device.state.sensor.firmware_version if device.state else '0.0.0',
            )


class AnovaOvenDescriptionEntity(AnovaOvenEntity):
    """Defines an Anova entity that uses a description."""

    def __init__(
        self,
        cooker_id: str,
        coordinator: AnovaCoordinator,
        description: EntityDescription
    ) -> None:
        """Initialize the entity and declare unique id based on description key."""
        super().__init__(cooker_id, coordinator)
        self.entity_description = description
        self._attr_unique_id = f"{self.cooker_id}_{description.key}"
