"""Support for Tech HVAC system."""
from __future__ import annotations

import logging
from typing import Any, Final

from custom_components.tech.tech_update_coordinator import TechUpdateCoordinator
from homeassistant.components.climate import (
    ClimateEntity,
    ClimateEntityFeature,
    HVACMode,
    HVACAction    
)
from homeassistant.const import (
    ATTR_TEMPERATURE,
    UnitOfTemperature,
)

from homeassistant.helpers.update_coordinator import CoordinatorEntity

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import (HomeAssistant, callback)
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN
from .tech import Tech

_LOGGER = logging.getLogger(__name__)

SUPPORT_HVAC: Final = [HVACMode.HEAT, HVACMode.OFF]
DEFAULT_PRESETS = ["Normalny", "Urlop", "Ekonomiczny", "Komfortowy"]
CHANGE_PRESET = "Oczekiwanie na zmianę"

async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> bool:
    """Set up Tech climate based on config_entry."""
    api: Tech = hass.data[DOMAIN][entry.entry_id]
    udid: str = entry.data["module"]["udid"]    
    
    try:
        zones = await api.get_module_zones(udid)
        menu_config = await api.get_module_menu(udid, "mu")
        if menu_config["status"] != "success":
            _LOGGER.warning("Failed to get menu config for Tech module %s, response: %s", udid, menu_config)
            menu_config = None
        
        coordinator = TechUpdateCoordinator(hass, entry, api, udid)
        await coordinator._async_update_data()

        async_add_entities(
            TechThermostat(zones[zone], coordinator, api)
            for zone in zones
        )
        return True
    except Exception as ex:
        _LOGGER.error("Failed to set up Tech climate: %s", ex)
        return False
    

class TechThermostat(CoordinatorEntity, ClimateEntity):
    """Representation of a Tech climate."""

    _attr_temperature_unit = UnitOfTemperature.CELSIUS
    _attr_hvac_modes = SUPPORT_HVAC
    _attr_supported_features = ClimateEntityFeature.TARGET_TEMPERATURE | ClimateEntityFeature.PRESET_MODE
    _attr_preset_modes = DEFAULT_PRESETS

    def __init__(self, device: dict[str, Any], coordinator, api: Tech) -> None:
        """Initialize the Tech device."""
        self._api = api
        self._id: int = device["zone"]["id"]
        self._udid = coordinator.udid
        
        # Set unique_id first as it's required for entity registry
        self._attr_unique_id = f"{self._udid}_{self._id}"
        self._attr_device_info = {
            "identifiers": {(DOMAIN, self._attr_unique_id)},
            "name": device["description"]["name"],
            "manufacturer": "Tech",
        }

        super().__init__(coordinator, context=self._id)
        
        # Initialize attributes that will be updated
        self._attr_name: str | None = None
        self._attr_target_temperature: float | None = None
        self._attr_current_temperature: float | None = None
        self._attr_current_humidity: int | None = None
        self._attr_hvac_action: str | None = None
        self._attr_hvac_mode: str = HVACMode.OFF
        self._attr_preset_mode: str | None = None
        
        self.update_properties(coordinator.data["zones"][self._id], coordinator.data["menu"])

    def update_properties(self, device: dict[str, Any], device_menu_config: dict[str, Any] | None) -> None:
        """Update the properties from device data."""
        self._attr_name = device["description"]["name"]
        
        zone = device["zone"]
        if zone["setTemperature"] is not None:
            self._attr_target_temperature = zone["setTemperature"] / 10
        
        if zone["currentTemperature"] is not None:
            self._attr_current_temperature = zone["currentTemperature"] / 10
            
        if zone["humidity"] is not None:
            self._attr_current_humidity = zone["humidity"]
            
        state = zone["flags"]["relayState"]
        if state == "on":
            self._attr_hvac_action = HVACAction.HEATING
        elif state == "off":
            self._attr_hvac_action = HVACAction.IDLE
        else:
            self._attr_hvac_action = HVACAction.OFF        
        
        mode = zone["zoneState"]
        self._attr_hvac_mode = HVACMode.HEAT if mode in ["zoneOn", "noAlarm"] else HVACMode.OFF
        
        heating_mode = self.get_heating_mode_from_menu_config(device_menu_config) if device_menu_config else None

        if heating_mode is not None:
            if heating_mode["duringChange"] == "t":
                self._attr_preset_modes = [CHANGE_PRESET]
                self._attr_preset_mode = CHANGE_PRESET
            else:
                self._attr_preset_modes = DEFAULT_PRESETS
                heating_mode_id = heating_mode["params"]["value"]
                self._attr_preset_mode = self.map_heating_mode_id_to_name(heating_mode_id)
        else:
            _LOGGER.warning("Heating mode menu not found for Tech zone %s", self._attr_name)

    
    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        data = self.coordinator.data
        self.update_properties(data["zones"][self._id], data["menu"])
        self.async_write_ha_state()

    """
    async def async_update(self) -> None:
        Update the entity.
        try:
            device = await self._api.get_zone(self._udid, self._id)
            menu_config = await self._api.get_module_menu(self._udid, "mu")
            if(menu_config["status"] == "success"):                
                self.update_properties(device, menu_config["data"])                
            else:
                _LOGGER.warning("Failed to get menu config for Tech module %s, response: %s", self._udid, menu_config)            
                self.update_properties(device, None)
        except Exception as ex:
            _LOGGER.error("Failed to update Tech zone %s: %s", self._attr_name, ex)
    """

    async def async_set_temperature(self, **kwargs: Any) -> None:
        """Set new target temperature."""
        temperature = kwargs.get(ATTR_TEMPERATURE)
        if temperature is not None:
            try:
                await self._api.set_const_temp(self._udid, self._id, temperature)
                await self.coordinator.async_request_refresh()
            except Exception as ex:
                _LOGGER.error(
                    "Failed to set temperature for %s to %s: %s",
                    self._attr_name,
                    temperature,
                    ex
                )
    
    async def async_set_preset_mode(self, preset_mode: str) -> None:
        try:
            if self._attr_preset_mode == CHANGE_PRESET:
                _LOGGER.debug("Preset mode change already in progress for %s", self._attr_name)
                return
            
            preset_mode_id = DEFAULT_PRESETS.index(preset_mode)
            await self._api.set_module_menu(
                self._udid,
                "mu",
                1000,
                preset_mode_id
            )

            await self.coordinator.async_request_refresh()
        except Exception as ex:
            _LOGGER.error(
                "Failed to set preset mode for %s to %s: %s",
                self._attr_name,
                preset_mode,
                ex
            )

    async def async_set_hvac_mode(self, hvac_mode: str) -> None:
        """Set new target hvac mode."""
        try:
            await self._api.set_zone(
                self._udid,
                self._id,
                hvac_mode == HVACMode.HEAT
            )
            await self.coordinator.async_request_refresh()
        except Exception as ex:
            _LOGGER.error(
                "Failed to set hvac mode for %s to %s: %s",
                self._attr_name,
                hvac_mode,
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