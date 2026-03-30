"""
展厅智控 企微Bot - v4 (async handler + reply_stream with uuid stream_id)
"""
import logging
import asyncio
import threading
import uuid
import httpx
import sys

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)]
)
logger = logging.getLogger(__name__)


def _get_config(key: str) -> str:
    try:
        resp = httpx.get(f"http://127.0.0.1:8200/api/config/{key}", timeout=5)
        if resp.status_code == 200:
            return resp.json().get("data", {}).get("value", "") or ""
    except Exception:
        pass
    return ""


async def _get_reply(text: str, sender: str, chatid: str, chattype: str) -> str:
    try:
        robot_sn = _get_config("robot.sn") or "MC1BCN2K100262058CA0"
        payload = {
            "event": "text",
            "text": text,
            "robot_sn": robot_sn,
            "source": "wecom",
            "params": {"sender": sender, "chatid": chatid, "chattype": chattype}
        }
        async with httpx.AsyncClient(timeout=35) as client:
            resp = await client.post("http://127.0.0.1:8200/api/chat/input", json=payload)
            if resp.status_code == 200:
                data = resp.json()
                reply = data.get("data", {}).get("reply")
                if reply:
                    return str(reply)
                return "收到，已处理。"
            return "处理出错，请稍后再试。"
    except Exception as e:
        logger.error(f"Get reply error: {e}")
        return "网络异常，请稍后再试。"


async def _poll_notifications(ws_client):
    """轮询 bot_notifications 推送到群"""
    while True:
        try:
            async with httpx.AsyncClient(timeout=10) as client:
                ng_resp = await client.get("http://127.0.0.1:8200/api/notify-groups")
                groups = [g for g in (ng_resp.json().get("data") or []) if g.get("enabled")] if ng_resp.status_code == 200 else []

                bn_resp = await client.get("http://127.0.0.1:8200/api/bot-notifications?sent=false&limit=20")
                items = bn_resp.json().get("data") or [] if bn_resp.status_code == 200 else []

                for item in items:
                    msg = item.get("message", "")
                    nid = item.get("id")
                    if not msg:
                        continue
                    for group in groups:
                        chat_id = group.get("chat_id")
                        if chat_id:
                            try:
                                await ws_client.send_message(
                                    chatid=chat_id,
                                    msgtype="markdown",
                                    markdown={"content": msg}
                                )
                            except Exception as e:
                                logger.warning(f"Push to {chat_id} failed: {e}")
                    try:
                        await client.patch(f"http://127.0.0.1:8200/api/bot-notifications/{nid}", json={"sent": True})
                    except Exception:
                        pass
        except Exception as e:
            logger.debug(f"Poll error: {e}")
        await asyncio.sleep(5)


def main():
    bot_id = _get_config("wecom_bot.bot_id")
    secret = _get_config("wecom_bot.secret")

    if not bot_id or not secret:
        logger.error("WecomBot: bot_id or secret not configured")
        import time
        time.sleep(10)
        return

    from aibot import WSClient, WSClientOptions
    options = WSClientOptions(bot_id=bot_id, secret=secret)
    ws_client = WSClient(options)

    @ws_client.on("message")
    async def on_message(frame):
        try:
            body = frame.get("body", {})
            msgtype = body.get("msgtype", "")
            if msgtype not in ("text", "voice"):
                return

            text = (body.get("text") or {}).get("content", "") or \
                   (body.get("voice") or {}).get("content", "") or ""
            if "@" in text:
                parts = text.split(" ", 1)
                text = parts[1].strip() if len(parts) > 1 else text.strip()
            text = text.strip()
            if not text:
                return

            sender = (body.get("from") or {}).get("userid", "") or ""
            chatid = body.get("chatid", "") or ""
            chattype = body.get("chattype", "group")

            logger.info(f"收到消息 [{chattype}] from {sender}: {text}")

            if "群ID" in text or "chatid" in text.lower():
                reply = f"当前会话ID：`{chatid}`"
            else:
                reply = await _get_reply(text, sender, chatid, chattype)

            # 用 reply_stream 发送（需要 stream_id + finish=True）
            stream_id = str(uuid.uuid4())
            await ws_client.reply_stream(frame, stream_id, reply, finish=True)
            logger.info(f"已回复: {reply[:80]}")
        except Exception as e:
            logger.error(f"处理消息失败: {e}")

    # 启动通知轮询（作为 coroutine，由 ws_client 的 event loop 运行）
    # 注入到 ws_client 的 loop 里
    @ws_client.on("connected")
    async def on_connected():
        asyncio.ensure_future(_poll_notifications(ws_client))
        logger.info("WecomBot connected, notification polling started")

    logger.info("WecomBot starting...")
    ws_client.run()


def start_bot_background():
    t = threading.Thread(target=main, daemon=True)
    t.start()
    logger.info("WecomBot thread started")


if __name__ == "__main__":
    main()
