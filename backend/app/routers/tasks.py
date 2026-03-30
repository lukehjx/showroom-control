"""定时任务 & 通知群组管理"""
from fastapi import APIRouter, Depends
from pydantic import BaseModel
from typing import Optional, List
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from ..database import get_db
from ..models import ScheduledTask, NotifyGroup

router = APIRouter(prefix="/api/tasks", tags=["tasks"])


# ===== 定时任务 =====

@router.get("/")
async def list_tasks(db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(ScheduledTask).order_by(ScheduledTask.id))
    items = result.scalars().all()
    return {"code": 200, "data": [
        {
            "id": t.id,
            "name": t.name,
            "cron_expr": t.cron_expr,
            "task_type": t.task_type,
            "payload": t.payload or {},
            "enabled": t.enabled,
            "last_run": t.last_run,
            "next_run": t.next_run,
        } for t in items
    ]}


class TaskCreate(BaseModel):
    name: str
    cron_expr: str  # "0 9 * * 1-5" = 工作日9点
    task_type: str  # open_hall / close_hall / sync_data / custom_flow
    payload: dict = {}
    enabled: bool = True


@router.post("/")
async def create_task(body: TaskCreate, db: AsyncSession = Depends(get_db)):
    t = ScheduledTask(**body.model_dump())
    db.add(t)
    await db.commit()
    await db.refresh(t)
    # 注册到 APScheduler
    from ..main import scheduler
    _register_job(scheduler, t)
    return {"code": 200, "data": {"id": t.id}}


@router.put("/{tid}")
async def update_task(tid: int, body: TaskCreate, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(ScheduledTask).where(ScheduledTask.id == tid))
    t = result.scalar_one_or_none()
    if not t:
        return {"code": 404}
    for k, v in body.model_dump().items():
        setattr(t, k, v)
    await db.commit()
    # 重新注册
    from ..main import scheduler
    try:
        scheduler.remove_job(f"task_{tid}")
    except Exception:
        pass
    if t.enabled:
        _register_job(scheduler, t)
    return {"code": 200}


@router.delete("/{tid}")
async def delete_task(tid: int, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(ScheduledTask).where(ScheduledTask.id == tid))
    t = result.scalar_one_or_none()
    if t:
        from ..main import scheduler
        try:
            scheduler.remove_job(f"task_{tid}")
        except Exception:
            pass
        await db.delete(t)
        await db.commit()
    return {"code": 200}


@router.post("/{tid}/run")
async def run_task_now(tid: int, db: AsyncSession = Depends(get_db)):
    """立即执行一次定时任务"""
    result = await db.execute(select(ScheduledTask).where(ScheduledTask.id == tid))
    t = result.scalar_one_or_none()
    if not t:
        return {"code": 404}
    import asyncio
    asyncio.create_task(_exec_task(t.task_type, t.payload or {}))
    return {"code": 200, "msg": f"任务 [{t.name}] 已触发"}


def _register_job(scheduler, task):
    from apscheduler.triggers.cron import CronTrigger
    scheduler.add_job(
        _exec_task_sync,
        CronTrigger.from_crontab(task.cron_expr),
        id=f"task_{task.id}",
        args=[task.task_type, task.payload or {}],
        replace_existing=True,
    )


def _exec_task_sync(task_type: str, payload: dict):
    import asyncio
    asyncio.create_task(_exec_task(task_type, payload))


async def _exec_task(task_type: str, payload: dict):
    from ..services.commands import send_group_command
    from ..services.sync import sync_all
    from ..database import AsyncSessionLocal
    if task_type == "open_hall":
        await send_group_command("0_all_on")
    elif task_type == "close_hall":
        await send_group_command("0_all_off")
    elif task_type == "sync_data":
        async with AsyncSessionLocal() as db:
            await sync_all(db)
    elif task_type == "custom_flow":
        flow_id = payload.get("flow_id")
        if flow_id:
            from ..services.flow_engine import execute_flow
            async with AsyncSessionLocal() as db:
                await execute_flow(flow_id, db)


# ===== 通知群组 =====

notify_router = APIRouter(prefix="/api/notify-groups", tags=["notify"])


@notify_router.get("/")
async def list_groups(db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(NotifyGroup))
    items = result.scalars().all()
    return {"code": 200, "data": [
        {
            "id": g.id,
            "name": g.name,
            "chat_id": g.chat_id,
            "enabled": g.enabled,
            "notify_types": g.notify_types or [],
        } for g in items
    ]}


class GroupCreate(BaseModel):
    name: str
    chat_id: str
    enabled: bool = True
    notify_types: List[str] = ["arrival", "command", "error"]


@notify_router.post("/")
async def create_group(body: GroupCreate, db: AsyncSession = Depends(get_db)):
    g = NotifyGroup(**body.model_dump())
    db.add(g)
    await db.commit()
    await db.refresh(g)
    return {"code": 200, "data": {"id": g.id}}


@notify_router.put("/{gid}")
async def update_group(gid: int, body: GroupCreate, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(NotifyGroup).where(NotifyGroup.id == gid))
    g = result.scalar_one_or_none()
    if not g:
        return {"code": 404}
    for k, v in body.model_dump().items():
        setattr(g, k, v)
    await db.commit()
    return {"code": 200}


@notify_router.delete("/{gid}")
async def delete_group(gid: int, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(NotifyGroup).where(NotifyGroup.id == gid))
    g = result.scalar_one_or_none()
    if g:
        await db.delete(g)
        await db.commit()
    return {"code": 200}


@notify_router.post("/{gid}/test")
async def test_notify(gid: int, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(NotifyGroup).where(NotifyGroup.id == gid))
    g = result.scalar_one_or_none()
    if not g:
        return {"code": 404}
    from ..services.wecom_bot import send_notify
    await send_notify(g.chat_id, "🔔 测试通知：展厅智控系统连接正常")
    return {"code": 200, "msg": "测试消息已发送"}
