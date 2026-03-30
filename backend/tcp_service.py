import asyncio
import logging
from datetime import datetime
from config import get_config

logger = logging.getLogger(__name__)


async def send_tcp(host: str, port: int, data: str, encoding: str = 'utf-8', is_hex: bool = False) -> bool:
    """统一TCP发送"""
    try:
        reader, writer = await asyncio.wait_for(
            asyncio.open_connection(host, port), timeout=10
        )
        if is_hex:
            raw = bytes.fromhex(data.replace(' ', ''))
        else:
            raw = data.encode(encoding)
        writer.write(raw)
        await writer.drain()
        writer.close()
        await writer.wait_closed()
        logger.info(f"TCP sent to {host}:{port}: {data[:100]}")
        return True
    except Exception as e:
        logger.error(f"TCP send error to {host}:{port}: {e}")
        return False


async def cast_resource(scene_id: int, terminal_id: int, resource_id: int) -> bool:
    """投放资源 格式：2_{scene_id}_{terminal_id}_{resource_id}"""
    host = await get_config("tcp.host") or "112.20.77.18"
    port = int(await get_config("tcp.port") or "8989")
    cmd = f"2_{scene_id}_{terminal_id}_{resource_id}"
    return await send_tcp(host, port, cmd)


async def switch_scene_tcp(scene_id: int) -> bool:
    """切换专场 格式：2_update_{scene_id}"""
    host = await get_config("tcp.host") or "112.20.77.18"
    port = int(await get_config("tcp.port") or "8989")
    cmd = f"2_update_{scene_id}"
    return await send_tcp(host, port, cmd)


# TCP监听服务（端口19888）
class TCPListenServer:
    def __init__(self):
        self.server = None
        self._on_scene_update = None

    def set_scene_update_callback(self, callback):
        self._on_scene_update = callback

    async def handle_client(self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter):
        addr = writer.get_extra_info('peername')
        try:
            data = await asyncio.wait_for(reader.read(1024), timeout=30)
            message = data.decode('utf-8', errors='ignore').strip()
            logger.info(f"TCP received from {addr}: {message}")

            if message.startswith("update_"):
                # 解析场景ID: update_xx
                parts = message.split("_")
                if len(parts) >= 2:
                    try:
                        scene_id = int(parts[1])
                        if self._on_scene_update:
                            asyncio.create_task(self._on_scene_update(scene_id, message))
                    except ValueError:
                        logger.warning(f"Invalid scene ID in message: {message}")
        except asyncio.TimeoutError:
            logger.debug(f"TCP client {addr} timed out")
        except Exception as e:
            logger.error(f"TCP handle error from {addr}: {e}")
        finally:
            try:
                writer.close()
                await writer.wait_closed()
            except Exception:
                pass

    async def start(self, host: str = "0.0.0.0", port: int = 19888):
        try:
            self.server = await asyncio.start_server(
                self.handle_client, host, port
            )
            logger.info(f"TCP listen server started on {host}:{port}")
            async with self.server:
                await self.server.serve_forever()
        except Exception as e:
            logger.error(f"TCP listen server error: {e}")

    async def stop(self):
        if self.server:
            self.server.close()
            await self.server.wait_closed()
            logger.info("TCP listen server stopped")


tcp_listen_server = TCPListenServer()
