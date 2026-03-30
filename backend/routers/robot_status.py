from fastapi import APIRouter
from database import async_session
from sqlalchemy import text
from pydantic import BaseModel
from typing import Optional, List
import json, logging

router = APIRouter(prefix="/api/robot", tags=["robot_status"])
logger = logging.getLogger(__name__)


class BatteryUpdate(BaseModel):
    robot_sn: str
    battery_level: int
    is_charging: bool


class MapPositionsUpdate(BaseModel):
    robot_sn: str
    positions: List[str]


class StatusUpdate(BaseModel):
    robot_sn: str
    status: str
    current_position: Optional[str] = None
    visitor_name: Optional[str] = None
    visitor_dept: Optional[str] = None


class SystemStatusReport(BaseModel):
    robot_sn: str
    status_type: str = ""
    status_data: str = "{}"


@router.post("/battery")
async def update_battery(data: BatteryUpdate):
    async with async_session() as db:
        await db.execute(text("""
            INSERT INTO robot_status (robot_sn, battery_level, is_charging, last_seen, updated_at)
            VALUES (:sn, :level, :charging, NOW(), NOW())
            ON CONFLICT (robot_sn) DO UPDATE SET
                battery_level=:level,
                is_charging=:charging,
                last_seen=NOW(), updated_at=NOW()
        """), {"sn": data.robot_sn, "level": data.battery_level, "charging": data.is_charging})
        await db.commit()
    return {"code": 0}


@router.post("/map-positions")
async def update_map_positions(data: MapPositionsUpdate):
    async with async_session() as db:
        await db.execute(text("""
            INSERT INTO robot_status (robot_sn, map_positions, last_seen, updated_at)
            VALUES (:sn, :pos, NOW(), NOW())
            ON CONFLICT (robot_sn) DO UPDATE SET
                map_positions=:pos,
                last_seen=NOW(), updated_at=NOW()
        """), {"sn": data.robot_sn, "pos": json.dumps(data.positions, ensure_ascii=False)})
        await db.commit()
    return {"code": 0, "count": len(data.positions)}


@router.get("/status/{robot_sn}")
async def get_robot_status(robot_sn: str):
    async with async_session() as db:
        row = await db.execute(text("SELECT * FROM robot_status WHERE robot_sn=:sn"), {"sn": robot_sn})
        r = row.fetchone()
    if not r:
        return {"code": 0, "data": {"robot_sn": robot_sn, "status": "offline"}}
    return {"code": 0, "data": dict(r._mapping)}


@router.get("/map-positions/{robot_sn}")
async def get_map_positions(robot_sn: str):
    async with async_session() as db:
        row = await db.execute(text("SELECT map_positions FROM robot_status WHERE robot_sn=:sn"), {"sn": robot_sn})
        r = row.fetchone()
    positions = []
    if r and r[0]:
        try:
            positions = json.loads(r[0])
        except Exception:
            pass
    return {"code": 0, "data": positions}


@router.post("/system-status")
async def report_system_status(data: SystemStatusReport):
    """接收 APK 上报的系统状态（急停/低电/定位丢失等）"""
    logger.warning(
        f"[SystemStatus] robot={data.robot_sn} type={data.status_type} data={data.status_data}"
    )
    return {"ok": True}
