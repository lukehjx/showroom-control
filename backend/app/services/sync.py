"""
中控云平台数据同步服务
"""
import aiohttp
import logging
import time
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, delete
from ..config import settings
from ..models import (
    CloudSpecial, CloudArea, CloudTerminal, CloudResource,
    CloudCommand, SyncLog, CurrentSpecial
)

logger = logging.getLogger(__name__)

BASE_URL = settings.ZHONGKONG_BASE_URL
HALL_ID = settings.ZHONGKONG_HALL_ID

_token_cache = {"token": None, "expires": 0}


async def get_token() -> str:
    """获取并缓存认证token"""
    if _token_cache["token"] and time.time() < _token_cache["expires"]:
        return _token_cache["token"]
    async with aiohttp.ClientSession() as s:
        resp = await s.post(
            f"{BASE_URL}/pc/authority/api/v1/login",
            data={"account": settings.ZHONGKONG_ACCOUNT, "password": settings.ZHONGKONG_PASSWORD}
        )
        data = await resp.json()
        token = data["data"]["token"]
        _token_cache["token"] = token
        _token_cache["expires"] = time.time() + 3600 * 6  # 6小时
        return token


async def api_get(path: str) -> dict:
    token = await get_token()
    async with aiohttp.ClientSession() as s:
        resp = await s.get(
            f"{BASE_URL}{path}",
            headers={"X-token": token}
        )
        return await resp.json()


def now_ms():
    return int(time.time() * 1000)


async def sync_specials(db: AsyncSession) -> int:
    data = await api_get(f"/pc/exhibition/api/v1/hall/{HALL_ID}/specialExhibitions")
    items = data.get("data", []) or []
    await db.execute(delete(CloudSpecial))
    for item in items:
        db.add(CloudSpecial(
            id=item["id"],
            name=item.get("specialExhibitionName", ""),
            description=item.get("specialExhibitionDescription", ""),
            hall_id=HALL_ID,
            state=item.get("state", "1"),
        ))
    await db.commit()
    return len(items)


async def sync_areas(db: AsyncSession) -> int:
    data = await api_get(f"/pc/exhibition/api/v1/hall/{HALL_ID}/areas")
    items = data.get("data", []) or []
    await db.execute(delete(CloudArea))
    for item in items:
        db.add(CloudArea(
            id=item["id"],
            name=item.get("exhibitionAreaName", ""),
            description=item.get("exhibitionAreaDescription", ""),
            hall_id=HALL_ID,
            sort=item.get("sort", 0),
        ))
    await db.commit()
    return len(items)


async def sync_terminals_and_resources(db: AsyncSession) -> int:
    """同步主机（含资源）"""
    # 先拿专场列表
    specials_result = await db.execute(select(CloudSpecial))
    specials = specials_result.scalars().all()
    if not specials:
        return 0

    await db.execute(delete(CloudTerminal))
    await db.execute(delete(CloudResource))
    total = 0

    for special in specials[:3]:  # 只同步前3个专场避免太慢
        data = await api_get(f"/pc/exhibition/api/v1/halls/{HALL_ID}/specialExhibitions/{special.id}")
        areas = (data.get("data") or {}).get("exhibitionAreaList", [])
        for area in areas:
            for terminal_data in area.get("exhibitionAreaTerminalList", []):
                t = terminal_data
                terminal = CloudTerminal(
                    id=t["id"],
                    name=t.get("hostName", ""),
                    host_ip=t.get("hostIp", ""),
                    host_port=str(t.get("hostPort", "8888")),
                    host_protocol=t.get("hostProtocol", "tcp"),
                    area_id=t.get("exhibitionAreaId"),
                    hall_id=HALL_ID,
                    sort=t.get("sort", 0),
                )
                db.add(terminal)
                total += 1

    await db.commit()
    return total


async def sync_commands(db: AsyncSession) -> int:
    """同步组策略命令"""
    data = await api_get(f"/pc/exhibition/api/v1/group-command/")
    items = data.get("data", []) or []
    await db.execute(delete(CloudCommand))
    for item in items:
        db.add(CloudCommand(
            id=item["id"],
            name=item.get("wholeOrderName", ""),
            group_name="组策略",
            protocol="tcp",
            target_ip=settings.ZHONGKONG_TCP_HOST,
            target_port=settings.ZHONGKONG_TCP_PORT,
            command_str=item.get("wholeOrderMsg", ""),
            hall_id=HALL_ID,
        ))
    await db.commit()
    return len(items)


async def sync_all(db: AsyncSession) -> dict:
    """全量同步"""
    results = {}
    for name, fn in [
        ("specials", sync_specials),
        ("areas", sync_areas),
        ("terminals", sync_terminals_and_resources),
        ("commands", sync_commands),
    ]:
        try:
            count = await fn(db)
            results[name] = count
            db.add(SyncLog(sync_type=name, records_count=count, status="success"))
            await db.commit()
        except Exception as e:
            logger.error(f"[Sync] {name} 失败: {e}")
            results[name] = f"失败: {e}"
            db.add(SyncLog(sync_type=name, records_count=0, status="failed", error=str(e)))
            await db.commit()
    return results
