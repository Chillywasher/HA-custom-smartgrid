import logging
import pickle
import os

from collections import defaultdict
from datetime import datetime, timedelta

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, DOMAIN
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from .controller import SmartGrid
from .const import DATA_SCHEDULE, DATA_LAST_UPDATED, DATA_SWITCHES, DATA_REPORT, SMARTGRID_DATA, SWITCH_PICKLE_FILE, \
    SWITCH_PREFIX, SMARTGRID_ENABLED, DATA_CHARGE_NOW
from .dataclass import SmartGridDataSchedule

_LOGGER = logging.getLogger(__name__)
MIDNIGHT_TASK = "midnight_"


def load_switch_values() -> list[str]:
    if os.path.exists(SWITCH_PICKLE_FILE):
        with open(SWITCH_PICKLE_FILE, "rb") as file:
            return pickle.load(file)
    else:
        return []


def save_switch_values(data: list[str]):
    with open(SWITCH_PICKLE_FILE, "wb") as file:
        pickle.dump(data, file)


class SmartGridCoordinator(DataUpdateCoordinator[defaultdict]):
    """SmartGrid Coordinator"""

    def __init__(
            self,
            hass: HomeAssistant,
            entry: ConfigEntry,
            controller: SmartGrid
    ) -> None:
        """Initialise the coordinator."""

        self.controller = controller
        self.hass = hass
        self.schedule_timestamp: datetime | None = None
        self.schedule: SmartGridDataSchedule | None = None
        self.report: dict | None = None
        self.switches: list[str] = []
        self.day_last_run_midnight_task: int = 0
        self.should_be_charging_now = False
        self.now = self.get_now()

        super().__init__(
            hass,
            _LOGGER,
            name=SMARTGRID_DATA,
            config_entry=entry,
            update_interval=timedelta(seconds=15)
        )

    async def _async_update_data(self) -> defaultdict | dict:

        self.now = self.get_now()

        # after midnight switch 'tomorrow' as 'today'
        if self.day_last_run_midnight_task != self.now.day:
            self.switches = await self.hass.async_add_executor_job(self.mignight_routine)
        else:
            self.switches = await self.hass.async_add_executor_job(load_switch_values)

        if not self.schedule_timestamp or self.now > self.schedule_timestamp + timedelta(minutes=10):
            data = await self.hass.async_add_executor_job(self.controller.main)

            if not data:
                _LOGGER.warning("Unable to obtain schedule data, will wait until "
                                "Octopus Enmergy integration can supply rates")
                return {}

            self.schedule = data[DATA_SCHEDULE]
            self.report = data[DATA_REPORT]
            self.schedule_timestamp = self.now
            _LOGGER.info("Schedule update finished, processed data: %s", self.schedule)

        self.should_be_charging_now = self.get_should_be_charging_now()

        return {
            DATA_CHARGE_NOW: self.should_be_charging_now,
            DATA_SCHEDULE: self.schedule,
            DATA_REPORT: self.report,
            DATA_SWITCHES: self.switches,
            DATA_LAST_UPDATED: self.schedule_timestamp
        }

    def mignight_routine(self) -> list[str]:
        """
        Changes anything that was set to run tomorrow to run today;
        Removes anything that was set to run 'today';
        Preserves SMARTGRID_ENABLED and MIDNIGHT_RUN_X items

        This will routine will always run on initialisation

        It will look for an item in the list named MIDNIGHT_RUN_X where X equals
        the day number the routine was last run.

        If it doens't find this item then the item will be created
        and added to the list so it doesn't run again

        If it does find the item then it will check the current day against the
        item X day and decide whether to run again

        Returns: [current switches turned on, SMARTGRID_ENABLED if on, MIDNIGHT_RUN_X]
        """

        run_today_key = MIDNIGHT_TASK + str(self.now.day)

        if not os.path.exists(SWITCH_PICKLE_FILE):

            # has never run before as file does not exist
            new_items = [run_today_key, SMARTGRID_ENABLED]
            save_switch_values(new_items)
            self.day_last_run_midnight_task = self.now.day
            return new_items

        else:
            current_items = load_switch_values()
            if not run_today_key in current_items:
                # runs when the current items does not contain the midnight item
                tomorrow_prefix = SWITCH_PREFIX + "_t"
                new_items = [
                    item.replace("_t", "_")
                    for item in current_items
                    if item.startswith(tomorrow_prefix)
                ]

                # transfer the eneabled key if present
                if SMARTGRID_ENABLED in current_items:
                    new_items.append(SMARTGRID_ENABLED)

                new_items.append(run_today_key)
                save_switch_values(new_items)
                self.day_last_run_midnight_task = self.now.day
                return new_items
            else:
                # runs when midnight task already run and HA restarted
                return current_items

    def get_should_be_charging_now(self) -> bool:
        cp = self.get_current_charging_period()
        if SMARTGRID_ENABLED in self.switches:
            return cp in self.schedule.force_charge
        else:
            time_string = str(cp.hour).zfill(2) + str(cp.minute).zfill(2)
            entity = f"{SWITCH_PREFIX}{time_string}"
            return entity in self.switches

    @staticmethod
    def get_current_charging_period() -> datetime:
        n = datetime.now().astimezone()
        if n.minute >= 30:
            m = 30
        else:
            m = 0
        return datetime(n.year, n.month, n.day, n.hour, m , 0 , 0)


    @staticmethod
    def get_now():
        d = datetime.now().astimezone()
        return datetime(d.year, d.month, d.day, d.hour, d.minute, d.second).astimezone()
