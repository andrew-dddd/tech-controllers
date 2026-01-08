"""Models for module menu API responses."""
from typing import Optional
from pydantic import BaseModel


class MenuElementOption(BaseModel):
    """Represents a single option in a radio button control."""
    txtId: int
    value: int


class MenuElementParams(BaseModel):
    """Represents parameters of a menu element."""
    description: str
    value: Optional[int] = None
    default: Optional[int] = None
    options: Optional[list[MenuElementOption]] = None
    txtId: Optional[int] = None
    type: Optional[int] = None
    blockHide: Optional[int] = None


class MenuElement(BaseModel):
    """Represents a single menu element."""
    menuType: str
    type: int
    id: int
    parentId: int
    access: bool
    txtId: int
    wikiTxtId: int
    iconId: int
    params: MenuElementParams
    duringChange: Optional[str]


class ModuleMenuData(BaseModel):
    """Represents the data section of module menu response."""
    elements: list[MenuElement]
    transaction_time: str


class ModuleMenuResponse(BaseModel):
    """Represents the full response from get_module_menu API."""
    status: str
    data: ModuleMenuData
