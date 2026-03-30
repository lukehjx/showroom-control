from pydantic_settings import BaseSettings
from typing import Optional

class Settings(BaseSettings):
    DATABASE_URL: str = "postgresql+asyncpg://showroom:showroom123@localhost/showroom"
    REDIS_URL: str = "redis://localhost:6379/0"
    SECRET_KEY: str = "change-me-in-production"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24 * 7

    QWEN_API_KEY: str = ""
    QWEN_MODEL: str = "qwen-plus-latest"
    QWEN_BASE_URL: str = "https://dashscope.aliyuncs.com/compatible-mode/v1"
    QWEN_TIMEOUT: int = 5

    WECOM_BOT_ID: str = ""
    WECOM_BOT_SECRET: str = ""
    WECOM_CHAT_ID: str = ""

    ZHONGKONG_BASE_URL: str = "http://112.20.77.18:7772"
    ZHONGKONG_ACCOUNT: str = "ZhanGuan"
    ZHONGKONG_PASSWORD: str = ""
    ZHONGKONG_HALL_ID: int = 5
    ZHONGKONG_TCP_HOST: str = "112.20.77.18"
    ZHONGKONG_TCP_PORT: int = 8989
    ZHONGKONG_HTTP_HOST: str = "112.20.77.18"
    ZHONGKONG_HTTP_PORT: int = 8899

    ROBOT_SN: str = "MC1BCN2K100262058CA0"
    ROBOT_APP_KEY: str = ""
    ROBOT_APP_SECRET: str = ""

    COS_SECRET_ID: str = ""
    COS_SECRET_KEY: str = ""
    COS_BUCKET: str = "zyk-1252093492"
    COS_REGION: str = "ap-tokyo"
    COS_DOMAIN: str = "cct.sidex.cn"

    UPDATE_LISTENER_PORT: int = 8989
    FREE_WAKE_WINDOW: int = 30

    class Config:
        env_file = ".env"
        extra = "ignore"

settings = Settings()
