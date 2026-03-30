from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from database import get_db
from models import SystemConfig
from schemas import ok, err, ConfigItem
from datetime import datetime
import logging

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/config", tags=["config"])


@router.get("")
async def get_all_configs(db: AsyncSession = Depends(get_db)):
    try:
        result = await db.execute(select(SystemConfig))
        configs = result.scalars().all()
        data = [{"key": c.key, "value": c.value, "description": c.description, "updated_at": str(c.updated_at)} for c in configs]
        return ok(data)
    except Exception as e:
        logger.error(f"Get configs error: {e}")
        return err(str(e))


@router.post("")
async def batch_update_configs(items: list[ConfigItem], db: AsyncSession = Depends(get_db)):
    try:
        for item in items:
            result = await db.execute(select(SystemConfig).where(SystemConfig.key == item.key))
            cfg = result.scalar_one_or_none()
            if cfg:
                cfg.value = item.value
                if item.description:
                    cfg.description = item.description
                cfg.updated_at = datetime.now()
            else:
                db.add(SystemConfig(key=item.key, value=item.value, description=item.description, updated_at=datetime.now()))
        await db.commit()
        return ok({"updated": len(items)})
    except Exception as e:
        await db.rollback()
        logger.error(f"Batch update configs error: {e}")
        return err(str(e))


@router.get("/{key}")
async def get_config(key: str, db: AsyncSession = Depends(get_db)):
    try:
        result = await db.execute(select(SystemConfig).where(SystemConfig.key == key))
        cfg = result.scalar_one_or_none()
        if not cfg:
            return err(f"Config key '{key}' not found", 404)
        return ok({"key": cfg.key, "value": cfg.value, "description": cfg.description})
    except Exception as e:
        logger.error(f"Get config {key} error: {e}")
        return err(str(e))


@router.put("/{key}")
async def update_config(key: str, item: ConfigItem, db: AsyncSession = Depends(get_db)):
    try:
        result = await db.execute(select(SystemConfig).where(SystemConfig.key == key))
        cfg = result.scalar_one_or_none()
        if cfg:
            cfg.value = item.value
            if item.description:
                cfg.description = item.description
            cfg.updated_at = datetime.now()
        else:
            db.add(SystemConfig(key=key, value=item.value, description=item.description, updated_at=datetime.now()))
        await db.commit()
        return ok({"key": key})
    except Exception as e:
        await db.rollback()
        logger.error(f"Update config {key} error: {e}")
        return err(str(e))


@router.put("")
async def update_configs_batch(body: dict, db: AsyncSession = Depends(get_db)):
    """Batch update configs via dict {key: value}"""
    try:
        for key, value in body.items():
            result = await db.execute(select(SystemConfig).where(SystemConfig.key == key))
            cfg = result.scalar_one_or_none()
            if cfg:
                cfg.value = str(value)
                cfg.updated_at = datetime.now()
            else:
                db.add(SystemConfig(key=key, value=str(value), description=None, updated_at=datetime.now()))
        await db.commit()
        return ok({"updated": len(body)})
    except Exception as e:
        await db.rollback()
        logger.error(f"Batch update configs error: {e}")
        return err(str(e))
