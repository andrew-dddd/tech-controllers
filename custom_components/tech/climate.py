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

async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> bool:
    """Set up Tech climate based on config_entry."""
    api: Tech = hass.data[DOMAIN][entry.entry_id]["api"]
    coordinator: TechUpdateCoordinator = hass.data[DOMAIN][entry.entry_id]["coordinator"]
    
    try:               
        zones = coordinator.get_zones()

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
    _attr_supported_features = ClimateEntityFeature.TARGET_TEMPERATURE

    def __init__(self, device: dict[str, Any], coordinator, api: Tech) -> None:
        """Initialize the Tech device."""
        self._api = api
        self._id: int = device["zone"]["id"]
        self._zone_mode_id = device["mode"]["id"]
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
        
        self.update_properties(coordinator.get_zones()[self._id])

    def update_properties(self, device: dict[str, Any]) -> None:
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
    
    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""        
        _LOGGER.debug("Coordinator update for zone %s", self._attr_name)
        self.update_properties(self.coordinator.get_zones()[self._id])
        self.async_write_ha_state()

    async def async_set_temperature(self, **kwargs: Any) -> None:
        """Set new target temperature."""
        temperature = kwargs.get(ATTR_TEMPERATURE)
        if temperature is not None:
            try:
                await self._api.set_const_temp(self._udid, self._zone_mode_id, self._id, temperature)
                await self.coordinator.async_request_refresh()
            except Exception as ex:
                _LOGGER.error(
                    "Failed to set temperature for %s to %s: %s",
                    self._attr_name,
                    temperature,
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