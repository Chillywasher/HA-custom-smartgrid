from __future__ import annotations

import logging

from datetime import datetime

from homeassistant.core import State
from homeassistant.helpers.restore_state import RestoreEntity
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .coordinator import SmartGridCoordinator
from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)


class SmartGridEntity(CoordinatorEntity[SmartGridCoordinator], RestoreEntity):

    last_updated: datetime | None = None
    restored_state: State | None = None

    @property
    def device_info(self) -> dict[str, object]:
        """Return the device_info of the device."""
        return {
            "identifiers": {(DOMAIN, "abcdefg")},
            "name": "SmartGrid",
        }
