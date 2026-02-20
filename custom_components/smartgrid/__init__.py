"""The SmartGrid integration."""

from __future__ import annotations

import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant

from .coordinator import SmartGridCoordinator
from .controller import SmartGrid
from .const import DOMAIN, CONF_CURRENT_RATES_SENSOR, CONF_NEXT_DAY_RATES_SENSOR, CONF_BATTERY_SOC_SENSOR

_LOGGER = logging.getLogger(__name__)

_PLATFORMS: list[Platform] = [
    Platform.SENSOR,
    Platform.SWITCH,
    Platform.BINARY_SENSOR
]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    _LOGGER.info("This is the SmartGrid integration")

    smartgrid = SmartGrid(
        hass=hass,
        battery_soc_sensor=entry.data.get(CONF_BATTERY_SOC_SENSOR),
        current_rates_sensor=entry.data.get(CONF_CURRENT_RATES_SENSOR),
        next_day_rates_sensor=entry.data.get(CONF_NEXT_DAY_RATES_SENSOR)
    )

    smartgrid_coordinator = SmartGridCoordinator(
        hass=hass,
        controller=smartgrid,
        entry=entry,
    )

    await smartgrid_coordinator.async_config_entry_first_refresh()

    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = smartgrid_coordinator
    hass.data[DOMAIN]["controller"] = controller

    await hass.config_entries.async_forward_entry_setups(entry, _PLATFORMS)

    return True