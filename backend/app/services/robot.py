"""
机器人WebSocket连接管理与动作控制
"""
import asyncio
import json
import logging
from typing import Optional
from fastapi import WebSocket

logger = logging.getLogger(__name__)

# ─── 连接池 ──────────────────────────────────────────────────
class RobotConnectionManager:
    def __init__(self):
        self._connections: dict[str, WebSocket] = {}  # sn -> ws
        self._pending_callbacks: dict[str, asyncio.Future] = {}  # callback_id -> future

    async def connect(self, sn: str, ws: WebSocket):
        await ws.accept()
        self._connections[sn] = ws
        logger.info(f"[Robot] {sn} 已连接")

    async def disconnect(self, sn: str):
        self._connections.pop(sn, None)
        logger.info(f"[Robot] {sn} 已断开")

    def is_online(self, sn: str) -> bool:
        return sn in self._connections

    async def send(self, sn: str, msg: dict) -> bool:
        ws = self._connections.get(sn)
        if not ws:
            logger.warning(f"[Robot] {sn} 不在线，指令丢弃: {msg}")
            return False
        try:
            await ws.send_json(msg)
            return True
        except Exception as e:
            logger.error(f"[Robot] 发送失败: {e}")
            await self.disconnect(sn)
            return False

    async def send_and_wait(self, sn: str, msg: dict, timeout: int = 30) -> Optional[dict]:
        """发送并等待回调"""
        callback_id = msg.get("callback_id") or f"cb_{asyncio.get_event_loop().time()}"
        msg["callback_id"] = callback_id
        fut = asyncio.get_event_loop().create_future()
        self._pending_callbacks[callback_id] = fut
        try:
            sent = await self.send(sn, msg)
            if not sent:
                return None
            return await asyncio.wait_for(fut, timeout=timeout)
        except asyncio.TimeoutError:
            logger.warning(f"[Robot] 等待回调超时: {callback_id}")
            return None
        finally:
            self._pending_callbacks.pop(callback_id, None)

    def resolve_callback(self, callback_id: str, data: dict):
        fut = self._pending_callbacks.get(callback_id)
        if fut and not fut.done():
            fut.set_result(data)

    async def broadcast(self, msg: dict):
        for sn in list(self._connections.keys()):
            await self.send(sn, msg)


robot_mgr = RobotConnectionManager()


# ─── 动作封装 ────────────────────────────────────────────────
class RobotAction:
    def __init__(self, sn: str):
        self.sn = sn

    async def navigate(self, poi: str, wait_arrival: bool = True) -> dict:
        """导航到POI点位"""
        msg = {
            "action": "navigate",
            "poi": poi,
            "wait_arrival": wait_arrival,
        }
        if wait_arrival:
            result = await robot_mgr.send_and_wait(self.sn, msg, timeout=60)
            return result or {"status": "timeout"}
        else:
            await robot_mgr.send(self.sn, msg)
            return {"status": "sent"}

    async def speak(self, text: str, wait_done: bool = True) -> dict:
        """TTS播报"""
        msg = {
            "action": "speak",
            "text": text,
            "wait_done": wait_done,
        }
        if wait_done:
            result = await robot_mgr.send_and_wait(self.sn, msg, timeout=120)
            return result or {"status": "timeout"}
        else:
            await robot_mgr.send(self.sn, msg)
            return {"status": "sent"}

    async def stop(self) -> dict:
        await robot_mgr.send(self.sn, {"action": "stop"})
        return {"status": "sent"}

    async def go_charge(self) -> dict:
        await robot_mgr.send(self.sn, {"action": "go_charge"})
        return {"status": "sent"}

    async def go_entry(self, entry_poi: str) -> dict:
        return await self.navigate(entry_poi, wait_arrival=False)

    async def get_poi_list(self) -> list:
        result = await robot_mgr.send_and_wait(self.sn, {"action": "get_poi_list"}, timeout=10)
        return (result or {}).get("poi_list", [])

    async def set_free_wake(self, duration_sec: int):
        """开启免唤醒词模式"""
        await robot_mgr.send(self.sn, {
            "action": "set_free_wake",
            "duration": duration_sec,
        })
