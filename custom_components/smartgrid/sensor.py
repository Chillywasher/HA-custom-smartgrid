from collections import defaultdict
from dataclasses import dataclass
from typing import Callable, Any
from datetime import datetime

from homeassistant.components.sensor import SensorEntity, SensorEntityDescription
from homeassistant.core import HomeAssistant
from homeassistant.helpers.typing import StateType

from .coordinator import SmartGridCoordinator
from .dataclass import SmartGridDataSchedule
from .entity import SmartGridEntity
from .const import DOMAIN, CHARGING_TIMES, LAST_UPDATED, SCHEDULE, CHARGING_PERIODS


@dataclass(frozen=True)
class SmartGridSensorDescription(SensorEntityDescription):
    state: Callable[[defaultdict], Any] | None = None
    format: Callable[[Any], Any] | None = None


def get_first_charging_period(value: list[datetime]):
    if len(value) > 0:
        return value[0]
    else:
        return "Not scheduled"

async def async_setup_entry(hass: HomeAssistant, entry, async_add_entities) -> None:
    """Set up the SmartGrid sensor entities."""
    coordinator: SmartGridCoordinator = hass.data[DOMAIN][entry.entry_id]
    if coordinator.data is not None:
        async_add_entities([
            ChargingTimesSensor(
                coordinator=coordinator,
                entity_description=SmartGridSensorDescription(
                    key=CHARGING_TIMES,
                    name="Charging Times",
                    state=lambda data: data[SCHEDULE].force_charge,
                    format=lambda value: get_first_charging_period(value),
                ),
            ),
            ReportSensor(
                coordinator=coordinator,
                entity_description=SmartGridSensorDescription(
                    key=LAST_UPDATED,
                    name="Last Updated",
                    state=lambda data: data[LAST_UPDATED],
                )
            ),
            ]
        )

class SmartGridSensor(SmartGridEntity, SensorEntity):

    entity_description: SmartGridSensorDescription
    _attr_has_entity_name = True

    def __init__(
            self,
            *,
            coordinator: SmartGridCoordinator,
            entity_description: SmartGridSensorDescription
    ) -> None:
        super().__init__(coordinator=coordinator)

        self.entity_description = entity_description
        self.entity_id = f"sensor.{DOMAIN}_{entity_description.key}"
        self._attr_unique_id = f"{DOMAIN}_sensor_{entity_description.key}"
        self._attr_name = entity_description.name

    @property
    def icon(self) -> str | None:
        if self.entity_description.icon:
            return self.entity_description.icon
        return None

    @property
    def native_value(self) -> StateType:
        if self.entity_description.state is None:
            return None
        value = self.entity_description.state(self.coordinator.data)
        if self.entity_description.format is not None:
            value = self.entity_description.format(value)
        return value


class ReportSensor(SmartGridSensor):

    @property
    def extra_state_attributes(self):
        """Return entity specific state attributes."""
        data = self.coordinator.data
        return {
            "report": data["report"]
        }

class ChargingTimesSensor(SmartGridSensor):

    @staticmethod
    def format_charging_periods(times: list[datetime]) -> list[str]:
        now = datetime.now()
        def format_t(t: datetime):
            if t.day == now.day+1:
                prefix = "t"
            else:
                prefix = ""
            h = str(t.hour).zfill(2)
            m = str(t.minute).zfill(2)
            return prefix + h + m
        return [format_t(t) for t in times]

    @property
    def extra_state_attributes(self):
        """Return entity specific state attributes."""
        data = self.coordinator.data
        schedule: SmartGridDataSchedule = data[SCHEDULE]
        return {
            SCHEDULE: schedule,
            CHARGING_PERIODS: self.format_charging_periods(schedule.force_charge),
            LAST_UPDATED: data[LAST_UPDATED],
        }
