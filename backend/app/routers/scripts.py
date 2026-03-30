"""展项讲解词管理"""
from fastapi import APIRouter, Depends
from pydantic import BaseModel
from typing import Optional, List
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, delete
from ..database import get_db
from ..models import ExhibitScript

router = APIRouter(prefix="/api/scripts", tags=["scripts"])


@router.get("/")
async def list_scripts(db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(ExhibitScript).order_by(ExhibitScript.sort))
    items = result.scalars().all()
    return {"code": 200, "data": [
        {
            "id": s.id,
            "title": s.title,
            "trigger_keywords": s.trigger_keywords or [],
            "nav_poi": s.nav_poi,
            "tts_text": s.tts_text,
            "resource_id": s.resource_id,
            "terminal_id": s.terminal_id,
            "duration": s.duration,
            "sort": s.sort,
            "enabled": s.enabled,
        } for s in items
    ]}


class ScriptCreate(BaseModel):
    title: str
    trigger_keywords: List[str] = []
    nav_poi: Optional[str] = None
    tts_text: Optional[str] = None
    resource_id: Optional[str] = None
    terminal_id: Optional[int] = None
    duration: int = 60
    sort: int = 0
    enabled: bool = True


@router.post("/")
async def create_script(body: ScriptCreate, db: AsyncSession = Depends(get_db)):
    s = ExhibitScript(**body.model_dump())
    db.add(s)
    await db.commit()
    await db.refresh(s)
    return {"code": 200, "data": {"id": s.id}}


@router.put("/{sid}")
async def update_script(sid: int, body: ScriptCreate, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(ExhibitScript).where(ExhibitScript.id == sid))
    s = result.scalar_one_or_none()
    if not s:
        return {"code": 404}
    for k, v in body.model_dump().items():
        setattr(s, k, v)
    await db.commit()
    return {"code": 200}


@router.delete("/{sid}")
async def delete_script(sid: int, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(ExhibitScript).where(ExhibitScript.id == sid))
    s = result.scalar_one_or_none()
    if s:
        await db.delete(s)
        await db.commit()
    return {"code": 200}
