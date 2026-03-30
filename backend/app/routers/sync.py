from fastapi import APIRouter, Depends, BackgroundTasks
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from ..database import get_db
from ..services.sync import sync_all, sync_specials, sync_areas, sync_terminals_and_resources, sync_commands
from ..models import SyncLog, CloudSpecial, CloudTerminal, CloudResource, CloudCommand, CurrentSpecial

router = APIRouter(prefix="/api/sync", tags=["sync"])


@router.post("/all")
async def sync_all_data(bg: BackgroundTasks, db: AsyncSession = Depends(get_db)):
    async def do_sync():
        from ..database import AsyncSessionLocal
        async with AsyncSessionLocal() as db2:
            await sync_all(db2)
    bg.add_task(do_sync)
    return {"code": 200, "msg": "同步任务已启动"}


@router.get("/status")
async def sync_status(db: AsyncSession = Depends(get_db)):
    specials = (await db.execute(select(CloudSpecial))).scalars().all()
    terminals = (await db.execute(select(CloudTerminal))).scalars().all()
    resources = (await db.execute(select(CloudResource))).scalars().all()
    commands = (await db.execute(select(CloudCommand))).scalars().all()
    current = (await db.execute(select(CurrentSpecial).limit(1))).scalar_one_or_none()

    logs = (await db.execute(
        select(SyncLog).order_by(SyncLog.created_at.desc()).limit(10)
    )).scalars().all()

    return {
        "code": 200,
        "data": {
            "counts": {
                "specials": len(specials),
                "terminals": len(terminals),
                "resources": len(resources),
                "commands": len(commands),
            },
            "current_special": {
                "id": current.special_id if current else None,
                "name": current.special_name if current else None,
            } if current else None,
            "recent_logs": [
                {
                    "type": log.sync_type,
                    "count": log.records_count,
                    "status": log.status,
                    "error": log.error,
                    "time": log.created_at,
                }
                for log in logs
            ]
        }
    }
