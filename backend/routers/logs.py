from fastapi import APIRouter, Query
from sqlalchemy import select, func
from database import async_session
from models import OperationLog
from schemas import ok, err
import logging

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/logs", tags=["logs"])


@router.get("")
async def list_logs(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=200),
    action: str = Query(None)
):
    try:
        async with async_session() as session:
            query = select(OperationLog)
            if action:
                query = query.where(OperationLog.action.contains(action))
            query = query.order_by(OperationLog.created_at.desc())

            # 总数
            count_q = select(func.count()).select_from(query.subquery())
            total = (await session.execute(count_q)).scalar()

            # 分页
            query = query.offset((page - 1) * page_size).limit(page_size)
            result = await session.execute(query)
            logs = result.scalars().all()

            data = [{
                "id": l.id,
                "action": l.action,
                "source": l.source,
                "params": l.params,
                "result": l.result,
                "created_at": str(l.created_at)
            } for l in logs]

        return ok({"total": total, "page": page, "page_size": page_size, "items": data})
    except Exception as e:
        logger.error(f"List logs error: {e}")
        return err(str(e))
