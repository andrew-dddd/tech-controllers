"""Models for module API responses."""
from typing import Any, Optional
from pydantic import BaseModel

class Module(BaseModel):
    """Represents a single module."""
    id: int
    default: bool
    name: str
    email: str
    type: str
    controllerStatus: str
    moduleStatus: str
    additionalInformation: str
    phoneNumber: Optional[str] = None
    zipCode: str
    tag: Optional[str] = None
    country: Optional[str] = None
    gmtId: int
    gmtTime: str
    postcodePolicyAccepted: bool
    style: str
    version: str
    company: str
    udid: str

class UserModule(BaseModel):
    """Represents a user module."""
    user_id: str
    token: str
    module: Module
    module_title: str

# Models for get_module_data response

class ZoneFlags(BaseModel):
    """Represents zone flags."""
    relayState: str
    minOneWindowOpen: bool
    algorithm: str
    floorSensor: int
    humidityAlgorytm: int
    zoneExcluded: int


class Zone(BaseModel):
    """Represents zone information."""
    id: int
    parentId: int
    time: str
    duringChange: bool
    index: int
    currentTemperature: int
    setTemperature: int
    flags: ZoneFlags
    zoneState: str
    signalStrength: Optional[int] = None
    batteryLevel: Optional[int] = None
    actuatorsOpen: int
    humidity: int
    visibility: bool


class ZoneDescription(BaseModel):
    """Represents zone description."""
    id: int
    parentId: int
    name: str
    styleId: int
    styleIcon: str
    duringChange: bool


class ZoneMode(BaseModel):
    """Represents zone mode."""
    id: int
    parentId: int
    mode: str
    constTempTime: int
    setTemperature: int
    scheduleIndex: int


class ScheduleInterval(BaseModel):
    """Represents a schedule interval."""
    start: int
    stop: int
    temp: int


class ZoneSchedule(BaseModel):
    """Represents zone schedule."""
    id: int
    parentId: int
    index: int
    p0Days: list[str]
    p0Intervals: list[ScheduleInterval]
    p0SetbackTemp: int
    p1Days: list[str]
    p1Intervals: list[ScheduleInterval]
    p1SetbackTemp: int


class ZoneElement(BaseModel):
    """Represents a zone element."""
    zone: Zone
    description: ZoneDescription
    mode: ZoneMode
    schedule: ZoneSchedule
    actuators: list[Any]
    underfloor: dict[str, Any]
    windowsSensors: list[Any]
    additionalContacts: list[Any]


class GlobalSchedule(BaseModel):
    """Represents a global schedule."""
    id: int
    parentId: int
    index: int
    name: str
    p0Days: list[str]
    p0SetbackTemp: int
    p0Intervals: list[ScheduleInterval]
    p1Days: list[str]
    p1SetbackTemp: int
    p1Intervals: list[ScheduleInterval]


class GlobalSchedules(BaseModel):
    """Represents global schedules container."""
    time: str
    duringChange: bool
    elements: list[GlobalSchedule]


class ControllerMode(BaseModel):
    """Represents controller mode."""
    id: int
    parentId: int
    type: int
    txtId: int
    iconId: int
    value: int
    menuId: int


class ControllerParameters(BaseModel):
    """Represents controller parameters."""
    controllerMode: ControllerMode
    globalSchedulesNumber: dict[str, Any]


class Zones(BaseModel):
    """Represents zones container."""
    transaction_time: str
    elements: list[ZoneElement]
    globalSchedules: GlobalSchedules
    controllerParameters: ControllerParameters


class TileParams(BaseModel):
    """Represents tile parameters."""
    description: str
    txtId: int
    iconId: int
    version: Optional[str] = None
    companyId: Optional[int] = None
    controllerName: Optional[str] = None
    mainControllerId: Optional[int] = None
    workingStatus: Optional[bool] = None


class Tile(BaseModel):
    """Represents a tile."""
    id: int
    parentId: int
    type: int
    menuId: int
    orderId: Optional[int] = None
    visibility: bool
    params: TileParams


class ModuleData(BaseModel):
    """Represents the full response from get_module_data API."""
    zones: Zones
    tiles: list[Tile]
    tilesOrder: Optional[Any] = None
    tilesLastUpdate: str
