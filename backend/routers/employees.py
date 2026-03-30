from fastapi import APIRouter, HTTPException, UploadFile, File, Form
from fastapi.responses import FileResponse
from typing import Optional
import os
from database import async_session
from schemas import ok, err
import logging
from datetime import datetime

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api", tags=["employees"])

FACE_PHOTO_DIR = "/tmp/showroom-ctrl/backend/face_photos"
os.makedirs(FACE_PHOTO_DIR, exist_ok=True)


# GET /api/employees — 员工列表
@router.get("/employees")
async def list_employees():
    try:
        from sqlalchemy import text
        async with async_session() as session:
            result = await session.execute(text("SELECT * FROM employees ORDER BY id"))
            rows = result.mappings().all()
            data = []
            for r in rows:
                d = dict(r)
                photo_path = f"{FACE_PHOTO_DIR}/{r['id']}.jpg"
                d['has_photo'] = os.path.exists(photo_path)
                d['photo_url'] = f"/api/employees/{r['id']}/photo" if d['has_photo'] else None
                # Convert datetime fields to string for JSON serialization
                for k in ['created_at', 'updated_at']:
                    if k in d and d[k] is not None:
                        d[k] = str(d[k])
                data.append(d)
        return ok(data)
    except Exception as e:
        logger.error(f"List employees error: {e}")
        return err(str(e))


# POST /api/employees — 创建员工（multipart，照片可选）
@router.post("/employees")
async def create_employee(
    name: str = Form(...),
    department: str = Form(""),
    userid: str = Form(""),
    photo: Optional[UploadFile] = File(None),
):
    try:
        from sqlalchemy import text
        async with async_session() as session:
            # 生成唯一userid如果未提供
            actual_userid = userid if userid else f"emp_{int(datetime.now().timestamp() * 1000)}"
            result = await session.execute(
                text("INSERT INTO employees (name, department, userid, face_registered) VALUES (:name, :dept, :uid, FALSE) RETURNING *"),
                {"name": name, "dept": department, "uid": actual_userid}
            )
            row = result.mappings().one()
            emp_id = row['id']
            has_photo = False

            # 保存照片
            if photo and photo.filename:
                photo_path = f"{FACE_PHOTO_DIR}/{emp_id}.jpg"
                content = await photo.read()
                with open(photo_path, "wb") as f:
                    f.write(content)
                await session.execute(
                    text("UPDATE employees SET face_registered=TRUE WHERE id=:id"),
                    {"id": emp_id}
                )
                has_photo = True

            await session.commit()
            d = dict(row)
            for k in ['created_at', 'updated_at']:
                if k in d and d[k] is not None:
                    d[k] = str(d[k])
            d['has_photo'] = has_photo
            d['photo_url'] = f"/api/employees/{emp_id}/photo" if has_photo else None
            return ok(d)
    except Exception as e:
        logger.error(f"Create employee error: {e}")
        return err(str(e))


# GET /api/employees/{id}/photo — 返回照片
@router.get("/employees/{emp_id}/photo")
async def get_employee_photo(emp_id: int):
    photo_path = f"{FACE_PHOTO_DIR}/{emp_id}.jpg"
    if not os.path.exists(photo_path):
        raise HTTPException(404, "No photo")
    return FileResponse(photo_path, media_type="image/jpeg")


# POST /api/employees/{id}/photo — 单独上传照片
@router.post("/employees/{emp_id}/photo")
async def upload_employee_photo(emp_id: int, photo: UploadFile = File(...)):
    try:
        from sqlalchemy import text
        async with async_session() as session:
            result = await session.execute(
                text("SELECT id FROM employees WHERE id=:id"),
                {"id": emp_id}
            )
            row = result.one_or_none()
            if not row:
                raise HTTPException(404, "Employee not found")

            photo_path = f"{FACE_PHOTO_DIR}/{emp_id}.jpg"
            os.makedirs(FACE_PHOTO_DIR, exist_ok=True)
            content = await photo.read()
            with open(photo_path, "wb") as f:
                f.write(content)
            await session.execute(
                text("UPDATE employees SET face_registered=TRUE WHERE id=:id"),
                {"id": emp_id}
            )
            await session.commit()
        return ok({"emp_id": emp_id, "face_registered": True})
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Upload photo error: {e}")
        return err(str(e))


# PUT /api/employees/{id} — 更新员工信息
@router.put("/employees/{emp_id}")
async def update_employee(emp_id: int, data: dict):
    try:
        from sqlalchemy import text
        fields = []
        values = {}
        for k in ['name', 'department', 'userid']:
            if k in data:
                fields.append(f"{k}=:{k}")
                values[k] = data[k]
        if not fields:
            raise HTTPException(400, "No fields to update")
        values['id'] = emp_id
        async with async_session() as session:
            await session.execute(
                text(f"UPDATE employees SET {', '.join(fields)} WHERE id=:id"),
                values
            )
            await session.commit()
        return ok({"status": "ok"})
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Update employee error: {e}")
        return err(str(e))


# DELETE /api/employees/{id} — 删除员工
@router.delete("/employees/{emp_id}")
async def delete_employee(emp_id: int):
    try:
        from sqlalchemy import text
        async with async_session() as session:
            await session.execute(
                text("DELETE FROM employees WHERE id=:id"),
                {"id": emp_id}
            )
            await session.commit()
        photo_path = f"{FACE_PHOTO_DIR}/{emp_id}.jpg"
        if os.path.exists(photo_path):
            os.remove(photo_path)
        return ok({"status": "ok"})
    except Exception as e:
        logger.error(f"Delete employee error: {e}")
        return err(str(e))
