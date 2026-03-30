"""
数据库模型 - 展厅智控系统
"""
from sqlalchemy import Column, Integer, String, Boolean, Float, Text, BigInteger, ForeignKey, JSON
from sqlalchemy.orm import DeclarativeBase, relationship
from datetime import datetime


class Base(DeclarativeBase):
    pass


def now_ms():
    return int(datetime.utcnow().timestamp() * 1000)


# ─── 系统配置 ───────────────────────────────────────────────
class SystemConfig(Base):
    __tablename__ = "system_config"
    id = Column(Integer, primary_key=True)
    key = Column(String(100), unique=True, nullable=False)
    value = Column(Text)
    description = Column(String(200))
    is_secret = Column(Boolean, default=False)
    updated_at = Column(BigInteger, default=now_ms)


# ─── 机器人状态 ──────────────────────────────────────────────
class RobotStatus(Base):
    __tablename__ = "robot_status"
    id = Column(Integer, primary_key=True)
    sn = Column(String(100), unique=True, nullable=False)
    name = Column(String(100), default="豹小秘")
    online = Column(Boolean, default=False)
    battery = Column(Integer, default=0)       # 电量百分比
    current_poi = Column(String(100))          # 当前点位名
    status = Column(String(50), default="idle")  # idle/navigating/speaking/charging
    app_version = Column(String(50))
    map_name = Column(String(100))
    last_seen = Column(BigInteger, default=now_ms)
    poi_list = Column(JSON)                    # 机器人上报的POI列表


# ─── 中控云平台同步数据 ──────────────────────────────────────
class CloudSpecial(Base):
    """专场"""
    __tablename__ = "cloud_specials"
    id = Column(Integer, primary_key=True)  # 云平台专场ID
    name = Column(String(200))
    description = Column(String(500))
    hall_id = Column(Integer)
    state = Column(String(10))
    synced_at = Column(BigInteger, default=now_ms)


class CloudArea(Base):
    """展区"""
    __tablename__ = "cloud_areas"
    id = Column(Integer, primary_key=True)
    name = Column(String(200))
    description = Column(String(500))
    hall_id = Column(Integer)
    sort = Column(Integer, default=0)
    synced_at = Column(BigInteger, default=now_ms)


class CloudTerminal(Base):
    """展项主机"""
    __tablename__ = "cloud_terminals"
    id = Column(Integer, primary_key=True)
    name = Column(String(200))
    host_ip = Column(String(50))
    host_port = Column(String(10))
    host_protocol = Column(String(20), default="tcp")  # tcp/http/udp
    area_id = Column(Integer, ForeignKey("cloud_areas.id"))
    hall_id = Column(Integer)
    sort = Column(Integer, default=0)
    online = Column(Boolean, default=False)
    synced_at = Column(BigInteger, default=now_ms)


class CloudResource(Base):
    """展项资源"""
    __tablename__ = "cloud_resources"
    id = Column(Integer, primary_key=True)
    title = Column(String(300))
    resource_type = Column(String(50))   # 图片/视频/PPT
    file_url = Column(Text)
    cover_url = Column(Text)
    audio_url = Column(Text)
    terminal_id = Column(Integer, ForeignKey("cloud_terminals.id"))
    special_id = Column(Integer, ForeignKey("cloud_specials.id"))
    sort = Column(Integer, default=0)
    synced_at = Column(BigInteger, default=now_ms)


class CloudCommand(Base):
    """命令配置"""
    __tablename__ = "cloud_commands"
    id = Column(Integer, primary_key=True)
    name = Column(String(200))
    group_name = Column(String(200))
    protocol = Column(String(20))   # tcp/http/udp
    target_ip = Column(String(50))
    target_port = Column(Integer)
    command_str = Column(Text)      # 原始命令字符串
    is_hex = Column(Boolean, default=False)
    hall_id = Column(Integer)
    synced_at = Column(BigInteger, default=now_ms)


class CurrentSpecial(Base):
    """当前专场（全局唯一）"""
    __tablename__ = "current_special"
    id = Column(Integer, primary_key=True)
    special_id = Column(Integer)
    special_name = Column(String(200))
    source = Column(String(50))   # system/external
    updated_at = Column(BigInteger, default=now_ms)


# ─── 点位映射 ────────────────────────────────────────────────
class NavPosition(Base):
    __tablename__ = "nav_positions"
    id = Column(Integer, primary_key=True)
    robot_poi = Column(String(100), unique=True)   # 机器人内部POI名
    display_name = Column(String(200))             # 展示名（对应展区）
    terminal_id = Column(Integer, ForeignKey("cloud_terminals.id"), nullable=True)
    area_id = Column(Integer, ForeignKey("cloud_areas.id"), nullable=True)
    aliases = Column(JSON)                         # 别名列表（用于意图匹配）
    is_entry = Column(Boolean, default=False)      # 是否入口
    is_charger = Column(Boolean, default=False)    # 是否充电桩
    sort = Column(Integer, default=0)


# ─── 展项讲解配置 ────────────────────────────────────────────
class ExhibitScript(Base):
    __tablename__ = "exhibit_scripts"
    id = Column(Integer, primary_key=True)
    name = Column(String(200))               # 展项名称
    aliases = Column(JSON)                   # 别名触发词
    nav_poi = Column(String(100))            # 对应导航POI
    terminal_id = Column(Integer, ForeignKey("cloud_terminals.id"), nullable=True)
    welcome_text = Column(Text)              # 到达欢迎语
    narration = Column(Text)                 # 主讲解词
    arrival_delay = Column(Integer, default=2)  # 到达后延迟播报(秒)
    ai_narration = Column(Boolean, default=False)  # 是否AI生成讲解
    in_tour = Column(Boolean, default=True)   # 是否参与自动导览
    sort = Column(Integer, default=0)
    enabled = Column(Boolean, default=True)
    items = relationship("ExhibitItem", back_populates="script")


class ExhibitItem(Base):
    """展项内容条目"""
    __tablename__ = "exhibit_items"
    id = Column(Integer, primary_key=True)
    script_id = Column(Integer, ForeignKey("exhibit_scripts.id"))
    title = Column(String(300))
    resource_id = Column(Integer, ForeignKey("cloud_resources.id"), nullable=True)
    narration = Column(Text)
    sort = Column(Integer, default=0)
    script = relationship("ExhibitScript", back_populates="items")


# ─── 导览路线 ────────────────────────────────────────────────
class TourRoute(Base):
    __tablename__ = "tour_routes"
    id = Column(Integer, primary_key=True)
    name = Column(String(200))
    robot_sn = Column(String(100))
    enabled = Column(Boolean, default=True)
    auto_advance = Column(Boolean, default=True)  # 自动进入下一站
    stops = relationship("TourStop", back_populates="route", order_by="TourStop.sort")


class TourStop(Base):
    __tablename__ = "tour_stops"
    id = Column(Integer, primary_key=True)
    route_id = Column(Integer, ForeignKey("tour_routes.id"))
    nav_poi = Column(String(100))
    script_id = Column(Integer, ForeignKey("exhibit_scripts.id"), nullable=True)
    welcome_text = Column(Text)
    sort = Column(Integer, default=0)
    route = relationship("TourRoute", back_populates="stops")


# ─── 流程引擎 ────────────────────────────────────────────────
class FlowRoute(Base):
    __tablename__ = "flow_routes"
    id = Column(Integer, primary_key=True)
    name = Column(String(200))
    description = Column(Text)
    canvas_json = Column(JSON)       # React Flow 画布数据
    enabled = Column(Boolean, default=True)
    created_at = Column(BigInteger, default=now_ms)
    lanes = relationship("FlowLane", back_populates="route")


class FlowLane(Base):
    __tablename__ = "flow_lanes"
    id = Column(Integer, primary_key=True)
    route_id = Column(Integer, ForeignKey("flow_routes.id"))
    name = Column(String(100))
    sort = Column(Integer, default=0)
    route = relationship("FlowRoute", back_populates="lanes")
    steps = relationship("FlowStep", back_populates="lane", order_by="FlowStep.sort")


class FlowStep(Base):
    """
    action_type: robot_nav / robot_speak / media_play / scene_switch /
                 digital_human / tcp_send / http_request / udp_send /
                 wait / narrate / webhook
    wait_strategy: immediate / delay_ms / wait_callback / wait_http / timeout_ms
    """
    __tablename__ = "flow_steps"
    id = Column(Integer, primary_key=True)
    lane_id = Column(Integer, ForeignKey("flow_lanes.id"))
    action_type = Column(String(50))
    params = Column(JSON)              # 动作参数
    wait_strategy = Column(String(50), default="immediate")
    wait_value = Column(Integer, default=0)   # delay_ms 或 timeout_ms
    on_failure = Column(String(50), default="continue")  # continue/abort
    sort = Column(Integer, default=0)
    lane = relationship("FlowLane", back_populates="steps")


class FlowExecution(Base):
    __tablename__ = "flow_executions"
    id = Column(Integer, primary_key=True)
    route_id = Column(Integer, ForeignKey("flow_routes.id"))
    route_name = Column(String(200))
    triggered_by = Column(String(100))   # robot/wecom/admin/schedule
    status = Column(String(50), default="running")  # running/completed/failed
    started_at = Column(BigInteger, default=now_ms)
    ended_at = Column(BigInteger, nullable=True)
    error_msg = Column(Text, nullable=True)
    step_log = Column(JSON)              # 每步执行结果


# ─── 接待套餐 ────────────────────────────────────────────────
class ReceptionPreset(Base):
    __tablename__ = "reception_presets"
    id = Column(Integer, primary_key=True)
    name = Column(String(200))
    description = Column(Text)
    icon = Column(String(100))
    color = Column(String(20))
    enabled = Column(Boolean, default=True)
    sort = Column(Integer, default=0)
    routes = Column(JSON)   # [{route_id, sort}]


# ─── 对话会话 ────────────────────────────────────────────────
class ChatSession(Base):
    __tablename__ = "chat_sessions"
    id = Column(Integer, primary_key=True)
    session_key = Column(String(200), unique=True)  # robot_sn 或 wecom_user_id
    source = Column(String(50))   # robot / wecom
    robot_status = Column(String(50), default="idle")
    current_poi = Column(String(100))
    current_terminal_id = Column(Integer, nullable=True)
    current_file_list = Column(JSON)         # 最近一次文件列表
    current_file_index = Column(Integer, nullable=True)
    free_wake_until = Column(BigInteger, default=0)  # 免唤醒词截止时间ms
    visitor_name = Column(String(100))
    tour_route_id = Column(Integer, nullable=True)
    tour_stop_index = Column(Integer, default=0)
    pending_action = Column(JSON, nullable=True)
    updated_at = Column(BigInteger, default=now_ms)


class ChatLog(Base):
    __tablename__ = "chat_logs"
    id = Column(Integer, primary_key=True)
    session_key = Column(String(200))
    source = Column(String(50))
    input_text = Column(Text)
    intent = Column(String(100))
    intent_params = Column(JSON)
    action_taken = Column(String(200))
    action_result = Column(String(100))
    reply_text = Column(Text)
    error_msg = Column(Text, nullable=True)
    created_at = Column(BigInteger, default=now_ms)


# ─── 预约 ────────────────────────────────────────────────────
class Appointment(Base):
    __tablename__ = "appointments"
    id = Column(Integer, primary_key=True)
    visitor_name = Column(String(200))
    visit_time = Column(BigInteger)
    purpose = Column(Text)
    host_name = Column(String(100))
    preset_id = Column(Integer, ForeignKey("reception_presets.id"), nullable=True)
    status = Column(String(50), default="pending")  # pending/reminded/completed/cancelled
    notified = Column(Boolean, default=False)
    created_at = Column(BigInteger, default=now_ms)


# ─── 定时任务 ────────────────────────────────────────────────
class ScheduledTask(Base):
    __tablename__ = "scheduled_tasks"
    id = Column(Integer, primary_key=True)
    name = Column(String(200))
    task_type = Column(String(50))   # daily/weekly/once/interval/cron
    schedule_expr = Column(String(200))  # cron表达式或时间
    action_type = Column(String(50))   # flow/scene_switch/command/sync
    action_params = Column(JSON)
    enabled = Column(Boolean, default=True)
    last_run_at = Column(BigInteger, nullable=True)
    next_run_at = Column(BigInteger, nullable=True)
    created_at = Column(BigInteger, default=now_ms)


# ─── 通知群 ──────────────────────────────────────────────────
class NotifyGroup(Base):
    __tablename__ = "notify_groups"
    id = Column(Integer, primary_key=True)
    name = Column(String(200))
    chat_id = Column(String(200))
    enabled = Column(Boolean, default=True)
    notify_types = Column(JSON)   # ["arrival","appointment","alert","sync_fail"]


# ─── 企微用户 ────────────────────────────────────────────────
class WecomUser(Base):
    __tablename__ = "wecom_users"
    id = Column(Integer, primary_key=True)
    wecom_user_id = Column(String(200), unique=True)
    name = Column(String(100))
    avatar_url = Column(Text, nullable=True)
    last_active = Column(BigInteger, default=now_ms)


# ─── 操作日志 ────────────────────────────────────────────────
class OperationLog(Base):
    __tablename__ = "operation_logs"
    id = Column(Integer, primary_key=True)
    operator = Column(String(100))
    action = Column(String(200))
    target = Column(String(200))
    detail = Column(Text)
    created_at = Column(BigInteger, default=now_ms)


# ─── 同步日志 ────────────────────────────────────────────────
class SyncLog(Base):
    __tablename__ = "sync_logs"
    id = Column(Integer, primary_key=True)
    sync_type = Column(String(100))   # specials/terminals/resources/commands
    records_count = Column(Integer, default=0)
    status = Column(String(50))       # success/failed
    error = Column(Text, nullable=True)
    created_at = Column(BigInteger, default=now_ms)


# ─── 访客记录 ────────────────────────────────────────────────
class VisitorLog(Base):
    __tablename__ = "visitor_logs"
    id = Column(Integer, primary_key=True)
    visitor_name = Column(String(200))
    action = Column(String(100))   # arrived/toured/left
    detail = Column(Text)
    created_at = Column(BigInteger, default=now_ms)
