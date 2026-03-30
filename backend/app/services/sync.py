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
            f"{BASE_URL}/app/authority/api/v1/login",
            data={"account": settings.ZHONGKONG_ACCOUNT, "password": settings.ZHONGKONG_PASSWORD}
        )
        data = await resp.json()
        if not data.get("data") or not data["data"].get("token"):
            raise Exception(f"中控登录失败: {data.get('msg', '未知错误')} (code={data.get('code')})")
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
    data = await api_get(f"/app/exhibition/api/v1/halls/{HALL_ID}/specialExhibitions")
    items = data.get("data", []) or []
    await db.execute(delete(CloudSpecial))
    await db.commit()
    for item in items:
        db.add(CloudSpecial(
            id=item["id"],
            name=item.get("specialExhibitionName", ""),
            description=item.get("specialExhibitionDescription", ""),
            hall_id=HALL_ID,
            state=str(item.get("operationState") or item.get("state") or "1"),
        ))
    await db.commit()
    return len(items)


async def sync_areas(db: AsyncSession) -> int:
    # 展区通过专场详情获取
    specials_result = await db.execute(select(CloudSpecial))
    specials = specials_result.scalars().all()
    if not specials:
        return 0
    await db.execute(delete(CloudArea))
    await db.commit()
    area_ids = set()
    total = 0
    for special in specials[:3]:
        data = await api_get(f"/app/exhibition/api/v1/halls/{HALL_ID}/specialExhibitions/{special.id}")
        areas = (data.get("data") or {}).get("exhibitionAreaList", [])
        for area in areas:
            if area["id"] not in area_ids:
                area_ids.add(area["id"])
                db.add(CloudArea(
                    id=area["id"],
                    name=area.get("exhibitionAreaName", ""),
                    description=area.get("exhibitionAreaDescription", ""),
                    hall_id=HALL_ID,
                    sort=area.get("sort", 0),
                ))
                total += 1
    await db.commit()
    return total


async def sync_terminals_and_resources(db: AsyncSession) -> int:
    """同步主机（含资源）"""
    # 先拿专场列表
    specials_result = await db.execute(select(CloudSpecial))
    specials = specials_result.scalars().all()
    if not specials:
        return 0

    # 先清理，使用独立事务
    await db.execute(delete(CloudTerminal))
    await db.execute(delete(CloudResource))
    await db.commit()

    total = 0
    seen_ids = set()

    for special in specials[:3]:  # 只同步前3个专场避免太慢
        data = await api_get(f"/app/exhibition/api/v1/halls/{HALL_ID}/specialExhibitions/{special.id}")
        areas = (data.get("data") or {}).get("exhibitionAreaList", [])
        for area in areas:
            for t in area.get("exhibitionAreaTerminalList", []):
                tid = t["id"]
                if tid in seen_ids:
                    continue
                seen_ids.add(tid)
                terminal = CloudTerminal(
                    id=tid,
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
    data = await api_get(f"/app/exhibition/api/v1/group-command/")
    items = data.get("data", []) or []
    await db.execute(delete(CloudCommand))
    await db.commit()
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
