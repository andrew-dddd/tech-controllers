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
    """Validate the user input allows us to connect."""
    api = await validate_api_login(hass, data)
    modules = await api.list_modules()

    return { 
        "username": data["username"], 
        "password": data["password"], 
        "user_id": api.user_id, 
        "token": api.token, 
        "modules": modules 
    }

async def validate_api_login(hass: core.HomeAssistant, data):
    """Validate the user input allows us to connect with the Tech API."""
    http_session = aiohttp_client.async_get_clientsession(hass)
    api = Tech(http_session)

    if not await api.authenticate(data["username"], data["password"]):
        raise InvalidAuth
    
    return api


class ConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Tech Sterowniki."""

    VERSION = 1
    MINOR_VERSION = 1
    CONNECTION_CLASS = config_entries.CONN_CLASS_CLOUD_POLL

    def __init__(self):
        """Initialize the config flow."""
        self.reauth_entry = None

    async def async_step_user(self, user_input=None):
        """Handle the initial step when adding the integration."""
        errors = {}
        if user_input is not None:
            try:
                _LOGGER.debug("Context: " + str(self.context))
                validated_input = await validate_input(self.hass, user_input)

                modules: list[UserModule] = self._create_modules_array(validated_input=validated_input)

                if len(modules) == 0:
                    return self.async_abort(reason="no_modules")

                if len(modules) > 1:
                    for module in modules[1:len(modules)]:
                        await self.hass.config_entries.async_add(self._create_config_entry(module=module))

                return self.async_create_entry(title=modules[0].module_title, data=modules[0].dict())
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

    async def async_step_reauth(self, entry_data=None):
        """Handle a reauthentication flow triggered by a ConfigEntryAuthFailed exception."""
        # Fetch the config entry that requested re-authentication
        self.reauth_entry = self._get_reauth_entry()
        
        # Immediately proceed to the confirmation/login step
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(self, user_input=None):
        """Handle the reauth confirmation flow (automatic login or manual form fallback)."""
        errors = {}
        
        # Retrieve the currently saved credentials from Home Assistant storage
        existing_data = self.reauth_entry.data
        username = existing_data.get("username")
        password = existing_data.get("password")

        _LOGGER.debug("Starting re-authentication for entry_id %s with username %s", self.reauth_entry.entry_id, username)

        # If user_input is None, it means this is the first automatic background run
        if user_input is None:
            user_input = {"username": username, "password": password}
            auto_attempt = True
        else:
            auto_attempt = False

        if user_input is not None:
            try:
                # Try to re-authenticate using the stored (or newly typed) credentials
                await validate_api_login(self.hass, user_input)
                
                # If successful, update the config entry data with the new credentials
                self.hass.config_entries.async_update_entry(
                    self.reauth_entry,
                    data={**self.reauth_entry.data, **user_input}
                )
                
                # Reload the integration immediately to apply changes and resume tracking
                await self.hass.config_entries.async_reload(self.reauth_entry.entry_id)

                _LOGGER.debug("Re-authentication successful for entry_id %s with username %s", self.reauth_entry.entry_id, username)

                return self.async_abort(reason="reauth_successful")                
            except InvalidAuth:
                errors["base"] = "invalid_auth"
                if auto_attempt:
                    # Suppress the error on the background run to seamlessly show the fallback form
                    pass
            except Exception:
                _LOGGER.exception("Unexpected exception during re-authentication")
                errors["base"] = "cannot_connect"
                if auto_attempt:
                    pass

        _LOGGER.debug("Re-authentication failed for entry_id %s with username %s. Showing fallback form. Errors: %s", self.reauth_entry.entry_id, username, errors)            
        # Fallback form if the automatic background login failed. 
        # Prefilled with the current username so the user only needs to fix the password.
        return self.async_show_form(
            step_id="reauth_confirm",
            data_schema=vol.Schema({
                vol.Required("username", default=username): str,
                vol.Required("password"): str,
            }),
            errors=errors,
        )
    
    def _create_config_entry(self, module: UserModule) -> ConfigEntry:
        """Create a config entry object for additional modules."""
        return ConfigEntry(
            data=module.dict(),
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
        """Map validated input modules into UserModule objects."""
        return [
            self._create_module_dict(validated_input, module_dict)
            for module_dict in validated_input["modules"]
        ]

    def _create_module_dict(self, validated_input: dict, module: Module) -> UserModule:
        """Helper to structure a UserModule dictionary model."""
        return UserModule(
            user_id=validated_input["user_id"],
            token=validated_input["token"],
            module=module,
            module_title=module.version + ": " + module.name,
            username=validated_input["username"],
            password=validated_input["password"]
        )


class CannotConnect(exceptions.HomeAssistantError):
    """Error to indicate we cannot connect."""


class InvalidAuth(exceptions.HomeAssistantError):
    """Error to indicate there is invalid auth."""