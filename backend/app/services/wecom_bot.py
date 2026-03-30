"""
企微Bot长连接服务
"""
import threading
import logging
import asyncio
import aiohttp
from ..config import settings

logger = logging.getLogger(__name__)

_chat_handler = None  # 注入 handle_input 函数


def set_chat_handler(fn):
    global _chat_handler
    _chat_handler = fn


def start_bot(loop: asyncio.AbstractEventLoop):
    """在独立线程中运行企微Bot"""
    def run():
        try:
            from wecom_aibot import WSClient, WSClientOptions

            options = WSClientOptions(
                bot_id=settings.WECOM_BOT_ID,
                bot_secret=settings.WECOM_BOT_SECRET,
            )
            client = WSClient(options)

            @client.on_message
            def on_message(frame):
                try:
                    msg_text = frame.body.text.content if hasattr(frame.body, "text") else str(frame.body)
                    sender = getattr(frame, "sender_id", "wecom_unknown")
                    logger.info(f"[WecomBot] 收到消息: {msg_text} from {sender}")

                    if _chat_handler and msg_text:
                        async def process():
                            from ..database import AsyncSessionLocal
                            async with AsyncSessionLocal() as db:
                                result = await _chat_handler(
                                    db=db,
                                    text=msg_text,
                                    source="wecom",
                                    session_key=f"wecom_{sender}",
                                )
                                reply = result.get("reply", "")
                                if reply:
                                    await send_to_wecom(reply)
                        asyncio.run_coroutine_threadsafe(process(), loop)
                except Exception as e:
                    logger.error(f"[WecomBot] 消息处理异常: {e}")

            # 断线重连循环
            while True:
                try:
                    client.run()
                except Exception as e:
                    logger.error(f"[WecomBot] 连接断开，5秒后重连: {e}")
                    import time
                    time.sleep(5)

        except ImportError:
            logger.warning("[WecomBot] wecom_aibot 未安装，Bot功能禁用")

    t = threading.Thread(target=run, daemon=True, name="wecom-bot")
    t.start()
    logger.info("[WecomBot] 后台线程已启动")


async def send_to_wecom(text: str, chat_id: str = None):
    """主动推送消息到企微群"""
    chat_id = chat_id or settings.WECOM_CHAT_ID
    # 用企微Bot HTTP API发送
    url = f"https://qyapi.weixin.qq.com/cgi-bin/appchat/send"
    # 实际上我们用AiBot SDK的send接口
    try:
        from wecom_aibot import WSClient, WSClientOptions
        # TODO: 调用client.send_message
        pass
    except Exception:
        pass
    logger.info(f"[WecomBot] 推送: {text[:50]}")
