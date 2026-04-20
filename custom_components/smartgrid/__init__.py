"""The SmartGrid integration."""

from __future__ import annotations

import logging

from datetime import datetime

from .v2.smartgrid_v2 import SmartGridV2
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant


from .dataclass import Rate
from .coordinator import SmartGridCoordinator

from .const import DOMAIN, CONF_CURRENT_RATES_SENSOR, CONF_NEXT_DAY_RATES_SENSOR, CONF_BATTERY_SOC_SENSOR, \
    CONF_BATTERY_CAPACITY_SENSOR, CONF_BATTERY_MIN_SOC_SENSOR

_LOGGER = logging.getLogger(__name__)

_PLATFORMS: list[Platform] = [
    Platform.SENSOR,
    Platform.SWITCH,
    Platform.BINARY_SENSOR
]

async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    _LOGGER.info("This is the SmartGrid integration")

    def get_rates():
        # date_format = "%Y-%m-%dT%H:%M:%S%z"
        entity1 = entry.data.get(CONF_CURRENT_RATES_SENSOR)
        entity2 = entry.data.get(CONF_NEXT_DAY_RATES_SENSOR)
        today = hass.states.get(entity1).attributes.get("rates")
        tmmrw = hass.states.get(entity2).attributes.get("rates")
        rates = [
            Rate(
                start=rate["start"],
                end=rate["end"],
                value_inc_vat=rate["value_inc_vat"]
            )
            for rate in today + tmmrw
            if rate["end"] > datetime.now().astimezone()
        ]
        return tuple(rates)

    def get_soc() -> float:
        return float(
            hass.states.get(
                entry.data.get(CONF_BATTERY_SOC_SENSOR)
            ).state
        )

    def get_min_soc() -> float:
        return float(
            hass.states.get(
                entry.data.get(CONF_BATTERY_MIN_SOC_SENSOR)
            ).state
        )

    def get_battery_capacity() -> float:
        return float(
            hass.states.get(
                entry.data.get(CONF_BATTERY_CAPACITY_SENSOR)
            ).state
        )

    # smartgrid = SmartGrid(
    #     hass=hass,
    #     battery_soc_sensor=entry.data.get(CONF_BATTERY_SOC_SENSOR),
    #     battery_capacity_sensor=entry.data.get(CONF_BATTERY_CAPACITY_SENSOR),
    #     current_rates_sensor=entry.data.get(CONF_CURRENT_RATES_SENSOR),
    #     next_day_rates_sensor=entry.data.get(CONF_NEXT_DAY_RATES_SENSOR)
    # )

    controller = SmartGridV2(
        get_battery_capacity=get_battery_capacity,
        get_battery_soc=get_soc,
        get_battery_min_soc=get_min_soc,
        get_rates=get_rates,
    )

    smartgrid_coordinator = SmartGridCoordinator(
        hass=hass,
        controller=controller,
        entry=entry,
    )

    await smartgrid_coordinator.async_config_entry_first_refresh()

    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = smartgrid_coordinator
    hass.data[DOMAIN]["controller"] = controller

    await hass.config_entries.async_forward_entry_setups(entry, _PLATFORMS)

    return True