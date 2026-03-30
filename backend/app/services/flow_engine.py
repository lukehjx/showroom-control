"""
流程执行引擎 - 顺序执行多步骤动作
"""
import asyncio
import logging
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

logger = logging.getLogger(__name__)


async def execute_flow(flow_id: int, db: AsyncSession):
    """通过flow_id执行流程"""
    from ..models import FlowRoute
    result = await db.execute(select(FlowRoute).where(FlowRoute.id == flow_id))
    flow = result.scalar_one_or_none()
    if not flow:
        logger.error(f"流程不存在: {flow_id}")
        return
    await execute_flow_steps(flow.steps_json or [])


async def execute_flow_steps(steps: list):
    """直接执行步骤列表"""
    from .commands import send_group_command
    from .robot import RobotAction
    from .wecom_bot import send_notify
    from ..config import settings

    robot = RobotAction(settings.ROBOT_SN)
    logger.info(f"[Flow] 开始执行，共 {len(steps)} 步")

    for i, step in enumerate(steps):
        t = step.get("type") or step.get("action_type", "")
        cfg = step.get("config") or step.get("params") or {}
        wait = step.get("wait_done", True)
        logger.info(f"[Flow] 步骤 {i+1}/{len(steps)}: {t} {cfg}")

        try:
            if t == "navigate":
                await robot.navigate(cfg.get("poi", ""), wait=wait)
            elif t == "speak":
                await robot.speak(cfg.get("text", ""), wait=wait)
            elif t == "delay":
                await asyncio.sleep(int(cfg.get("seconds", 3)))
            elif t == "device_command":
                cmd = cfg.get("command", "")
                if cmd:
                    await send_group_command(cmd)
            elif t == "wecom_notify":
                text = cfg.get("text", "")
                chat_id = cfg.get("chat_id", settings.WECOM_CHAT_ID)
                if text:
                    await send_notify(chat_id, text)
            elif t == "switch_special":
                special_id = cfg.get("special_id")
                if special_id:
                    await send_group_command(f"special_{special_id}")
            elif t == "wait_input":
                await asyncio.sleep(int(cfg.get("timeout", 10)))
        except Exception as e:
            logger.error(f"[Flow] 步骤 {i+1} 失败: {e}")

    logger.info(f"[Flow] 执行完毕")


async def execute_tour_route(route_id: int):
    """执行导览路线（按站点顺序导航+播报）"""
    from ..database import AsyncSessionLocal
    from ..models import TourRoute
    from ..services.robot import RobotAction
    from ..config import settings

    async with AsyncSessionLocal() as db:
        result = await db.execute(select(TourRoute).where(TourRoute.id == route_id))
        route = result.scalar_one_or_none()
        if not route:
            return

        robot = RobotAction(settings.ROBOT_SN)
        steps = route.steps or []

        logger.info(f"[Tour] 开始导览: {route.name}，{len(steps)} 站")
        for i, step in enumerate(steps):
            poi = step.get("poi")
            speak_text = step.get("speak_text")
            dwell = int(step.get("dwell_seconds", 30))

            if poi:
                logger.info(f"[Tour] 导航到 {poi}")
                await robot.navigate(poi, wait=True)

            if speak_text:
                await robot.speak(speak_text, wait=True)

            if dwell > 0:
                await asyncio.sleep(dwell)


async def execute_reception_preset(preset_id: int):
    """执行接待套餐"""
    from ..database import AsyncSessionLocal
    from ..models import ReceptionPreset
    from ..services.robot import RobotAction
    from ..services.commands import send_group_command
    from ..services.wecom_bot import send_notify
    from ..config import settings

    async with AsyncSessionLocal() as db:
        result = await db.execute(select(ReceptionPreset).where(ReceptionPreset.id == preset_id))
        preset = result.scalar_one_or_none()
        if not preset:
            return

        robot = RobotAction(settings.ROBOT_SN)
        steps = preset.steps or []

        logger.info(f"[Reception] 执行套餐: {preset.name}")
        for step in steps:
            t = step.get("type")
            val = step.get("value", "")
            wait = step.get("wait", True)

            if t == "navigate" and val:
                await robot.navigate(val, wait=wait)
            elif t == "speak" and val:
                await robot.speak(val, wait=wait)
            elif t == "wait":
                await asyncio.sleep(int(step.get("delay", 3)))
            elif t == "command" and val:
                await send_group_command(val)
            elif t == "notify" and val:
                await send_notify(settings.WECOM_CHAT_ID, val)
