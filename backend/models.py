from datetime import datetime
from sqlalchemy import (
    Column, Integer, String, Text, Boolean, DateTime, JSON, Float, ForeignKey
)
from sqlalchemy.dialects.postgresql import JSONB
from database import Base


class SystemConfig(Base):
    __tablename__ = "system_config"
    key = Column(String, primary_key=True)
    value = Column(Text)
    description = Column(Text)
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now)


class CloudTerminal(Base):
    __tablename__ = "cloud_terminals"
    id = Column(Integer, primary_key=True, autoincrement=True)
    terminal_id = Column(Integer)
    special_terminal_id = Column(Integer)
    name = Column(String)
    ip = Column(String)
    port = Column(Integer)
    exhibition_id = Column(Integer)
    raw_data = Column(JSONB)
    synced_at = Column(DateTime, default=datetime.now)


class CloudResource(Base):
    __tablename__ = "cloud_resources"
    id = Column(Integer, primary_key=True, autoincrement=True)
    resource_id = Column(Integer)
    terminal_id = Column(Integer)
    exhibit_id = Column(Integer)
    title = Column(String)
    description = Column(Text)
    sort = Column(Integer)
    file_name = Column(String)
    raw_data = Column(JSONB)
    synced_at = Column(DateTime, default=datetime.now)


class CloudCommand(Base):
    __tablename__ = "cloud_commands"
    id = Column(Integer, primary_key=True, autoincrement=True)
    command_id = Column(Integer)
    name = Column(String)
    command_type = Column(String)
    command_str = Column(Text)
    encoding = Column(String, default='utf-8')
    group_name = Column(String)
    protocol_type = Column(String, default='http')  # 'http' or 'tcp'
    is_hex = Column(Boolean, default=False)
    url = Column(String)  # base URL for HTTP commands
    area_id = Column(Integer)
    area_name = Column(String)
    raw_data = Column(JSONB)
    synced_at = Column(DateTime, default=datetime.now)


class CloudScene(Base):
    __tablename__ = "cloud_scenes"
    id = Column(Integer, primary_key=True, autoincrement=True)
    scene_id = Column(Integer)
    name = Column(String)
    exhibition_id = Column(Integer)
    raw_data = Column(JSONB)
    synced_at = Column(DateTime, default=datetime.now)


class Exhibit(Base):
    __tablename__ = "exhibits"
    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String)
    keywords = Column(Text)
    nav_position_id = Column(Integer)
    sort_order = Column(Integer, default=0)
    auto_intro = Column(Boolean, default=False)
    description = Column(Text)
    created_at = Column(DateTime, default=datetime.now)


class ExhibitResource(Base):
    __tablename__ = "exhibit_resources"
    id = Column(Integer, primary_key=True, autoincrement=True)
    exhibit_id = Column(Integer)
    cloud_resource_id = Column(Integer)
    terminal_id = Column(Integer)
    sort_order = Column(Integer, default=0)
    notes = Column(Text)


class NavPosition(Base):
    __tablename__ = "nav_positions"
    id = Column(Integer, primary_key=True, autoincrement=True)
    cloud_position_name = Column(String)
    robot_poi_name = Column(String)
    description = Column(Text)


class ApiRoute(Base):
    __tablename__ = "api_routes"
    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String)
    path = Column(String, unique=True)
    description = Column(Text)
    enabled = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.now)


class RouteLane(Base):
    __tablename__ = "route_lanes"
    id = Column(Integer, primary_key=True, autoincrement=True)
    route_id = Column(Integer)
    name = Column(String)
    sort_order = Column(Integer, default=0)
    parallel_group = Column(String, default='default')


class LaneStep(Base):
    __tablename__ = "lane_steps"
    id = Column(Integer, primary_key=True, autoincrement=True)
    lane_id = Column(Integer)
    sort_order = Column(Integer, default=0)
    action_type = Column(String)
    action_config = Column(JSONB)
    wait_type = Column(String, default='none')
    wait_timeout = Column(Integer, default=30)
    description = Column(Text)


class ChatSession(Base):
    __tablename__ = "chat_sessions"
    id = Column(Integer, primary_key=True, autoincrement=True)
    robot_sn = Column(String)
    state = Column(String, default='idle')
    current_exhibit_id = Column(Integer)
    shown_resources = Column(JSONB)
    last_activity_at = Column(DateTime, default=datetime.now)
    created_at = Column(DateTime, default=datetime.now)


class RobotConfig(Base):
    __tablename__ = "robot_config"
    id = Column(Integer, primary_key=True, autoincrement=True)
    sn = Column(String, unique=True)
    name = Column(String)
    app_key = Column(String)
    app_secret = Column(String)
    webhook_url = Column(String)
    enabled = Column(Boolean, default=True)


class FlowExecution(Base):
    __tablename__ = "flow_executions"
    id = Column(Integer, primary_key=True, autoincrement=True)
    route_id = Column(Integer)
    triggered_by = Column(String)
    status = Column(String)
    started_at = Column(DateTime, default=datetime.now)
    finished_at = Column(DateTime)
    error = Column(Text)


class ExecutionStep(Base):
    __tablename__ = "execution_steps"
    id = Column(Integer, primary_key=True, autoincrement=True)
    execution_id = Column(Integer)
    step_id = Column(Integer)
    status = Column(String)
    result = Column(JSONB)
    started_at = Column(DateTime)
    finished_at = Column(DateTime)


class OperationLog(Base):
    __tablename__ = "operation_logs"
    id = Column(Integer, primary_key=True, autoincrement=True)
    action = Column(String)
    source = Column(String)
    params = Column(JSONB)
    result = Column(JSONB)
    created_at = Column(DateTime, default=datetime.now)


class CurrentScene(Base):
    __tablename__ = "current_scene"
    id = Column(Integer, primary_key=True, autoincrement=True)
    scene_id = Column(Integer)
    scene_name = Column(String)
    updated_at = Column(DateTime, default=datetime.now)


class SyncLog(Base):
    __tablename__ = "sync_logs"
    id = Column(Integer, primary_key=True, autoincrement=True)
    sync_type = Column(String)
    status = Column(String)
    records_count = Column(Integer, default=0)
    error = Column(Text)
    created_at = Column(DateTime, default=datetime.now)


# ===== 新功能模型 =====

class ReceptionPreset(Base):
    __tablename__ = "reception_presets"
    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String)
    description = Column(Text)
    icon = Column(String)
    color = Column(String)
    sort_order = Column(Integer, default=0)
    enabled = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.now)


class PresetRoute(Base):
    __tablename__ = "preset_routes"
    id = Column(Integer, primary_key=True, autoincrement=True)
    preset_id = Column(Integer)
    route_id = Column(Integer)
    sort_order = Column(Integer, default=0)


class ScheduledTask(Base):
    __tablename__ = "scheduled_tasks"
    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String)
    cron_expr = Column(String)
    action_type = Column(String)
    action_config = Column(JSONB)
    enabled = Column(Boolean, default=True)
    last_run_at = Column(DateTime)
    next_run_at = Column(DateTime)
    created_at = Column(DateTime, default=datetime.now)


class ReceptionSession(Base):
    __tablename__ = "reception_sessions"
    id = Column(Integer, primary_key=True, autoincrement=True)
    started_at = Column(DateTime, default=datetime.now)
    ended_at = Column(DateTime)
    exhibits_visited = Column(JSONB)
    resources_played = Column(JSONB)
    preset_used = Column(Integer)
    total_duration = Column(Integer)
    summary = Column(Text)


class DeviceStatus(Base):
    __tablename__ = "device_status"
    id = Column(Integer, primary_key=True, autoincrement=True)
    terminal_id = Column(Integer)
    terminal_name = Column(String)
    ip = Column(String)
    port = Column(Integer)
    is_online = Column(Boolean, default=False)
    last_checked_at = Column(DateTime)
    response_ms = Column(Integer)
