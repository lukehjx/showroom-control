"""
机器人WebSocket接入端点
APK 连接后：
  1. 发送身份认证（sn）
  2. 接收云端指令
  3. 上报状态/回调
"""
import json
import logging
import time
from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from sqlalchemy import select, update
from ..database import AsyncSessionLocal
from ..models import RobotStatus, ChatSession
from ..services.robot import robot_mgr
from ..services.chat import handle_input
from ..config import settings

router = APIRouter()
logger = logging.getLogger(__name__)


@router.websocket("/ws/robot/{sn}")
async def robot_ws(websocket: WebSocket, sn: str):
    await robot_mgr.connect(sn, websocket)

    # 更新机器人在线状态
    async with AsyncSessionLocal() as db:
        result = await db.execute(select(RobotStatus).where(RobotStatus.sn == sn))
        robot = result.scalar_one_or_none()
        if not robot:
            robot = RobotStatus(sn=sn)
            db.add(robot)
        robot.online = True
        robot.last_seen = int(time.time() * 1000)
        await db.commit()

    logger.info(f"[WS] 机器人 {sn} 已连接")

    try:
        while True:
            data = await websocket.receive_json()
            msg_type = data.get("type")

            if msg_type == "auth":
                # APK 初次认证，发送当前配置
                await websocket.send_json({
                    "type": "auth_ok",
                    "config": {
                        "app_key": settings.ROBOT_APP_KEY,
                        "app_secret": settings.ROBOT_APP_SECRET,
                        "sn": sn,
                        "free_wake_window": settings.FREE_WAKE_WINDOW,
                    }
                })

            elif msg_type == "status":
                # APK 上报状态
                async with AsyncSessionLocal() as db:
                    result = await db.execute(select(RobotStatus).where(RobotStatus.sn == sn))
                    robot = result.scalar_one_or_none()
                    if robot:
                        robot.battery = data.get("battery", robot.battery)
                        robot.current_poi = data.get("poi", robot.current_poi)
                        robot.status = data.get("status", robot.status)
                        robot.app_version = data.get("app_version", robot.app_version)
                        robot.last_seen = int(time.time() * 1000)
                        await db.commit()

            elif msg_type == "poi_list":
                # APK 上报点位列表
                poi_list = data.get("poi_list", [])
                async with AsyncSessionLocal() as db:
                    result = await db.execute(select(RobotStatus).where(RobotStatus.sn == sn))
                    robot = result.scalar_one_or_none()
                    if robot:
                        robot.poi_list = poi_list
                        await db.commit()
                logger.info(f"[WS] {sn} 上报 {len(poi_list)} 个POI点位")

            elif msg_type == "callback":
                # APK 回调（导航完成/TTS完成等）
                callback_id = data.get("callback_id")
                if callback_id:
                    robot_mgr.resolve_callback(callback_id, data)

                # 导航到达后处理
                if data.get("event") == "navigation_arrived":
                    poi = data.get("poi")
                    logger.info(f"[WS] {sn} 到达 {poi}")
                    async with AsyncSessionLocal() as db:
                        # 触发到达逻辑：更新位置、播报欢迎语等
                        await on_robot_arrived(db, sn, poi)

            elif msg_type == "speech_input":
                # APK 上报语音识别结果（ASR）
                text = data.get("text", "")
                if text:
                    logger.info(f"[WS] {sn} 语音输入: {text}")
                    async with AsyncSessionLocal() as db:
                        result = await handle_input(
                            db=db,
                            text=text,
                            source="robot",
                            session_key=sn,
                            robot_sn=sn,
                        )
                    # 回复给APK
                    await websocket.send_json({
                        "type": "reply",
                        "text": result.get("reply", ""),
                        "intent": result.get("intent", ""),
                    })

            elif msg_type == "heartbeat":
                await websocket.send_json({"type": "heartbeat_ack"})

    except WebSocketDisconnect:
        logger.info(f"[WS] {sn} 断开连接")
    except Exception as e:
        logger.error(f"[WS] {sn} 异常: {e}")
    finally:
        await robot_mgr.disconnect(sn)
        async with AsyncSessionLocal() as db:
            result = await db.execute(select(RobotStatus).where(RobotStatus.sn == sn))
            robot = result.scalar_one_or_none()
            if robot:
                robot.online = False
                await db.commit()


async def on_robot_arrived(db, sn: str, poi: str):
    """机器人到达POI后的处理逻辑"""
    from ..models import NavPosition, ExhibitScript
    from ..services.robot import RobotAction

    # 更新机器人位置
    result = await db.execute(select(RobotStatus).where(RobotStatus.sn == sn))
    robot = result.scalar_one_or_none()
    if robot:
        robot.current_poi = poi
        await db.commit()

    # 查找对应展项配置
    pos_result = await db.execute(select(NavPosition).where(NavPosition.robot_poi == poi))
    nav_pos = pos_result.scalar_one_or_none()

    if nav_pos and nav_pos.terminal_id:
        # 更新会话中的当前终端
        session_result = await db.execute(
            select(ChatSession).where(ChatSession.session_key == sn)
        )
        session = session_result.scalar_one_or_none()
        if session:
            session.current_terminal_id = nav_pos.terminal_id
            session.current_poi = poi
            await db.commit()

    # 查找展项讲解脚本
    if nav_pos:
        script_result = await db.execute(
            select(ExhibitScript).where(
                ExhibitScript.nav_poi == poi,
                ExhibitScript.enabled == True
            ).limit(1)
        )
        script = script_result.scalar_one_or_none()
        if script and script.welcome_text:
            import asyncio
            robot_action = RobotAction(sn)
            # 延迟播报
            await asyncio.sleep(script.arrival_delay or 2)
            await robot_action.speak(script.welcome_text, wait_done=False)
            await robot_action.set_free_wake(settings.FREE_WAKE_WINDOW)
