"""Platform for sensor integration."""
import logging

from collections import defaultdict
from dataclasses import dataclass
from typing import Callable, Any

from homeassistant.components.binary_sensor import BinarySensorEntityDescription, BinarySensorEntity
from homeassistant.components.binary_sensor import DOMAIN as COMPONENT
from homeassistant.core import HomeAssistant

from .entity import SmartGridEntity
from .const import (
    DOMAIN, DATA_CHARGE_NOW
)
from .coordinator import SmartGridCoordinator


_LOGGER = logging.getLogger(__name__)



@dataclass(frozen=True)
class SmartGridBinarySensorDescription(BinarySensorEntityDescription):
    state: Callable[[defaultdict], Any] | None = None
    icon_on: str | None = None
    icon_off: str | None = None


BINARY_SENSORS: tuple[SmartGridBinarySensorDescription, ...] = (
    SmartGridBinarySensorDescription(
        key=DATA_CHARGE_NOW,
        name="Should Be Charging Now",
        state=lambda data: data[DATA_CHARGE_NOW],
    ),
)


async def async_setup_entry(hass: HomeAssistant, entry, async_add_entities) -> None:
    """Set up the SmartGrid binary sensor entities."""
    coordinator: SmartGridCoordinator = hass.data[DOMAIN][entry.entry_id]
    if coordinator.data is not None:
        async_add_entities(
            SmartGridBinarySensor(
                coordinator=coordinator,
                entity_description=entity_description,
            )
            for entity_description in BINARY_SENSORS
        )


class SmartGridBinarySensor(SmartGridEntity, BinarySensorEntity):
    entity_description: SmartGridBinarySensorDescription
    _attr_has_entity_name = True

    def __init__(
            self,
            *,
            coordinator: SmartGridCoordinator,
            entity_description: SmartGridBinarySensorDescription
    ) -> None:
        super().__init__(
            coordinator=coordinator
        )
        self.entity_description = entity_description
        self.entity_id = f"{COMPONENT}.{DOMAIN}_{entity_description.key}"
        self._attr_unique_id = f"{DOMAIN}_{COMPONENT}_{entity_description.key}"
        self._attr_name = entity_description.name
        self.data = coordinator.data

    @property
    def icon(self) -> str | None:
        if self.is_on:
            if self.entity_description.icon_on:
                return self.entity_description.icon_on
        else:
            if self.entity_description.icon_off:
                return self.entity_description.icon_off
        return None

    @property
    def is_on(self) -> bool | None:
        if self.entity_description.state is None:
            return None
        return self.entity_description.state(self.coordinator.data)


