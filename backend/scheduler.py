import logging
import asyncio
from datetime import datetime
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from sqlalchemy import select
from database import async_session
from models import ScheduledTask

logger = logging.getLogger(__name__)

_scheduler: AsyncIOScheduler = None


async def run_task(task_id: int):
    """执行定时任务"""
    async with async_session() as session:
        task = await session.get(ScheduledTask, task_id)
        if not task or not task.enabled:
            return

        logger.info(f"Running scheduled task {task_id}: {task.name} ({task.action_type})")

        config = task.action_config or {}
        try:
            if task.action_type == "trigger_preset":
                preset_id = config.get("preset_id")
                if preset_id:
                    from routers.presets import trigger_preset_logic
                    await trigger_preset_logic(preset_id)

            elif task.action_type == "trigger_route":
                route_id = config.get("route_id")
                if route_id:
                    from lane_engine import execute_route
                    await execute_route(route_id, triggered_by=f"schedule_{task_id}")

            elif task.action_type == "tcp_send":
                from tcp_service import send_tcp
                await send_tcp(
                    config.get("host", ""),
                    int(config.get("port", 80)),
                    config.get("data", ""),
                    config.get("encoding", "utf-8"),
                    config.get("is_hex", False)
                )

            elif task.action_type == "http_get":
                import httpx
                async with httpx.AsyncClient(timeout=15) as client:
                    await client.get(config.get("url", ""), params=config.get("params", {}))

            task.last_run_at = datetime.now()
            await session.commit()
            logger.info(f"Task {task_id} completed")

        except Exception as e:
            logger.error(f"Task {task_id} failed: {e}")


async def reload_all_tasks():
    """从数据库重新加载所有定时任务"""
    global _scheduler
    if not _scheduler:
        return

    # 清空现有job
    _scheduler.remove_all_jobs()

    async with async_session() as session:
        result = await session.execute(select(ScheduledTask).where(ScheduledTask.enabled == True))
        tasks = result.scalars().all()

    for task in tasks:
        try:
            _scheduler.add_job(
                run_task,
                CronTrigger.from_crontab(task.cron_expr),
                args=[task.id],
                id=f"task_{task.id}",
                replace_existing=True
            )
            logger.info(f"Scheduled task {task.id} ({task.name}) with cron: {task.cron_expr}")
        except Exception as e:
            logger.error(f"Failed to schedule task {task.id}: {e}")


async def add_or_update_task(task_id: int, cron_expr: str, enabled: bool):
    """添加或更新单个任务"""
    global _scheduler
    if not _scheduler:
        return

    job_id = f"task_{task_id}"
    _scheduler.remove_job(job_id) if _scheduler.get_job(job_id) else None

    if enabled:
        try:
            _scheduler.add_job(
                run_task,
                CronTrigger.from_crontab(cron_expr),
                args=[task_id],
                id=job_id,
                replace_existing=True
            )
        except Exception as e:
            logger.error(f"Failed to add job {job_id}: {e}")


def remove_task(task_id: int):
    global _scheduler
    if _scheduler:
        job_id = f"task_{task_id}"
        if _scheduler.get_job(job_id):
            _scheduler.remove_job(job_id)


async def start_scheduler():
    global _scheduler
    _scheduler = AsyncIOScheduler(timezone="Asia/Shanghai")
    _scheduler.start()
    await reload_all_tasks()
    logger.info("APScheduler started")


def get_scheduler() -> AsyncIOScheduler:
    return _scheduler
