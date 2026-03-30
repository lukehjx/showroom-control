"""
中控云平台数据直读接口
提供前端直接查询中控数据（专场列表、展项列表、命令列表等）
"""
from fastapi import APIRouter, Depends, Query
from typing import Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from ..database import get_db
from ..models import CloudSpecial, CloudTerminal, CloudCommand, CurrentSpecial
from ..services.sync import api_get, get_token
from ..config import settings

router = APIRouter(prefix="/api/zhongkong", tags=["zhongkong"])

HALL_ID = settings.ZHONGKONG_HALL_ID


@router.get("/specials")
async def list_specials(db: AsyncSession = Depends(get_db)):
    """专场列表（从本地数据库）"""
    result = await db.execute(select(CloudSpecial))
    items = result.scalars().all()
    return {"code": 200, "data": [
        {"id": s.id, "name": s.name, "description": s.description, "state": s.state}
        for s in items
    ]}


@router.post("/specials/{special_id}/switch")
async def switch_special(special_id: int):
    """切换当前专场（通知中控）"""
    try:
        # 中控切换专场接口
        token = await get_token()
        import aiohttp
        async with aiohttp.ClientSession() as s:
            # 尝试多种方式
            resp = await s.get(
                f"{settings.ZHONGKONG_BASE_URL}/app/special/api/v1/exhibitions/change/{special_id}",
                headers={"X-token": token}
            )
            data = await resp.json()
            if data.get("code") == 200:
                return {"code": 200, "msg": f"已切换到专场 {special_id}"}
            return {"code": 200, "data": data, "msg": "切换命令已发送"}
    except Exception as e:
        return {"code": 500, "msg": str(e)}


@router.get("/specials/{special_id}/terminals")
async def get_special_terminals(special_id: int):
    """获取专场下的终端列表"""
    try:
        data = await api_get(f"/app/special/api/v1/exhibitions/{special_id}/forControl")
        result = data.get("data") or {}
        terminals = result.get("exhibitionHallTerminalList", [])
        return {"code": 200, "data": [
            {
                "id": t.get("id"),
                "name": t.get("hostName", ""),
                "host_ip": t.get("hostIp", ""),
                "host_port": t.get("hostPort", 8888),
            }
            for t in terminals
        ]}
    except Exception as e:
        return {"code": 500, "msg": str(e)}


@router.get("/specials/{special_id}/terminals/{terminal_id}/exhibits")
async def get_exhibits(special_id: int, terminal_id: int):
    """获取专场+终端下的展项列表（含讲解词、缩略图）"""
    try:
        data = await api_get(
            f"/app/special/api/v1/exhibitions/{special_id}/terminals/{terminal_id}/exhibits"
        )
        items = data.get("data", []) or []
        result = []
        for item in items:
            res = item.get("resourceExhibitDo") or {}
            result.append({
                "id": item["id"],
                "exhibit_id": item.get("exhibitId"),
                "sort": item.get("sort", 0),
                "title": res.get("exhibitTitle") or res.get("programName", ""),
                "description": res.get("exhibitDescription", ""),
                "commentary": res.get("commentary") or res.get("allCommentary", ""),
                "thumbnail_url": res.get("minioThumbnailUrl") or res.get("thumbnailUrl", ""),
                "file_url": res.get("minioUrl") or res.get("fileUrl", ""),
                "category": res.get("categoryDicName", ""),
                "ai_explain": res.get("aiExplain") == "1",
            })
        return {"code": 200, "data": result}
    except Exception as e:
        return {"code": 500, "msg": str(e)}


@router.post("/terminals/{terminal_id}/play/{exhibit_id}")
async def play_exhibit(terminal_id: int, exhibit_id: int, special_id: int = Query(...)):
    """播放指定展项到终端"""
    try:
        data = await api_get(
            f"/app/command/api/v1/terminals/{terminal_id}/specialExhibitions/{special_id}/exhibits/{exhibit_id}"
        )
        return {"code": 200, "data": data.get("data"), "msg": "播放指令已发送"}
    except Exception as e:
        return {"code": 500, "msg": str(e)}


@router.get("/commands")
async def list_commands(db: AsyncSession = Depends(get_db)):
    """组策略命令列表（从本地数据库）"""
    result = await db.execute(select(CloudCommand))
    items = result.scalars().all()
    return {"code": 200, "data": [
        {
            "id": c.id,
            "name": c.name,
            "command_str": c.command_str,
            "protocol": c.protocol,
        }
        for c in items
    ]}


@router.post("/commands/{command_id}/execute")
async def execute_command(command_id: int, db: AsyncSession = Depends(get_db)):
    """执行组策略命令"""
    result = await db.execute(select(CloudCommand).where(CloudCommand.id == command_id))
    cmd = result.scalar_one_or_none()
    if not cmd:
        return {"code": 404, "msg": "命令不存在"}

    try:
        from ..services.commands import send_tcp_command
        await send_tcp_command(
            settings.ZHONGKONG_TCP_HOST,
            settings.ZHONGKONG_TCP_PORT,
            cmd.command_str
        )
        return {"code": 200, "msg": f"命令 [{cmd.name}] 已发送: {cmd.command_str}"}
    except Exception as e:
        return {"code": 500, "msg": str(e)}


@router.get("/terminals")
async def list_terminals(db: AsyncSession = Depends(get_db)):
    """主机设备列表"""
    result = await db.execute(select(CloudTerminal).order_by(CloudTerminal.sort))
    items = result.scalars().all()
    return {"code": 200, "data": [
        {
            "id": t.id,
            "name": t.name,
            "host_ip": t.host_ip,
            "host_port": t.host_port,
            "area_id": t.area_id,
            "online": t.online,
        }
        for t in items
    ]}


@router.get("/hall-status")
async def get_hall_status(db: AsyncSession = Depends(get_db)):
    """展厅整体状态（专场数/主机数/命令数/当前专场）"""
    from sqlalchemy import func
    specials_count = (await db.execute(select(func.count(CloudSpecial.id)))).scalar()
    terminals_count = (await db.execute(select(func.count(CloudTerminal.id)))).scalar()
    commands_count = (await db.execute(select(func.count(CloudCommand.id)))).scalar()
    current = (await db.execute(select(CurrentSpecial).limit(1))).scalar_one_or_none()
    return {"code": 200, "data": {
        "specials_count": specials_count,
        "terminals_count": terminals_count,
        "commands_count": commands_count,
        "current_special": {
            "id": current.special_id,
            "name": current.special_name
        } if current else None
    }}
