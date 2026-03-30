"""
对话引擎 - 意图处理 + 动作执行 + 双端同步（机器人 + 企微Bot）
"""
import asyncio
import logging
import time
import aiohttp
from datetime import datetime
from typing import Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, desc

from ..config import settings
from ..database import AsyncSessionLocal
from ..models import (
    ChatLog, ChatSession, CurrentSpecial, CloudCommand,
    CloudSpecial, TourRoute, TourStop, NavPosition,
    ExhibitScript, ExhibitItem, OperationLog
)
from .intent import recognize_intent, INTENTS
from .persona import (
    get_reply, get_arrive_reply, get_time_greeting,
    build_speak_params, PERSONA_NAME, VENUE_NAME
)
from .robot import robot_mgr
from .commands import send_tcp_command, send_group_command

logger = logging.getLogger(__name__)

# 全局 WecomBot 推送回调（由 wecom_bot.py 注入）
_notify_callback = None

def set_notify_callback(fn):
    global _notify_callback
    _notify_callback = fn


async def handle_input(text: str, source: str = "robot", session_key: str = "default",
                       db: Optional[AsyncSession] = None) -> dict:
    """
    统一输入处理入口
    source: robot | wecom | admin | face_detect
    返回：{reply_text, action, params, intent}
    """
    start_ms = int(time.time() * 1000)
    close_db = False
    if db is None:
        db = AsyncSessionLocal()
        close_db = True

    try:
        # 1. 意图识别
        intent_result = await recognize_intent(text)
        intent = intent_result["intent"]
        params = intent_result.get("params", {})
        confidence = intent_result.get("confidence", 0.0)

        logger.info(f"[{source}] 输入: '{text}' → 意图: {intent}({confidence:.2f}) 参数: {params}")

        # 2. 执行动作
        reply, action_result = await _execute_intent(intent, params, text, db, source)

        # 3. 记录日志
        await _save_chat_log(db, session_key, source, text, intent, reply, confidence)

        # 4. 双端同步推送
        await _sync_both_ends(reply, action_result, intent, source, db)

        return {
            "reply": reply,
            "intent": intent,
            "confidence": confidence,
            "params": params,
            "action": action_result,
        }

    except Exception as e:
        logger.error(f"handle_input异常: {e}", exc_info=True)
        err_reply = "抱歉，处理您的请求时遇到了问题，请稍后再试。"
        return {"reply": err_reply, "intent": "error", "confidence": 0, "params": {}, "action": None}
    finally:
        if close_db:
            await db.close()


async def _execute_intent(intent: str, params: dict, raw_text: str,
                           db: AsyncSession, source: str) -> tuple[str, dict]:
    """
    执行意图对应的动作
    返回：(reply_text, action_info)
    """
    action = {"type": intent, "success": True, "detail": {}}

    # ── 问候 ────────────────────────────────────────────────────────────────
    if intent == "chitchat":
        greeting = get_time_greeting()
        return f"{greeting}我是{PERSONA_NAME}，有什么我可以帮您的吗？", action

    if intent == "who_are_you":
        return get_reply("introduce_self"), action

    # ── 开始导览 ────────────────────────────────────────────────────────────
    if intent == "start_tour":
        poi = params.get("poi")
        if poi:
            await _robot_navigate(poi, db)
            reply = get_arrive_reply(poi)
        else:
            reply = get_reply("tour_start")
            # 从数据库取默认路线第一站
            route = await _get_default_route(db)
            if route and route.get("stops"):
                first_poi = route["stops"][0]["poi_name"]
                await _robot_navigate(first_poi, db)
        return reply, action

    # ── 停止导览 ────────────────────────────────────────────────────────────
    if intent == "stop_tour":
        robot_mgr.cancel_tour()
        await _robot_stop()
        return "好的，导览已暂停。随时告诉我继续！", action

    # ── 导航到指定点位 ──────────────────────────────────────────────────────
    if intent == "goto_position":
        poi = params.get("poi") or _extract_poi_from_text(raw_text, db)
        if poi:
            ok = await _robot_navigate(poi, db)
            reply = get_arrive_reply(poi) if ok else get_reply("navigation_failed")
        else:
            reply = "请告诉我您想去哪里？我们有入口、大岛台、小岛台和CAVE。"
        return reply, action

    if intent == "goto_entrance":
        await _robot_navigate("入口", db)
        return "好的，带您回到入口！", action

    if intent == "goto_charge":
        await _robot_charge()
        return get_reply("going_charge"), action

    # ── 展项讲解 ────────────────────────────────────────────────────────────
    if intent in ("start_explain", "explain_exhibit"):
        exhibit_hint = params.get("exhibit_hint", raw_text)
        poi = params.get("poi")
        script = await _find_exhibit_script(exhibit_hint, poi, db)
        if script:
            reply = get_reply("explain_start") + "\n" + script
            # 机器人TTS朗读
            await _robot_speak(script, "explain")
        else:
            # 无脚本 → Qwen AI生成讲解词
            ai_script = await _generate_explain_with_ai(exhibit_hint, raw_text)
            reply = get_reply("explain_start") + "\n" + ai_script
            await _robot_speak(ai_script, "explain")
        return reply, action

    if intent == "stop_explain":
        await _robot_stop_speak()
        return "好的，讲解已停止。", action

    if intent == "repeat_explain":
        # 取最近一次讲解内容
        last = await _get_last_explain(db)
        if last:
            await _robot_speak(last, "explain")
            return f"好的，再说一遍：{last[:50]}...", action
        return "我最近没有讲解内容可以重复。", action

    # ── 场景控制 ────────────────────────────────────────────────────────────
    if intent == "open_hall":
        await _send_group_cmd("0_all_com_on")
        await _send_group_cmd("0_all_light_on")
        reply = get_reply("open_hall")
        action["detail"] = {"cmds": ["0_all_com_on", "0_all_light_on"]}
        return reply, action

    if intent == "close_hall":
        await _send_group_cmd("0_all_com_off")
        await _send_group_cmd("0_all_light_off")
        reply = get_reply("close_hall")
        action["detail"] = {"cmds": ["0_all_com_off", "0_all_light_off"]}
        return reply, action

    if intent == "lights_on":
        await _send_group_cmd("0_all_light_on")
        return "好的，灯光已全部打开！💡", action

    if intent == "lights_off":
        await _send_group_cmd("0_all_light_off")
        return "好的，灯光已全部关闭。", action

    if intent == "devices_on":
        await _send_group_cmd("0_all_com_on")
        return "好的，所有屏幕和设备已开启！", action

    if intent == "devices_off":
        await _send_group_cmd("0_all_com_off")
        return "好的，设备已全部关闭。", action

    if intent == "ads_on":
        await _send_group_cmd("0_all_ggj_on")
        return "广告机已开启。", action

    if intent == "ads_off":
        await _send_group_cmd("0_all_ggj_off")
        return "广告机已关闭。", action

    if intent == "standby":
        await _send_tcp("5_ready")
        return "已进入待展状态，展厅准备就绪！", action

    if intent == "switch_special":
        special_name = params.get("special_name", "")
        special = await _find_special(special_name, db)
        if special:
            await _send_tcp(f"4_{special.id}")
            reply = f"好的，已切换到【{special.name}】专场！"
        else:
            reply = f"没有找到【{special_name}】专场，请告诉我具体专场名称。"
        return reply, action

    # ── 机器人控制 ──────────────────────────────────────────────────────────
    if intent == "robot_stop":
        await _robot_stop()
        return "已停止！", action

    if intent == "robot_follow":
        robot_mgr.send_command({"type": "follow", "start": True})
        return get_reply("follow_start"), action

    if intent == "robot_stop_follow":
        robot_mgr.send_command({"type": "follow", "start": False})
        return "跟随模式已关闭。", action

    if intent == "robot_status":
        status = robot_mgr.get_status()
        battery = status.get("battery", -1)
        poi = status.get("current_poi", "未知")
        online = status.get("online", False)
        if online:
            return f"我现在在{poi}，电量{battery}%，状态良好！", action
        return "我目前离线，可能在充电或网络有问题。", action

    if intent == "set_volume":
        vol = params.get("volume", 70)
        robot_mgr.send_command({"type": "set_volume", "volume": vol})
        return f"好的，音量已调整到{vol}。", action

    if intent == "volume_up":
        robot_mgr.send_command({"type": "set_volume", "volume": 80})
        return "好的，声音调大了！", action

    if intent == "volume_down":
        robot_mgr.send_command({"type": "set_volume", "volume": 50})
        return "好的，声音调小了。", action

    # ── 接待 ────────────────────────────────────────────────────────────────
    if intent == "welcome":
        greeting = get_time_greeting() + get_reply("welcome")
        await _robot_speak(greeting, "welcome")
        return greeting, action

    if intent == "vip_reception":
        text_out = f"VIP接待模式已开启！{get_reply('welcome')}"
        await _robot_speak(text_out, "welcome")
        # 灯光加强
        await _send_group_cmd("0_all_light_on")
        return text_out, action

    if intent == "goodbye":
        reply = get_reply("goodbye")
        await _robot_speak(reply, "normal")
        return reply, action

    # ── 问公司/展厅 ─────────────────────────────────────────────────────────
    if intent == "ask_company":
        reply = get_reply("company_intro")
        await _robot_speak(reply, "explain")
        return reply, action

    if intent == "ask_time":
        now = datetime.now()
        reply = f"现在是{now.strftime('%Y年%m月%d日 %H:%M')}，{['周一','周二','周三','周四','周五','周六','周日'][now.weekday()]}。"
        return reply, action

    # ── 系统 ────────────────────────────────────────────────────────────────
    if intent == "system_status":
        status = robot_mgr.get_status()
        return (f"系统运行正常。机器人{'在线' if status.get('online') else '离线'}，"
                f"电量{status.get('battery', '?')}%，当前位置：{status.get('current_poi', '未知')}"), action

    if intent == "sync_data":
        from .sync import sync_all
        asyncio.create_task(sync_all(db))
        return "已启动数据同步，稍后完成。", action

    # ── 未知意图 → Qwen自由问答 ───────────────────────────────────────────
    if intent == "unknown" or intent == "ask_about":
        reply = await _free_qa(raw_text)
        return reply, {"type": "free_qa", "success": True, "detail": {}}

    # ── 问候兜底 ────────────────────────────────────────────────────────────
    return get_reply("not_understand"), {"type": "unknown", "success": False, "detail": {}}


# ==================== 辅助函数 ====================

async def _robot_navigate(poi: str, db: AsyncSession) -> bool:
    """向机器人发导航命令"""
    nav_pos = await _get_nav_position(poi, db)
    poi_name = nav_pos.robot_poi if nav_pos else poi
    robot_mgr.send_command({"type": "navigate", "poi": poi_name, "callback_id": f"nav_{poi}"})
    return True


async def _robot_speak(text: str, scene: str = "normal"):
    """向机器人发TTS命令"""
    params = build_speak_params(text, scene)
    robot_mgr.send_command({
        "type": "speak",
        "text": params["text"],
        "speed": params["speed"],
        "callback_id": f"speak_{int(time.time())}",
    })


async def _robot_stop():
    robot_mgr.send_command({"type": "stop"})


async def _robot_stop_speak():
    robot_mgr.send_command({"type": "stop_speak"})


async def _robot_charge():
    robot_mgr.send_command({"type": "go_charge"})


async def _send_tcp(cmd: str):
    """发TCP命令到中控"""
    try:
        await send_tcp_command(settings.ZHONGKONG_TCP_HOST, settings.ZHONGKONG_TCP_PORT, cmd)
    except Exception as e:
        logger.error(f"TCP命令失败 {cmd}: {e}")


async def _send_group_cmd(cmd: str):
    """发组策略命令"""
    await _send_tcp(cmd)


async def _get_nav_position(poi: str, db: AsyncSession):
    r = await db.execute(
        select(NavPosition).where(
            NavPosition.display_name.ilike(f"%{poi}%") |
            NavPosition.robot_poi.ilike(f"%{poi}%") |
            NavPosition.aliases.ilike(f"%{poi}%")
        )
    )
    return r.scalar_one_or_none()


async def _get_default_route(db: AsyncSession) -> Optional[dict]:
    r = await db.execute(select(TourRoute).where(TourRoute.enabled == True).limit(1))
    route = r.scalar_one_or_none()
    if not route:
        return None
    stops_r = await db.execute(
        select(TourStop).where(TourStop.route_id == route.id).order_by(TourStop.sort)
    )
    stops = stops_r.scalars().all()
    return {"id": route.id, "name": route.name,
            "stops": [{"poi_name": s.poi_name, "duration": s.duration_sec} for s in stops]}


async def _find_exhibit_script(hint: str, poi: Optional[str], db: AsyncSession) -> Optional[str]:
    """根据提示查找展项讲解词"""
    # 先在本地数据库查
    q = select(ExhibitScript).where(ExhibitScript.enabled == True)
    if poi:
        q = q.where(ExhibitScript.poi_name.ilike(f"%{poi}%"))
    r = await db.execute(q.limit(10))
    scripts = r.scalars().all()

    for s in scripts:
        if hint and (hint in s.title or s.title in hint):
            return s.commentary or s.ai_content or ""

    if scripts:
        return scripts[0].commentary or scripts[0].ai_content or ""
    return None


async def _find_special(name: str, db: AsyncSession):
    r = await db.execute(
        select(CloudSpecial).where(CloudSpecial.name.ilike(f"%{name}%"))
    )
    return r.scalar_one_or_none()


async def _get_last_explain(db: AsyncSession) -> Optional[str]:
    r = await db.execute(
        select(ChatLog).where(ChatLog.intent == "start_explain").order_by(desc(ChatLog.created_at)).limit(1)
    )
    log = r.scalar_one_or_none()
    return log.bot_reply if log else None


def _extract_poi_from_text(text: str, db) -> Optional[str]:
    """从文本中提取POI名"""
    poi_map = {"大岛台": "大岛台", "小岛台": "小岛台", "入口": "入口", "cave": "CAVE", "CAVE": "CAVE"}
    for k, v in poi_map.items():
        if k.lower() in text.lower():
            return v
    return None


async def _generate_explain_with_ai(exhibit_hint: str, user_text: str) -> str:
    """用Qwen AI生成展项讲解词"""
    system = f"""你是{VENUE_NAME}的专业导览员{PERSONA_NAME}。
根据展项名称或用户问题，生成一段自然流畅的中文讲解词（200字以内）。
语气亲切专业，结合展厅智能化、数字化的特色。不要编造具体数据。"""

    payload = {
        "model": settings.QWEN_MODEL,
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": f"请讲解：{exhibit_hint}\n用户原话：{user_text}"}
        ],
        "max_tokens": 300,
        "temperature": 0.7,
    }

    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(
                f"{settings.QWEN_BASE_URL}/chat/completions",
                json=payload,
                headers={"Authorization": f"Bearer {settings.QWEN_API_KEY}"},
                timeout=aiohttp.ClientTimeout(total=10),
            ) as resp:
                data = await resp.json()
                return data["choices"][0]["message"]["content"].strip()
    except Exception as e:
        logger.error(f"AI讲解生成失败: {e}")
        return f"这是{VENUE_NAME}的特色展项，展示了思德科技在数字化展厅领域的创新成果。"


async def _free_qa(user_text: str) -> str:
    """Qwen自由问答"""
    system = f"""你是{VENUE_NAME}的AI导览官{PERSONA_NAME}。
你可以回答关于展厅、思德科技、数字化展览等问题，也可以进行轻松的日常对话。
回答要简洁、亲切，不超过150字。如果是展厅无关的问题，礼貌地引导回展厅话题。"""

    payload = {
        "model": settings.QWEN_MODEL,
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": user_text},
        ],
        "max_tokens": 200,
        "temperature": 0.7,
    }

    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(
                f"{settings.QWEN_BASE_URL}/chat/completions",
                json=payload,
                headers={"Authorization": f"Bearer {settings.QWEN_API_KEY}"},
                timeout=aiohttp.ClientTimeout(total=8),
            ) as resp:
                data = await resp.json()
                return data["choices"][0]["message"]["content"].strip()
    except Exception as e:
        logger.error(f"自由问答失败: {e}")
        return get_reply("not_understand")


# ==================== 双端同步推送 ====================

async def _sync_both_ends(reply: str, action: dict, intent: str, source: str, db: AsyncSession):
    """
    同步推送到机器人端（如果来自企微）和企微端（如果来自机器人）
    """
    # 推送到企微Bot
    if source == "robot" and _notify_callback:
        emoji = _get_intent_emoji(intent)
        msg = f"{emoji} **{PERSONA_NAME}** 正在执行：{action.get('type', intent)}\n💬 {reply[:80]}"
        try:
            await asyncio.get_event_loop().run_in_executor(None, _notify_callback, msg)
        except Exception as e:
            logger.warning(f"企微推送失败: {e}")

    # 推送到机器人（如果来自企微/管理端且需要机器人执行）
    # 已在 _execute_intent 中直接调用了 robot_mgr.send_command


def _get_intent_emoji(intent: str) -> str:
    emoji_map = {
        "start_tour": "🚀", "goto_position": "🧭", "navigate": "🧭",
        "open_hall": "💡", "close_hall": "🌙", "lights_on": "💡", "lights_off": "🌙",
        "start_explain": "🎙️", "explain_exhibit": "🎙️",
        "goto_charge": "⚡", "robot_follow": "👣",
        "welcome": "🎉", "goodbye": "👋",
        "error": "❌", "unknown": "🤔",
    }
    return emoji_map.get(intent, "📡")


# ==================== 日志 ====================

async def _save_chat_log(db: AsyncSession, session_key: str, source: str,
                          user_text: str, intent: str, reply: str, confidence: float):
    try:
        log = ChatLog(
            session_key=session_key,
            source=source,
            user_text=user_text,
            intent=intent,
            confidence=confidence,
            bot_reply=reply[:500],
            created_at=int(time.time() * 1000),
        )
        db.add(log)
        await db.commit()
    except Exception as e:
        logger.error(f"保存聊天日志失败: {e}")
        await db.rollback()
