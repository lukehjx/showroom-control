import asyncio
from fastapi import APIRouter, Query
from sqlalchemy import select, func
from database import async_session
from models import ReceptionSession, ReceptionPreset, Exhibit
from schemas import ok, err, ReceptionStart
from datetime import datetime
import logging

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/reception", tags=["reception"])

# 当前活跃接待会话
_active_session_id = None


@router.post("/start")
async def start_reception(body: ReceptionStart):
    """开始接待"""
    global _active_session_id
    try:
        async with async_session() as session:
            reception = ReceptionSession(
                started_at=datetime.now(),
                preset_used=body.preset_id,
                exhibits_visited=[],
                resources_played=[]
            )
            session.add(reception)
            await session.commit()
            await session.refresh(reception)
            _active_session_id = reception.id

        # 如果指定了套餐，触发套餐
        if body.preset_id:
            async with async_session() as session:
                preset = await session.get(ReceptionPreset, body.preset_id)
                if preset and preset.enabled:
                    from routers.presets import trigger_preset
                    asyncio.create_task(trigger_preset(body.preset_id))

        return ok({
            "session_id": _active_session_id,
            "started_at": datetime.now().isoformat(),
            "preset_id": body.preset_id
        })
    except Exception as e:
        logger.error(f"Start reception error: {e}")
        return err(str(e))


@router.post("/end")
async def end_reception():
    """结束接待并生成报告"""
    global _active_session_id
    try:
        if not _active_session_id:
            return err("No active reception session")

        async with async_session() as session:
            reception = await session.get(ReceptionSession, _active_session_id)
            if not reception:
                return err(f"Session {_active_session_id} not found", 404)

            ended_at = datetime.now()
            duration = int((ended_at - reception.started_at).total_seconds()) if reception.started_at else 0

            # 生成摘要
            exhibits_count = len(reception.exhibits_visited or [])
            resources_count = len(reception.resources_played or [])
            summary = f"接待时长：{duration}秒，参观展项：{exhibits_count}个，播放资源：{resources_count}个"

            reception.ended_at = ended_at
            reception.total_duration = duration
            reception.summary = summary
            await session.commit()
            await session.refresh(reception)

        session_id = _active_session_id
        _active_session_id = None

        return ok({
            "session_id": session_id,
            "duration": duration,
            "summary": summary,
            "exhibits_visited": reception.exhibits_visited or [],
            "resources_played": reception.resources_played or []
        })
    except Exception as e:
        logger.error(f"End reception error: {e}")
        return err(str(e))


@router.get("/reports")
async def list_reports(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100)
):
    """报告列表"""
    try:
        async with async_session() as session:
            total_q = select(func.count()).select_from(ReceptionSession)
            total = (await session.execute(total_q)).scalar()

            result = await session.execute(
                select(ReceptionSession)
                .order_by(ReceptionSession.id.desc())
                .offset((page - 1) * page_size)
                .limit(page_size)
            )
            sessions = result.scalars().all()

            data = [{
                "id": s.id,
                "started_at": str(s.started_at),
                "ended_at": str(s.ended_at) if s.ended_at else None,
                "preset_used": s.preset_used,
                "total_duration": s.total_duration,
                "summary": s.summary,
                "exhibits_count": len(s.exhibits_visited or []),
                "resources_count": len(s.resources_played or [])
            } for s in sessions]

        return ok({"total": total, "page": page, "page_size": page_size, "items": data})
    except Exception as e:
        return err(str(e))


@router.get("/reports/{report_id}")
async def get_report(report_id: int):
    """报告详情"""
    try:
        async with async_session() as session:
            reception = await session.get(ReceptionSession, report_id)
            if not reception:
                return err(f"Report {report_id} not found", 404)

            # 查询套餐名称
            preset_name = None
            if reception.preset_used:
                preset = await session.get(ReceptionPreset, reception.preset_used)
                if preset:
                    preset_name = preset.name

        report = {
            "id": reception.id,
            "started_at": str(reception.started_at),
            "ended_at": str(reception.ended_at) if reception.ended_at else None,
            "preset_used": reception.preset_used,
            "preset_name": preset_name,
            "total_duration": reception.total_duration,
            "summary": reception.summary,
            "exhibits_visited": reception.exhibits_visited or [],
            "resources_played": reception.resources_played or []
        }

        # 发送到企微
        try:
            from config import get_config
            import httpx
            bot_id = await get_config("wecom_bot.bot_id") or ""
            if bot_id:
                report_text = f"📊 接待报告 #{report_id}\n{reception.summary or '无摘要'}\n开始：{reception.started_at}\n结束：{reception.ended_at}"
                logger.info(f"Sending report to wecom: {report_text[:100]}")
        except Exception as e:
            logger.warning(f"Send to wecom failed: {e}")

        return ok(report)
    except Exception as e:
        return err(str(e))
