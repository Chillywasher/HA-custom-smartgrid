import logging
from collections import defaultdict
from datetime import datetime, timedelta

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from .controller import SmartGrid
from ..foxcloud.const import SCHEDULE

_LOGGER = logging.getLogger(__name__)


class SmartGridCoordinator(DataUpdateCoordinator[defaultdict]):
    """SmartGrid Coordinator"""

    def __init__(
            self,
            hass: HomeAssistant,
            entry: ConfigEntry,
            controller: SmartGrid
    ) -> None:
        """Initialize the coordinator."""

        self.controller = controller
        self.hass = hass

        super().__init__(
            hass,
            _LOGGER,
            name="smartgrid_data",
            config_entry=entry,
            update_interval=timedelta(minutes=10)
        )

    async def _async_update_data(self) -> defaultdict | dict:
        data = await self.hass.async_add_executor_job(self.controller.main)
        schedule = data[SCHEDULE]
        report = data["report"]
        _LOGGER.info("Update finished, processed data: %s", schedule)
        return {
            "schedule": schedule,
            "report": report,
            "last_updated": datetime.now()
        }
