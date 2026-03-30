from fastapi import APIRouter
from sqlalchemy import select
from database import async_session
from models import SyncLog
from schemas import ok, err
from cloud_sync import sync_all, sync_terminals, sync_resources, sync_commands, sync_scenes
import logging

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/sync", tags=["sync"])

SYNC_FUNCS = {
    "terminals": sync_terminals,
    "resources": sync_resources,
    "commands": sync_commands,
    "scenes": sync_scenes,
}


@router.post("/all")
async def sync_all_data():
    try:
        result = await sync_all()
        return ok(result)
    except Exception as e:
        logger.error(f"Sync all error: {e}")
        return err(str(e))


@router.post("/{sync_type}")
async def sync_by_type(sync_type: str):
    if sync_type not in SYNC_FUNCS:
        return err(f"Unknown sync type: {sync_type}. Use: terminals, resources, commands, scenes")
    try:
        result = await SYNC_FUNCS[sync_type]()
        return ok(result)
    except Exception as e:
        logger.error(f"Sync {sync_type} error: {e}")
        return err(str(e))


@router.get("/status")
async def sync_status():
    try:
        async with async_session() as session:
            result = await session.execute(
                select(SyncLog).order_by(SyncLog.created_at.desc()).limit(20)
            )
            logs = result.scalars().all()
            data = [{
                "id": l.id,
                "sync_type": l.sync_type,
                "status": l.status,
                "records_count": l.records_count,
                "error": l.error,
                "created_at": str(l.created_at)
            } for l in logs]
        return ok(data)
    except Exception as e:
        logger.error(f"Sync status error: {e}")
        return err(str(e))
