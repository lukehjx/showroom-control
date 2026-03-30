import asyncio
from fastapi import APIRouter
from sqlalchemy import select
from database import async_session
from models import ReceptionPreset, PresetRoute, ApiRoute
from schemas import ok, err, PresetCreate, PresetUpdate, PresetRouteCreate
from lane_engine import execute_route
import logging

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/presets", tags=["presets"])


@router.get("")
async def list_presets():
    try:
        async with async_session() as session:
            result = await session.execute(
                select(ReceptionPreset).order_by(ReceptionPreset.sort_order, ReceptionPreset.id)
            )
            presets = result.scalars().all()
            data = [{
                "id": p.id, "name": p.name, "description": p.description,
                "icon": p.icon, "color": p.color, "sort_order": p.sort_order,
                "enabled": p.enabled, "created_at": str(p.created_at)
            } for p in presets]
        return ok(data)
    except Exception as e:
        return err(str(e))


@router.post("")
async def create_preset(body: PresetCreate):
    try:
        async with async_session() as session:
            preset = ReceptionPreset(**body.model_dump())
            session.add(preset)
            await session.commit()
            await session.refresh(preset)
            return ok({"id": preset.id})
    except Exception as e:
        return err(str(e))


@router.get("/{preset_id}")
async def get_preset(preset_id: int):
    try:
        async with async_session() as session:
            preset = await session.get(ReceptionPreset, preset_id)
            if not preset:
                return err(f"Preset {preset_id} not found", 404)

            # 查询绑定的路由
            result = await session.execute(
                select(PresetRoute).where(PresetRoute.preset_id == preset_id).order_by(PresetRoute.sort_order)
            )
            routes = result.scalars().all()

            return ok({
                "id": preset.id, "name": preset.name, "description": preset.description,
                "icon": preset.icon, "color": preset.color, "sort_order": preset.sort_order,
                "enabled": preset.enabled, "created_at": str(preset.created_at),
                "routes": [{"id": r.id, "route_id": r.route_id, "sort_order": r.sort_order} for r in routes]
            })
    except Exception as e:
        return err(str(e))


@router.put("/{preset_id}")
async def update_preset(preset_id: int, body: PresetUpdate):
    try:
        async with async_session() as session:
            preset = await session.get(ReceptionPreset, preset_id)
            if not preset:
                return err(f"Preset {preset_id} not found", 404)
            for k, v in body.model_dump(exclude_none=True).items():
                setattr(preset, k, v)
            await session.commit()
            return ok({"id": preset_id})
    except Exception as e:
        return err(str(e))


@router.delete("/{preset_id}")
async def delete_preset(preset_id: int):
    try:
        async with async_session() as session:
            preset = await session.get(ReceptionPreset, preset_id)
            if not preset:
                return err(f"Preset {preset_id} not found", 404)
            await session.delete(preset)
            await session.commit()
            return ok({"deleted": preset_id})
    except Exception as e:
        return err(str(e))


@router.post("/{preset_id}/routes")
async def bind_route_to_preset(preset_id: int, body: PresetRouteCreate):
    try:
        async with async_session() as session:
            preset = await session.get(ReceptionPreset, preset_id)
            if not preset:
                return err(f"Preset {preset_id} not found", 404)
            pr = PresetRoute(preset_id=preset_id, route_id=body.route_id, sort_order=body.sort_order)
            session.add(pr)
            await session.commit()
            await session.refresh(pr)
            return ok({"id": pr.id})
    except Exception as e:
        return err(str(e))


@router.post("/{preset_id}/trigger")
async def trigger_preset(preset_id: int):
    """一键启动套餐：依次触发绑定的所有路由"""
    try:
        async with async_session() as session:
            preset = await session.get(ReceptionPreset, preset_id)
            if not preset:
                return err(f"Preset {preset_id} not found", 404)
            if not preset.enabled:
                return err(f"Preset {preset_id} is disabled")

            result = await session.execute(
                select(PresetRoute).where(PresetRoute.preset_id == preset_id).order_by(PresetRoute.sort_order)
            )
            preset_routes = result.scalars().all()

        if not preset_routes:
            return ok({"preset_id": preset_id, "routes_triggered": 0, "message": "No routes bound"})

        # 创建接待会话
        from models import ReceptionSession
        from datetime import datetime
        async with async_session() as session:
            reception = ReceptionSession(
                preset_used=preset_id,
                started_at=datetime.now(),
                exhibits_visited=[],
                resources_played=[]
            )
            session.add(reception)
            await session.commit()
            await session.refresh(reception)
            reception_id = reception.id

        # 异步顺序触发所有路由
        async def run_preset_routes():
            for pr in preset_routes:
                try:
                    await execute_route(pr.route_id, triggered_by=f"preset_{preset_id}")
                except Exception as e:
                    logger.error(f"Preset {preset_id} route {pr.route_id} failed: {e}")

        asyncio.create_task(run_preset_routes())

        return ok({
            "preset_id": preset_id,
            "preset_name": preset.name,
            "routes_triggered": len(preset_routes),
            "reception_id": reception_id
        })
    except Exception as e:
        logger.error(f"Trigger preset {preset_id} error: {e}")
        return err(str(e))


@router.delete('/{preset_id}/routes')
async def clear_preset_routes(preset_id: int):
    """清空套餐绑定的所有流程"""
    try:
        from sqlalchemy import delete as sa_delete
        async with async_session() as session:
            await session.execute(
                sa_delete(PresetRoute).where(PresetRoute.preset_id == preset_id)
            )
            await session.commit()
            return ok({'deleted': True, 'preset_id': preset_id})
    except Exception as e:
        return err(str(e))


@router.delete('/{preset_id}/routes/{route_binding_id}')
async def delete_preset_route(preset_id: int, route_binding_id: int):
    """删除套餐中某条绑定流程"""
    try:
        async with async_session() as session:
            pr = await session.get(PresetRoute, route_binding_id)
            if not pr or pr.preset_id != preset_id:
                return err('Not found', 404)
            await session.delete(pr)
            await session.commit()
            return ok({'deleted': route_binding_id})
    except Exception as e:
        return err(str(e))
