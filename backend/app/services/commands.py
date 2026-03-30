"""
指令发送服务 - 按协议分类

协议分类：
  TCP → 112.20.77.18:8989  中控Server（资源播放/场景控制/硬件控制/专场切换）
  HTTP → 112.20.77.18:8866  云平台（认证/数据查询）
  HTTP → {主机IP}:8899       数字人/讲解接口
  HTTP → {主机IP}:7789       播放控制（action参数）

命令格式（飞书文档）：
  0_*  硬件控制单命令：0_设备类型_目标ID_on/off
  0_all_*  组策略：0_all_light_on/off / 0_all_com_on/off / 0_all_ggj_on/off
  1_*  软件控制：1_设备id_win_max/min / 1_设备id_vol_value
  2_*  资源播放：2_专场id_设备id_资源id / 2_设备id_video_play 等
  3_*  分屏播放：3_设备id_专场id_场景id...
  4_*  专场切换：4_专场id
  5_*  一键待展：5_ready
  3rd_*  第三方直控：3rd_设备id_命令字符串
"""
import asyncio
import aiohttp
import logging
import socket
from typing import Optional

from ..config import settings

logger = logging.getLogger(__name__)

TCP_HOST = settings.ZHONGKONG_TCP_HOST   # 112.20.77.18
TCP_PORT = settings.ZHONGKONG_TCP_PORT   # 8989
HTTP_CLOUD_HOST = settings.ZHONGKONG_HTTP_HOST  # 112.20.77.18
HTTP_CLOUD_PORT = 8866


# ==================== TCP 指令（中控Server） ====================

async def send_tcp_command(host: str, port: int, cmd: str, timeout: float = 5.0) -> bool:
    """
    发TCP指令到中控Server
    适用：所有数字前缀命令（0/1/2/3/4/5/6/7）
    """
    try:
        loop = asyncio.get_event_loop()
        await asyncio.wait_for(
            loop.run_in_executor(None, _tcp_send_sync, host, port, cmd),
            timeout=timeout
        )
        logger.info(f"TCP发送成功 → {host}:{port} [{cmd}]")
        return True
    except asyncio.TimeoutError:
        logger.error(f"TCP超时 → {host}:{port} [{cmd}]")
        return False
    except Exception as e:
        logger.error(f"TCP发送失败 → {host}:{port} [{cmd}]: {e}")
        return False


def _tcp_send_sync(host: str, port: int, cmd: str):
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.settimeout(5)
        s.connect((host, port))
        s.sendall((cmd + "\r\n").encode("utf-8"))
        logger.debug(f"TCP已发: {cmd}")


# ==================== 便捷TCP命令 ====================

async def cmd_open_all():
    """一键开馆：设备全开 + 灯光全开"""
    await send_tcp_command(TCP_HOST, TCP_PORT, "0_all_com_on")
    await asyncio.sleep(0.3)
    await send_tcp_command(TCP_HOST, TCP_PORT, "0_all_light_on")


async def cmd_close_all():
    """一键关馆：设备全关 + 灯光全关"""
    await send_tcp_command(TCP_HOST, TCP_PORT, "0_all_com_off")
    await asyncio.sleep(0.3)
    await send_tcp_command(TCP_HOST, TCP_PORT, "0_all_light_off")


async def cmd_lights_on():
    return await send_tcp_command(TCP_HOST, TCP_PORT, "0_all_light_on")


async def cmd_lights_off():
    return await send_tcp_command(TCP_HOST, TCP_PORT, "0_all_light_off")


async def cmd_ads_on():
    return await send_tcp_command(TCP_HOST, TCP_PORT, "0_all_ggj_on")


async def cmd_ads_off():
    return await send_tcp_command(TCP_HOST, TCP_PORT, "0_all_ggj_off")


async def cmd_standby():
    """一键待展"""
    return await send_tcp_command(TCP_HOST, TCP_PORT, "5_ready")


async def cmd_switch_special(special_id: int):
    """切换专场（TCP）"""
    return await send_tcp_command(TCP_HOST, TCP_PORT, f"4_{special_id}")


async def cmd_play_resource(device_id: int, special_id: int, resource_id: int):
    """
    播放资源
    格式：2_专场id_设备id_资源id
    """
    cmd = f"2_{special_id}_{device_id}_{resource_id}"
    return await send_tcp_command(TCP_HOST, TCP_PORT, cmd)


async def cmd_video_play(device_id: int):
    return await send_tcp_command(TCP_HOST, TCP_PORT, f"2_{device_id}_video_play")


async def cmd_video_pause(device_id: int):
    return await send_tcp_command(TCP_HOST, TCP_PORT, f"2_{device_id}_video_pause")


async def cmd_video_replay(device_id: int):
    return await send_tcp_command(TCP_HOST, TCP_PORT, f"2_{device_id}_video_replay")


async def cmd_ppt_next(device_id: int):
    return await send_tcp_command(TCP_HOST, TCP_PORT, f"2_{device_id}_ppt_next")


async def cmd_ppt_prev(device_id: int):
    return await send_tcp_command(TCP_HOST, TCP_PORT, f"2_{device_id}_ppt_last")


async def cmd_volume(device_id: int, value: int):
    """调整主机音量（0-100）"""
    return await send_tcp_command(TCP_HOST, TCP_PORT, f"1_{device_id}_vol_{value}")


async def cmd_software_control(device_id: int, action: str):
    """软件控制：max/min/win_max/win_min"""
    return await send_tcp_command(TCP_HOST, TCP_PORT, f"1_{device_id}_{action}")


async def cmd_back_to_screensaver(device_id: int):
    """返回屏保"""
    return await send_tcp_command(TCP_HOST, TCP_PORT, f"1_{device_id}_main")


async def cmd_third_party(device_id: int, cmd_str: str):
    """
    发送到第三方设备
    格式：3rd_设备ID_命令字符串
    """
    cmd = f"3rd_{device_id}_{cmd_str}"
    return await send_tcp_command(TCP_HOST, TCP_PORT, cmd)


# ==================== 发组策略命令（通过名称查DB）====================

async def send_group_command(command_name: str, db) -> bool:
    """通过命令名称查找并发送（TCP）"""
    from sqlalchemy import select
    from ..models import CloudCommand
    try:
        r = await db.execute(
            select(CloudCommand).where(CloudCommand.name.ilike(f"%{command_name}%"))
        )
        cmd = r.scalar_one_or_none()
        if cmd:
            return await send_tcp_command(TCP_HOST, TCP_PORT, cmd.command_str)
        logger.warning(f"未找到命令: {command_name}")
        return False
    except Exception as e:
        logger.error(f"发组策略命令失败: {e}")
        return False


# ==================== HTTP → 云平台（数据查询用，不发控制命令）====================

async def http_get_device_status(device_ip: str) -> Optional[dict]:
    """
    获取设备当前状态
    GET http://{ip}:8899/
    （注意：这是状态查询接口，不是控制接口）
    """
    url = f"http://{device_ip}:8899/"
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url, timeout=aiohttp.ClientTimeout(total=3)) as resp:
                if resp.status == 200:
                    return await resp.json()
    except Exception as e:
        logger.debug(f"设备状态查询失败 {device_ip}: {e}")
    return None


async def http_get_playback_info(host_ip: str) -> Optional[dict]:
    """
    获取主机当前播放信息
    GET http://{主机IP}:7789/info
    （HTTP，不是TCP）
    """
    url = f"http://{host_ip}:7789/info"
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url, timeout=aiohttp.ClientTimeout(total=3)) as resp:
                if resp.status == 200:
                    return await resp.json()
    except Exception as e:
        logger.debug(f"播放信息查询失败 {host_ip}: {e}")
    return None


async def http_play_action(host_ip: str, special_id: int, resource_id: int) -> bool:
    """
    直接HTTP播放命令到主机（不走中控）
    GET http://{主机IP}:7789/action?targetType=2&command=2_{专场ID}_{资源ID}
    注意：这是备用方案，正常走TCP到中控Server
    """
    cmd = f"2_{special_id}_{resource_id}"
    url = f"http://{host_ip}:7789/action?targetType=2&command={cmd}"
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url, timeout=aiohttp.ClientTimeout(total=3)) as resp:
                ok = resp.status == 200
                logger.info(f"HTTP播放 → {url} : {resp.status}")
                return ok
    except Exception as e:
        logger.error(f"HTTP播放失败 {host_ip}: {e}")
        return False


# ==================== 数字人 / 讲解接口（HTTP:8899）====================

async def http_digital_human_speak(host_ip: str, text: str) -> bool:
    """
    控制数字人讲解（HTTP → {主机IP}:8899）
    """
    url = f"http://{host_ip}:8899/speak"
    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(
                url, json={"text": text},
                timeout=aiohttp.ClientTimeout(total=5)
            ) as resp:
                return resp.status == 200
    except Exception as e:
        logger.error(f"数字人讲解失败 {host_ip}: {e}")
        return False
