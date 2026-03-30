"""机器人状态与控制API"""
from fastapi import APIRouter, Depends
from pydantic import BaseModel
from typing import Optional, List
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from ..database import get_db
from ..models import RobotStatus, NavPosition
from ..services.robot import robot_mgr, RobotAction
from ..config import settings

router = APIRouter(prefix="/api/robot", tags=["robot"])


@router.get("/status")
async def get_robot_status(db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(RobotStatus).where(RobotStatus.sn == settings.ROBOT_SN))
    robot = result.scalar_one_or_none()
    if not robot:
        return {"code": 200, "data": {"online": False}}
    return {"code": 200, "data": {
        "sn": robot.sn,
        "online": robot.online and robot_mgr.is_online(robot.sn),
        "battery": robot.battery,
        "current_poi": robot.current_poi,
        "status": robot.status,
        "poi_list": robot.poi_list or [],
        "last_seen": robot.last_seen,
    }}


class SpeakRequest(BaseModel):
    text: str
    wait_done: bool = False

class NavRequest(BaseModel):
    poi: str
    wait_arrival: bool = False


@router.post("/speak")
async def robot_speak(body: SpeakRequest):
    action = RobotAction(settings.ROBOT_SN)
    result = await action.speak(body.text, body.wait_done)
    return {"code": 200, "data": result}


@router.post("/navigate")
async def robot_navigate(body: NavRequest):
    action = RobotAction(settings.ROBOT_SN)
    result = await action.navigate(body.poi, body.wait_arrival)
    return {"code": 200, "data": result}


@router.post("/stop")
async def robot_stop():
    action = RobotAction(settings.ROBOT_SN)
    result = await action.stop()
    return {"code": 200, "data": result}


@router.post("/charge")
async def robot_charge():
    action = RobotAction(settings.ROBOT_SN)
    result = await action.go_charge()
    return {"code": 200, "data": result}


# 点位映射管理
@router.get("/positions")
async def list_positions(db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(NavPosition).order_by(NavPosition.sort))
    positions = result.scalars().all()
    return {"code": 200, "data": [
        {
            "id": p.id,
            "robot_poi": p.robot_poi,
            "display_name": p.display_name,
            "terminal_id": p.terminal_id,
            "area_id": p.area_id,
            "aliases": p.aliases,
            "is_entry": p.is_entry,
            "is_charger": p.is_charger,
        }
        for p in positions
    ]}


class NavPosCreate(BaseModel):
    robot_poi: str
    display_name: str
    terminal_id: Optional[int] = None
    area_id: Optional[int] = None
    aliases: list[str] = []
    is_entry: bool = False
    is_charger: bool = False


@router.post("/positions")
async def create_position(body: NavPosCreate, db: AsyncSession = Depends(get_db)):
    pos = NavPosition(**body.model_dump())
    db.add(pos)
    await db.commit()
    return {"code": 200, "data": {"id": pos.id}}


@router.put("/positions/{pos_id}")
async def update_position(pos_id: int, body: NavPosCreate, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(NavPosition).where(NavPosition.id == pos_id))
    pos = result.scalar_one_or_none()
    if not pos:
        return {"code": 404, "msg": "not found"}
    for k, v in body.model_dump().items():
        setattr(pos, k, v)
    await db.commit()
    return {"code": 200}


@router.delete("/positions/{pos_id}")
async def delete_position(pos_id: int, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(NavPosition).where(NavPosition.id == pos_id))
    pos = result.scalar_one_or_none()
    if pos:
        await db.delete(pos)
        await db.commit()
    return {"code": 200}
