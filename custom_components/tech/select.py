"""Support for Tech HVAC system."""
from __future__ import annotations

import logging
from typing import Any

from custom_components.tech.tech_update_coordinator import TechUpdateCoordinator

from homeassistant.components.select import SelectEntity

from homeassistant.helpers.update_coordinator import CoordinatorEntity

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import (HomeAssistant, callback)
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN
from .tech import Tech

_LOGGER = logging.getLogger(__name__)

DEFAULT_PRESETS = ["Normalny", "Urlop", "Ekonomiczny", "Komfortowy"]
CHANGE_PRESET = "Oczekiwanie na zmianę"


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> bool:
    """Set up Tech climate based on config_entry."""
    api: Tech = hass.data[DOMAIN][entry.entry_id]
    coordinator: TechUpdateCoordinator = hass.data[DOMAIN][entry.entry_id]["coordinator"]
    
    try:
        async_add_entities(
            [TechHub(entry.data["module"], coordinator, api)]
        )

        return True
    except Exception as ex:
        _LOGGER.error("Failed to set up Tech climate: %s", ex)
        return False

class TechHub(CoordinatorEntity, SelectEntity):    
    _attr_options: list[str] = DEFAULT_PRESETS
    _attr_current_option: str | None = None

    def __init__(self, hub, coordinator, api: Tech) -> None:
        """Initialize the Tech Hub device."""
        self._api = api
        self._udid = coordinator.udid
        self._id = coordinator.udid
        
        # Set unique_id first as it's required for entity registry
        self._attr_unique_id = self._udid
        self._attr_device_info = {
            "identifiers": {(DOMAIN, self._attr_unique_id)},
            "name": hub["name"],
            "manufacturer": "Tech",
        }

        super().__init__(coordinator, context=self._udid)
        
        # Initialize attributes that will be updated
        self._attr_name: str | None = hub["name"]
        
        self.update_properties(coordinator.get_menu())
        
    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""        
        _LOGGER.debug("Coordinator update for hub %s", self._attr_name)
        self.update_properties(self.coordinator.get_menu())
        self.async_write_ha_state()

    def update_properties(self, device_menu_config: dict[str, Any] | None) -> None:
        heating_mode = self.get_heating_mode_from_menu_config(device_menu_config) if device_menu_config else None
        _LOGGER.debug("Updating heating mode for hub %s: %s", self._attr_name, heating_mode)

        if heating_mode is not None:            
            if heating_mode["duringChange"] == "t":
                _LOGGER.debug("Preset mode change in progress for %s", self._attr_name)
                self._attr_options = [CHANGE_PRESET]
                self._attr_current_option = CHANGE_PRESET
                _LOGGER.debug("Current preset mode for %s: %s", self._attr_name, self._attr_current_option)
            else:
                self._attr_options = DEFAULT_PRESETS
                heating_mode_id = heating_mode["params"]["value"]
                self._attr_current_option = self.map_heating_mode_id_to_name(heating_mode_id)
                _LOGGER.debug("Current preset mode for %s: %s", self._attr_name, self._attr_current_option)
        else:
            _LOGGER.warning("Heating mode menu not found for Tech hub %s", self._attr_name)
    
    async def async_select_option(self, option: str) -> None:
        try:
            if self._attr_current_option == CHANGE_PRESET:
                _LOGGER.debug("Preset mode change already in progress for %s", self._attr_name)
                return
            
            preset_mode_id = DEFAULT_PRESETS.index(option)
            await self._api.set_module_menu(
                self._udid,
                "mu",
                1000,
                preset_mode_id
            )

            self._attr_options = [CHANGE_PRESET]
            self._attr_current_option = CHANGE_PRESET

            await self.coordinator.async_request_refresh()
        except Exception as ex:
            _LOGGER.error(
                "Failed to set preset mode for %s to %s: %s",
                self._attr_name,
                option,
                ex
            )

    def get_heating_mode_from_menu_config(self, menu_config: dict[str, Any]) -> dict[str, Any] | None:
        """Get current preset mode from menu config."""
        element = None
        heating_mode_menu_id = 1000
        for e in menu_config["elements"]:
            if e["id"] == heating_mode_menu_id:
                element = e
                break   
        return element
    
    def map_heating_mode_id_to_name(self, heating_mode_id) -> str:
        """Map heating mode id to preset mode name."""
        mapping = {
            0: "Normalny",
            1: "Urlop",
            2: "Ekonomiczny",
            3: "Komfortowy"
        }
        return mapping.get(heating_mode_id, "Unknown")