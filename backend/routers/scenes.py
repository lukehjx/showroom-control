from fastapi import APIRouter
from sqlalchemy import select
from database import async_session
from models import CurrentScene, CloudScene
from schemas import ok, err, SceneSwitch
from tcp_service import switch_scene_tcp
from datetime import datetime
import logging

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api", tags=["scenes"])


@router.get("/current-scene")
async def get_current_scene():
    try:
        async with async_session() as session:
            result = await session.execute(
                select(CurrentScene).order_by(CurrentScene.id.desc()).limit(1)
            )
            scene = result.scalar_one_or_none()
            if not scene:
                return ok(None)
            return ok({
                "id": scene.id,
                "scene_id": scene.scene_id,
                "scene_name": scene.scene_name,
                "updated_at": str(scene.updated_at)
            })
    except Exception as e:
        return err(str(e))


@router.post("/scenes/switch")
async def switch_scene(body: SceneSwitch):
    try:
        scene_id = body.scene_id

        # 查找场景名称
        scene_name = ""
        async with async_session() as session:
            result = await session.execute(
                select(CloudScene).where(CloudScene.scene_id == scene_id).limit(1)
            )
            cloud_scene = result.scalar_one_or_none()
            if cloud_scene:
                scene_name = cloud_scene.name or ""

        # 发送TCP命令
        ok_result = await switch_scene_tcp(scene_id)

        # 更新当前场景
        async with async_session() as session:
            existing = await session.execute(select(CurrentScene).limit(1))
            current = existing.scalar_one_or_none()
            if current:
                current.scene_id = scene_id
                current.scene_name = scene_name
                current.updated_at = datetime.now()
            else:
                session.add(CurrentScene(scene_id=scene_id, scene_name=scene_name, updated_at=datetime.now()))
            await session.commit()

        return ok({"scene_id": scene_id, "scene_name": scene_name, "tcp_sent": ok_result})
    except Exception as e:
        logger.error(f"Switch scene error: {e}")
        return err(str(e))
