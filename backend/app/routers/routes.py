"""导览路线管理"""
from fastapi import APIRouter, Depends
from pydantic import BaseModel
from typing import Optional, List
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from ..database import get_db
from ..models import TourRoute

router = APIRouter(prefix="/api/routes", tags=["routes"])


@router.get("/")
async def list_routes(db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(TourRoute).order_by(TourRoute.sort))
    items = result.scalars().all()
    return {"code": 200, "data": [
        {
            "id": r.id,
            "name": r.name,
            "description": r.description,
            "trigger_keywords": r.trigger_keywords or [],
            "steps": r.steps or [],
            "sort": r.sort,
            "enabled": r.enabled,
            "estimated_minutes": r.estimated_minutes,
        } for r in items
    ]}


class RouteCreate(BaseModel):
    name: str
    description: Optional[str] = None
    trigger_keywords: List[str] = []
    # steps: [{poi, script_id, dwell_seconds, speak_text}]
    steps: List[dict] = []
    sort: int = 0
    enabled: bool = True
    estimated_minutes: int = 15


@router.post("/")
async def create_route(body: RouteCreate, db: AsyncSession = Depends(get_db)):
    r = TourRoute(**body.model_dump())
    db.add(r)
    await db.commit()
    await db.refresh(r)
    return {"code": 200, "data": {"id": r.id}}


@router.put("/{rid}")
async def update_route(rid: int, body: RouteCreate, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(TourRoute).where(TourRoute.id == rid))
    r = result.scalar_one_or_none()
    if not r:
        return {"code": 404}
    for k, v in body.model_dump().items():
        setattr(r, k, v)
    await db.commit()
    return {"code": 200}


@router.delete("/{rid}")
async def delete_route(rid: int, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(TourRoute).where(TourRoute.id == rid))
    r = result.scalar_one_or_none()
    if r:
        await db.delete(r)
        await db.commit()
    return {"code": 200}


@router.post("/{rid}/start")
async def start_route(rid: int, db: AsyncSession = Depends(get_db)):
    """触发执行这条导览路线"""
    from ..services.chat import execute_tour_route
    from ..database import AsyncSessionLocal
    import asyncio
    asyncio.create_task(execute_tour_route(rid))
    return {"code": 200, "msg": "导览路线已启动"}
