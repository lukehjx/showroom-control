from fastapi import APIRouter
from database import async_session
from sqlalchemy import text
from pydantic import BaseModel
from typing import Optional
import logging

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/appointments", tags=["appointments"])


class AppointmentCreate(BaseModel):
    creator_userid: Optional[str] = "frontend"
    creator_name: Optional[str] = ""
    visitor_name: str
    visit_time: Optional[str] = None
    purpose: Optional[str] = None
    attendees: Optional[str] = None
    notes: Optional[str] = None
    raw_text: Optional[str] = None


class AppointmentUpdate(BaseModel):
    visitor_name: Optional[str] = None
    visit_time: Optional[str] = None
    purpose: Optional[str] = None
    status: Optional[str] = None
    notes: Optional[str] = None


@router.get("")
async def list_appointments(
    status: Optional[str] = None,
    visitor_name: Optional[str] = None,
    creator_name: Optional[str] = None,
    date_str: Optional[str] = None,
    date_range: Optional[str] = None,
    limit: int = 50,
):
    conditions = ["1=1"]

    if status:
        conditions.append(f"status='{status.replace(chr(39), chr(39)*2)}'")

    if visitor_name:
        vn = visitor_name.replace("'", "''")
        conditions.append(f"visitor_name ILIKE '%{vn}%'")

    if creator_name:
        cn = creator_name.replace("'", "''")
        conditions.append(f"(creator_name ILIKE '%{cn}%' OR creator_userid ILIKE '%{cn}%')")

    if date_str:
        from datetime import date, timedelta
        today = date.today()
        tomorrow = today + timedelta(days=1)
        if date_str == "today":
            conditions.append(f"DATE(visit_time)='{today}'")
        elif date_str == "tomorrow":
            conditions.append(f"DATE(visit_time)='{tomorrow}'")
        elif date_str == "this_week":
            monday = today - timedelta(days=today.weekday())
            sunday = monday + timedelta(days=6)
            conditions.append(f"DATE(visit_time) BETWEEN '{monday}' AND '{sunday}'")
        elif date_str == "morning":
            conditions.append("EXTRACT(HOUR FROM visit_time) < 12")
        elif date_str == "afternoon":
            conditions.append("EXTRACT(HOUR FROM visit_time) >= 12 AND EXTRACT(HOUR FROM visit_time) < 18")
        else:
            conditions.append(f"DATE(visit_time)='{date_str}'")

    if date_range:
        parts = date_range.split(",")
        if len(parts) == 2:
            conditions.append(
                f"DATE(visit_time) BETWEEN '{parts[0].strip()}' AND '{parts[1].strip()}'"
            )

    where = " AND ".join(conditions)
    sql = f"SELECT * FROM appointments WHERE {where} ORDER BY visit_time ASC LIMIT {limit}"

    vt = int(vt) if vt is not None else 0
    async with async_session() as db:
        result = await db.execute(text(sql))
        rows = result.mappings().fetchall()
    return {"code": 0, "data": [dict(r) for r in rows]}


@router.post("/batch-cancel")
async def batch_cancel(body: dict):
    """批量取消：支持按 visitor_name / date_range / date_str 取消"""
    visitor_name = body.get("visitor_name")
    date_range = body.get("date_range")
    date_str = body.get("date_str")

    conditions = ["status='pending'"]

    if visitor_name:
        vn = visitor_name.replace("'", "''")
        conditions.append(f"visitor_name ILIKE '%{vn}%'")

    if date_str:
        from datetime import date, timedelta
        today = date.today()
        tomorrow = today + timedelta(days=1)
        if date_str == "tomorrow":
            conditions.append(f"DATE(visit_time)='{tomorrow}'")
        elif date_str == "today":
            conditions.append(f"DATE(visit_time)='{today}'")
        elif date_str == "morning":
            conditions.append("EXTRACT(HOUR FROM visit_time) < 12")
        elif date_str == "afternoon":
            conditions.append("EXTRACT(HOUR FROM visit_time) >= 12 AND EXTRACT(HOUR FROM visit_time) < 18")
        else:
            conditions.append(f"DATE(visit_time)='{date_str}'")

    if date_range:
        parts = date_range.split(",")
        if len(parts) == 2:
            conditions.append(
                f"DATE(visit_time) BETWEEN '{parts[0].strip()}' AND '{parts[1].strip()}'"
            )

    if not visitor_name and not date_range and not date_str:
        return {"code": 1, "data": None, "message": "请指定取消条件（来访人/日期）"}

    where = " AND ".join(conditions)
    sql = (
        f"UPDATE appointments SET status='cancelled', updated_at=NOW() WHERE {where}"
        f" RETURNING id, visitor_name, visit_time"
    )

    vt = int(vt) if vt is not None else 0
    async with async_session() as db:
        result = await db.execute(text(sql))
        cancelled = result.mappings().fetchall()
        await db.commit()
    return {"code": 0, "data": [dict(r) for r in cancelled]}


@router.post("")
async def create_appointment(data: AppointmentCreate):
    from datetime import datetime
    vn = data.visitor_name.replace("'", "''")
    cn = (data.creator_name or "").replace("'", "''")
    cu = (data.creator_userid or "frontend").replace("'", "''")
    pu = (data.purpose or "").replace("'", "''")
    rt = (data.raw_text or "").replace("'", "''")
    # 时间字符串→毫秒时间戳
    vt = data.visit_time
    if isinstance(vt, str):
        for fmt in ["%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M", "%Y-%m-%dT%H:%M"]:
            try: vt = int(datetime.strptime(vt, fmt).timestamp() * 1000); break
            except: pass
        else: vt = 0
    vt = int(vt) if vt is not None else 0
    async with async_session() as db:
        result = await db.execute(text(
            f"INSERT INTO appointments (creator_userid, creator_name, visitor_name, visit_time, purpose, raw_text, created_at, updated_at) VALUES ('{cu}', '{cn}', '{vn}', {vt}, '{pu}', '{rt}', NOW(), NOW()) RETURNING id"
        ))
        new_id = result.scalar()
        await db.commit()
    return {"code": 0, "data": {"id": new_id}}


@router.patch("/{apt_id}")
async def update_appointment(apt_id: int, data: AppointmentUpdate):
    updates = []

    if data.visitor_name:
        updates.append(f"visitor_name='{data.visitor_name.replace(chr(39), chr(39)*2)}'")

    if data.visit_time:
        updates.append(f"visit_time='{data.visit_time}'")

    if data.purpose is not None:
        updates.append(f"purpose='{data.purpose.replace(chr(39), chr(39)*2)}'")

    if data.status:
        updates.append(f"status='{data.status}'")

    if data.notes is not None:
        updates.append(f"notes='{data.notes.replace(chr(39), chr(39)*2)}'")

    if not updates:
        return {"code": 0}

    updates.append("updated_at=NOW()")
    vt = int(vt) if vt is not None else 0
    async with async_session() as db:
        await db.execute(text(f"UPDATE appointments SET {', '.join(updates)} WHERE id={apt_id}"))
        await db.commit()

    if data.status == "confirmed":
        try:
            async with async_session() as db2:
                result2 = await db2.execute(text(f"SELECT * FROM appointments WHERE id={apt_id}"))
                row2 = result2.mappings().first()
            if row2:
                vt2 = row2["visit_time"]
                from routers.chat import _push_bot_notification
                await _push_bot_notification(
                    "MC1BCN2K100262058CA0",
                    f"✅ 预约 #{apt_id} 已确认\n👤 {row2['visitor_name']} — {vt2.strftime('%m/%d %H:%M')}"
                )
        except Exception as _e_notify:
            logger.warning(f"Push confirm notify error: {_e_notify}")

    if data.status == "cancelled":
        try:
            from routers.chat import _push_bot_notification
            await _push_bot_notification(
                "MC1BCN2K100262058CA0",
                f"❌ 预约 #{apt_id} 已取消"
            )
        except Exception as _e_notify2:
            logger.warning(f"Push cancel notify error: {_e_notify2}")

    return {"code": 0}


@router.delete("/{apt_id}")
async def delete_appointment(apt_id: int):
    async with async_session() as db:
        await db.execute(text(f"UPDATE appointments SET status='cancelled', updated_at=NOW() WHERE id={apt_id}"))
        await db.commit()
    return {"code": 0}


# ── 企微Bot辅助函数 ──────────────────────────────────────────────

async def get_display_name(userid: str) -> str:
    """查 wecom_users 表取真实姓名：管理员设置的优先，其次自报，否则返回空"""
    async with async_session() as db:
        result = await db.execute(text(f"SELECT * FROM wecom_users WHERE userid='{userid.replace(chr(39), chr(39)*2)}'"))
        row = result.mappings().first()
    if not row:
        return ""
    return row.get("display_name") or row.get("self_reported_name") or ""


async def push_appointment_notify(apt_id: int, visitor_name: str, visit_time: str, creator_name: str, purpose: str = ""):
    """新建预约后推送企微群通知，含 #ID 和确认指引"""
    try:
        from routers.notify_groups import get_enabled_chat_ids
        chat_ids = await get_enabled_chat_ids()
        if not chat_ids:
            return
        msg = (
            f"📅 新预约 #{apt_id}\n"
            f"👤 来访：{visitor_name}\n"
            f"🕐 时间：{visit_time}\n"
            f"👨‍💼 接待：{creator_name}\n"
        )
        if purpose:
            msg += f"📋 事由：{purpose}\n"
        msg += f"\n回复「确认 #{apt_id}」或「取消 #{apt_id}」"
        async with async_session() as db:
            for chat_id in chat_ids:
                await db.execute(text(
                    "INSERT INTO bot_notifications (robot_sn, user_key, message, created_at) "
                    "VALUES (:sn, :uk, :msg, NOW())"
                ), {"sn": "system", "uk": chat_id, "msg": msg})
            await db.commit()
    except Exception as e:
        logger.warning(f"push_appointment_notify error: {e}")
