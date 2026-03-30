from typing import Any, Optional, List
from pydantic import BaseModel
from datetime import datetime


def ok(data: Any = None, message: str = "ok"):
    return {"code": 0, "data": data, "message": message}


def err(message: str, code: int = 1):
    return {"code": code, "data": None, "message": message}


# Config
class ConfigItem(BaseModel):
    key: str
    value: Optional[str] = None
    description: Optional[str] = None


# Exhibit
class ExhibitCreate(BaseModel):
    name: str
    keywords: Optional[str] = None
    nav_position_id: Optional[int] = None
    sort_order: int = 0
    auto_intro: bool = False
    description: Optional[str] = None


class ExhibitUpdate(BaseModel):
    name: Optional[str] = None
    keywords: Optional[str] = None
    nav_position_id: Optional[int] = None
    sort_order: Optional[int] = None
    auto_intro: Optional[bool] = None
    description: Optional[str] = None


class ExhibitResourceCreate(BaseModel):
    cloud_resource_id: int
    terminal_id: Optional[int] = None
    sort_order: int = 0
    notes: Optional[str] = None


# NavPosition
class NavPositionCreate(BaseModel):
    cloud_position_name: Optional[str] = None
    robot_poi_name: Optional[str] = None
    description: Optional[str] = None


class NavPositionUpdate(BaseModel):
    cloud_position_name: Optional[str] = None
    robot_poi_name: Optional[str] = None
    description: Optional[str] = None


# Route
class RouteCreate(BaseModel):
    name: str
    path: Optional[str] = None
    description: Optional[str] = None
    enabled: bool = True


class RouteUpdate(BaseModel):
    name: Optional[str] = None
    path: Optional[str] = None
    description: Optional[str] = None
    enabled: Optional[bool] = None


# Lane
class LaneCreate(BaseModel):
    name: str
    sort_order: int = 0
    parallel_group: Optional[str] = 'default'


class LaneUpdate(BaseModel):
    name: Optional[str] = None
    sort_order: Optional[int] = None
    parallel_group: Optional[str] = None


# Step
class StepCreate(BaseModel):
    sort_order: int = 0
    action_type: str
    action_config: Optional[dict] = None
    wait_type: str = 'none'
    wait_timeout: int = 30
    description: Optional[str] = None


class StepUpdate(BaseModel):
    sort_order: Optional[int] = None
    action_type: Optional[str] = None
    action_config: Optional[dict] = None
    wait_type: Optional[str] = None
    wait_timeout: Optional[int] = None
    description: Optional[str] = None


# Robot
class RobotCreate(BaseModel):
    sn: str
    name: Optional[str] = None
    app_key: Optional[str] = None
    app_secret: Optional[str] = None
    webhook_url: Optional[str] = None
    enabled: bool = True


class RobotUpdate(BaseModel):
    name: Optional[str] = None
    app_key: Optional[str] = None
    app_secret: Optional[str] = None
    webhook_url: Optional[str] = None
    enabled: Optional[bool] = None


# Chat
class ChatInput(BaseModel):
    event: str
    robot_sn: str = ""
    params: dict = {}
    text: str = ""  # 直接传文本，兼容企微Bot


# Scene switch
class SceneSwitch(BaseModel):
    scene_id: int


# Reception Preset
class PresetCreate(BaseModel):
    name: str
    description: Optional[str] = None
    icon: Optional[str] = None
    color: Optional[str] = None
    sort_order: int = 0
    enabled: bool = True


class PresetUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    icon: Optional[str] = None
    color: Optional[str] = None
    sort_order: Optional[int] = None
    enabled: Optional[bool] = None


class PresetRouteCreate(BaseModel):
    route_id: int
    sort_order: int = 0


# Scheduled Task
class ScheduledTaskCreate(BaseModel):
    name: str
    cron_expr: str
    action_type: str
    action_config: Optional[dict] = None
    enabled: bool = True


class ScheduledTaskUpdate(BaseModel):
    name: Optional[str] = None
    cron_expr: Optional[str] = None
    action_type: Optional[str] = None
    action_config: Optional[dict] = None
    enabled: Optional[bool] = None


# Kiosk
class KioskSelect(BaseModel):
    exhibit_id: int
    robot_sn: Optional[str] = None


# Reception
class ReceptionStart(BaseModel):
    preset_id: Optional[int] = None
    robot_sn: Optional[str] = None
