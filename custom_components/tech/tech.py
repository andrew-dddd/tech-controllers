"""
Python wrapper for getting interaction with Tech devices.
"""
import logging
import aiohttp
import json
import time
import asyncio
from aiocache import Cache, cached

logging.basicConfig(level=logging.DEBUG)
_LOGGER = logging.getLogger(__name__)

class Tech:
    """Main class to perform Tech API requests"""

    TECH_API_URL = "https://emodul.eu/api/v1/"

    def __init__(self, session: aiohttp.ClientSession, user_id = None, token = None, base_url = TECH_API_URL):
        _LOGGER.debug("Init Tech")
        self.headers = {
            'Accept': 'application/json',
            'Accept-Encoding': 'gzip'
        }
        self.base_url = base_url
        self.session = session
        if user_id and token:
            self.user_id = user_id
            self.token = token
            self.headers.setdefault("Authorization", "Bearer " + token)
            self.authenticated = True
        else:
            self.authenticated = False
        self.zones = {}
    
    async def get(self, request_path):
        url = self.base_url + request_path
        _LOGGER.debug("Sending GET request: " + url)
        async with self.session.get(url, headers=self.headers) as response:
            if response.status != 200:
                _LOGGER.warning("Invalid response from Tech API: %s", response.status)
                raise TechError(response.status, await response.text())

            data = await response.json()
            _LOGGER.debug(data)
            return data
    
    async def post(self, request_path, post_data):
        url = self.base_url + request_path
        _LOGGER.debug("Sending POST request: " + url)
        async with self.session.post(url, data=post_data, headers=self.headers) as response:
            if response.status != 200:
                _LOGGER.warning("Invalid response from Tech API: %s", response.status)
                raise TechError(response.status, await response.text())

            data = await response.json()
            _LOGGER.debug(data)
            return data
    
    async def authenticate(self, username, password):
        path = "authentication"
        post_data = '{"username": "' + username + '", "password": "' + password + '"}'
        result = await self.post(path, post_data)
        self.authenticated = result["authenticated"]
        if self.authenticated:
            self.user_id = str(result["user_id"])
            self.token = result["token"]
            self.headers = {
                'Accept': 'application/json',
                'Accept-Encoding': 'gzip',
                'Authorization': 'Bearer ' + self.token
            }
        return result["authenticated"]

    async def list_modules(self):
        if self.authenticated:
            path = "users/" + self.user_id + "/modules"
            result = await self.get(path)
        else:
            raise TechError(401, "Unauthorized")
        return result
    
    async def get_module_data(self, module_udid):
        _LOGGER.debug("Getting module data..." + module_udid + ", " + self.user_id)
        if self.authenticated:
            path = "users/" + self.user_id + "/modules/" + module_udid
            result = await self.get(path)
        else:
            raise TechError(401, "Unauthorized")
        return result
    
    @cached(ttl=10, cache=Cache.MEMORY)
    async def get_module_zones(self, module_udid):
        """Returns Tech module zones either from cache or it will
        update all the cached values for Tech module assuming
        no update has occurred for at least the [update_interval].

        Parameters:
        inst (Tech): The instance of the Tech API.
        module_udid (string): The Tech module udid.

        Returns:
        Dictionary of zones indexed by zone ID.
        """
        result = await self.get_module_data(module_udid)
        zones = result["zones"]["elements"]
        zones = list(filter(lambda e: e['zone']['zoneState'] != "zoneUnregistered", zones))
        zones_dict = {}
        for zone in zones:
            zones_dict[zone["zone"]["id"]] = zone
        return zones_dict
    
    async def get_zone(self, module_udid, zone_id):
        """Returns zone from Tech API cache.

        Parameters:
        module_udid (string): The Tech module udid.
        zone_id (int): The Tech module zone ID.

        Returns:
        Dictionary of zone.
        """
        zones = await self.get_module_zones(module_udid)
        return zones[zone_id]

    async def set_const_temp(self, module_udid, zone_mode_id, zone_id, target_temp):
        """Sets constant temperature of the zone.
        
        Parameters:
        module_udid (string): The Tech module udid.
        zone_id (int): The Tech module zone ID.
        target_temp (float): The target temperature to be set within the zone.

        Returns:
        JSON object with the result.
        """
        _LOGGER.debug("Setting zone constant temperature...")
        if self.authenticated:
            path = f"users/{self.user_id}/modules/{module_udid}/zones"
            _LOGGER.debug("Path: " + path)
            data = {
                "mode" : {
                    "id" : zone_mode_id,
                    "parentId" : zone_id,
                    "mode" : "constantTemp",
                    "constTempTime" : 60,
                    "setTemperature" : int(target_temp  * 10),
                    "scheduleIndex" : 0
                }
            }
            _LOGGER.debug(data)
            result = await self.post(path, json.dumps(data))
        else:
            raise TechError(401, "Unauthorized")
        return result

    async def set_zone(self, module_udid, zone_id, on = True):
        """Turns the zone on or off.
        
        Parameters:
        module_udid (string): The Tech module udid.
        zone_id (int): The Tech module zone ID.
        on (bool): Flag indicating to turn the zone on if True or off if False.

        Returns:
        JSON object with the result.
        """
        _LOGGER.debug("Turing zone on/off: %s", on)
        if self.authenticated:
            path = f"users/{self.user_id}/modules/{module_udid}/zones"
            data = {
                "zone" : {
                    "id" : zone_id,
                    "zoneState" : "zoneOn" if on else "zoneOff"
                }
            }
            _LOGGER.debug(data)
            result = await self.post(path, json.dumps(data))
        else:
            raise TechError(401, "Unauthorized")
        return result

    @cached(ttl=10, cache=Cache.MEMORY)
    async def get_module_menu(self, module_udid, menu_type):
        """ Gets module menu options
       
        Parameters:
        module_udid (string): The tech module udid
        menu_type (string): Menu type, one of the following: "MU", "MI", "MS", "MP"

        Return:
        JSON object with results
        """

        _LOGGER.debug("Getting module menu: %s", menu_type)
        if self.authenticated:
            path = f"users/{self.user_id}/modules/{module_udid}/menu/{menu_type}"
            result = await self.get(path)       
        else:
            raise TechError(401, "Unauthorized")
        return result

    async def set_module_menu(self, module_udid, menu_type, menu_id, menu_value):
        """ Sets module menu value

        Parameters:
        module_udid (string): The tech module udid
        menu_type (string): Menu type, one of the following: "MU", "MI", "MS", "MP"
        menu_id (integer): Menu option id, integer
        menu_value (integer): Menu option value, positive integ
        """

        _LOGGER.debug("Setting menu %s id: %s value to: %s", menu_type, menu_id, menu_value)
        if self.authenticated:
            path = f"users/{self.user_id}/modules/{module_udid}/menu/{menu_type}/ido/{menu_id}"
            data = {
                "value": menu_value
            }
            _LOGGER.debug(data)
            result = await self.post(path, json.dumps(data))
        else:
            raise TechError(401, "Unauthorized")
        return result

class TechError(Exception):
    """Raised when Tech APi request ended in error.
    Attributes:
        status_code - error code returned by Tech API
        status - more detailed description
    """
    def __init__(self, status_code, status):
        self.status_code = status_code
        self.status = status
