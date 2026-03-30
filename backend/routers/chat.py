import logging
from fastapi import APIRouter
from sqlalchemy import select, text
from database import async_session
from models import ChatSession, Exhibit, OperationLog
from schemas import ok, err, ChatInput
from intent import recognize_intent
from datetime import datetime, timezone

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/chat", tags=["chat"])


@router.post("/input")
async def chat_input(body: ChatInput):
    """对话入口：接收事件并处理意图"""
    try:
        event = body.event
        robot_sn = body.robot_sn or ""
        params = body.params or {}

        # 记录操作日志
        log = OperationLog(
            action=f"chat_input:{event}",
            source=robot_sn,
            params={"event": event, "params": params},
            created_at=datetime.now()
        )

        # 获取或创建会话
        async with async_session() as session:
            result = await session.execute(
                select(ChatSession).where(ChatSession.robot_sn == robot_sn).order_by(ChatSession.id.desc()).limit(1)
            )
            chat_session = result.scalar_one_or_none()

            if not chat_session:
                chat_session = ChatSession(robot_sn=robot_sn, state="idle")
                session.add(chat_session)
                await session.commit()
                await session.refresh(chat_session)

        response_data = {"event": event, "robot_sn": robot_sn, "result": None}

        if event in ("voice_input", "text"):
            text = params.get("text", "") or body.text or ""
            if not text:
                return err("Missing text in params")

            # 意图识别
            intent_result = await recognize_intent(text, {"robot_sn": robot_sn})
            intent = intent_result.get("intent", "unknown")
            extra = intent_result.get("extra", {})

            response_data["intent"] = intent
            response_data["intent_result"] = intent_result

            # 根据意图执行动作
            action_result = await handle_intent(intent, extra, robot_sn, chat_session)
            response_data["result"] = action_result

            # 生成人话回复文本
            reply_text = await _generate_reply(intent, extra, action_result, text)
            response_data["reply"] = reply_text

            # 机器人回复后进入对话模式30秒（只要有动作响应就激活）
            await _set_listening_mode(robot_sn, True)

        elif event == "robot_arrived":
            poi = params.get("poi", "")
            from lane_engine import trigger_callback
            await trigger_callback(f"arrived_{poi}")
            response_data["result"] = f"Arrived at {poi}"

        elif event == "tts_done":
            from lane_engine import trigger_callback
            await trigger_callback("tts_done")
            # TTS播完后激活对话模式30秒
            await _set_listening_mode(robot_sn, True)
            response_data["result"] = "TTS done"

        elif event == "robot_callback":
            cb_type = params.get("type", "")
            from lane_engine import trigger_callback
            await trigger_callback(cb_type)
            response_data["result"] = f"Callback {cb_type} triggered"

        else:
            response_data["result"] = f"Unknown event: {event}"

        # 保存操作日志
        async with async_session() as session:
            log.result = response_data
            session.add(log)
            await session.commit()

        return ok(response_data)

    except Exception as e:
        logger.error(f"Chat input error: {e}")
        return err(str(e))


async def _set_listening_mode(robot_sn: str, active: bool):
    """设置机器人的对话监听模式"""
    try:
        async with async_session() as session:
            if active:
                await session.execute(
                    text("""
                        UPDATE chat_sessions
                        SET listening_mode=TRUE,
                            listening_expires_at=NOW() AT TIME ZONE 'UTC' + INTERVAL '30 seconds'
                        WHERE robot_sn=:sn
                    """),
                    {"sn": robot_sn}
                )
            else:
                await session.execute(
                    text("UPDATE chat_sessions SET listening_mode=FALSE WHERE robot_sn=:sn"),
                    {"sn": robot_sn}
                )
            await session.commit()
    except Exception as e:
        logger.warning(f"Set listening mode error: {e}")


@router.get("/listening-mode/{robot_sn}")
async def get_listening_mode(robot_sn: str):
    """APK轮询：查询机器人是否在对话监听模式（TTS后30秒内免唤醒词）"""
    try:
        async with async_session() as session:
            result = await session.execute(
                text("""
                    SELECT listening_mode, listening_expires_at
                    FROM chat_sessions WHERE robot_sn=:sn
                    ORDER BY id DESC LIMIT 1
                """),
                {"sn": robot_sn}
            )
            row = result.fetchone()

        if not row:
            return ok({"listening": False})

        listening_mode = row[0]
        listening_expires_at = row[1]

        if not listening_mode or not listening_expires_at:
            return ok({"listening": False})

        now_utc = datetime.now(timezone.utc)
        # listening_expires_at may be naive (no tz), compare carefully
        if hasattr(listening_expires_at, 'tzinfo') and listening_expires_at.tzinfo:
            active = listening_expires_at > now_utc
        else:
            from datetime import timezone as tz
            expires_utc = listening_expires_at.replace(tzinfo=timezone.utc)
            active = expires_utc > now_utc

        if not active and listening_mode:
            # 过期，重置
            await _set_listening_mode(robot_sn, False)

        return ok({"listening": bool(active)})

    except Exception as e:
        logger.error(f"Get listening mode error: {e}")
        return ok({"listening": False})


async def handle_intent(intent: str, extra: dict, robot_sn: str, chat_session: ChatSession) -> dict:
    """根据意图执行相应动作"""
    try:
        if intent == "start_tour":
            # 获取第一个展项
            async with async_session() as session:
                result = await session.execute(
                    select(Exhibit).order_by(Exhibit.sort_order, Exhibit.id).limit(1)
                )
                first_exhibit = result.scalar_one_or_none()

            if first_exhibit:
                async with async_session() as session:
                    cs = await session.get(ChatSession, chat_session.id)
                    if cs:
                        cs.state = "touring"
                        cs.current_exhibit_id = first_exhibit.id
                        cs.last_activity_at = datetime.now()
                        await session.commit()
                return {"action": "start_tour", "exhibit_id": first_exhibit.id, "exhibit_name": first_exhibit.name}
            return {"action": "start_tour", "message": "No exhibits found"}

        elif intent == "next_exhibit":
            async with async_session() as session:
                cs = await session.get(ChatSession, chat_session.id)
                current_id = cs.current_exhibit_id if cs else None

                if current_id:
                    result = await session.execute(
                        select(Exhibit).where(Exhibit.id > current_id).order_by(Exhibit.sort_order, Exhibit.id).limit(1)
                    )
                    next_exhibit = result.scalar_one_or_none()
                else:
                    result = await session.execute(
                        select(Exhibit).order_by(Exhibit.sort_order, Exhibit.id).limit(1)
                    )
                    next_exhibit = result.scalar_one_or_none()

                if next_exhibit and cs:
                    cs.current_exhibit_id = next_exhibit.id
                    cs.last_activity_at = datetime.now()
                    await session.commit()
                    return {"action": "next_exhibit", "exhibit_id": next_exhibit.id, "exhibit_name": next_exhibit.name}
            return {"action": "next_exhibit", "message": "No more exhibits"}

        elif intent == "prev_exhibit":
            async with async_session() as session:
                cs = await session.get(ChatSession, chat_session.id)
                current_id = cs.current_exhibit_id if cs else None

                if current_id:
                    result = await session.execute(
                        select(Exhibit).where(Exhibit.id < current_id).order_by(Exhibit.sort_order.desc(), Exhibit.id.desc()).limit(1)
                    )
                    prev_exhibit = result.scalar_one_or_none()
                    if prev_exhibit and cs:
                        cs.current_exhibit_id = prev_exhibit.id
                        cs.last_activity_at = datetime.now()
                        await session.commit()
                        return {"action": "prev_exhibit", "exhibit_id": prev_exhibit.id, "exhibit_name": prev_exhibit.name}
            return {"action": "prev_exhibit", "message": "No previous exhibit"}

        elif intent == "go_home":
            async with async_session() as session:
                cs = await session.get(ChatSession, chat_session.id)
                if cs:
                    cs.state = "idle"
                    cs.current_exhibit_id = None
                    cs.last_activity_at = datetime.now()
                    await session.commit()
            return {"action": "go_home"}

        elif intent == "stop":
            async with async_session() as session:
                cs = await session.get(ChatSession, chat_session.id)
                if cs:
                    cs.state = "idle"
                    cs.last_activity_at = datetime.now()
                    await session.commit()
            return {"action": "stop"}

        elif intent == "list_files":
            async with async_session() as session:
                cs = await session.get(ChatSession, chat_session.id)
                current_id = cs.current_exhibit_id if cs else None

            if current_id:
                from models import CloudResource, CloudTerminal
                from sqlalchemy import text as sa_text
                async with async_session() as session:
                    # current_exhibit_id 可能是 terminal_id 或 cloud_terminals.id
                    # 先获取真正的 terminal_id
                    real_tid = current_id
                    t_result = await session.execute(select(CloudTerminal).where(CloudTerminal.id == current_id))
                    terminal = t_result.scalars().first()
                    if terminal:
                        real_tid = terminal.terminal_id

                    result = await session.execute(
                        sa_text("SELECT id, resource_id, title, file_name, sort FROM cloud_resources WHERE (raw_data->>'_terminal_id')::int = :tid ORDER BY sort"),
                        {"tid": real_tid}
                    )
                    rows = result.mappings().all()
                    files = [{"id": r["id"], "resource_id": r["resource_id"], "title": r["title"] or r["file_name"] or f"资源{i+1}"} for i, r in enumerate(rows)]
                return {"action": "list_files", "terminal_id": real_tid, "count": len(files), "files": files}
            return {"action": "list_files", "count": 0, "files": [], "message": "未指定展位"}

        elif intent == "select":
            index = extra.get("index", 1)
            return {"action": "select", "index": index}

        elif intent in ("lights_off", "lights_on", "devices_off", "devices_on"):
            import socket as _socket
            from sqlalchemy import text as sa_text

            if intent == "lights_off":
                name_filter, group_filter = "关", "灯"
            elif intent == "lights_on":
                name_filter, group_filter = "开", "灯"
            elif intent == "devices_off":
                name_filter, group_filter = "关机", ""
            else:
                name_filter, group_filter = "开机", ""

            async with async_session() as session:
                if group_filter:
                    q = await session.execute(
                        sa_text("SELECT command_str, is_hex FROM cloud_commands WHERE name=:n AND group_name LIKE :g AND protocol_type='tcp'"),
                        {"n": name_filter, "g": f"%{group_filter}%"}
                    )
                else:
                    q = await session.execute(
                        sa_text("SELECT command_str, is_hex FROM cloud_commands WHERE name=:n AND protocol_type='tcp'"),
                        {"n": name_filter}
                    )
                cmds = q.mappings().all()

            sent, errors = 0, []
            for cmd in cmds:
                try:
                    cmd_str = cmd["command_str"] or ""
                    is_hex = cmd["is_hex"] or False
                    with _socket.create_connection(("112.20.77.18", 8989), timeout=3) as s:
                        data = bytes.fromhex(cmd_str) if is_hex else cmd_str.encode("utf-8")
                        s.sendall(data)
                    sent += 1
                except Exception as e:
                    errors.append(str(e)[:40])
            return {"action": intent, "total": len(cmds), "sent": sent, "errors": errors[:3]}


        elif intent == "narrate":
            # 讲解当前展项
            async with async_session() as session:
                cs = await session.get(ChatSession, chat_session.id)
                current_id = cs.current_exhibit_id if cs else None
            if current_id:
                from models import Exhibit
                async with async_session() as session:
                    ex = await session.get(Exhibit, current_id)
                if ex:
                    return {"action": "narrate", "exhibit_id": current_id,
                            "exhibit_name": ex.name, "narration": ex.description or ""}
            return {"action": "narrate", "message": "当前没有选中展项，请先说 开始参观"}

        elif intent == "narrate_select":
            index = extra.get("index", 1)
            return {"action": "narrate_select", "index": index}

        elif intent == "scene_switch":
            return {"action": "scene_switch", "status": "acknowledged"}

        elif intent == "query_scene":
            from sqlalchemy import text as sa_text
            async with async_session() as session:
                r = await session.execute(sa_text("SELECT name FROM cloud_scenes ORDER BY id LIMIT 20"))
                scenes = [row[0] for row in r.fetchall()]
                cur = await session.execute(sa_text("SELECT scene_id FROM current_scene LIMIT 1"))
                cur_row = cur.fetchone()
                cur_id = cur_row[0] if cur_row else None
                if cur_id:
                    cr = await session.execute(sa_text(f"SELECT name FROM cloud_scenes WHERE scene_id={cur_id} LIMIT 1"))
                    cur_scene_row = cr.fetchone()
                    cur_scene = cur_scene_row[0] if cur_scene_row else f"专场{cur_id}"
                else:
                    cur_scene = "未知"
            return {"action": "query_scene", "current": cur_scene, "all": scenes}

        elif intent == "query_exhibits":
            async with async_session() as session:
                result = await session.execute(
                    text("SELECT id, terminal_id, name FROM cloud_terminals ORDER BY id")
                )
                terminals = [{"id": r[0], "terminal_id": r[1], "name": r[2]} for r in result.fetchall()]
            return {"action": "query_exhibits", "count": len(terminals), "exhibits": terminals}

        elif intent == "query_progress":
            async with async_session() as session:
                cs = await session.get(ChatSession, chat_session.id)
                current_id = cs.current_exhibit_id if cs else None
                state = cs.state if cs else "idle"
            if current_id:
                from models import Exhibit
                async with async_session() as session:
                    ex = await session.get(Exhibit, current_id)
                name = ex.name if ex else f"展项{current_id}"
                return {"action": "query_progress", "state": state, "current_exhibit": name}
            return {"action": "query_progress", "state": state, "current_exhibit": None}

        elif intent == "query_status":
            from sqlalchemy import text as sa_text
            async with async_session() as session:
                sr = await session.execute(sa_text("SELECT scene_id FROM current_scene LIMIT 1"))
                scene_row = sr.fetchone()
            return {"action": "query_status", "scene_id": scene_row[0] if scene_row else None,
                    "robot_sn": robot_sn, "status": "running"}

        elif intent in ("media_play", "media_pause", "media_prev", "media_next",
                         "media_mute", "media_vol_up", "media_vol_down"):
            media_cmd_map = {
                "media_play": "play", "media_pause": "pause",
                "media_prev": "prev", "media_next": "next",
                "media_mute": "mute", "media_vol_up": "vol_up", "media_vol_down": "vol_down"
            }
            cmd = media_cmd_map.get(intent, intent)
            return {"action": "media_control", "command": cmd, "status": "sent"}

        elif intent == "device_ad":
            return {"action": "device_ad", "status": "acknowledged"}

        elif intent == "help":
            return {"action": "help"}

        else:
            return {"action": intent, "status": "acknowledged"}

    except Exception as e:
        logger.error(f"Handle intent {intent} error: {e}")
        return {"action": intent, "error": str(e)}


async def _generate_reply(intent: str, extra: dict, action_result: dict, text: str) -> str:
    """根据意图生成人话回复"""
    from config import get_config
    from openai import AsyncOpenAI

    INTENT_REPLIES = {
        "list_files": None,  # 由 handle_intent 的 result 构建
        "next_exhibit": "好的，我们去下一个展项！",
        "prev_exhibit": "好的，回到上一个展项。",
        "start_tour": "好的，我带您开始参观！",
        "go_home": "好的，我们回到入口！",
        "go_charge": "好的，我去充电了，一会儿见！",
        "repeat": "好的，我再说一遍。",
        "stop": "好的，停止了。",
        "continue": "好的，继续。",
        "select": None,  # 由 handle_intent 的 result 构建
    }

    if intent in INTENT_REPLIES and INTENT_REPLIES[intent] is not None:
        return INTENT_REPLIES[intent]

    if intent == "list_files":
        count = action_result.get("count", 0)
        files = action_result.get("files", [])
        if count > 0 and files:
            names = "".join([f"\n第{i+1}个：《{f['title']}》" for i, f in enumerate(files[:8])])
            if count > 8:
                names += f"\n...共{count}个"
            return f"当前展位共有 {count} 个内容：{names}\n\n说「第一个」「第二个」等来播放。"
        return "当前展位暂无内容资源，可能需要先同步数据。"

    if intent == "select":
        index = extra.get("index", 1)
        return f"好的，正在播放第{index}个内容。"

    if intent == "lights_off":
        sent = action_result.get("sent", 0)
        total = action_result.get("total", 0)
        return f"好的，已发送关灯指令，共 {sent}/{total} 路灯光关闭。"

    if intent == "lights_on":
        sent = action_result.get("sent", 0)
        total = action_result.get("total", 0)
        return f"好的，已发送开灯指令，共 {sent}/{total} 路灯光开启。"

    if intent in ("devices_off", "devices_on"):
        sent = action_result.get("sent", 0)
        total = action_result.get("total", 0)
        action_word = "关机" if intent == "devices_off" else "开机"
        return f"好的，已发送{action_word}指令，共 {sent}/{total} 个设备。"


    if intent == "narrate":
        narration = action_result.get("narration", "")
        name = action_result.get("exhibit_name", "当前展项")
        if narration:
            return "📍 " + name + "\n" + narration
        return f"正在为您讲解《{name}》，精彩内容即将呈现～"

    if intent == "narrate_select":
        index = extra.get("index", 1)
        return f"好的，正在讲解第{index}个内容。"

    if intent == "scene_switch":
        return "好的，正在为您切换专场，稍候片刻～"

    if intent == "query_scene":
        cur = action_result.get("current", "未知")
        all_scenes = action_result.get("all", [])
        if all_scenes:
            scene_list = "、".join(all_scenes[:6])
            return "🎭 当前专场：" + cur + "\n所有专场：" + scene_list + "\n说「切换到XX专场」即可切换。"
        return "🎭 当前专场：" + cur

    if intent == "query_exhibits":
        exhibits = action_result.get("exhibits", [])
        count = action_result.get("count", 0)
        if exhibits:
            names = "\n".join(["• " + e["name"] for e in exhibits[:8]])
            return f"📍 共{count}个展位：\n" + names
        return "暂未配置展位信息。"

    if intent == "query_progress":
        ex = action_result.get("current_exhibit")
        state = action_result.get("state", "idle")
        if state == "touring" and ex:
            return "🚶 正在参观中，当前展位：" + ex + "\n说「下一个」继续，「停」结束参观。"
        return "😊 当前没有正在进行的参观导览。说「开始参观」开始吧！"

    if intent == "query_status":
        scene_id = action_result.get("scene_id")
        return f"🤖 系统运行正常 机器人：{robot_sn} 当前专场ID：{scene_id or '未知'}"

    if intent in ("media_play", "media_pause", "media_prev", "media_next",
                  "media_mute", "media_vol_up", "media_vol_down"):
        cmd_text = {
            "media_play": "▶️ 开始播放", "media_pause": "⏸️ 已暂停",
            "media_prev": "⏮️ 上一页", "media_next": "⏭️ 下一页",
            "media_mute": "🔇 已静音", "media_vol_up": "🔊 音量加大", "media_vol_down": "🔉 音量减小"
        }.get(intent, "已执行")
        return cmd_text

    if intent == "device_ad":
        return "📺 广告机开启中，请稍候～"

    if intent == "help":
        lines = [
            "我是展厅导览助手，以下是我能做的：",
            "",
            "📂 查看当前内容：「有哪些文件」",
            "▶️ 播放内容：「第X个」（如：第二个）",
            "🎙️ 听讲解：「讲解一下」/「讲解第X个」",
            "🚶 参观导览：「开始参观」/「下一个」/「上一个」",
            "💡 控制设备：「开灯」/「关灯」/「开广告机」",
            "🔄 换展示内容：「切换到XX专场」",
            "🎮 媒体控制：「播放」/「暂停」/「上一页」/「下一页」/「静音」/「音量大」",
            "🔍 查询状态：「现在什么专场」/「有哪些专场」/「有哪些展位」/「参观到哪了」/「系统状态」",
            "🔁 重复：「再说一遍」",
            "⏹️ 停止：「停」",
        ]
        return "\n".join(lines)

    # unknown 意图 → Qwen 闲聊
    try:
        qwen_key = await get_config("ai.qwen_key") or "sk-845c78e1c9a749ba901c5ce3d68f4a33"
        qwen_model = await get_config("ai.qwen_model") or "qwen-plus-latest"
        bot_name = await get_config("bot.name") or "旺财"
        location = await get_config("bot.location") or "南京"
        system_prompt = await get_config("bot.system_prompt") or f"你是展厅导览机器人{bot_name}，请用简短活泼的语气回复（不超过150字）。"
        system_prompt = system_prompt.replace("{name}", bot_name).replace("{location}", location)

        client = AsyncOpenAI(api_key=qwen_key, base_url="https://dashscope.aliyuncs.com/compatible-mode/v1")
        response = await client.chat.completions.create(
            model=qwen_model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": text}
            ],
            temperature=0.7,
            max_tokens=300,
            extra_body={"enable_search": True}
        )
        return response.choices[0].message.content.strip()
    except Exception as e:
        logger.warning(f"Qwen llm_chat failed: {e}")
        return f"您好！我是{await get_config('bot.name') or '旺财'}，有什么需要帮助的吗？您可以说「开始参观」「有哪些文件」等指令。"
