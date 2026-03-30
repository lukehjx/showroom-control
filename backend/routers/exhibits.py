from fastapi import APIRouter
from sqlalchemy import select
from database import async_session
from models import Exhibit, ExhibitResource, NavPosition
from schemas import ok, err, ExhibitCreate, ExhibitUpdate, ExhibitResourceCreate
import logging

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/exhibits", tags=["exhibits"])


@router.get("")
async def list_exhibits():
    try:
        async with async_session() as session:
            result = await session.execute(select(Exhibit).order_by(Exhibit.sort_order, Exhibit.id))
            exhibits = result.scalars().all()
            data = [{
                "id": e.id,
                "name": e.name,
                "keywords": e.keywords,
                "nav_position_id": e.nav_position_id,
                "sort_order": e.sort_order,
                "auto_intro": e.auto_intro,
                "description": e.description,
                "created_at": str(e.created_at)
            } for e in exhibits]
        return ok(data)
    except Exception as e:
        logger.error(f"List exhibits error: {e}")
        return err(str(e))


@router.post("")
async def create_exhibit(body: ExhibitCreate):
    try:
        async with async_session() as session:
            exhibit = Exhibit(**body.model_dump())
            session.add(exhibit)
            await session.commit()
            await session.refresh(exhibit)
            return ok({"id": exhibit.id, "name": exhibit.name})
    except Exception as e:
        logger.error(f"Create exhibit error: {e}")
        return err(str(e))


@router.get("/{exhibit_id}")
async def get_exhibit(exhibit_id: int):
    try:
        async with async_session() as session:
            exhibit = await session.get(Exhibit, exhibit_id)
            if not exhibit:
                return err(f"Exhibit {exhibit_id} not found", 404)
            return ok({
                "id": exhibit.id,
                "name": exhibit.name,
                "keywords": exhibit.keywords,
                "nav_position_id": exhibit.nav_position_id,
                "sort_order": exhibit.sort_order,
                "auto_intro": exhibit.auto_intro,
                "description": exhibit.description,
                "created_at": str(exhibit.created_at)
            })
    except Exception as e:
        logger.error(f"Get exhibit error: {e}")
        return err(str(e))


@router.put("/{exhibit_id}")
async def update_exhibit(exhibit_id: int, body: ExhibitUpdate):
    try:
        async with async_session() as session:
            exhibit = await session.get(Exhibit, exhibit_id)
            if not exhibit:
                return err(f"Exhibit {exhibit_id} not found", 404)
            for k, v in body.model_dump(exclude_none=True).items():
                setattr(exhibit, k, v)
            await session.commit()
            return ok({"id": exhibit_id})
    except Exception as e:
        await session.rollback()
        logger.error(f"Update exhibit error: {e}")
        return err(str(e))


@router.delete("/{exhibit_id}")
async def delete_exhibit(exhibit_id: int):
    try:
        async with async_session() as session:
            exhibit = await session.get(Exhibit, exhibit_id)
            if not exhibit:
                return err(f"Exhibit {exhibit_id} not found", 404)
            await session.delete(exhibit)
            await session.commit()
            return ok({"deleted": exhibit_id})
    except Exception as e:
        logger.error(f"Delete exhibit error: {e}")
        return err(str(e))


@router.get("/{exhibit_id}/resources")
async def get_exhibit_resources(exhibit_id: int):
    try:
        async with async_session() as session:
            result = await session.execute(
                select(ExhibitResource).where(ExhibitResource.exhibit_id == exhibit_id).order_by(ExhibitResource.sort_order)
            )
            resources = result.scalars().all()
            data = [{
                "id": r.id,
                "exhibit_id": r.exhibit_id,
                "cloud_resource_id": r.cloud_resource_id,
                "terminal_id": r.terminal_id,
                "sort_order": r.sort_order,
                "notes": r.notes
            } for r in resources]
        return ok(data)
    except Exception as e:
        logger.error(f"Get exhibit resources error: {e}")
        return err(str(e))


@router.post("/{exhibit_id}/resources")
async def add_exhibit_resource(exhibit_id: int, body: ExhibitResourceCreate):
    try:
        async with async_session() as session:
            resource = ExhibitResource(exhibit_id=exhibit_id, **body.model_dump())
            session.add(resource)
            await session.commit()
            await session.refresh(resource)
            return ok({"id": resource.id})
    except Exception as e:
        logger.error(f"Add exhibit resource error: {e}")
        return err(str(e))
