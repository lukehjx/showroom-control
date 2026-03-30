"""系统设置"""
from fastapi import APIRouter, Depends
from pydantic import BaseModel
from typing import Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from ..database import get_db
from ..models import SystemSetting

router = APIRouter(prefix="/api/settings", tags=["settings"])


@router.get("/")
async def get_settings(db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(SystemSetting))
    items = result.scalars().all()
    data = {s.key: s.value for s in items}
    return {"code": 200, "data": data}


class SettingUpdate(BaseModel):
    key: str
    value: str


@router.put("/")
async def update_setting(body: SettingUpdate, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(SystemSetting).where(SystemSetting.key == body.key))
    s = result.scalar_one_or_none()
    if s:
        s.value = body.value
    else:
        db.add(SystemSetting(key=body.key, value=body.value))
    await db.commit()
    return {"code": 200}


@router.get("/robot-config")
async def get_robot_config():
    """获取机器人相关配置（掩码敏感信息）"""
    from ..config import settings
    return {"code": 200, "data": {
        "robot_sn": settings.ROBOT_SN,
        "backend_ws_url": "wss://robot.sidex.cn/ws/robot/",
        "zhongkong_base_url": settings.ZHONGKONG_BASE_URL,
        "zhongkong_tcp": f"{settings.ZHONGKONG_TCP_HOST}:{settings.ZHONGKONG_TCP_PORT}",
        "wecom_bot_id": settings.WECOM_BOT_ID[:8] + "****" if settings.WECOM_BOT_ID else "",
    }}
