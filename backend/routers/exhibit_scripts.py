"""
展项讲解脚本管理路由
"""
import logging
from fastapi import APIRouter
from sqlalchemy import select, text
from database import async_session
from schemas import ok, err
from datetime import datetime

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/exhibit-scripts", tags=["exhibit-scripts"])


@router.get("")
async def list_scripts():
    """获取所有展项讲解脚本"""
    try:
        async with async_session() as session:
            result = await session.execute(
                text("SELECT * FROM exhibit_scripts ORDER BY sort_order, id")
            )
            rows = result.mappings().all()
            data = [dict(r) for r in rows]
        return ok(data)
    except Exception as e:
        logger.error(f"List exhibit_scripts error: {e}")
        return err(str(e))


@router.post("")
async def create_script(body: dict):
    """创建展项讲解脚本"""
    try:
        async with async_session() as session:
            result = await session.execute(
                text("""
                    INSERT INTO exhibit_scripts
                    (terminal_id, terminal_name, trigger_phrases, opening_speech,
                     resource_id, resource_title, commentary, nav_position,
                     tts_delay_seconds, enabled, note, sort_order,
                     ai_commentary_enabled, auto_tour_enabled, created_at, updated_at)
                    VALUES
                    (:terminal_id, :terminal_name, :trigger_phrases, :opening_speech,
                     :resource_id, :resource_title, :commentary, :nav_position,
                     :tts_delay_seconds, :enabled, :note, :sort_order,
                     :ai_commentary_enabled, :auto_tour_enabled, NOW(), NOW())
                    RETURNING id
                """),
                {
                    "terminal_id": body.get("terminal_id", 0),
                    "terminal_name": body.get("terminal_name", ""),
                    "trigger_phrases": body.get("trigger_phrases", ""),
                    "opening_speech": body.get("opening_speech", ""),
                    "resource_id": body.get("resource_id"),
                    "resource_title": body.get("resource_title", ""),
                    "commentary": body.get("commentary", ""),
                    "nav_position": body.get("nav_position", ""),
                    "tts_delay_seconds": body.get("tts_delay_seconds", 2),
                    "enabled": body.get("enabled", True),
                    "note": body.get("note", ""),
                    "sort_order": body.get("sort_order", 99),
                    "ai_commentary_enabled": body.get("ai_commentary_enabled", True),
                    "auto_tour_enabled": body.get("auto_tour_enabled", False),
                }
            )
            row = result.fetchone()
            await session.commit()
        return ok({"id": row[0]})
    except Exception as e:
        logger.error(f"Create exhibit_script error: {e}")
        return err(str(e))


@router.get("/{script_id}")
async def get_script(script_id: int):
    """获取单个展项讲解脚本"""
    try:
        async with async_session() as session:
            result = await session.execute(
                text("SELECT * FROM exhibit_scripts WHERE id=:id"),
                {"id": script_id}
            )
            row = result.mappings().fetchone()
        if not row:
            return err(f"Script {script_id} not found", 404)
        return ok(dict(row))
    except Exception as e:
        logger.error(f"Get exhibit_script error: {e}")
        return err(str(e))


@router.put("/{script_id}")
async def update_script(script_id: int, body: dict):
    """更新展项讲解脚本"""
    try:
        async with async_session() as session:
            # Build dynamic SET clause
            allowed = [
                "terminal_id", "terminal_name", "trigger_phrases", "opening_speech",
                "resource_id", "resource_title", "commentary", "nav_position",
                "tts_delay_seconds", "enabled", "note", "sort_order",
                "ai_commentary_enabled", "auto_tour_enabled",
                "name", "narration", "trigger_keywords", "auto_play"
            ]
            sets = []
            params = {"id": script_id}
            for k in allowed:
                if k in body:
                    sets.append(f"{k}=:{k}")
                    params[k] = body[k]
            if not sets:
                return err("No fields to update")
            sets.append("updated_at=NOW()")
            sql = f"UPDATE exhibit_scripts SET {', '.join(sets)} WHERE id=:id"
            await session.execute(text(sql), params)
            await session.commit()
        return ok({"id": script_id})
    except Exception as e:
        logger.error(f"Update exhibit_script error: {e}")
        return err(str(e))


@router.delete("/{script_id}")
async def delete_script(script_id: int):
    """删除展项讲解脚本"""
    try:
        async with async_session() as session:
            await session.execute(
                text("DELETE FROM exhibit_scripts WHERE id=:id"),
                {"id": script_id}
            )
            await session.commit()
        return ok({"deleted": script_id})
    except Exception as e:
        logger.error(f"Delete exhibit_script error: {e}")
        return err(str(e))
