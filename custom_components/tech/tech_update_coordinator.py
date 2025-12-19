"""Example integration using DataUpdateCoordinator."""

from datetime import timedelta
import logging
from typing import Any

import async_timeout

from custom_components.tech.tech import (Tech, TechError)
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.update_coordinator import (
    DataUpdateCoordinator,
    UpdateFailed,
)

_LOGGER = logging.getLogger(__name__)


class TechUpdateCoordinator(DataUpdateCoordinator):
    """My custom coordinator."""

    def __init__(self, hass, config_entry, tech_api : Tech, udid):
        """Initialize my coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            # Name of the data. For logging purposes.
            name="My sensor",
            config_entry=config_entry,
            # Polling interval. Will only be polled if there are subscribers.
            update_interval=timedelta(seconds=30),
            # Set always_update to `False` if the data returned from the
            # api can be compared via `__eq__` to avoid duplicate updates
            # being dispatched to listeners
            always_update=True
        )
        self.tech_api = tech_api
        self.udid: str = udid

    def get_data(self) -> dict[str, Any]:
        """Return the latest data."""
        return self.data
    
    def get_zones(self) -> dict[str, Any]:
        """Return the latest zones data."""
        return self.data["zones"]
    
    def get_menu(self) -> dict[str, Any]:
        """Return the latest menu data."""
        return self.data["menu"]

    async def _async_update_data(self):
        """Fetch data from API endpoint.

        This is the place to pre-process the data to lookup tables
        so entities can quickly look up their data.
        """
        try:
            # Note: asyncio.TimeoutError and aiohttp.ClientError are already
            # handled by the data update coordinator.
            async with async_timeout.timeout(10):
                # Grab active context variables to limit data required to be fetched from API
                # Note: using context is not required if there is no need or ability to limit
                # data retrieved from API.
                _LOGGER.debug("getting data for module %s", self.udid)
                zones = await self.tech_api.get_module_zones(self.udid)
                menu = await self.tech_api.get_module_menu(self.udid, "mu")

                if menu["status"] != "success":
                    _LOGGER.warning("Failed to get menu config for Tech module %s, response: %s", self.udid, menu)
                    menu = None

                self.data = {"zones": zones, "menu": menu}                            
        except TechError as err:
            # Raising ConfigEntryAuthFailed will cancel future updates
            # and start a config flow with SOURCE_REAUTH (async_step_reauth)            
            raise UpdateFailed(f"Error communicating with API: {err}")  
        except Exception as err:
            raise ConfigEntryAuthFailed from err