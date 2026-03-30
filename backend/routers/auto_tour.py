"""
自动参观路由（重构版 - 基于 exhibit_scripts.auto_tour_enabled + tour_stops 顺序）
GET    /api/auto-tour/resources/{terminal_id}  某展位在当前专场的资源列表
POST   /api/auto-tour/start          启动自动参观
POST   /api/auto-tour/stop           停止自动参观
GET    /api/auto-tour/status         当前运行状态
"""
import asyncio
import logging
from fastapi import APIRouter, BackgroundTasks
from pydantic import BaseModel
from typing import Optional
from sqlalchemy import text as _sql
from database import async_session

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/auto-tour", tags=["auto-tour"])

_running_tasks: dict = {}
_running_info: dict = {}


@router.get("/resources/{terminal_id}")
async def list_terminal_resources(terminal_id: int):
    """获取某展位的资源列表（供前端选择投放资源）"""
    async with async_session() as db:
        s = await db.execute(_sql("SELECT scene_id FROM current_scene LIMIT 1"))
        sr = s.fetchone()
        scene_id = sr[0] if sr else None

        scene_filter = f"AND raw_data->>'_scene_id' = '{scene_id}'" if scene_id else ""

        rows = await db.execute(_sql(
            f"\n            SELECT resource_id, title,\n                   raw_data->>'allCommentary' as all_cmt,\n                   raw_data->>'commentary' as cmt,\n                   raw_data->>'resourceType' as rty"
            f" FROM exhibit_resources WHERE terminal_id={terminal_id} {scene_filter}'\n              "
            f"\n            ORDER BY sort\n        "
        ))
        items = [dict(r._mapping) for r in rows.fetchall()]
    return {"code": 0, "data": items}


@router.get("/status")
async def get_status():
    """当前运行状态 + 自动导览展位数统计"""
    async with async_session() as db:
        total_stops = await db.execute(_sql("SELECT COUNT(*) FROM tour_stops"))
        auto_count_row = await db.execute(_sql("SELECT COUNT(*) FROM exhibit_scripts WHERE in_tour=true AND enabled=true"))
        auto_count = auto_count_row.fetchone()[0]

    running_sn = None
    for sn, task in _running_tasks.items():
        if not task.done():
            running_sn = sn
            break

    if running_sn:
        info = _running_info.get(running_sn, {})
        return {"code": 0, "data": {
            "status": "running",
            "robot_sn": running_sn,
            "current_step": info.get("current_step"),
            "total_steps": info.get("total_steps"),
            "started_at": info.get("started_at"),
            "auto_enabled_count": auto_count
        }}
    return {"code": 0, "data": {
        "status": "idle",
        "auto_enabled_count": auto_count
    }}


@router.post("/stop")
async def stop_tour(robot_sn: str = "MC1BCN2K100262058CA0"):
    task = _running_tasks.get(robot_sn)
    if task and not task.done():
        task.cancel()
        _running_info.pop(robot_sn, None)
        return {"code": 0, "message": "已停止自动参观"}
    return {"code": 0, "message": "当前没有运行中的参观任务"}


@router.post("/start")
async def start_tour(background_tasks: BackgroundTasks, robot_sn: str = "MC1BCN2K100262058CA0", triggered_by: str = "bot"):
    task = _running_tasks.get(robot_sn)
    if task and not task.done():
        return {"code": 1, "message": "自动参观正在进行中，请先说「停止参观」"}

    async with async_session() as db:
        rows = await db.execute(_sql(
            f"\n            SELECT ts.terminal_id, ts.terminal_name, ts.order_index,\n                   es.id as script_id, es.nav_position, es.opening_speech,\n                   es.ai_commentary_enabled\n           "
            f" FROM tour_stops ts"
            f" JOIN exhibit_scripts es ON es.terminal_id = ts.terminal_id AND es.auto_tour_enabled = true"
            f" WHERE ts.enabled = true AND ts.robot_sn = :sn"
            f" ORDER BY ts.order_index",
            {}
        ))
        stop_list = [dict(r._mapping) for r in rows.fetchall()]

        scripts = []
        for stop in stop_list:
            sid = stop["script_id"]
            item_rows = await db.execute(_sql(
                f"\n                    SELECT id, sort_order, title, resource_id, resource_title,\n                           commentary, tts_delay_seconds, enabled\n                    FROM exhibit_script_items\n        "
                f" WHERE script_id = :sid AND enabled = true ORDER BY sort_order",
                {"sid": sid}
            ))
            items = [dict(r._mapping) for r in item_rows.fetchall()]
            stop["items"] = items
            scripts.append(stop)

    if not scripts:
        return {"code": 1, "message": "自动参观无展位，请先在「导览配置」设置展位顺序，并在「展项讲解」中开启「自动导览」"}

    total = sum(max(len(s["items"]), 1) for s in scripts)
    from datetime import datetime
    _running_info[robot_sn] = {
        "current_step": 0,
        "total_steps": total,
        "started_at": datetime.now().isoformat()
    }

    loop = asyncio.get_event_loop()
    t = loop.create_task(_run_auto_tour(robot_sn, scripts))
    _running_tasks[robot_sn] = t

    return {"code": 0, "message": f"自动参观已启动，共 {len(scripts)} 站，说「停止参观」可随时中断"}


async def _run_auto_tour(robot_sn: str, scripts: list):
    """后台顺序执行自动参观"""
    try:
        from config import get_config
        from tcp_service import send_tcp

        tcp_host = await get_config("tcp.host") or "112.20.77.18"
        tcp_port = int(await get_config("tcp.port") or "8989")
        orion_base = await get_config("robot.orion_api_base") or ""
        app_key = await get_config("robot.app_key") or ""
        app_secret = await get_config("robot.app_secret") or ""

        async with async_session() as db:
            sr = await db.execute(_sql("SELECT scene_id FROM current_scene LIMIT 1"))
            scene_row = sr.fetchone()
            scene_id = scene_row[0] if scene_row else None

        global_step = 0
        for stop in scripts:
            terminal_id = stop.get("terminal_id")
            terminal_name = stop.get("terminal_name") or f"展位"
            nav_pos = stop.get("nav_position")
            opening = stop.get("opening_speech")
            ai_enabled = stop.get("ai_commentary_enabled") or stop.get("ai_narration")
            items = stop.get("items", [])

            logger.info(f"[AutoTour] → {terminal_name} ({len(items)} items)")

            if nav_pos and orion_base:
                await _orion_navigate(orion_base, app_key, app_secret, robot_sn, nav_pos)

            if opening:
                if orion_base:
                    await _orion_tts(orion_base, app_key, app_secret, robot_sn, opening)
                else:
                    try:
                        await send_tcp(tcp_host, tcp_port, opening)
                    except Exception as e:
                        logger.warning(f"[AutoTour] TCP failed: {e}")

            for item in items:
                global_step += 1
                _running_info[robot_sn]["current_step"] = global_step

                resource_id = item.get("resource_id")
                commentary = item.get("commentary") or ""
                tts_delay = item.get("tts_delay_seconds") or stop.get("arrival_delay") or 3
                resource_title = item.get("title") or item.get("resource_title") or ""

                if resource_id and scene_id:
                    tcp_cmd = f"2_{scene_id}_{terminal_id}_{resource_id}"
                    try:
                        await send_tcp(tcp_host, tcp_port, tcp_cmd)
                    except Exception as e:
                        logger.warning(f"[AutoTour] TCP failed: {e}")

                if tts_delay > 0:
                    await asyncio.sleep(tts_delay)

                if commentary:
                    if ai_enabled:
                        try:
                            from routers.exhibit_scripts import _generate_ai_commentary
                            commentary = await _generate_ai_commentary(commentary)
                        except Exception as e:
                            logger.warning(f"[AutoTour] AI commentary failed: {e}")
                    ai_text = f"📍 【{resource_title}】\n{commentary}"
                    if orion_base:
                        await _orion_tts(orion_base, app_key, app_secret, robot_sn, ai_text)
                    else:
                        try:
                            await send_tcp(tcp_host, tcp_port, ai_text)
                        except Exception as e:
                            logger.warning(f"[AutoTour] TCP failed: {e}")

                try:
                    async with async_session() as db:
                        await db.execute(_sql(
                            "\n                    UPDATE chat_sessions SET current_exhibit_id=:tid, last_activity_at=NOW()\n                    WHERE robot_sn=:sn\n                ",
                            {"tid": terminal_id, "sn": f"%{robot_sn}%"}
                        ))
                        await db.commit()
                except Exception:
                    pass

        _running_info[robot_sn]["status"] = "finished"
        finish_msg = "🎉 自动参观完成！欢迎莅临，感谢您的参观！"
        if orion_base:
            await _orion_tts(orion_base, app_key, app_secret, robot_sn, finish_msg)
        try:
            await send_tcp(tcp_host, tcp_port, finish_msg)
        except Exception:
            pass

        await _push_notification(robot_sn, f"[AutoTour] {robot_sn} 自动参观完成")
        logger.info(f"[AutoTour] {robot_sn} 自动参观完成")

    except asyncio.CancelledError:
        logger.info(f"[AutoTour] {robot_sn} 被取消")
    except Exception as e:
        logger.error(f"[AutoTour] {robot_sn} error: {e}")
        _running_info[robot_sn]["error"] = str(e)


async def _orion_tts(base: str, app_key: str, app_secret: str, robot_sn: str, text: str):
    import time, hashlib, httpx
    ts = str(int(time.time()))
    sign = hashlib.md5(f"{app_key}{app_secret}{ts}".encode()).hexdigest().upper()
    headers = {"Content-Type": "application/json"}
    try:
        async with httpx.AsyncClient() as client:
            r = await client.post(f"{base}/openapi/robot/tts/v2", headers=headers, json={
                "robotSn": robot_sn, "text": text, "appKey": app_key, "ts": ts, "sign": sign
            })
            logger.info(f"[Orion TTS] {r.status_code}: {r.text[:100]}")
    except Exception as e:
        logger.warning(f"[Orion TTS] error: {e}")


async def _orion_navigate(base: str, app_key: str, app_secret: str, robot_sn: str, position: str):
    import time, hashlib, httpx
    ts = str(int(time.time()))
    sign = hashlib.md5(f"{app_key}{app_secret}{ts}".encode()).hexdigest().upper()
    headers = {"Content-Type": "application/json"}
    try:
        async with httpx.AsyncClient() as client:
            r = await client.post(f"{base}/openapi/robot/navigation/v2", headers=headers, json={
                "robotSn": robot_sn, "position": position, "appKey": app_key, "ts": ts, "sign": sign
            })
            logger.info(f"[Orion Nav] {r.status_code}: {r.text[:100]}")
    except Exception as e:
        logger.warning(f"[Orion Nav] error: {e}")


async def _push_notification(robot_sn: str, message: str):
    try:
        async with async_session() as db:
            cs = await db.execute(_sql(
                "SELECT session_key FROM chat_sessions WHERE session_key LIKE :sn LIMIT 1",
                {"sn": robot_sn}
            ))
            row = cs.fetchone()
            if row:
                user_key = row[0]
                await db.execute(_sql(
                    "\n                    INSERT INTO bot_notifications (robot_sn, message, created_at)\n                    VALUES (:sn, :msg, NOW())\n                ",
                    {"sn": robot_sn, "msg": message}
                ))
                await db.commit()
    except Exception as e:
        logger.warning(f"[AutoTour notify] {e}")
