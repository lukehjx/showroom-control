import logging
from sqlalchemy import select
from database import async_session
from models import SystemConfig
from datetime import datetime

logger = logging.getLogger(__name__)

DEFAULT_CONFIGS = [
    ("tcp.host", "112.20.77.18", "TCP主机地址"),
    ("tcp.port", "8989", "TCP端口"),
    ("tcp.listen_port", "19888", "TCP监听端口"),
    ("cloud.api_url", "http://112.20.77.18:7772", "中控云平台API地址"),
    ("cloud.account", "ZhanGuan", "云平台账号"),
    ("cloud.password", "sidex@123", "云平台密码"),
    ("cloud.basic_auth_user", "admin", "Basic Auth用户名"),
    ("cloud.basic_auth_pass", "admin123", "Basic Auth密码"),
    ("cloud.exhibition_id", "5", "展览ID"),
    ("robot.sn", "MC1BCN2K100262058CA0", "机器人SN"),
    ("robot.app_key", "", "机器人AppKey"),
    ("robot.app_secret", "", "机器人AppSecret"),
    ("wecom_bot.bot_id", "aibQrNJ78ZCf_Nmy2QSxQVTr_N4QsbplePy", "企微BotID"),
    ("wecom_bot.secret", "yac9cTn8MGLEx6tbh4IDiJexrTdS1ptiHIYkIZyAbg5", "企微Bot密钥"),
    ("ai.qwen_key", "sk-845c78e1c9a749ba901c5ce3d68f4a33", "通义千问API密钥"),
    ("ai.qwen_model", "qwen-plus-latest", "通义千问模型"),
]


async def init_config():
    async with async_session() as session:
        try:
            for key, value, desc in DEFAULT_CONFIGS:
                existing = await session.execute(
                    select(SystemConfig).where(SystemConfig.key == key)
                )
                if not existing.scalar_one_or_none():
                    session.add(SystemConfig(key=key, value=value, description=desc, updated_at=datetime.now()))
            await session.commit()
            logger.info("Default configs initialized")
        except Exception as e:
            await session.rollback()
            logger.error(f"Failed to init configs: {e}")


async def get_config(key: str) -> str:
    async with async_session() as session:
        result = await session.execute(
            select(SystemConfig).where(SystemConfig.key == key)
        )
        cfg = result.scalar_one_or_none()
        return cfg.value if cfg else None


async def get_all_configs() -> dict:
    async with async_session() as session:
        result = await session.execute(select(SystemConfig))
        return {cfg.key: cfg.value for cfg in result.scalars().all()}
