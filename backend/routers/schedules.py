from fastapi import APIRouter
from sqlalchemy import select
from database import async_session
from models import ScheduledTask
from schemas import ok, err, ScheduledTaskCreate, ScheduledTaskUpdate
from scheduler import add_or_update_task, remove_task, reload_all_tasks
from datetime import datetime
import logging

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/schedules", tags=["schedules"])


@router.get("")
async def list_schedules():
    try:
        async with async_session() as session:
            result = await session.execute(select(ScheduledTask).order_by(ScheduledTask.id))
            tasks = result.scalars().all()
            data = [{
                "id": t.id, "name": t.name, "cron_expr": t.cron_expr,
                "action_type": t.action_type, "action_config": t.action_config,
                "enabled": t.enabled,
                "last_run_at": str(t.last_run_at) if t.last_run_at else None,
                "next_run_at": str(t.next_run_at) if t.next_run_at else None,
                "created_at": str(t.created_at)
            } for t in tasks]
        return ok(data)
    except Exception as e:
        return err(str(e))


@router.post("")
async def create_schedule(body: ScheduledTaskCreate):
    try:
        async with async_session() as session:
            task = ScheduledTask(**body.model_dump())
            session.add(task)
            await session.commit()
            await session.refresh(task)
            # 注册到调度器
            if task.enabled:
                await add_or_update_task(task.id, task.cron_expr, task.enabled)
            return ok({"id": task.id})
    except Exception as e:
        return err(str(e))


@router.get("/{task_id}")
async def get_schedule(task_id: int):
    try:
        async with async_session() as session:
            task = await session.get(ScheduledTask, task_id)
            if not task:
                return err(f"Schedule {task_id} not found", 404)
            return ok({
                "id": task.id, "name": task.name, "cron_expr": task.cron_expr,
                "action_type": task.action_type, "action_config": task.action_config,
                "enabled": task.enabled,
                "last_run_at": str(task.last_run_at) if task.last_run_at else None,
                "created_at": str(task.created_at)
            })
    except Exception as e:
        return err(str(e))


@router.put("/{task_id}")
async def update_schedule(task_id: int, body: ScheduledTaskUpdate):
    try:
        async with async_session() as session:
            task = await session.get(ScheduledTask, task_id)
            if not task:
                return err(f"Schedule {task_id} not found", 404)
            for k, v in body.model_dump(exclude_none=True).items():
                setattr(task, k, v)
            await session.commit()
            await session.refresh(task)
            # 更新调度器
            await add_or_update_task(task.id, task.cron_expr, task.enabled)
            return ok({"id": task_id})
    except Exception as e:
        return err(str(e))


@router.delete("/{task_id}")
async def delete_schedule(task_id: int):
    try:
        async with async_session() as session:
            task = await session.get(ScheduledTask, task_id)
            if not task:
                return err(f"Schedule {task_id} not found", 404)
            remove_task(task_id)
            await session.delete(task)
            await session.commit()
            return ok({"deleted": task_id})
    except Exception as e:
        return err(str(e))


@router.post("/{task_id}/toggle")
async def toggle_schedule(task_id: int):
    try:
        async with async_session() as session:
            task = await session.get(ScheduledTask, task_id)
            if not task:
                return err(f"Schedule {task_id} not found", 404)
            task.enabled = not task.enabled
            await session.commit()
            await add_or_update_task(task.id, task.cron_expr, task.enabled)
            return ok({"id": task_id, "enabled": task.enabled})
    except Exception as e:
        return err(str(e))
