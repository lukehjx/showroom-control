from fastapi import APIRouter, Query
from database import async_session
from sqlalchemy import text
import logging

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/visitor-logs", tags=["visitor_logs"])


@router.get("")
async def list_visitor_logs(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=500),
    robot_sn: str = None,
):
    conditions = ["1=1"]
    if robot_sn:
        conditions.append(f"robot_sn='{robot_sn.replace(chr(39), chr(39)*2)}'")
    where = " AND ".join(conditions)

    async with async_session() as db:
        result = await db.execute(text(
            f"SELECT * FROM visitor_logs WHERE {where} ORDER BY created_at DESC LIMIT {limit} OFFSET {skip}"
        ))
        rows = result.mappings().fetchall()
        count_result = await db.execute(text(f"SELECT COUNT(*) FROM visitor_logs WHERE {where}"))
        total = count_result.scalar()

    return {"code": 0, "data": [dict(r) for r in rows], "total": total}


@router.get("/{log_id}")
async def get_visitor_log(log_id: int):
    async with async_session() as db:
        result = await db.execute(text(f"SELECT * FROM visitor_logs WHERE id={log_id}"))
        row = result.mappings().first()
    if not row:
        return {"code": 404, "data": None, "message": "Not found"}
    return {"code": 0, "data": dict(row)}
