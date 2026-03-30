import io
import base64
import asyncio
import logging
from fastapi import APIRouter
from fastapi.responses import Response
from database import async_session
from models import Exhibit
from schemas import ok, err

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/qrcode", tags=["qrcode"])


def generate_qr_base64(data: str) -> str:
    """生成二维码并返回base64"""
    import qrcode
    from PIL import Image

    qr = qrcode.QRCode(
        version=1,
        error_correction=qrcode.constants.ERROR_CORRECT_L,
        box_size=10,
        border=4,
    )
    qr.add_data(data)
    qr.make(fit=True)
    img = qr.make_image(fill_color="black", back_color="white")

    buffer = io.BytesIO()
    img.save(buffer, format="PNG")
    buffer.seek(0)
    return base64.b64encode(buffer.getvalue()).decode()


@router.get("/{exhibit_id}")
async def get_exhibit_qrcode(exhibit_id: int, base_url: str = "http://36.134.146.69:8200"):
    """生成展项二维码"""
    try:
        async with async_session() as session:
            exhibit = await session.get(Exhibit, exhibit_id)
            if not exhibit:
                return err(f"Exhibit {exhibit_id} not found", 404)

        # 二维码内容：扫描触发URL
        scan_url = f"{base_url}/api/qrcode/scan/{exhibit_id}"

        try:
            qr_b64 = generate_qr_base64(scan_url)
            return ok({
                "exhibit_id": exhibit_id,
                "exhibit_name": exhibit.name,
                "scan_url": scan_url,
                "qr_base64": f"data:image/png;base64,{qr_b64}"
            })
        except ImportError:
            # qrcode未安装，返回URL
            return ok({
                "exhibit_id": exhibit_id,
                "exhibit_name": exhibit.name,
                "scan_url": scan_url,
                "qr_base64": None,
                "message": "qrcode library not installed"
            })
    except Exception as e:
        logger.error(f"Generate QR code error: {e}")
        return err(str(e))


@router.get("/scan/{exhibit_id}")
async def scan_qrcode(exhibit_id: int, robot_sn: str = ""):
    """扫码后触发该展项讲解流程"""
    try:
        async with async_session() as session:
            exhibit = await session.get(Exhibit, exhibit_id)
            if not exhibit:
                return err(f"Exhibit {exhibit_id} not found", 404)

        # 触发聊天输入
        from routers.chat import chat_input
        from schemas import ChatInput

        chat_body = ChatInput(
            event="voice_input",
            robot_sn=robot_sn,
            params={"text": f"介绍{exhibit.name}", "source": "qrcode", "exhibit_id": exhibit_id}
        )

        result = await chat_input(chat_body)

        return ok({
            "exhibit_id": exhibit_id,
            "exhibit_name": exhibit.name,
            "triggered": True,
            "result": result
        })
    except Exception as e:
        logger.error(f"QR scan trigger error: {e}")
        return err(str(e))
