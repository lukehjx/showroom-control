import asyncio
from fastapi import APIRouter
from sqlalchemy import select
from database import async_session
from models import Exhibit, NavPosition, ChatSession, ExhibitResource, CloudResource
from schemas import ok, err, KioskSelect
from datetime import datetime
import logging

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/kiosk", tags=["kiosk"])

# 全局自助状态
_kiosk_state = {
    "active": False,
    "exhibit_id": None,
    "exhibit_name": None,
    "robot_sn": None,
    "started_at": None
}


@router.get("/exhibits")
async def kiosk_list_exhibits():
    """返回展项列表（含点位信息，供机器人屏幕显示）"""
    try:
        async with async_session() as session:
            result = await session.execute(
                select(Exhibit).order_by(Exhibit.sort_order, Exhibit.id)
            )
            exhibits = result.scalars().all()

            data = []
            for e in exhibits:
                # 获取点位信息
                pos_info = None
                if e.nav_position_id:
                    pos = await session.get(NavPosition, e.nav_position_id)
                    if pos:
                        pos_info = {
                            "id": pos.id,
                            "cloud_position_name": pos.cloud_position_name,
                            "robot_poi_name": pos.robot_poi_name
                        }

                # 资源数量
                res_result = await session.execute(
                    select(ExhibitResource).where(ExhibitResource.exhibit_id == e.id)
                )
                resource_count = len(res_result.scalars().all())

                data.append({
                    "id": e.id,
                    "name": e.name,
                    "description": e.description,
                    "keywords": e.keywords,
                    "sort_order": e.sort_order,
                    "auto_intro": e.auto_intro,
                    "nav_position": pos_info,
                    "resource_count": resource_count
                })

        return ok(data)
    except Exception as e:
        logger.error(f"Kiosk exhibits error: {e}")
        return err(str(e))


@router.post("/select")
async def kiosk_select_exhibit(body: KioskSelect):
    """访客点选展项，触发机器人走位+讲解"""
    try:
        exhibit_id = body.exhibit_id
        robot_sn = body.robot_sn or ""

        async with async_session() as session:
            exhibit = await session.get(Exhibit, exhibit_id)
            if not exhibit:
                return err(f"Exhibit {exhibit_id} not found", 404)

            # 更新自助状态
            _kiosk_state.update({
                "active": True,
                "exhibit_id": exhibit_id,
                "exhibit_name": exhibit.name,
                "robot_sn": robot_sn,
                "started_at": datetime.now().isoformat()
            })

            # 获取导航点位
            poi_name = None
            if exhibit.nav_position_id:
                pos = await session.get(NavPosition, exhibit.nav_position_id)
                if pos:
                    poi_name = pos.robot_poi_name

        # 触发导航+讲解动作（异步）
        async def navigate_and_intro():
            try:
                from tcp_service import send_tcp
                from config import get_config

                if poi_name:
                    # 发送导航指令
                    logger.info(f"Kiosk: navigating to {poi_name} for exhibit {exhibit_id}")

                if exhibit.auto_intro and exhibit.description:
                    # 发送TTS讲解
                    logger.info(f"Kiosk: TTS intro for {exhibit.name}")

                # 更新会话
                async with async_session() as session:
                    result = await session.execute(
                        select(ChatSession).where(ChatSession.robot_sn == robot_sn).order_by(ChatSession.id.desc()).limit(1)
                    )
                    cs = result.scalar_one_or_none()
                    if cs:
                        cs.current_exhibit_id = exhibit_id
                        cs.last_activity_at = datetime.now()
                        await session.commit()
            except Exception as e:
                logger.error(f"Kiosk navigate_and_intro error: {e}")

        asyncio.create_task(navigate_and_intro())

        return ok({
            "exhibit_id": exhibit_id,
            "exhibit_name": exhibit.name,
            "poi_name": poi_name,
            "status": "triggered"
        })
    except Exception as e:
        logger.error(f"Kiosk select error: {e}")
        return err(str(e))


@router.get("/current")
async def kiosk_current():
    """获取当前自助状态"""
    return ok(_kiosk_state)
