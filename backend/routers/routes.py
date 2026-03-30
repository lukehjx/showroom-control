import asyncio
from fastapi import APIRouter
from sqlalchemy import select
from database import async_session
from models import ApiRoute, RouteLane, LaneStep, FlowExecution, ExecutionStep
from schemas import ok, err, RouteCreate, RouteUpdate, LaneCreate, LaneUpdate, StepCreate, StepUpdate
from lane_engine import execute_route
import logging

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api", tags=["routes"])


# ============ Routes ============
@router.get("/routes")
async def list_routes():
    try:
        async with async_session() as session:
            result = await session.execute(select(ApiRoute).order_by(ApiRoute.id))
            routes = result.scalars().all()
            data = [{
                "id": r.id, "name": r.name, "path": r.path,
                "description": r.description, "enabled": r.enabled,
                "created_at": str(r.created_at)
            } for r in routes]
        return ok(data)
    except Exception as e:
        return err(str(e))


@router.post("/routes")
async def create_route(body: RouteCreate):
    try:
        async with async_session() as session:
            route = ApiRoute(**body.model_dump())
            session.add(route)
            await session.commit()
            await session.refresh(route)
            return ok({"id": route.id})
    except Exception as e:
        return err(str(e))


@router.get("/routes/{route_id}")
async def get_route(route_id: int):
    try:
        async with async_session() as session:
            route = await session.get(ApiRoute, route_id)
            if not route:
                return err(f"Route {route_id} not found", 404)
            return ok({"id": route.id, "name": route.name, "path": route.path, "description": route.description, "enabled": route.enabled})
    except Exception as e:
        return err(str(e))


@router.put("/routes/{route_id}")
async def update_route(route_id: int, body: RouteUpdate):
    try:
        async with async_session() as session:
            route = await session.get(ApiRoute, route_id)
            if not route:
                return err(f"Route {route_id} not found", 404)
            for k, v in body.model_dump(exclude_none=True).items():
                setattr(route, k, v)
            await session.commit()
            return ok({"id": route_id})
    except Exception as e:
        return err(str(e))


@router.delete("/routes/{route_id}")
async def delete_route(route_id: int):
    try:
        async with async_session() as session:
            route = await session.get(ApiRoute, route_id)
            if not route:
                return err(f"Route {route_id} not found", 404)
            await session.delete(route)
            await session.commit()
            return ok({"deleted": route_id})
    except Exception as e:
        return err(str(e))


@router.post("/routes/{route_id}/trigger")
async def trigger_route(route_id: int):
    try:
        # 先同步创建 execution 记录，再异步执行步骤
        from models import FlowExecution
        from database import async_session
        from datetime import datetime
        async with async_session() as session:
            execution = FlowExecution(
                route_id=route_id,
                triggered_by="api",
                status="running",
                started_at=datetime.now()
            )
            session.add(execution)
            await session.commit()
            await session.refresh(execution)
            execution_id = execution.id

        async def _run():
            from lane_engine import execute_route as _exec
            await _exec(route_id, triggered_by="api", execution_id=execution_id)

        asyncio.create_task(_run())
        return ok({"route_id": route_id, "status": "triggered", "execution_id": execution_id})
    except Exception as e:
        logger.error(f"Trigger route {route_id} error: {e}")
        return err(str(e))


# ============ Lanes ============
@router.get("/routes/{route_id}/lanes")
async def get_route_lanes(route_id: int):
    try:
        async with async_session() as session:
            result = await session.execute(
                select(RouteLane).where(RouteLane.route_id == route_id).order_by(RouteLane.sort_order)
            )
            lanes = result.scalars().all()
            data = [{
                "id": l.id, "route_id": l.route_id, "name": l.name,
                "sort_order": l.sort_order, "parallel_group": l.parallel_group
            } for l in lanes]
        return ok(data)
    except Exception as e:
        return err(str(e))


@router.post("/routes/{route_id}/lanes")
async def create_lane(route_id: int, body: LaneCreate):
    try:
        async with async_session() as session:
            lane = RouteLane(route_id=route_id, **body.model_dump())
            session.add(lane)
            await session.commit()
            await session.refresh(lane)
            return ok({"id": lane.id})
    except Exception as e:
        return err(str(e))


@router.get("/lanes/{lane_id}")
async def get_lane(lane_id: int):
    try:
        async with async_session() as session:
            lane = await session.get(RouteLane, lane_id)
            if not lane:
                return err(f"Lane {lane_id} not found", 404)
            return ok({"id": lane.id, "route_id": lane.route_id, "name": lane.name, "sort_order": lane.sort_order, "parallel_group": lane.parallel_group})
    except Exception as e:
        return err(str(e))


@router.put("/lanes/{lane_id}")
async def update_lane(lane_id: int, body: LaneUpdate):
    try:
        async with async_session() as session:
            lane = await session.get(RouteLane, lane_id)
            if not lane:
                return err(f"Lane {lane_id} not found", 404)
            for k, v in body.model_dump(exclude_none=True).items():
                setattr(lane, k, v)
            await session.commit()
            return ok({"id": lane_id})
    except Exception as e:
        return err(str(e))


@router.delete("/lanes/{lane_id}")
async def delete_lane(lane_id: int):
    try:
        async with async_session() as session:
            lane = await session.get(RouteLane, lane_id)
            if not lane:
                return err(f"Lane {lane_id} not found", 404)
            await session.delete(lane)
            await session.commit()
            return ok({"deleted": lane_id})
    except Exception as e:
        return err(str(e))


# ============ Steps ============
@router.get("/lanes/{lane_id}/steps")
async def get_lane_steps(lane_id: int):
    try:
        async with async_session() as session:
            result = await session.execute(
                select(LaneStep).where(LaneStep.lane_id == lane_id).order_by(LaneStep.sort_order)
            )
            steps = result.scalars().all()
            data = [{
                "id": s.id, "lane_id": s.lane_id, "sort_order": s.sort_order,
                "action_type": s.action_type, "action_config": s.action_config,
                "wait_type": s.wait_type, "wait_timeout": s.wait_timeout, "description": s.description
            } for s in steps]
        return ok(data)
    except Exception as e:
        return err(str(e))


@router.post("/lanes/{lane_id}/steps")
async def create_step(lane_id: int, body: StepCreate):
    try:
        async with async_session() as session:
            step = LaneStep(lane_id=lane_id, **body.model_dump())
            session.add(step)
            await session.commit()
            await session.refresh(step)
            return ok({"id": step.id})
    except Exception as e:
        return err(str(e))


@router.get("/steps/{step_id}")
async def get_step(step_id: int):
    try:
        async with async_session() as session:
            step = await session.get(LaneStep, step_id)
            if not step:
                return err(f"Step {step_id} not found", 404)
            return ok({"id": step.id, "lane_id": step.lane_id, "sort_order": step.sort_order,
                       "action_type": step.action_type, "action_config": step.action_config,
                       "wait_type": step.wait_type, "wait_timeout": step.wait_timeout, "description": step.description})
    except Exception as e:
        return err(str(e))


@router.put("/steps/{step_id}")
async def update_step(step_id: int, body: StepUpdate):
    try:
        async with async_session() as session:
            step = await session.get(LaneStep, step_id)
            if not step:
                return err(f"Step {step_id} not found", 404)
            for k, v in body.model_dump(exclude_none=True).items():
                setattr(step, k, v)
            await session.commit()
            return ok({"id": step_id})
    except Exception as e:
        return err(str(e))


@router.delete("/steps/{step_id}")
async def delete_step(step_id: int):
    try:
        async with async_session() as session:
            step = await session.get(LaneStep, step_id)
            if not step:
                return err(f"Step {step_id} not found", 404)
            await session.delete(step)
            await session.commit()
            return ok({"deleted": step_id})
    except Exception as e:
        return err(str(e))


# ============ Executions ============
@router.get("/executions/{execution_id}/status")
async def get_execution_status(execution_id: int):
    try:
        async with async_session() as session:
            execution = await session.get(FlowExecution, execution_id)
            if not execution:
                return err(f"Execution {execution_id} not found", 404)
            result = await session.execute(
                select(ExecutionStep).where(ExecutionStep.execution_id == execution_id).order_by(ExecutionStep.id)
            )
            steps = result.scalars().all()
            return ok({
                "id": execution.id,
                "route_id": execution.route_id,
                "triggered_by": execution.triggered_by,
                "status": execution.status,
                "started_at": str(execution.started_at),
                "finished_at": str(execution.finished_at) if execution.finished_at else None,
                "error": execution.error,
                "steps": [{
                    "id": s.id, "step_id": s.step_id, "status": s.status,
                    "result": s.result,
                    "started_at": str(s.started_at) if s.started_at else None,
                    "finished_at": str(s.finished_at) if s.finished_at else None
                } for s in steps]
            })
    except Exception as e:
        return err(str(e))
