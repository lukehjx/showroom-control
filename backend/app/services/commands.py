"""
设备指令发送服务：TCP / HTTP / UDP
"""
import asyncio
import aiohttp
import logging
import struct
from typing import Optional

logger = logging.getLogger(__name__)


async def send_tcp(host: str, port: int, data: str, is_hex: bool = False, timeout: int = 5) -> bool:
    """发送TCP指令"""
    try:
        reader, writer = await asyncio.wait_for(
            asyncio.open_connection(host, port), timeout=timeout
        )
        if is_hex:
            payload = bytes.fromhex(data.replace(" ", ""))
        else:
            payload = data.encode("utf-8")
        writer.write(payload)
        await writer.drain()
        writer.close()
        logger.info(f"[TCP] {host}:{port} → {data[:50]}")
        return True
    except Exception as e:
        logger.error(f"[TCP] {host}:{port} 发送失败: {e}")
        return False


async def send_http(url: str, method: str = "GET", body: Optional[dict] = None,
                    headers: Optional[dict] = None, timeout: int = 10) -> Optional[dict]:
    """发送HTTP指令"""
    try:
        async with aiohttp.ClientSession() as session:
            kwargs = {"headers": headers or {}, "timeout": aiohttp.ClientTimeout(total=timeout)}
            if method.upper() == "GET":
                resp = await session.get(url, **kwargs)
            elif method.upper() == "POST":
                resp = await session.post(url, json=body, **kwargs)
            else:
                resp = await session.request(method, url, json=body, **kwargs)
            data = await resp.json()
            logger.info(f"[HTTP] {method} {url} → {resp.status}")
            return data
    except Exception as e:
        logger.error(f"[HTTP] {url} 失败: {e}")
        return None


async def send_udp(host: str, port: int, data: str, is_hex: bool = False) -> bool:
    """发送UDP指令"""
    try:
        loop = asyncio.get_event_loop()
        transport, protocol = await loop.create_datagram_endpoint(
            asyncio.DatagramProtocol,
            remote_addr=(host, port)
        )
        if is_hex:
            payload = bytes.fromhex(data.replace(" ", ""))
        else:
            payload = data.encode("utf-8")
        transport.sendto(payload)
        transport.close()
        logger.info(f"[UDP] {host}:{port} → {data[:50]}")
        return True
    except Exception as e:
        logger.error(f"[UDP] {host}:{port} 发送失败: {e}")
        return False


async def play_resource_on_terminal(host_ip: str, special_id: int, resource_id: int) -> Optional[dict]:
    """
    播控命令：控制展项主机播放指定资源
    格式：GET http://{hostIp}:7789/action?targetType=2&command={specialId}_{resourceId}
    """
    url = f"http://{host_ip}:7789/action?targetType=2&command=2_{special_id}_{resource_id}"
    return await send_http(url)


async def get_terminal_play_info(host_ip: str) -> Optional[dict]:
    """查询展项主机当前播放状态"""
    url = f"http://{host_ip}:7789/info"
    return await send_http(url)


async def switch_scene_command(scene_command: str, tcp_host: str, tcp_port: int) -> bool:
    """场景切换TCP命令"""
    return await send_tcp(tcp_host, tcp_port, scene_command)


async def parse_and_send_command(command_str: str, protocol: str, target_ip: str,
                                  target_port: int, is_hex: bool = False) -> bool:
    """
    根据命令字符串解析并发送
    支持格式：
      - 普通字符串 → TCP/UDP 直发
      - "3rd_{tcp#IP#PORT}_CMD" → 解析后发送
      - http:// 开头 → HTTP GET
    """
    # 解析 3rd_{tcp#IP#PORT}_CMD 格式
    if command_str.startswith("3rd_"):
        import re
        m = re.match(r"3rd_\{(tcp|http|udp)#([\d.]+)#(\d+)\}_(.+)", command_str)
        if m:
            proto, ip, port, cmd = m.group(1), m.group(2), int(m.group(3)), m.group(4)
            if proto == "tcp":
                return await send_tcp(ip, port, cmd)
            elif proto == "http":
                return await send_http(f"http://{ip}:{port}/{cmd}") is not None
            elif proto == "udp":
                return await send_udp(ip, port, cmd)

    # HTTP URL
    if command_str.startswith("http"):
        return await send_http(command_str) is not None

    # 默认按协议发送
    if protocol == "tcp":
        return await send_tcp(target_ip, target_port, command_str, is_hex)
    elif protocol == "udp":
        return await send_udp(target_ip, target_port, command_str, is_hex)
    elif protocol == "http":
        return await send_http(f"http://{target_ip}:{target_port}/{command_str}") is not None

    return False
