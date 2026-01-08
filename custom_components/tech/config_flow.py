"""Config flow for Tech Sterowniki integration."""
from typing import Any
import logging, uuid
import voluptuous as vol
from homeassistant import config_entries, core, exceptions
from homeassistant.helpers import aiohttp_client
from homeassistant.config_entries import ConfigEntry
from .const import DOMAIN  # pylint:disable=unused-import
from .tech import Tech
from types import MappingProxyType
from .models.module import Module, UserModule

_LOGGER = logging.getLogger(__name__)

DATA_SCHEMA = vol.Schema({
    vol.Required("username"): str,
    vol.Required("password"): str,
})


async def validate_input(hass: core.HomeAssistant, data):
    """Validate the user input allows us to connect.

    Data has the keys from DATA_SCHEMA with values provided by the user.
    """

    http_session = aiohttp_client.async_get_clientsession(hass)
    api = Tech(http_session)

    if not await api.authenticate(data["username"], data["password"]):
        raise InvalidAuth
    modules = await api.list_modules()

    # If you cannot connect:
    # throw CannotConnect
    # If the authentication is wrong:
    # InvalidAuth

    # Return info that you want to store in the config entry.
    return { "user_id": api.user_id, "token": api.token, "modules": modules }


class ConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Tech Sterowniki."""

    VERSION = 1
    MINOR_VERSION = 1
    # Pick one of the available connection classes in homeassistant/config_entries.py
    CONNECTION_CLASS = config_entries.CONN_CLASS_CLOUD_POLL

    async def async_step_user(self, user_input=None):
        """Handle the initial step."""
        errors = {}
        if user_input is not None:
            try:
                _LOGGER.debug("Context: " + str(self.context))
                validated_input = await validate_input(self.hass, user_input)

                modules: list[UserModule] = self._create_modules_array(validated_input=validated_input)

                if len(modules) == 0:
                    return self.async_abort("no_modules")

                if len(modules) > 1:
                    for module in modules[1:len(modules)]:
                        await self.hass.config_entries.async_add(self._create_config_entry(module=module))

                return self.async_create_entry(title=modules[0].module_title, data=modules[0])
            except CannotConnect:
                errors["base"] = "cannot_connect"
            except InvalidAuth:
                errors["base"] = "invalid_auth"
            except Exception:  # pylint: disable=broad-except
                _LOGGER.exception("Unexpected exception")
                errors["base"] = "unknown"

        return self.async_show_form(
            step_id="user", data_schema=DATA_SCHEMA, errors=errors
        )

    def _create_config_entry(self, module: UserModule) -> ConfigEntry:
        return ConfigEntry(
            data=module,            
            title=module.module_title,
            entry_id=uuid.uuid4().hex,
	        discovery_keys=MappingProxyType({}),
            domain=DOMAIN,
            version=ConfigFlow.VERSION,
            minor_version=ConfigFlow.MINOR_VERSION,
            source=ConfigFlow.CONNECTION_CLASS,
	        options={},
            unique_id=None,
	        subentries_data=[])
    
    def _create_modules_array(self, validated_input: dict) -> list[UserModule]:
        return [
            self._create_module_dict(validated_input, module_dict)
            for module_dict in validated_input["modules"]
        ]

    def _create_module_dict(self, validated_input: dict, module: Module) -> UserModule:
        return UserModule(   
            user_id=validated_input["user_id"],
            token=validated_input["token"],
            module=module,
            module_title=module.version + ": " + module.name
        )


class CannotConnect(exceptions.HomeAssistantError):
    """Error to indicate we cannot connect."""


class InvalidAuth(exceptions.HomeAssistantError):
    """Error to indicate there is invalid auth."""