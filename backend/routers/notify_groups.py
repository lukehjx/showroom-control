from fastapi import APIRouter
from database import async_session
from sqlalchemy import text
from pydantic import BaseModel
from typing import Optional
import logging

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/notify-groups", tags=["notify_groups"])


class NotifyGroupCreate(BaseModel):
    name: str
    chat_id: str
    enabled: bool = True
    notify_types: str = "all"


class NotifyGroupUpdate(BaseModel):
    name: Optional[str] = None
    enabled: Optional[bool] = None
    notify_types: Optional[str] = None


@router.get("")
async def list_groups():
    async with async_session() as db:
        result = await db.execute(text("SELECT * FROM notify_groups ORDER BY created_at DESC"))
        rows = result.mappings().fetchall()
    return {"code": 0, "data": [dict(r) for r in rows]}


@router.post("")
async def create_group(data: NotifyGroupCreate):
    n = data.name.replace("'", "''")
    c = data.chat_id.replace("'", "''")
    t = data.notify_types.replace("'", "''")
    async with async_session() as db:
        result = await db.execute(text(
            f"\n            INSERT INTO notify_groups (name, chat_id, enabled, notify_types)\n            VALUES ('{n}', '{c}', {data.enabled}, '{t}')\n            ON CONFLICT (chat_id) DO UPDATE SET name='{n}', enabled={data.enabled}, updated_at=NOW()\n            RETURNING id\n        "
        ))
        new_id = result.scalar()
        await db.commit()
    return {"code": 0, "data": {"id": new_id}}


@router.patch("/{group_id}")
async def update_group(group_id: int, data: NotifyGroupUpdate):
    updates = []

    if data.name:
        updates.append(f"name='{data.name.replace(chr(39), chr(39)*2)}'")

    if data.enabled is not None:
        updates.append(f"enabled={data.enabled}")

    if data.notify_types:
        updates.append(f"notify_types='{data.notify_types.replace(chr(39), chr(39)*2)}'")

    if not updates:
        return {"code": 0}

    updates.append("updated_at=NOW()")
    async with async_session() as db:
        await db.execute(text(f"UPDATE notify_groups SET {', '.join(updates)} WHERE id={group_id}"))
        await db.commit()
    return {"code": 0}


@router.delete("/{group_id}")
async def delete_group(group_id: int):
    async with async_session() as db:
        await db.execute(text(f"DELETE FROM notify_groups WHERE id={group_id}"))
        await db.commit()
    return {"code": 0}


async def get_enabled_chat_ids() -> list:
    """获取所有启用的群ID列表，供推送使用"""
    async with async_session() as db:
        result = await db.execute(text("SELECT chat_id FROM notify_groups WHERE enabled=true"))
        rows = result.fetchall()
    return [r[0] for r in rows]
