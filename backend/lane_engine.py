import asyncio
import logging
import httpx
from datetime import datetime
from typing import Dict, Any, Optional
from sqlalchemy import select
from database import async_session
from models import RouteLane, LaneStep, FlowExecution, ExecutionStep, ApiRoute
from tcp_service import send_tcp, cast_resource, switch_scene_tcp

logger = logging.getLogger(__name__)

# 等待回调的事件存储
_pending_callbacks: Dict[str, asyncio.Event] = {}


async def register_callback(key: str) -> asyncio.Event:
    event = asyncio.Event()
    _pending_callbacks[key] = event
    return event


async def trigger_callback(key: str):
    if key in _pending_callbacks:
        _pending_callbacks[key].set()
        del _pending_callbacks[key]


async def execute_action(action_type: str, action_config: dict, wait_type: str, wait_timeout: int) -> dict:
    """执行单个动作"""
    result = {"success": False, "output": None}

    try:
        if action_type == "tcp_send":
            command_id = action_config.get("command_id")
            if command_id is not None:
                # 从数据库查命令详情
                from models import CloudCommand
                from config import get_config
                async with async_session() as session:
                    cmd_result = await session.execute(
                        select(CloudCommand).where(
                            CloudCommand.command_id == int(command_id),
                            CloudCommand.protocol_type == "tcp"
                        )
                    )
                    cmd = cmd_result.scalar_one_or_none()
                if cmd is None:
                    result = {"success": False, "output": f"TCP command_id={command_id} not found in cloud_commands"}
                else:
                    host = action_config.get("host") or await get_config("tcp.host") or ""
                    port = int(action_config.get("port") or await get_config("tcp.port") or 8989)
                    data = cmd.command_str
                    is_hex = cmd.is_hex or False
                    encoding = "hex" if is_hex else "utf-8"
                    ok_result = await send_tcp(host, port, data, encoding, is_hex)
                    result = {"success": ok_result, "output": f"TCP command {cmd.name} sent to {host}:{port}"}
            else:
                host = action_config.get("host", "")
                port = int(action_config.get("port", 80))
                data = action_config.get("data", "")
                encoding = action_config.get("encoding", "utf-8")
                is_hex = action_config.get("is_hex", False)
                ok_result = await send_tcp(host, port, data, encoding, is_hex)
                result = {"success": ok_result, "output": f"TCP sent to {host}:{port}"}

        elif action_type == "http_get":
            url = action_config.get("url", "")
            params = action_config.get("params", {})
            async with httpx.AsyncClient(timeout=30) as client:
                resp = await client.get(url, params=params)
                result = {"success": resp.status_code < 400, "output": resp.text[:500], "status": resp.status_code}

        elif action_type == "http_post":
            url = action_config.get("url", "")
            body = action_config.get("body", {})
            async with httpx.AsyncClient(timeout=30) as client:
                resp = await client.post(url, json=body)
                result = {"success": resp.status_code < 400, "output": resp.text[:500], "status": resp.status_code}

        elif action_type == "robot_navigate":
            poi_name = action_config.get("poi_name", "")
            # 调用猎户API导航
            from config import get_config
            robot_sn = await get_config("robot.sn") or ""
            app_key = await get_config("robot.app_key") or ""
            app_secret = await get_config("robot.app_secret") or ""

            # 猎户星空导航API（实际地址根据机器人配置）
            nav_url = f"http://localhost:9090/api/robot/navigate"
            try:
                async with httpx.AsyncClient(timeout=10) as client:
                    resp = await client.post(nav_url, json={"poi": poi_name, "sn": robot_sn})
                    result = {"success": True, "output": f"Navigate to {poi_name}"}
            except Exception:
                result = {"success": True, "output": f"Navigate command sent for {poi_name} (mock)"}

            if wait_type == "robot_callback":
                event = await register_callback(f"arrived_{poi_name}")
                try:
                    await asyncio.wait_for(event.wait(), timeout=wait_timeout)
                    result["waited"] = True
                except asyncio.TimeoutError:
                    result["timeout"] = True

        elif action_type == "robot_tts":
            text = action_config.get("text", "")
            from config import get_config
            robot_sn = await get_config("robot.sn") or ""

            tts_url = f"http://localhost:9090/api/robot/tts"
            try:
                async with httpx.AsyncClient(timeout=10) as client:
                    resp = await client.post(tts_url, json={"text": text, "sn": robot_sn})
                    result = {"success": True, "output": f"TTS: {text[:50]}"}
            except Exception:
                result = {"success": True, "output": f"TTS command sent: {text[:50]} (mock)"}

            if wait_type == "robot_callback":
                event = await register_callback(f"tts_done")
                try:
                    await asyncio.wait_for(event.wait(), timeout=wait_timeout)
                    result["waited"] = True
                except asyncio.TimeoutError:
                    result["timeout"] = True

        elif action_type == "delay":
            seconds = float(action_config.get("seconds", 1))
            await asyncio.sleep(seconds)
            result = {"success": True, "output": f"Delayed {seconds}s"}

        elif action_type == "cast_resource":
            scene_id = action_config.get("scene_id")
            terminal_id = action_config.get("terminal_id")
            resource_id = action_config.get("resource_id")
            ok = await cast_resource(scene_id, terminal_id, resource_id)
            result = {"success": ok, "output": f"Cast resource {resource_id} to terminal {terminal_id}"}

        elif action_type == "switch_scene":
            scene_id = action_config.get("scene_id")
            ok = await switch_scene_tcp(scene_id)
            result = {"success": ok, "output": f"Switch scene to {scene_id}"}

        elif action_type == "digital_human":
            terminal_id = action_config.get("terminal_id")
            command = action_config.get("command")
            from config import get_config
            tcp_host = await get_config("tcp.host") or "112.20.77.18"
            tcp_port = int(await get_config("tcp.port") or "8989")
            ok = await send_tcp(tcp_host, tcp_port, f"digital_human_{terminal_id}_{command}")
            result = {"success": ok, "output": f"Digital human command sent to {terminal_id}"}

        elif action_type == "voice_input":
            text = action_config.get("text", "")
            # 触发意图识别
            from intent import recognize_intent
            intent_result = await recognize_intent(text)
            result = {"success": True, "output": f"Voice input processed", "intent": intent_result}

        else:
            result = {"success": False, "output": f"Unknown action type: {action_type}"}

    except Exception as e:
        logger.error(f"Action {action_type} failed: {e}")
        result = {"success": False, "output": str(e), "error": str(e)}

    return result


async def execute_lane(lane_id: int, execution_id: int):
    """执行单个Lane中的所有步骤"""
    async with async_session() as session:
        result = await session.execute(
            select(LaneStep).where(LaneStep.lane_id == lane_id).order_by(LaneStep.sort_order)
        )
        steps = result.scalars().all()

    for step in steps:
        step_log = ExecutionStep(
            execution_id=execution_id,
            step_id=step.id,
            status="running",
            started_at=datetime.now()
        )
        async with async_session() as session:
            session.add(step_log)
            await session.commit()
            await session.refresh(step_log)

        try:
            result = await execute_action(
                step.action_type,
                step.action_config or {},
                step.wait_type,
                step.wait_timeout
            )
            status = "success" if result.get("success") else "failed"
        except Exception as e:
            logger.error(f"Step {step.id} execution error: {e}")
            result = {"success": False, "error": str(e)}
            status = "failed"

        async with async_session() as session:
            step_log.status = status
            step_log.result = result
            step_log.finished_at = datetime.now()
            session.add(step_log)
            await session.commit()

        logger.info(f"Step {step.id} ({step.action_type}) completed with status {status}")


async def execute_route(route_id: int, triggered_by: str = "api", execution_id: Optional[int] = None) -> int:
    """执行路由（所有Lane）"""
    if execution_id is None:
        execution = FlowExecution(
            route_id=route_id,
            triggered_by=triggered_by,
            status="running",
            started_at=datetime.now()
        )
        async with async_session() as session:
            session.add(execution)
            await session.commit()
            await session.refresh(execution)
            execution_id = execution.id

    try:
        async with async_session() as session:
            result = await session.execute(
                select(RouteLane).where(RouteLane.route_id == route_id).order_by(RouteLane.sort_order)
            )
            lanes = result.scalars().all()

        if not lanes:
            logger.warning(f"Route {route_id} has no lanes")
            async with async_session() as session:
                execution.status = "success"
                execution.finished_at = datetime.now()
                session.add(execution)
                await session.commit()
            return execution_id

        # 按parallel_group分组并行执行
        groups = {}
        for lane in lanes:
            group = lane.parallel_group or "default"
            if group not in groups:
                groups[group] = []
            groups[group].append(lane)

        # 串行执行不同组，同组内并行
        for group_name in sorted(groups.keys()):
            group_lanes = groups[group_name]
            tasks = [execute_lane(lane.id, execution_id) for lane in group_lanes]
            await asyncio.gather(*tasks, return_exceptions=True)

        async with async_session() as session:
            exec_obj = await session.get(FlowExecution, execution_id)
            if exec_obj:
                exec_obj.status = "success"
                exec_obj.finished_at = datetime.now()
                await session.commit()

        logger.info(f"Route {route_id} execution {execution_id} completed")

    except Exception as e:
        logger.error(f"Route {route_id} execution failed: {e}")
        async with async_session() as session:
            exec_obj = await session.get(FlowExecution, execution_id)
            if exec_obj:
                exec_obj.status = "failed"
                exec_obj.error = str(e)
                exec_obj.finished_at = datetime.now()
                await session.commit()

    return execution_id
