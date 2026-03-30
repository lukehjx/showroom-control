"""
对话处理引擎：意图 → 动作 → 回复
"""
import time
import logging
from typing import Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update
from ..models import ChatSession, ChatLog, ExhibitScript, NavPosition, CloudCommand, CurrentSpecial, CloudResource
from ..config import settings
from .intent import recognize_intent
from .robot import RobotAction, robot_mgr
from .commands import send_tcp, parse_and_send_command

logger = logging.getLogger(__name__)


def now_ms():
    return int(time.time() * 1000)


async def get_or_create_session(db: AsyncSession, session_key: str, source: str) -> ChatSession:
    result = await db.execute(select(ChatSession).where(ChatSession.session_key == session_key))
    session = result.scalar_one_or_none()
    if not session:
        session = ChatSession(session_key=session_key, source=source)
        db.add(session)
        await db.flush()
    return session


async def handle_input(
    db: AsyncSession,
    text: str,
    source: str,           # robot / wecom
    session_key: str,      # robot_sn 或 wecom_user_id
    robot_sn: Optional[str] = None,
) -> dict:
    """统一输入处理入口"""
    session = await get_or_create_session(db, session_key, source)
    robot = RobotAction(robot_sn or settings.ROBOT_SN) if robot_sn or source == "robot" else None

    # 意图识别
    intent, params = await recognize_intent(text)
    reply = ""
    action_taken = intent
    action_result = "ok"

    try:
        reply = await dispatch_intent(db, intent, params, session, robot, text)
    except Exception as e:
        logger.error(f"[Chat] 执行异常: {e}", exc_info=True)
        reply = "抱歉，执行时遇到了问题，请稍后再试。"
        action_result = "error"

    # 更新会话
    session.updated_at = now_ms()
    await db.commit()

    # 记录日志
    log = ChatLog(
        session_key=session_key,
        source=source,
        input_text=text,
        intent=intent,
        intent_params=params,
        action_taken=action_taken,
        action_result=action_result,
        reply_text=reply,
    )
    db.add(log)
    await db.commit()

    return {
        "intent": intent,
        "params": params,
        "reply": reply,
        "action": action_taken,
    }


async def dispatch_intent(
    db: AsyncSession,
    intent: str,
    params: dict,
    session: ChatSession,
    robot: Optional[RobotAction],
    raw_text: str,
) -> str:
    """根据意图分发执行"""

    # ─ 文件列表查询 ──────────────────────────────────────────
    if intent == "list_files":
        if not session.current_terminal_id:
            return "请先告诉我你想了解哪个展项，我来帮你查询相关文件。"
        result = await db.execute(
            select(CloudResource)
            .where(CloudResource.terminal_id == session.current_terminal_id)
            .order_by(CloudResource.sort)
            .limit(10)
        )
        resources = result.scalars().all()
        if not resources:
            return "当前展项暂时没有配置文件内容。"
        # 保存到会话上下文
        session.current_file_list = [{"id": r.id, "title": r.title, "type": r.resource_type} for r in resources]
        titles = [f"{i+1}. {r.title}" for i, r in enumerate(resources)]
        return f"当前展项共有 {len(resources)} 个文件：\n" + "\n".join(titles) + "\n\n请告诉我你想了解第几个？"

    # ─ 按序号选择 ────────────────────────────────────────────
    if intent in ("select_item_1","select_item_2","select_item_3","select_item_4","select_item_5"):
        n = int(intent.split("_")[-1])
        params["index"] = n
        intent = "select_item"

    if intent == "select_item":
        n = params.get("index", 1)
        file_list = session.current_file_list or []
        if not file_list:
            return "还没有查询文件列表，请先问我这里有哪些文件。"
        if n > len(file_list):
            return f"只有 {len(file_list)} 个文件，没有第 {n} 个。"
        item = file_list[n - 1]
        session.current_file_index = n - 1
        # 查找对应脚本讲解词
        narration = await get_item_narration(db, item["id"], item["title"])
        # 投放到终端（需要当前专场ID）
        special_result = await db.execute(select(CurrentSpecial).limit(1))
        current = special_result.scalar_one_or_none()
        if current and session.current_terminal_id:
            from .commands import play_resource_on_terminal
            # 获取主机IP
            from ..models import CloudTerminal
            terminal_result = await db.execute(select(CloudTerminal).where(CloudTerminal.id == session.current_terminal_id))
            terminal = terminal_result.scalar_one_or_none()
            if terminal:
                await play_resource_on_terminal(terminal.host_ip, current.special_id, item["id"])
        # 播报讲解词
        if robot and narration:
            await robot.speak(narration, wait_done=False)
            # 开启免唤醒词窗口
            await robot.set_free_wake(settings.FREE_WAKE_WINDOW)
        return narration or f"正在为您播放第 {n} 个文件：{item['title']}"

    # ─ 开始导览 ──────────────────────────────────────────────
    if intent == "start_tour":
        from ..models import TourRoute, TourStop
        result = await db.execute(
            select(TourRoute).where(TourRoute.enabled == True).limit(1)
        )
        route = result.scalar_one_or_none()
        if not route:
            return "还没有配置导览路线，请联系工作人员设置。"
        session.tour_route_id = route.id
        session.tour_stop_index = 0
        session.robot_status = "touring"
        return await go_to_stop(db, session, robot, route.id, 0)

    # ─ 下一站 ────────────────────────────────────────────────
    if intent == "tour_next":
        if not session.tour_route_id:
            return "当前没有正在进行的导览，请说「开始参观」。"
        return await go_to_stop(db, session, robot, session.tour_route_id, session.tour_stop_index + 1)

    # ─ 上一站 ────────────────────────────────────────────────
    if intent == "tour_prev":
        if not session.tour_route_id:
            return "当前没有正在进行的导览。"
        idx = max(0, session.tour_stop_index - 1)
        return await go_to_stop(db, session, robot, session.tour_route_id, idx)

    # ─ 停止 ──────────────────────────────────────────────────
    if intent == "stop":
        session.robot_status = "idle"
        session.tour_route_id = None
        if robot:
            await robot.stop()
        return "好的，已停止。"

    # ─ 继续 ──────────────────────────────────────────────────
    if intent == "resume":
        if session.tour_route_id:
            return await go_to_stop(db, session, robot, session.tour_route_id, session.tour_stop_index)
        return "没有可以继续的任务。"

    # ─ 回入口 ────────────────────────────────────────────────
    if intent == "go_entry":
        result = await db.execute(
            select(NavPosition).where(NavPosition.is_entry == True).limit(1)
        )
        entry = result.scalar_one_or_none()
        if not entry:
            return "还没有配置入口点位，请联系工作人员。"
        if robot:
            await robot.navigate(entry.robot_poi, wait_arrival=False)
        session.robot_status = "navigating"
        return "好的，正在返回展厅入口。"

    # ─ 去充电 ────────────────────────────────────────────────
    if intent == "go_charge":
        if robot:
            await robot.go_charge()
        session.robot_status = "charging"
        return "好的，正在前往充电桩充电。"

    # ─ 再说一遍 ──────────────────────────────────────────────
    if intent == "repeat":
        # 重新播报上次讲解（从日志或session中取）
        if robot and session.current_file_index is not None and session.current_file_list:
            item = session.current_file_list[session.current_file_index]
            narration = await get_item_narration(db, item["id"], item["title"])
            if narration:
                await robot.speak(narration, wait_done=False)
                return "好的，再为您讲解一遍。"
        return "没有可以重复的讲解内容。"

    # ─ 灯光控制 ──────────────────────────────────────────────
    if intent in ("lights_on", "lights_off", "all_on", "all_off"):
        cmd_map = {"lights_on": "开灯", "lights_off": "关灯", "all_on": "一键开馆", "all_off": "一键关馆"}
        target = cmd_map[intent]
        result = await db.execute(
            select(CloudCommand).where(CloudCommand.name.contains(target)).limit(1)
        )
        cmd = result.scalar_one_or_none()
        if cmd:
            from .commands import parse_and_send_command
            await parse_and_send_command(
                cmd.command_str, cmd.protocol,
                cmd.target_ip, cmd.target_port, cmd.is_hex
            )
            return f"好的，正在执行{target}。"
        # fallback 直发中控TCP
        from ..config import settings
        cmd_str = {"lights_on": "0_all_on", "lights_off": "0_all_off",
                   "all_on": "0_all_on", "all_off": "0_all_off"}[intent]
        await send_tcp(settings.ZHONGKONG_TCP_HOST, settings.ZHONGKONG_TCP_PORT, cmd_str)
        return f"好的，正在执行{target}。"

    # ─ 帮助 ──────────────────────────────────────────────────
    if intent == "help":
        return ("我可以帮你做这些事情：\n"
                "• 「开始参观」— 启动自动导览\n"
                "• 「这里有哪些文件」— 查看当前展项内容\n"
                "• 「第一个」「第二个」— 播放指定内容\n"
                "• 「下一个展项」「上一个展项」— 导览切换\n"
                "• 「停止」「继续」— 控制当前任务\n"
                "• 「回入口」「去充电」— 机器人位置控制\n"
                "• 「开灯」「关灯」— 控制灯光")

    # ─ 闲聊兜底 ──────────────────────────────────────────────
    if intent in ("chitchat", "unknown"):
        from openai import AsyncOpenAI
        client = AsyncOpenAI(api_key=settings.QWEN_API_KEY, base_url=settings.QWEN_BASE_URL)
        try:
            import asyncio
            resp = await asyncio.wait_for(
                client.chat.completions.create(
                    model=settings.QWEN_MODEL,
                    messages=[
                        {"role": "system", "content": "你是展厅智能讲解员旺财，活泼友好，专注于展厅服务。"},
                        {"role": "user", "content": raw_text}
                    ],
                    max_tokens=200,
                ),
                timeout=10
            )
            return resp.choices[0].message.content.strip()
        except Exception:
            return "您好！有什么可以帮助您的吗？"

    return "收到，正在处理您的请求。"


async def go_to_stop(db, session, robot, route_id, stop_index) -> str:
    """导航到指定导览站点"""
    from ..models import TourRoute, TourStop
    result = await db.execute(
        select(TourStop)
        .where(TourStop.route_id == route_id)
        .order_by(TourStop.sort)
    )
    stops = result.scalars().all()
    if stop_index >= len(stops):
        session.robot_status = "idle"
        session.tour_route_id = None
        return "导览已完成，感谢您的参观！"
    stop = stops[stop_index]
    session.tour_stop_index = stop_index
    if robot:
        await robot.navigate(stop.nav_poi, wait_arrival=False)
    welcome = stop.welcome_text or f"欢迎来到第 {stop_index + 1} 个展项。"
    return welcome


async def get_item_narration(db, resource_id: int, title: str) -> str:
    """获取资源讲解词，没有则AI生成"""
    # 先从展项条目中查
    from ..models import ExhibitItem
    result = await db.execute(
        select(ExhibitItem).where(ExhibitItem.resource_id == resource_id).limit(1)
    )
    item = result.scalar_one_or_none()
    if item and item.narration:
        return item.narration

    # AI生成兜底
    try:
        from openai import AsyncOpenAI
        import asyncio
        client = AsyncOpenAI(api_key=settings.QWEN_API_KEY, base_url=settings.QWEN_BASE_URL)
        resp = await asyncio.wait_for(
            client.chat.completions.create(
                model=settings.QWEN_MODEL,
                messages=[
                    {"role": "system", "content": "你是专业的展厅讲解员，请用100字左右介绍以下内容，语气亲切专业。"},
                    {"role": "user", "content": f"请介绍：{title}"}
                ],
                max_tokens=200,
            ),
            timeout=8
        )
        return resp.choices[0].message.content.strip()
    except Exception:
        return f"这是关于「{title}」的展示内容，欢迎您参观了解。"
