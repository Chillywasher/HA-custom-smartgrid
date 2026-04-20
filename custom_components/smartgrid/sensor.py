from collections import defaultdict
from dataclasses import dataclass
from typing import Callable, Any
from datetime import datetime

from homeassistant.components.sensor import SensorEntity, SensorEntityDescription
from homeassistant.core import HomeAssistant
from homeassistant.helpers.typing import StateType

from .coordinator import SmartGridCoordinator
from .dataclass import SmartGridDataSchedule, Rate
from .entity import SmartGridEntity
from .const import DOMAIN, CHARGING_TIMES, DATA_LAST_UPDATED, DATA_SCHEDULE, CHARGING_PERIODS, DATA_SWITCHES, \
    SMARTGRID_ENABLED, SWITCH_PREFIX


@dataclass(frozen=True)
class SmartGridSensorDescription(SensorEntityDescription):
    state: Callable[[defaultdict], Any] | None = None
    format: Callable[[Any], Any] | None = None


def get_first_charging_period(data: tuple[bool, list, tuple[Rate, ...]]):
    date_format = "%a %H:%M"
    smartgrid_enabled = data[0]
    pickled_switches = data[1]
    rates = data[2]
    if smartgrid_enabled:
        if len(rates) > 0:
            rates_list = list(rates)
            rates_list.sort(key=lambda rate: rate.start)
            return datetime.strftime(rates_list[0].start, date_format)            
    else:
        if len(pickled_switches) > 0:
            periods = []
            for ps in pickled_switches:
                # in format, e.g. 'charging_period_t2130'
                if ps.startswith(SWITCH_PREFIX):
                    str_period: str = ps.replace(SWITCH_PREFIX, "")
                    now = datetime.now().astimezone()
                    day = now.day
                    if str_period.startswith("t"):
                        day += 1
                        str_period = str_period.replace("t", "")
                    assert len(str_period) == 4
                    hour = int(str_period[:2])
                    mins = int(str_period[2:])
                    period = datetime(now.year, now.month, day, hour, mins, 0)
                    periods.append(period)
            periods.sort()
            return datetime.strftime(periods[0], date_format)
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
                    state=lambda data: (
                        SMARTGRID_ENABLED in data[DATA_SWITCHES],
                        data[DATA_SWITCHES],
                        data[DATA_SCHEDULE].charging_periods
                    ),
                    format=lambda value: get_first_charging_period(value),
                ),
            ),
            ReportSensor(
                coordinator=coordinator,
                entity_description=SmartGridSensorDescription(
                    key=DATA_LAST_UPDATED,
                    name="Last Updated",
                    state=lambda data: data[DATA_LAST_UPDATED],
                    format=lambda value: datetime.strftime(value, "%a %H:%M:%S")
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
    def is_smartgrid_enabled(self):
        data = self.coordinator.data[DATA_SWITCHES]
        return SMARTGRID_ENABLED in data

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
            "last_updated": data[DATA_LAST_UPDATED],
            "report": data["report"]
        }

class ChargingTimesSensor(SmartGridSensor):

    @staticmethod
    def format_charging_periods(rates: tuple[Rate, ...]) -> list[str]:

        now = datetime.now().astimezone()
        periods = []
        for rate in rates:
            if rate.start.day == now.day + 1:
                prefix = "t"
            else:
                prefix = ""
            h = str(rate.start.hour).zfill(2)
            m = str(rate.start.minute).zfill(2)
            periods.append(prefix + h + m)
        return periods

    @property
    def extra_state_attributes(self):
        """Return entity specific state attributes."""
        data = self.coordinator.data
        schedule: SmartGridDataSchedule = data[DATA_SCHEDULE]
        periods = self.format_charging_periods(schedule.charging_periods)
        return {
            DATA_SCHEDULE: schedule,
            CHARGING_PERIODS: periods,
            DATA_LAST_UPDATED: data[DATA_LAST_UPDATED],
        }
