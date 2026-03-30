from fastapi import APIRouter
from database import async_session
from sqlalchemy import text
from pydantic import BaseModel
from typing import Optional
import logging

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/wecom-users", tags=["wecom_users"])


class WecomUserUpdate(BaseModel):
    display_name: Optional[str] = None
    self_reported_name: Optional[str] = None
    name_confirmed: Optional[bool] = None


@router.get("")
async def list_users():
    async with async_session() as db:
        result = await db.execute(text("SELECT * FROM wecom_users ORDER BY last_active DESC NULLS LAST"))
        rows = result.mappings().fetchall()
    return {"code": 0, "data": [dict(r) for r in rows]}


@router.patch("/{user_id}")
async def update_user(user_id: int, data: WecomUserUpdate):
    async with async_session() as db:
        if data.display_name:
            dn = data.display_name.replace("'", "''")
            await db.execute(text(
                f"UPDATE wecom_users SET display_name='{dn}', name_confirmed=true, updated_at=NOW() WHERE id={user_id}"
            ))
        if data.name_confirmed is not None and not data.display_name:
            await db.execute(text(
                f"UPDATE wecom_users SET name_confirmed={data.name_confirmed}, updated_at=NOW() WHERE id={user_id}"
            ))
        await db.commit()
    return {"code": 0}


async def get_or_create_user(userid: str) -> dict:
    """获取或创建企微用户记录，返回用户信息"""
    async with async_session() as db:
        result = await db.execute(text(f"SELECT * FROM wecom_users WHERE wecom_user_id='{userid}'"))
        row = result.mappings().first()
        if not row:
            await db.execute(text(f"INSERT INTO wecom_users (userid) VALUES ('{userid}') ON CONFLICT DO NOTHING"))
            await db.commit()
            result = await db.execute(text(f"SELECT * FROM wecom_users WHERE wecom_user_id='{userid}'"))
            row = result.mappings().first()
    return dict(row) if row else {}


async def get_display_name(userid: str) -> str:
    """获取用户显示名：管理员设置的优先，其次自报，否则返回空"""
    user = await get_or_create_user(userid)
    return user.get("display_name") or user.get("self_reported_name") or ""


async def save_self_reported_name(userid: str, name: str):
    """保存用户自报姓名（仅当管理员未设置时才填充 display_name，避免覆盖）"""
    name_e = name.replace("'", "''")
    async with async_session() as db:
        await db.execute(text(
            f"\n            UPDATE wecom_users SET \n                self_reported_name='{name_e}',\n                updated_at=NOW()\n            WHERE wecom_user_id='{userid}'\n        "
        ))
        await db.commit()
