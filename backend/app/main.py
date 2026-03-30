"""
展厅智控系统后端主入口
"""
import asyncio
import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from apscheduler.schedulers.asyncio import AsyncIOScheduler

from .database import init_db
from .routers import chat, sync, robot_api
from .routers.ws_robot import router as ws_router
from .routers.scripts import router as scripts_router
from .routers.routes import router as routes_router
from .routers.reception import router as reception_router
from .routers.tasks import router as tasks_router, notify_router
from .routers.logs import router as logs_router
from .routers.settings_api import router as settings_router
from .routers.flows import router as flows_router
from .services.wecom_bot import start_bot, set_chat_handler
from .services.chat import handle_input
from .config import settings

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(name)s] [%(levelname)s] %(message)s"
)
logger = logging.getLogger(__name__)

# 全局调度器（供 tasks.py 使用）
scheduler = AsyncIOScheduler(timezone="Asia/Shanghai")


@asynccontextmanager
async def lifespan(app: FastAPI):
    # 初始化数据库
    await init_db()
    logger.info("数据库初始化完成")

    # 启动APScheduler
    scheduler.start()
    logger.info("定时任务调度器已启动")

    # 加载已有定时任务
    await _load_scheduled_tasks()

    # 注入对话处理函数到Bot
    set_chat_handler(handle_input)

    # 启动企微Bot（独立线程）
    loop = asyncio.get_event_loop()
    start_bot(loop)
    logger.info("企微Bot已启动")

    yield

    scheduler.shutdown()
    logger.info("系统关闭")


async def _load_scheduled_tasks():
    """从数据库加载并注册已有的定时任务"""
    try:
        from .database import AsyncSessionLocal
        from sqlalchemy import select
        from .models import ScheduledTask
        from .routers.tasks import _register_job
        async with AsyncSessionLocal() as db:
            result = await db.execute(select(ScheduledTask).where(ScheduledTask.enabled == True))
            tasks = result.scalars().all()
            for t in tasks:
                try:
                    _register_job(scheduler, t)
                except Exception as e:
                    logger.warning(f"定时任务 [{t.name}] 注册失败: {e}")
            logger.info(f"已加载 {len(tasks)} 个定时任务")
    except Exception as e:
        logger.warning(f"加载定时任务失败: {e}")


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
app.include_router(scripts_router)
app.include_router(routes_router)
app.include_router(reception_router)
app.include_router(tasks_router)
app.include_router(notify_router)
app.include_router(logs_router)
app.include_router(settings_router)
app.include_router(flows_router)


@app.get("/health")
async def health():
    return {"status": "ok", "service": "showroom-control"}


@app.get("/")
async def root():
    return {"msg": "展厅智控系统运行中", "version": "1.0.0"}
