from fastapi import APIRouter, Depends
from pydantic import BaseModel
from typing import Optional
from sqlalchemy.ext.asyncio import AsyncSession
from ..database import get_db
from ..services.chat import handle_input

router = APIRouter(prefix="/api/chat", tags=["chat"])


class ChatInput(BaseModel):
    text: str
    source: str = "wecom"   # robot / wecom / admin
    session_key: str         # robot_sn 或 user_id
    robot_sn: Optional[str] = None


@router.post("/input")
async def chat_input(body: ChatInput, db: AsyncSession = Depends(get_db)):
    result = await handle_input(
        db=db,
        text=body.text,
        source=body.source,
        session_key=body.session_key,
        robot_sn=body.robot_sn,
    )
    return {"code": 200, "data": result}
