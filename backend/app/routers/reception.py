"""接待套餐、预约管理"""
from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from typing import Optional, List
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_
from ..database import get_db
from ..models import ReceptionPreset, Appointment

router = APIRouter(prefix="/api/reception", tags=["reception"])


# ===== 接待套餐 =====

@router.get("/presets")
async def list_presets(db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(ReceptionPreset).order_by(ReceptionPreset.sort))
    items = result.scalars().all()
    return {"code": 200, "data": [
        {
            "id": p.id,
            "name": p.name,
            "description": p.description,
            "trigger_keywords": p.trigger_keywords or [],
            "steps": p.steps or [],
            "sort": p.sort,
            "enabled": p.enabled,
        } for p in items
    ]}


class PresetCreate(BaseModel):
    name: str
    description: Optional[str] = None
    trigger_keywords: List[str] = []
    steps: List[dict] = []
    sort: int = 0
    enabled: bool = True


@router.post("/presets")
async def create_preset(body: PresetCreate, db: AsyncSession = Depends(get_db)):
    p = ReceptionPreset(**body.model_dump())
    db.add(p)
    await db.commit()
    await db.refresh(p)
    return {"code": 200, "data": {"id": p.id}}


@router.put("/presets/{pid}")
async def update_preset(pid: int, body: PresetCreate, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(ReceptionPreset).where(ReceptionPreset.id == pid))
    p = result.scalar_one_or_none()
    if not p:
        return {"code": 404}
    for k, v in body.model_dump().items():
        setattr(p, k, v)
    await db.commit()
    return {"code": 200}


@router.delete("/presets/{pid}")
async def delete_preset(pid: int, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(ReceptionPreset).where(ReceptionPreset.id == pid))
    p = result.scalar_one_or_none()
    if p:
        await db.delete(p)
        await db.commit()
    return {"code": 200}


@router.post("/presets/{pid}/execute")
async def execute_preset(pid: int):
    """立即执行接待套餐"""
    import asyncio
    from ..services.chat import execute_reception_preset
    asyncio.create_task(execute_reception_preset(pid))
    return {"code": 200, "msg": "接待套餐已启动"}


# ===== 预约管理 =====

@router.get("/appointments")
async def list_appointments(
    status: Optional[str] = Query(None),
    db: AsyncSession = Depends(get_db)
):
    query = select(Appointment).order_by(Appointment.visit_time)
    if status:
        query = query.where(Appointment.status == status)
    result = await db.execute(query)
    items = result.scalars().all()
    return {"code": 200, "data": [
        {
            "id": a.id,
            "visitor_name": a.visitor_name,
            "visitor_company": a.visitor_company,
            "visitor_count": a.visitor_count,
            "visit_time": a.visit_time,
            "preset_id": a.preset_id,
            "contact": a.contact,
            "status": a.status,
            "notes": a.notes,
            "created_at": a.created_at,
        } for a in items
    ]}


class AppointmentCreate(BaseModel):
    visitor_name: str
    visitor_company: Optional[str] = None
    visitor_count: int = 1
    visit_time: str  # ISO datetime string
    preset_id: Optional[int] = None
    contact: Optional[str] = None
    notes: Optional[str] = None


@router.post("/appointments")
async def create_appointment(body: AppointmentCreate, db: AsyncSession = Depends(get_db)):
    from datetime import datetime
    a = Appointment(
        visitor_name=body.visitor_name,
        visitor_company=body.visitor_company,
        visitor_count=body.visitor_count,
        visit_time=datetime.fromisoformat(body.visit_time),
        preset_id=body.preset_id,
        contact=body.contact,
        notes=body.notes,
        status="pending",
    )
    db.add(a)
    await db.commit()
    await db.refresh(a)
    return {"code": 200, "data": {"id": a.id}}


@router.put("/appointments/{aid}/status")
async def update_appointment_status(
    aid: int,
    status: str = Query(..., description="pending/confirmed/cancelled/completed"),
    db: AsyncSession = Depends(get_db)
):
    result = await db.execute(select(Appointment).where(Appointment.id == aid))
    a = result.scalar_one_or_none()
    if not a:
        return {"code": 404}
    a.status = status
    await db.commit()
    return {"code": 200}


@router.delete("/appointments/{aid}")
async def delete_appointment(aid: int, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Appointment).where(Appointment.id == aid))
    a = result.scalar_one_or_none()
    if a:
        await db.delete(a)
        await db.commit()
    return {"code": 200}
