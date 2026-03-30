import asyncio
import logging
import time
from datetime import datetime
from sqlalchemy import select, delete
from database import async_session
from models import CloudTerminal, DeviceStatus

logger = logging.getLogger(__name__)

_monitor_task = None


async def check_device(ip: str, port: int, timeout: float = 3.0) -> tuple[bool, int]:
    """TCP connect探测，返回(is_online, response_ms)"""
    if not ip:
        return False, 0
    start = time.monotonic()
    try:
        reader, writer = await asyncio.wait_for(
            asyncio.open_connection(ip, port or 80),
            timeout=timeout
        )
        elapsed = int((time.monotonic() - start) * 1000)
        writer.close()
        try:
            await writer.wait_closed()
        except Exception:
            pass
        return True, elapsed
    except Exception:
        elapsed = int((time.monotonic() - start) * 1000)
        return False, elapsed


async def run_device_check():
    """检测所有终端设备状态"""
    try:
        async with async_session() as session:
            result = await session.execute(select(CloudTerminal))
            terminals = result.scalars().all()

        if not terminals:
            logger.debug("No terminals to check")
            return

        for terminal in terminals:
            if not terminal.ip:
                continue
            port = terminal.port or 80
            is_online, response_ms = await check_device(terminal.ip, port)

            async with async_session() as session:
                # 查找已有记录
                existing = await session.execute(
                    select(DeviceStatus).where(DeviceStatus.terminal_id == terminal.terminal_id).limit(1)
                )
                status = existing.scalar_one_or_none()

                if status:
                    status.is_online = is_online
                    status.last_checked_at = datetime.now()
                    status.response_ms = response_ms
                    status.terminal_name = terminal.name
                    status.ip = terminal.ip
                    status.port = port
                else:
                    status = DeviceStatus(
                        terminal_id=terminal.terminal_id,
                        terminal_name=terminal.name,
                        ip=terminal.ip,
                        port=port,
                        is_online=is_online,
                        last_checked_at=datetime.now(),
                        response_ms=response_ms
                    )
                    session.add(status)
                await session.commit()

            logger.debug(f"Device {terminal.name} ({terminal.ip}:{port}) - {'online' if is_online else 'offline'} {response_ms}ms")

    except Exception as e:
        logger.error(f"Device check error: {e}")


async def monitor_loop():
    """每60秒执行一次设备检测"""
    logger.info("Device monitor started")
    while True:
        try:
            await run_device_check()
        except Exception as e:
            logger.error(f"Monitor loop error: {e}")
        await asyncio.sleep(60)


def start_monitor():
    global _monitor_task
    loop = asyncio.get_event_loop()
    _monitor_task = loop.create_task(monitor_loop())
    logger.info("Device monitor task created")
