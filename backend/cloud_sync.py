"""
中控云平台数据同步

数据结构（已通过 Swagger + 实测确认）：
- 登录: POST /app/authority/api/v1/login?account=ZhanGuan&password=sidex@123
  Basic Auth: admin/admin123
  nonce 机制：每次请求必须重新登录，并用同一 httpx.AsyncClient 实例（保持 SESSION cookie）
  
- 专场列表: GET /pc/special/api/v1/exhibitions/querySpecialList
  params: exhibitionHallId=5, pageNum=1, pageSize=100
  返回: [{id, specialExhibitionName, ...}, ...]

- 专场终端+资源: GET /app/special/api/v1/exhibitions/{specialId}/forControl
  返回: {exhibitionHallTerminalList: [{
    id, hostName, hostIp, hostPort, specialExhibitionId, exhibitionHallId,
    exhibitionResourceList: [{
      id, fileName, resourceName, exhibitionHallTerminalId, specialExhibitionId, ...
    }]
  }]}

- HTTP命令分组: GET /app/command/api/v1/groups/
  返回: [{groupName, commandDetailVOList: [{id, btnName, command, url, ...}]}]

- TCP组策略命令树: GET /pc/resource/api/v1/group/command/tree
  返回树状3层: [{exhibitionAreaId, level:1, title, children:[
    {level:2, title, children:[
      {level:3, commandId, commandMsg, command, isHex, isOnOrOff, title}
    ]}
  ]}]
  isHex="1" 表示HEX发送，isHex="0" 表示字符串发送
"""
import logging
import httpx
from datetime import datetime
from sqlalchemy import delete, select
from database import async_session
from models import CloudTerminal, CloudResource, CloudCommand, CloudScene, SyncLog
from config import get_config

logger = logging.getLogger(__name__)


async def _fresh_client() -> httpx.AsyncClient:
    """创建已登录的 httpx 客户端（保持 SESSION cookie + Bearer token）"""
    api_url = await get_config("cloud.api_url") or "http://112.20.77.18:7772"
    basic_user = await get_config("cloud.basic_auth_user") or "admin"
    basic_pass = await get_config("cloud.basic_auth_pass") or "admin123"
    account = await get_config("cloud.account") or "ZhanGuan"
    password = await get_config("cloud.password") or "sidex@123"

    client = httpx.AsyncClient(
        auth=(basic_user, basic_pass),
        timeout=30,
        verify=False,
        follow_redirects=True
    )
    r = await client.post(
        f"{api_url}/app/authority/api/v1/login",
        params={"account": account, "password": password}
    )
    data = r.json()
    token = data["data"]["token"]
    client.headers.update({"Authorization": f"Bearer {token}"})
    return client


async def _fetch_scenes_list(api_url: str) -> list:
    """获取专场列表（每次独立登录）"""
    client = await _fresh_client()
    try:
        r = await client.get(
            f"{api_url}/pc/special/api/v1/exhibitions/querySpecialList",
            params={"exhibitionHallId": 5, "pageNum": 1, "pageSize": 100}
        )
        d = r.json()
        if d.get("code") == 200:
            return d.get("data", [])
        logger.warning(f"Fetch scenes: code={d.get('code')} msg={d.get('msg')}")
        return []
    finally:
        await client.aclose()


async def _fetch_scene_detail(api_url: str, scene_id: int) -> dict:
    """获取单个专场的 forControl 数据（包含终端+资源）"""
    client = await _fresh_client()
    try:
        r = await client.get(f"{api_url}/app/special/api/v1/exhibitions/{scene_id}/forControl")
        d = r.json()
        if d.get("code") == 200:
            return d.get("data", {})
        logger.warning(f"Fetch scene {scene_id} forControl: code={d.get('code')} msg={d.get('msg')}")
        return {}
    finally:
        await client.aclose()


async def _fetch_http_commands(api_url: str) -> list:
    """获取HTTP命令分组列表"""
    client = await _fresh_client()
    try:
        r = await client.get(f"{api_url}/app/command/api/v1/groups/")
        d = r.json()
        if d.get("code") == 200:
            return d.get("data", [])
        logger.warning(f"Fetch HTTP commands: code={d.get('code')} msg={d.get('msg')}")
        return []
    finally:
        await client.aclose()


async def _fetch_tcp_command_tree(api_url: str) -> list:
    """获取TCP组策略命令树（需要 exhibitionHallId 参数）"""
    client = await _fresh_client()
    try:
        exhibition_id = int(await get_config("cloud.exhibition_id") or "5")
        r = await client.get(
            f"{api_url}/pc/resource/api/v1/group/command/tree",
            params={"exhibitionHallId": exhibition_id}
        )
        d = r.json()
        if d.get("code") == 200:
            return d.get("data", [])
        logger.warning(f"Fetch TCP command tree: code={d.get('code')} msg={d.get('msg')}")
        return []
    finally:
        await client.aclose()


def _flatten_tcp_commands(tree: list) -> list:
    """将TCP命令树展平为命令列表（level=3节点）"""
    commands = []
    for area in tree:
        if area.get("level") != 1:
            continue
        area_id = area.get("exhibitionAreaId")
        area_title = area.get("title", "")
        for device in area.get("children", []):
            if device.get("level") != 2:
                continue
            device_title = device.get("title", "")
            for cmd in device.get("children", []):
                if cmd.get("level") != 3:
                    continue
                is_hex = cmd.get("isHex") == "1"
                commands.append({
                    "command_id": cmd.get("commandId"),
                    "name": cmd.get("title", ""),
                    "command_str": cmd.get("command", ""),
                    "protocol_type": "tcp",
                    "is_hex": is_hex,
                    "group_name": f"{area_title} / {device_title}",
                    "area_id": area_id,
                    "area_name": area_title,
                    "encoding": "hex" if is_hex else "utf-8",
                    "command_msg": cmd.get("commandMsg", ""),
                    "_raw": cmd,
                })
    return commands


async def sync_scenes() -> dict:
    """同步专场数据"""
    api_url = await get_config("cloud.api_url") or "http://112.20.77.18:7772"
    sync_log = SyncLog(sync_type="scenes", status="running", created_at=datetime.now())
    async with async_session() as session:
        session.add(sync_log)
        await session.commit()
        await session.refresh(sync_log)

    try:
        scenes_list = await _fetch_scenes_list(api_url)
        logger.info(f"Syncing {len(scenes_list)} scenes")

        exhibition_id = int(await get_config("cloud.exhibition_id") or "5")
        async with async_session() as session:
            await session.execute(delete(CloudScene))
            for s in scenes_list:
                session.add(CloudScene(
                    scene_id=s.get("id"),
                    name=s.get("specialExhibitionName") or s.get("name", ""),
                    exhibition_id=exhibition_id,
                    raw_data=s,
                    synced_at=datetime.now()
                ))
            sync_log.status = "success"
            sync_log.records_count = len(scenes_list)
            session.add(sync_log)
            await session.commit()

        return {"type": "scenes", "count": len(scenes_list)}

    except Exception as e:
        logger.error(f"Sync scenes failed: {e}", exc_info=True)
        async with async_session() as session:
            sync_log.status = "failed"
            sync_log.error = str(e)
            session.add(sync_log)
            await session.commit()
        return {"type": "scenes", "count": 0, "error": str(e)}


async def sync_terminals() -> dict:
    """
    同步终端数据：遍历所有专场，收集唯一终端
    终端字段: id, hostName, hostIp, hostPort, specialExhibitionId, exhibitionHallId
    """
    api_url = await get_config("cloud.api_url") or "http://112.20.77.18:7772"
    sync_log = SyncLog(sync_type="terminals", status="running", created_at=datetime.now())
    async with async_session() as session:
        session.add(sync_log)
        await session.commit()
        await session.refresh(sync_log)

    try:
        scenes_list = await _fetch_scenes_list(api_url)
        if not scenes_list:
            raise Exception("No scenes found, cannot sync terminals")

        # 去重：按 terminal id 去重
        unique_terminals: dict[int, dict] = {}
        exhibition_id = int(await get_config("cloud.exhibition_id") or "5")

        for scene in scenes_list:
            sid = scene["id"]
            detail = await _fetch_scene_detail(api_url, sid)
            terminals = detail.get("exhibitionHallTerminalList", [])
            for t in terminals:
                tid = t.get("id")
                if tid and tid not in unique_terminals:
                    unique_terminals[tid] = t
                    logger.debug(f"  Terminal {tid}: {t.get('hostName')} @ {t.get('hostIp')}")

        logger.info(f"Collected {len(unique_terminals)} unique terminals from {len(scenes_list)} scenes")

        async with async_session() as session:
            await session.execute(delete(CloudTerminal))
            for tid, t in unique_terminals.items():
                raw_port = t.get("hostPort")
                try:
                    port_int = int(raw_port) if raw_port is not None else None
                except (ValueError, TypeError):
                    port_int = None
                session.add(CloudTerminal(
                    terminal_id=tid,
                    special_terminal_id=t.get("specialExhibitionId"),
                    name=str(t.get("hostName") or ""),
                    ip=str(t.get("hostIp") or ""),
                    port=port_int,
                    exhibition_id=exhibition_id,
                    raw_data=t,
                    synced_at=datetime.now()
                ))
            sync_log.status = "success"
            sync_log.records_count = len(unique_terminals)
            session.add(sync_log)
            await session.commit()

        return {"type": "terminals", "count": len(unique_terminals)}

    except Exception as e:
        logger.error(f"Sync terminals failed: {e}", exc_info=True)
        async with async_session() as session:
            sync_log.status = "failed"
            sync_log.error = str(e)
            session.add(sync_log)
            await session.commit()
        return {"type": "terminals", "count": 0, "error": str(e)}


async def sync_resources() -> dict:
    """
    同步资源数据：遍历所有专场，收集唯一资源
    资源字段: id, fileName, resourceName, exhibitionHallTerminalId(终端ID),
              specialExhibitionId, exhibitDescription, thumbnailUrl, sortOrder
    """
    api_url = await get_config("cloud.api_url") or "http://112.20.77.18:7772"
    sync_log = SyncLog(sync_type="resources", status="running", created_at=datetime.now())
    async with async_session() as session:
        session.add(sync_log)
        await session.commit()
        await session.refresh(sync_log)

    try:
        scenes_list = await _fetch_scenes_list(api_url)
        if not scenes_list:
            raise Exception("No scenes found, cannot sync resources")

        # 去重：按 resource id 去重
        unique_resources: dict[int, dict] = {}

        for scene in scenes_list:
            sid = scene["id"]
            detail = await _fetch_scene_detail(api_url, sid)
            terminals = detail.get("exhibitionHallTerminalList", [])
            for t in terminals:
                for res in t.get("exhibitionResourceList", []):
                    rid = res.get("id")
                    if rid and rid not in unique_resources:
                        # 附加终端信息到资源
                        enriched = dict(res)
                        enriched["_terminal_id"] = t.get("id")
                        enriched["_terminal_name"] = t.get("hostName", "")
                        enriched["_terminal_ip"] = t.get("hostIp", "")
                        enriched["_scene_id"] = sid
                        unique_resources[rid] = enriched

        logger.info(f"Collected {len(unique_resources)} unique resources from {len(scenes_list)} scenes")

        async with async_session() as session:
            await session.execute(delete(CloudResource))
            for rid, res in unique_resources.items():
                session.add(CloudResource(
                    resource_id=rid,
                    terminal_id=res.get("exhibitionHallTerminalId") or res.get("_terminal_id"),
                    exhibit_id=res.get("exhibitId"),
                    title=str(res.get("resourceName") or res.get("fileName") or ""),
                    description=str(res.get("exhibitDescription") or res.get("keywords") or ""),
                    sort=int(res.get("sortOrder") or 0),
                    file_name=str(res.get("fileName") or ""),
                    raw_data=res,
                    synced_at=datetime.now()
                ))
            sync_log.status = "success"
            sync_log.records_count = len(unique_resources)
            session.add(sync_log)
            await session.commit()

        return {"type": "resources", "count": len(unique_resources)}

    except Exception as e:
        logger.error(f"Sync resources failed: {e}", exc_info=True)
        async with async_session() as session:
            sync_log.status = "failed"
            sync_log.error = str(e)
            session.add(sync_log)
            await session.commit()
        return {"type": "resources", "count": 0, "error": str(e)}


async def sync_commands() -> dict:
    """
    同步命令数据：HTTP命令 + TCP组策略命令
    - HTTP: GET /app/command/api/v1/groups/
    - TCP:  GET /pc/resource/api/v1/group/command/tree
    """
    api_url = await get_config("cloud.api_url") or "http://112.20.77.18:7772"
    sync_log = SyncLog(sync_type="commands", status="running", created_at=datetime.now())
    async with async_session() as session:
        session.add(sync_log)
        await session.commit()
        await session.refresh(sync_log)

    try:
        # 步骤1: 同步 HTTP 命令
        http_groups = await _fetch_http_commands(api_url)
        http_commands = []
        for group in http_groups:
            group_name = group.get("groupName", "")
            for cmd in group.get("commandDetailVOList", group.get("commands", [])):
                http_commands.append({
                    "command_id": cmd.get("id"),
                    "name": str(cmd.get("btnName") or ""),
                    "command_str": str(cmd.get("command") or ""),
                    "url": str(cmd.get("url") or ""),
                    "protocol_type": "http",
                    "is_hex": False,
                    "group_name": group_name,
                    "encoding": "utf-8",
                    "_raw": cmd,
                })
        logger.info(f"Collected {len(http_commands)} HTTP commands from {len(http_groups)} groups")

        # 步骤2: 同步 TCP 命令
        tcp_tree = await _fetch_tcp_command_tree(api_url)
        tcp_commands = _flatten_tcp_commands(tcp_tree)
        logger.info(f"Collected {len(tcp_commands)} TCP commands from tree")

        all_commands = http_commands + tcp_commands
        logger.info(f"Total commands: {len(all_commands)} (HTTP:{len(http_commands)}, TCP:{len(tcp_commands)})")

        async with async_session() as session:
            await session.execute(delete(CloudCommand))
            for c in http_commands:
                session.add(CloudCommand(
                    command_id=c.get("command_id"),
                    name=c.get("name", ""),
                    command_type="http",
                    command_str=c.get("command_str", ""),
                    url=c.get("url", ""),
                    encoding="utf-8",
                    group_name=c.get("group_name", ""),
                    protocol_type="http",
                    is_hex=False,
                    raw_data=c.get("_raw", {}),
                    synced_at=datetime.now()
                ))
            for c in tcp_commands:
                session.add(CloudCommand(
                    command_id=c.get("command_id"),
                    name=c.get("name", ""),
                    command_type="tcp",
                    command_str=c.get("command_str", ""),
                    encoding=c.get("encoding", "utf-8"),
                    group_name=c.get("group_name", ""),
                    protocol_type="tcp",
                    is_hex=c.get("is_hex", False),
                    area_id=c.get("area_id"),
                    area_name=c.get("area_name", ""),
                    raw_data=c.get("_raw", {}),
                    synced_at=datetime.now()
                ))
            sync_log.status = "success"
            sync_log.records_count = len(all_commands)
            session.add(sync_log)
            await session.commit()

        return {
            "type": "commands",
            "count": len(all_commands),
            "http_count": len(http_commands),
            "tcp_count": len(tcp_commands),
        }

    except Exception as e:
        logger.error(f"Sync commands failed: {e}", exc_info=True)
        async with async_session() as session:
            sync_log.status = "failed"
            sync_log.error = str(e)
            session.add(sync_log)
            await session.commit()
        return {"type": "commands", "count": 0, "error": str(e)}


async def sync_all() -> dict:
    """全量同步：scenes → terminals → resources → commands"""
    results = {}
    # 先同步专场（其他同步会读专场列表）
    for sync_func, name in [
        (sync_scenes, "scenes"),
        (sync_terminals, "terminals"),
        (sync_resources, "resources"),
        (sync_commands, "commands"),
    ]:
        try:
            result = await sync_func()
            results[name] = result
            logger.info(f"Sync {name}: {result}")
        except Exception as e:
            logger.error(f"Sync {name} error: {e}")
            results[name] = {"type": name, "count": 0, "error": str(e)}
    return results
