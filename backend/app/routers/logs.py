"""操作日志 & 对话记录"""
from fastapi import APIRouter, Depends, Query
from typing import Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, desc
from ..database import get_db
from ..models import OperationLog, ChatLog

router = APIRouter(prefix="/api/logs", tags=["logs"])


@router.get("/operations")
async def list_op_logs(
    limit: int = Query(100, le=500),
    offset: int = 0,
    level: Optional[str] = None,
    db: AsyncSession = Depends(get_db)
):
    query = select(OperationLog).order_by(desc(OperationLog.created_at)).offset(offset).limit(limit)
    if level:
        query = query.where(OperationLog.level == level)
    result = await db.execute(query)
    items = result.scalars().all()
    return {"code": 200, "data": [
        {
            "id": l.id,
            "level": l.level,
            "action": l.action,
            "detail": l.detail,
            "operator": l.operator,
            "result": l.result,
            "created_at": l.created_at,
        } for l in items
    ]}


@router.get("/chats")
async def list_chat_logs(
    limit: int = Query(50, le=200),
    offset: int = 0,
    source: Optional[str] = None,
    db: AsyncSession = Depends(get_db)
):
    query = select(ChatLog).order_by(desc(ChatLog.created_at)).offset(offset).limit(limit)
    if source:
        query = query.where(ChatLog.source == source)
    result = await db.execute(query)
    items = result.scalars().all()
    return {"code": 200, "data": [
        {
            "id": l.id,
            "source": l.source,
            "input_text": l.input_text,
            "intent": l.intent,
            "response": l.response,
            "success": l.success,
            "duration_ms": l.duration_ms,
            "created_at": l.created_at,
        } for l in items
    ]}


@router.delete("/operations")
async def clear_op_logs(days: int = Query(30), db: AsyncSession = Depends(get_db)):
    """清理N天前的操作日志"""
    from datetime import datetime, timedelta
    cutoff = datetime.now() - timedelta(days=days)
    from sqlalchemy import delete
    await db.execute(delete(OperationLog).where(OperationLog.created_at < cutoff))
    await db.commit()
    return {"code": 200, "msg": f"已清理 {days} 天前的操作日志"}
