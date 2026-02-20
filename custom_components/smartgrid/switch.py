"""Platform for sensor integration."""
import logging
from collections import defaultdict
from dataclasses import dataclass
from typing import Callable, Any
from datetime import datetime, timedelta

from homeassistant.components.switch import (
    SwitchEntity, SwitchEntityDescription,
)
from homeassistant.core import HomeAssistant

from . import SmartGridCoordinator
from .coordinator import load_switch_values, save_switch_values
from .dataclass import SmartGridDataSchedule
from .entity import SmartGridEntity
from .const import DOMAIN, DATA_SWITCHES, SMARTGRID_ENABLED, DATA_SCHEDULE, SWITCH_PREFIX

_LOGGER = logging.getLogger(__name__)


@dataclass(frozen=True)
class SmartGridSwitchDescription(SwitchEntityDescription):
    state: Callable[[defaultdict], Any] | None = None


SWITCHES: list[SmartGridSwitchDescription] = [
    SmartGridSwitchDescription(
        key=SMARTGRID_ENABLED,
        name="Enabled",
    )
]

schedule = dict[str, bool]


def get_charging_periods() -> list[SmartGridSwitchDescription]:
    def count(start=0, step=30):
        n = start
        while n < 2880:
            yield n
            n += step

    today = 1
    t_name = "today"
    t_key = ""
    dt = datetime(2025, 1, today, 0, 0)
    switches = []

    for mins in count(start=0, step=30):
        period = dt + timedelta(minutes=mins)
        if period.day != today:
            t_name = "tomorrow"
            t_key = "t"
        h = str(period.hour).zfill(2)
        m = str(period.minute).zfill(2)
        switches.append(
            SmartGridSwitchDescription(
                key=f"{SWITCH_PREFIX}{t_key}{h}{m}",
                name=f"Charge {t_name} {h}:{m}",
                # state=lambda data: data[DATA_SWITCHES][f"charging_period_{t_key}{h}{m}"]==True
            ),
        )
    return switches


async def async_setup_entry(hass: HomeAssistant, entry, async_add_entities) -> None:
    """Set up the SmartGrid switch entities."""

    coordinator: SmartGridCoordinator = hass.data[DOMAIN][entry.entry_id]
    if coordinator.data is not None:
        async_add_entities(
            SmartGridSwitch(
                coordinator=coordinator,
                entity_description=entity_description,
            )
            for entity_description in SWITCHES + get_charging_periods()
        )


class SmartGridSwitch(SmartGridEntity, SwitchEntity):
    entity_description: SmartGridSwitchDescription
    _attr_has_entity_name = True

    def __init__(
            self,
            *,
            coordinator: SmartGridCoordinator,
            entity_description: SmartGridSwitchDescription
    ) -> None:
        super().__init__(coordinator=coordinator)
        self.entity_description = entity_description
        self.entity_id = f"switch.{DOMAIN}_{entity_description.key}"
        self._attr_unique_id = f"{DOMAIN}_switch_{entity_description.key}"
        self._attr_name = entity_description.name

    def value_from_switches(self, key: str):
        data = self.coordinator.data[DATA_SWITCHES]
        return key in data

    def value_from_schedule(self, key: str):
        now = datetime.now().astimezone()

        def get_prefix(d: int):
            if d == now.day:
                return SWITCH_PREFIX
            return SWITCH_PREFIX + "t"

        data: SmartGridDataSchedule = self.coordinator.data[DATA_SCHEDULE]
        is_on = [
            get_prefix(dt.day) + str(dt.hour).zfill(2) + str(dt.minute).zfill(2)
            for dt in data.force_charge
        ]
        return key in is_on

    def is_smartgrid_enabled(self) -> bool:
        return self.value_from_switches(SMARTGRID_ENABLED)

    @property
    def is_on(self) -> bool:
        key = self.entity_description.key
        if key == SMARTGRID_ENABLED:
            return self.is_smartgrid_enabled()
        if self.is_smartgrid_enabled():
            return self.value_from_schedule(key)
        else:
            return self.value_from_switches(key)

    async def async_turn_on(self, **kwargs: object) -> None:
        await self.set_value(True)

    async def async_turn_off(self, **kwargs: object) -> None:
        await self.set_value(False)

    async def set_value(self, turn_on: bool):
        key = self.entity_description.key
        # will only work for the enabled switch or only if this switch is not enabled
        if key == SMARTGRID_ENABLED or not self.is_smartgrid_enabled():
            _LOGGER.info(f"Setting {key} to {turn_on}")
            data: list[str] = await self.hass.async_add_executor_job(load_switch_values)
            if turn_on and not key in data:
                data.append(key)
            elif key in data:
                data.remove(key)
            await self.hass.async_add_executor_job(save_switch_values, data)
            await self.coordinator.async_refresh()
        else:
            _LOGGER.info(f"Bypass setting {key} to {turn_on} - SmartGrid Enabled")
