"""流程编排管理"""
from fastapi import APIRouter, Depends
from pydantic import BaseModel
from typing import Optional, List
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from ..database import get_db
from ..models import FlowRoute

router = APIRouter(prefix="/api/flows", tags=["flows"])


@router.get("/")
async def list_flows(db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(FlowRoute).order_by(FlowRoute.sort))
    items = result.scalars().all()
    return {"code": 200, "data": [
        {
            "id": f.id,
            "name": f.name,
            "description": f.description,
            "trigger_keywords": f.trigger_keywords or [],
            "steps": f.steps_json or [],
            "enabled": f.enabled,
            "sort": f.sort,
        } for f in items
    ]}


class FlowStepCreate(BaseModel):
    type: str
    config: dict = {}
    wait_done: bool = True


class FlowCreate(BaseModel):
    name: str
    description: Optional[str] = None
    trigger_keywords: List[str] = []
    steps: List[FlowStepCreate] = []
    enabled: bool = True
    sort: int = 0


@router.post("/")
async def create_flow(body: FlowCreate, db: AsyncSession = Depends(get_db)):
    f = FlowRoute(
        name=body.name,
        description=body.description,
        trigger_keywords=body.trigger_keywords,
        steps_json=[s.model_dump() for s in body.steps],
        enabled=body.enabled,
        sort=body.sort,
    )
    db.add(f)
    await db.commit()
    await db.refresh(f)
    return {"code": 200, "data": {"id": f.id}}


@router.put("/{fid}")
async def update_flow(fid: int, body: FlowCreate, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(FlowRoute).where(FlowRoute.id == fid))
    f = result.scalar_one_or_none()
    if not f:
        return {"code": 404}
    f.name = body.name
    f.description = body.description
    f.trigger_keywords = body.trigger_keywords
    f.steps_json = [s.model_dump() for s in body.steps]
    f.enabled = body.enabled
    f.sort = body.sort
    await db.commit()
    return {"code": 200}


@router.delete("/{fid}")
async def delete_flow(fid: int, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(FlowRoute).where(FlowRoute.id == fid))
    f = result.scalar_one_or_none()
    if f:
        await db.delete(f)
        await db.commit()
    return {"code": 200}


@router.post("/{fid}/run")
async def run_flow(fid: int, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(FlowRoute).where(FlowRoute.id == fid))
    f = result.scalar_one_or_none()
    if not f:
        return {"code": 404}
    import asyncio
    from ..services.flow_engine import execute_flow_steps
    from ..database import AsyncSessionLocal
    steps = f.steps_json or []
    asyncio.create_task(execute_flow_steps(steps))
    return {"code": 200, "msg": f"流程 [{f.name}] 已启动"}
