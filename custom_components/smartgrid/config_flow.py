"""Config flow for the SmartGrid integration."""

from __future__ import annotations

import logging
from typing import Any

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
import homeassistant.helpers.config_validation as cv

from .const import DOMAIN, CONF_CURRENT_RATES_SENSOR, CONF_NEXT_DAY_RATES_SENSOR, CONF_BATTERY_SOC_SENSOR, \
    CONF_BATTERY_CAPACITY_SENSOR, CONF_BATTERY_MIN_SOC_SENSOR

_LOGGER = logging.getLogger(__name__)


DEV_SOC = "sensor.foxcloud_battery_soc"
DEV_MIN_SOC = "sensor.foxcloud_battery_min_soc"
DEV_CURRENT_RATES = "event.octopus_energy_electricity_21e1037308_1610002038466_current_day_rates"
DEV_NEXT_RATES = "event.octopus_energy_electricity_21e1037308_1610002038466_next_day_rates"
DEV_CAPACITY = "sensor.foxcloud_battery_capacity_remaining"

STEP_USER_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_BATTERY_SOC_SENSOR, default=DEV_SOC): cv.string,
        vol.Required(CONF_BATTERY_MIN_SOC_SENSOR, default=DEV_MIN_SOC): cv.string,
        vol.Required(CONF_BATTERY_CAPACITY_SENSOR, default=DEV_CAPACITY): cv.string,
        vol.Required(CONF_CURRENT_RATES_SENSOR, default=DEV_CURRENT_RATES): cv.string,
        vol.Required(CONF_NEXT_DAY_RATES_SENSOR, default=DEV_NEXT_RATES): cv.string,
    }
)

async def validate_input(hass: HomeAssistant, data: dict[str, Any]) -> dict[str, Any]:

    current_rates = hass.states.get(data[CONF_CURRENT_RATES_SENSOR])
    next_day_rates = hass.states.get(data[CONF_NEXT_DAY_RATES_SENSOR])
    battery_soc = hass.states.get(data[CONF_BATTERY_SOC_SENSOR])
    battery_min_soc = hass.states.get(data[CONF_BATTERY_MIN_SOC_SENSOR])
    battery_capacity = hass.states.get(data[CONF_BATTERY_CAPACITY_SENSOR])

    # TODO: Check that the uptodate rates have been populated inside the sensors

    if not current_rates:
        raise CannotConnectToCurrentRates

    if not next_day_rates:
        raise CannotConnectToNextDayRates

    if not battery_soc:
        raise CannotConnectToBatterySoc

    if not battery_min_soc:
        raise CannotConnectToBatteryMinSoc

    if not battery_capacity:
        raise CannotConnectToBatteryCapacity

    return {
        "title": "SmartGrid",
        "unique_id": "abcdefg"
    }

class SmartGridConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for SmartGrid."""

    VERSION = 1

    async def async_step_user(self, user_input: dict[str, Any] | None = None):
        """Handle the initial step."""
        errors: dict[str, str] = {}
        if user_input is not None:
            try:
                info = await validate_input(self.hass, user_input)
                _LOGGER.info(info)

                unique_id = info["unique_id"]
                await self.async_set_unique_id(unique_id)

            except CannotConnectToCurrentRates:
                errors["base"] = "cannot_connect_current_rates"
            except CannotConnectToNextDayRates:
                errors["base"] = "cannot_connect_next_day_rates"
            except CannotConnectToBatterySoc:
                errors["base"] = "cannot_connect_battery_soc"
            except CannotConnectToBatteryMinSoc:
                errors["base"] = "cannot_connect_battery_min_soc"
            except CannotConnectToBatteryCapacity:
                errors["base"] = "cannot_connect_battery_capacity"
            except CannotConnect:
                errors["base"] = "cannot_connect"
            except InvalidAuth:
                errors["base"] = "invalid_auth"
            except Exception:
                _LOGGER.exception("Unexpected exception")
                errors["base"] = "unknown"
            else:
                return self.async_create_entry(title=info["title"], data=user_input)

        return self.async_show_form(
            step_id="user", data_schema=STEP_USER_DATA_SCHEMA, errors=errors
        )

class CannotConnectToBatteryMinSoc(HomeAssistantError):
    """Error to indicate we cannot connect."""
    pass


class CannotConnectToBatterySoc(HomeAssistantError):
    """Error to indicate we cannot connect."""
    pass


class CannotConnectToBatteryCapacity(HomeAssistantError):
    """Error to indicate we cannot connect."""
    pass


class CannotConnectToCurrentRates(HomeAssistantError):
    """Error to indicate we cannot connect."""
    pass


class CannotConnectToNextDayRates(HomeAssistantError):
    """Error to indicate we cannot connect."""
    pass


class CannotConnect(HomeAssistantError):
    """Error to indicate we cannot connect."""
    pass


class InvalidAuth(HomeAssistantError):
    """Error to indicate there is invalid auth."""
    pass
