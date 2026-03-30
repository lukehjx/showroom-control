"""
展厅智控系统后端主入口
"""
import asyncio
import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .database import init_db
from .routers import chat, sync, robot_api
from .routers.ws_robot import router as ws_router
from .services.wecom_bot import start_bot, set_chat_handler
from .services.chat import handle_input
from .config import settings

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(name)s] [%(levelname)s] %(message)s"
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # 初始化数据库
    await init_db()
    logger.info("数据库初始化完成")

    # 注入对话处理函数到Bot
    set_chat_handler(handle_input)

    # 启动企微Bot（独立线程）
    loop = asyncio.get_event_loop()
    start_bot(loop)
    logger.info("企微Bot已启动")

    yield
    logger.info("系统关闭")


app = FastAPI(
    title="展厅智控系统 API",
    description="机器人+中控+企微一体化展厅管理平台",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 路由注册
app.include_router(chat.router)
app.include_router(sync.router)
app.include_router(robot_api.router)
app.include_router(ws_router)


@app.get("/health")
async def health():
    return {"status": "ok", "service": "showroom-control"}


@app.get("/")
async def root():
    return {"msg": "展厅智控系统运行中", "version": "1.0.0"}
