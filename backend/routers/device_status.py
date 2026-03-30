from fastapi import APIRouter
from sqlalchemy import select
from database import async_session
from models import DeviceStatus
from schemas import ok, err
from device_monitor import run_device_check
import logging

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/device-status", tags=["device-status"])


@router.get("")
async def list_device_status():
    """所有设备在线状态"""
    try:
        async with async_session() as session:
            result = await session.execute(select(DeviceStatus).order_by(DeviceStatus.terminal_id))
            statuses = result.scalars().all()
            data = [{
                "id": s.id,
                "terminal_id": s.terminal_id,
                "terminal_name": s.terminal_name,
                "ip": s.ip,
                "port": s.port,
                "is_online": s.is_online,
                "last_checked_at": str(s.last_checked_at) if s.last_checked_at else None,
                "response_ms": s.response_ms
            } for s in statuses]
        return ok(data)
    except Exception as e:
        return err(str(e))


@router.get("/{terminal_id}")
async def get_device_status(terminal_id: int):
    """单个设备状态"""
    try:
        async with async_session() as session:
            result = await session.execute(
                select(DeviceStatus).where(DeviceStatus.terminal_id == terminal_id).limit(1)
            )
            status = result.scalar_one_or_none()
            if not status:
                return err(f"Device status for terminal {terminal_id} not found", 404)
            return ok({
                "id": status.id,
                "terminal_id": status.terminal_id,
                "terminal_name": status.terminal_name,
                "ip": status.ip,
                "port": status.port,
                "is_online": status.is_online,
                "last_checked_at": str(status.last_checked_at) if status.last_checked_at else None,
                "response_ms": status.response_ms
            })
    except Exception as e:
        return err(str(e))


@router.post("/refresh")
async def refresh_device_status():
    """手动触发一次设备状态检测"""
    try:
        import asyncio
        asyncio.create_task(run_device_check())
        return ok({"message": "Device check triggered"})
    except Exception as e:
        return err(str(e))
