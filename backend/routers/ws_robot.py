import asyncio
import json
import logging
import time
from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from database import async_session
from sqlalchemy import text

router = APIRouter()
logger = logging.getLogger(__name__)

robot_connections: dict[str, WebSocket] = {}
robot_last_heartbeat: dict[str, float] = {}

OFFLINE_THRESHOLD = 60  # seconds


@router.websocket("/ws/robot/{robot_sn}")
async def robot_ws(websocket: WebSocket, robot_sn: str):
    await websocket.accept()
    robot_connections[robot_sn] = websocket
    robot_last_heartbeat[robot_sn] = time.time()
    logger.info(f"Robot {robot_sn} connected via WS")

    await _on_robot_reconnect(robot_sn)
    await _send_resume_hint_if_needed(robot_sn, websocket)

    try:
        while True:
            data = await websocket.receive_text()
            try:
                msg = json.loads(data)
                await handle_robot_message(robot_sn, msg)
            except Exception as e:
                logger.warning(f"handle message error: {e}")
    except WebSocketDisconnect:
        robot_connections.pop(robot_sn, None)
        await _handle_robot_offline(robot_sn)
        logger.info(f"Robot {robot_sn} disconnected")
    except Exception as e:
        robot_connections.pop(robot_sn, None)
        await _handle_robot_offline(robot_sn)
        logger.warning(f"Robot {robot_sn} WS error: {e}")


async def _on_robot_reconnect(robot_sn: str):
    try:
        async with async_session() as db:
            await db.execute(text(
                "UPDATE robot_status SET last_seen=NOW() WHERE robot_sn=:sn"
            ), {"sn": robot_sn})
            await db.commit()
    except Exception as e:
        logger.warning(f"_on_robot_reconnect error: {e}")


async def _send_resume_hint_if_needed(robot_sn: str, websocket: WebSocket):
    try:
        async with async_session() as db:
            row = await db.execute(text(
                "SELECT nav_started_at FROM chat_sessions WHERE robot_sn=:sn ORDER BY id DESC LIMIT 1"
            ), {"sn": robot_sn})
            r = row.fetchone()
            if r and r[0]:
                await websocket.send_text(json.dumps({"type": "resume_hint", "message": "网络已重连，可继续上次导览"}))
    except Exception as e:
        logger.warning(f"resume hint error: {e}")


async def check_robot_online():
    while True:
        await asyncio.sleep(30)
        now = time.time()
        offline = [sn for sn, ts in list(robot_last_heartbeat.items()) if now - ts > OFFLINE_THRESHOLD]
        for sn in offline:
            if sn in robot_connections:
                robot_connections.pop(sn, None)
                await _handle_robot_offline(sn)


async def _handle_robot_offline(robot_sn: str):
    try:
        async with async_session() as db:
            await db.execute(text(
                "UPDATE robot_status SET last_seen=NOW() WHERE robot_sn=:sn"
            ), {"sn": robot_sn})
            await db.commit()
    except Exception as e:
        logger.warning(f"_handle_robot_offline error: {e}")


async def handle_robot_message(robot_sn: str, msg: dict):
    event_type = msg.get("type")

    if event_type == "battery_update":
        import httpx
        try:
            async with httpx.AsyncClient(timeout=3) as client:
                await client.post("http://localhost:8200/api/robot/battery", json={
                    "robot_sn": robot_sn,
                    "battery_level": msg.get("level", 0),
                    "is_charging": msg.get("charging", False)
                })
        except Exception as e:
            logger.warning(f"battery update error: {e}")

    elif event_type == "map_positions":
        import httpx
        try:
            async with httpx.AsyncClient(timeout=3) as client:
                await client.post("http://localhost:8200/api/robot/map-positions", json={
                    "robot_sn": robot_sn,
                    "positions": msg.get("positions", [])
                })
        except Exception as e:
            logger.warning(f"map_positions update error: {e}")

    elif event_type == "visitor_arrived":
        visitor_name = msg.get("visitor_name", "")
        visitor_dept = msg.get("visitor_dept", "")
        is_employee = msg.get("is_employee", False)
        async with async_session() as db:
            await db.execute(text(
                "INSERT INTO visitor_logs (robot_sn, visitor_name, visitor_dept, is_employee, arrived_at) "
                "VALUES (:sn, :vname, :vdept, :is_emp, NOW())"
            ), {"sn": robot_sn, "vname": visitor_name, "vdept": visitor_dept, "is_emp": is_employee})
            await db.commit()
        async with async_session() as db:
            await db.execute(text(
                "UPDATE chat_sessions SET visitor_name=:vname WHERE robot_sn=:sn"
            ), {"vname": visitor_name, "sn": robot_sn})
            await db.commit()
        if is_employee and visitor_name:
            notif = f"\U0001f464 {visitor_name}\uff08{visitor_dept}\uff09\u8fdb\u5165\u5c55\u5385\uff0c\u65fa\u8d22\u5df2\u8bc6\u522b\u5e76\u95ee\u597d"
            try:
                from routers.chat import _push_bot_notification
                await _push_bot_notification(robot_sn, notif)
            except Exception as e:
                logger.warning(f"visitor push failed: {e}")
        # P1-3: 访客到达时让机器人点头致意
        try:
            await send_to_robot(robot_sn, {"type": "nod_head"})
            logger.info(f"Robot {robot_sn} nod_head sent on visitor_arrived")
        except Exception as e:
            logger.warning(f"nod_head send failed: {e}")

    elif event_type == "arrived":
        terminal_id = msg.get("terminal_id")
        terminal_name = msg.get("terminal_name", "")
        logger.info(f"Robot {robot_sn} arrived at {terminal_name} (id={terminal_id})")
        try:
            async with async_session() as db:
                await db.execute(text(
                    "UPDATE chat_sessions SET nav_started_at=NULL WHERE robot_sn=:sn"
                ), {"sn": robot_sn})
                await db.commit()
        except Exception as e:
            logger.warning(f"Clear nav_started_at failed: {e}")
        try:
            import httpx
            async with httpx.AsyncClient(timeout=5) as client:
                await client.post("http://localhost:8200/api/chat/input", json={
                    "robot_sn": robot_sn,
                    "event": "robot_arrived",
                    "terminal_id": terminal_id,
                    "terminal_name": terminal_name
                })
        except Exception as e:
            logger.warning(f"arrived event to chat error: {e}")

    elif event_type == "tts_done":
        logger.info(f"Robot {robot_sn} TTS done")

    elif event_type == "heartbeat":
        robot_last_heartbeat[robot_sn] = time.time()
        await send_to_robot(robot_sn, {"type": "heartbeat_ack"})

    elif event_type == "leave_charging_pile":
        logger.info(f"Robot {robot_sn} left charging pile")

    elif event_type == "nod_head":
        logger.info(f"Robot {robot_sn} nod_head command executed")

    elif event_type == "system_status":
        status_type = msg.get("status_type", "")
        status_data = msg.get("status_data", "{}")
        logger.warning(f"Robot {robot_sn} system_status: type={status_type} data={status_data}")


async def send_to_robot(robot_sn: str, message: dict) -> bool:
    ws = robot_connections.get(robot_sn)
    if not ws:
        return False
    try:
        await ws.send_text(json.dumps(message, ensure_ascii=False))
        return True
    except Exception as e:
        robot_connections.pop(robot_sn, None)
        logger.warning(f"Failed to send to robot {robot_sn}: {e}")
        return False


def get_online_robots() -> list:
    return list(robot_connections.keys())
