from fastapi import APIRouter
from sqlalchemy import select
from database import async_session
from models import RobotConfig
from schemas import ok, err, RobotCreate, RobotUpdate
import logging

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/robots", tags=["robots"])


@router.get("")
async def list_robots():
    try:
        async with async_session() as session:
            result = await session.execute(select(RobotConfig).order_by(RobotConfig.id))
            robots = result.scalars().all()
            data = [{
                "id": r.id, "sn": r.sn, "name": r.name,
                "app_key": r.app_key, "webhook_url": r.webhook_url, "enabled": r.enabled
            } for r in robots]
        return ok(data)
    except Exception as e:
        return err(str(e))


@router.post("")
async def create_robot(body: RobotCreate):
    try:
        async with async_session() as session:
            robot = RobotConfig(**body.model_dump())
            session.add(robot)
            await session.commit()
            await session.refresh(robot)
            return ok({"id": robot.id})
    except Exception as e:
        return err(str(e))


@router.get("/{robot_id}")
async def get_robot(robot_id: int):
    try:
        async with async_session() as session:
            robot = await session.get(RobotConfig, robot_id)
            if not robot:
                return err(f"Robot {robot_id} not found", 404)
            return ok({"id": robot.id, "sn": robot.sn, "name": robot.name,
                       "app_key": robot.app_key, "webhook_url": robot.webhook_url, "enabled": robot.enabled})
    except Exception as e:
        return err(str(e))


@router.put("/{robot_id}")
async def update_robot(robot_id: int, body: RobotUpdate):
    try:
        async with async_session() as session:
            robot = await session.get(RobotConfig, robot_id)
            if not robot:
                return err(f"Robot {robot_id} not found", 404)
            for k, v in body.model_dump(exclude_none=True).items():
                setattr(robot, k, v)
            await session.commit()
            return ok({"id": robot_id})
    except Exception as e:
        return err(str(e))


@router.delete("/{robot_id}")
async def delete_robot(robot_id: int):
    try:
        async with async_session() as session:
            robot = await session.get(RobotConfig, robot_id)
            if not robot:
                return err(f"Robot {robot_id} not found", 404)
            await session.delete(robot)
            await session.commit()
            return ok({"deleted": robot_id})
    except Exception as e:
        return err(str(e))
