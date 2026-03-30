import logging
from typing import Optional
from fastapi import APIRouter
from pydantic import BaseModel
from sqlalchemy import text
from database import async_session
from schemas import ok, err

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api", tags=["tour-stops"])


class TourStopCreate(BaseModel):
    terminal_id: int
    terminal_name: Optional[str] = None
    nav_poi_name: Optional[str] = None
    order_index: int = 0
    welcome_text: Optional[str] = None
    enabled: bool = True
    robot_sn: str = "MC1BCN2K100262058CA0"
    note: Optional[str] = None


class TourStopUpdate(BaseModel):
    terminal_id: Optional[int] = None
    terminal_name: Optional[str] = None
    nav_poi_name: Optional[str] = None
    order_index: Optional[int] = None
    welcome_text: Optional[str] = None
    enabled: Optional[bool] = None
    robot_sn: Optional[str] = None
    note: Optional[str] = None


class OrderDirection(BaseModel):
    direction: str  # "up" or "down"


def row_to_dict(row):
    return {
        "id": row.id,
        "robot_sn": row.robot_sn,
        "terminal_id": row.terminal_id,
        "terminal_name": row.terminal_name,
        "nav_poi_name": row.nav_poi_name,
        "order_index": row.order_index,
        "welcome_text": row.welcome_text,
        "enabled": row.enabled,
        "note": row.note,
        "created_at": str(row.created_at) if row.created_at else None,
        "updated_at": str(row.updated_at) if row.updated_at else None,
    }


@router.get("/tour-stops")
async def list_tour_stops():
    try:
        async with async_session() as session:
            result = await session.execute(
                text("SELECT * FROM tour_stops ORDER BY order_index, id")
            )
            rows = result.fetchall()
            data = [row_to_dict(r) for r in rows]
        return ok(data)
    except Exception as e:
        logger.error(f"List tour stops error: {e}")
        return err(str(e))


@router.post("/tour-stops")
async def create_tour_stop(body: TourStopCreate):
    try:
        async with async_session() as session:
            result = await session.execute(
                text("""
                    INSERT INTO tour_stops (robot_sn, terminal_id, terminal_name, nav_poi_name, order_index, welcome_text, enabled, note)
                    VALUES (:robot_sn, :terminal_id, :terminal_name, :nav_poi_name, :order_index, :welcome_text, :enabled, :note)
                    RETURNING *
                """),
                {
                    "robot_sn": body.robot_sn,
                    "terminal_id": body.terminal_id,
                    "terminal_name": body.terminal_name,
                    "nav_poi_name": body.nav_poi_name,
                    "order_index": body.order_index,
                    "welcome_text": body.welcome_text,
                    "enabled": body.enabled,
                    "note": body.note,
                }
            )
            await session.commit()
            row = result.fetchone()
        return ok(row_to_dict(row))
    except Exception as e:
        logger.error(f"Create tour stop error: {e}")
        return err(str(e))


@router.put("/tour-stops/{stop_id}")
async def update_tour_stop(stop_id: int, body: TourStopUpdate):
    try:
        async with async_session() as session:
            # Build dynamic SET clause
            updates = {}
            if body.terminal_id is not None:
                updates["terminal_id"] = body.terminal_id
            if body.terminal_name is not None:
                updates["terminal_name"] = body.terminal_name
            if body.nav_poi_name is not None:
                updates["nav_poi_name"] = body.nav_poi_name
            if body.order_index is not None:
                updates["order_index"] = body.order_index
            if body.welcome_text is not None:
                updates["welcome_text"] = body.welcome_text
            if body.enabled is not None:
                updates["enabled"] = body.enabled
            if body.robot_sn is not None:
                updates["robot_sn"] = body.robot_sn
            if body.note is not None:
                updates["note"] = body.note

            if not updates:
                return err("No fields to update")

            set_clause = ", ".join(f"{k} = :{k}" for k in updates)
            updates["id"] = stop_id
            result = await session.execute(
                text(f"UPDATE tour_stops SET {set_clause}, updated_at = NOW() WHERE id = :id RETURNING *"),
                updates
            )
            await session.commit()
            row = result.fetchone()
            if not row:
                return err("Not found", 404)
        return ok(row_to_dict(row))
    except Exception as e:
        logger.error(f"Update tour stop error: {e}")
        return err(str(e))


@router.delete("/tour-stops/{stop_id}")
async def delete_tour_stop(stop_id: int):
    try:
        async with async_session() as session:
            result = await session.execute(
                text("DELETE FROM tour_stops WHERE id = :id RETURNING id"),
                {"id": stop_id}
            )
            await session.commit()
            row = result.fetchone()
            if not row:
                return err("Not found", 404)
        return ok({"id": stop_id})
    except Exception as e:
        logger.error(f"Delete tour stop error: {e}")
        return err(str(e))


@router.patch("/tour-stops/{stop_id}/order")
async def reorder_tour_stop(stop_id: int, body: OrderDirection):
    try:
        async with async_session() as session:
            # Get current stop
            result = await session.execute(
                text("SELECT * FROM tour_stops WHERE id = :id"), {"id": stop_id}
            )
            current = result.fetchone()
            if not current:
                return err("Not found", 404)

            current_order = current.order_index

            if body.direction == "up":
                # Find the stop just above (lower order_index)
                result2 = await session.execute(
                    text("SELECT * FROM tour_stops WHERE order_index < :order ORDER BY order_index DESC LIMIT 1"),
                    {"order": current_order}
                )
            else:
                # Find the stop just below (higher order_index)
                result2 = await session.execute(
                    text("SELECT * FROM tour_stops WHERE order_index > :order ORDER BY order_index ASC LIMIT 1"),
                    {"order": current_order}
                )

            swap = result2.fetchone()
            if not swap:
                return ok({"message": "Already at boundary"})

            # Swap order_index
            await session.execute(
                text("UPDATE tour_stops SET order_index = :new_order, updated_at = NOW() WHERE id = :id"),
                {"new_order": swap.order_index, "id": stop_id}
            )
            await session.execute(
                text("UPDATE tour_stops SET order_index = :new_order, updated_at = NOW() WHERE id = :id"),
                {"new_order": current_order, "id": swap.id}
            )
            await session.commit()
        return ok({"message": "Order updated"})
    except Exception as e:
        logger.error(f"Reorder tour stop error: {e}")
        return err(str(e))


@router.post("/tour-stops/init")
async def init_tour_stops():
    try:
        async with async_session() as session:
            # Clear existing
            await session.execute(text("DELETE FROM tour_stops"))

            # Query terminals with matching nav positions
            # Actual terminal IDs: 230=入口三联屏, 223=小岛台正面, 222=大岛台正面, 229=CAVE空间投影
            terminals = await session.execute(text("""
                SELECT ct.id, ct.name,
                       np.robot_poi_name
                FROM cloud_terminals ct
                LEFT JOIN nav_positions np ON np.cloud_position_name = ct.name
                WHERE ct.name IN ('入口三联屏', '小岛台正面', '大岛台正面', 'CAVE空间投影')
                ORDER BY CASE ct.name
                    WHEN '入口三联屏' THEN 1
                    WHEN '小岛台正面' THEN 2
                    WHEN '大岛台正面' THEN 3
                    WHEN 'CAVE空间投影' THEN 4
                    ELSE 5
                END
            """))
            rows = terminals.fetchall()

            count = 0
            for i, t in enumerate(rows, 1):
                await session.execute(
                    text("""
                        INSERT INTO tour_stops (robot_sn, terminal_id, terminal_name, nav_poi_name, order_index, welcome_text, enabled)
                        VALUES (:robot_sn, :terminal_id, :terminal_name, :nav_poi_name, :order_index, :welcome_text, TRUE)
                    """),
                    {
                        "robot_sn": "MC1BCN2K100262058CA0",
                        "terminal_id": t.id,
                        "terminal_name": t.name,
                        "nav_poi_name": t.robot_poi_name,
                        "order_index": i,
                        "welcome_text": f"我们来到{t.name}，这里展示了最新的科技成果。",
                    }
                )
                count += 1

            await session.commit()

        return ok({"count": count, "message": f"已初始化{count}个导览站点"})
    except Exception as e:
        logger.error(f"Init tour stops error: {e}")
        return err(str(e))
