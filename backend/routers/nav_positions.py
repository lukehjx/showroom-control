from fastapi import APIRouter
from sqlalchemy import select
from database import async_session
from models import NavPosition
from schemas import ok, err, NavPositionCreate, NavPositionUpdate
import logging

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/nav-positions", tags=["nav-positions"])


@router.get("")
async def list_nav_positions():
    try:
        async with async_session() as session:
            result = await session.execute(select(NavPosition).order_by(NavPosition.id))
            positions = result.scalars().all()
            data = [{
                "id": p.id,
                "cloud_position_name": p.cloud_position_name,
                "robot_poi_name": p.robot_poi_name,
                "description": p.description
            } for p in positions]
        return ok(data)
    except Exception as e:
        return err(str(e))


@router.post("")
async def create_nav_position(body: NavPositionCreate):
    try:
        async with async_session() as session:
            pos = NavPosition(**body.model_dump())
            session.add(pos)
            await session.commit()
            await session.refresh(pos)
            return ok({"id": pos.id})
    except Exception as e:
        return err(str(e))


@router.get("/{pos_id}")
async def get_nav_position(pos_id: int):
    try:
        async with async_session() as session:
            pos = await session.get(NavPosition, pos_id)
            if not pos:
                return err(f"NavPosition {pos_id} not found", 404)
            return ok({"id": pos.id, "cloud_position_name": pos.cloud_position_name,
                       "robot_poi_name": pos.robot_poi_name, "description": pos.description})
    except Exception as e:
        return err(str(e))


@router.put("/{pos_id}")
async def update_nav_position(pos_id: int, body: NavPositionUpdate):
    try:
        async with async_session() as session:
            pos = await session.get(NavPosition, pos_id)
            if not pos:
                return err(f"NavPosition {pos_id} not found", 404)
            for k, v in body.model_dump(exclude_none=True).items():
                setattr(pos, k, v)
            await session.commit()
            return ok({"id": pos_id})
    except Exception as e:
        return err(str(e))


@router.delete("/{pos_id}")
async def delete_nav_position(pos_id: int):
    try:
        async with async_session() as session:
            pos = await session.get(NavPosition, pos_id)
            if not pos:
                return err(f"NavPosition {pos_id} not found", 404)
            await session.delete(pos)
            await session.commit()
            return ok({"deleted": pos_id})
    except Exception as e:
        return err(str(e))
