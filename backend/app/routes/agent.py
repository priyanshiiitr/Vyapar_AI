from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.agent.orchestrator import run_agent
from app.config import get_settings
from app.database import get_db
from app.models import ChatMessage, Conversation

router = APIRouter(prefix="/agent")


class ChatRequest(BaseModel):
    message: str
    conversation_id: int | None = None


@router.post("/chat")
def chat(payload: ChatRequest, db: Session = Depends(get_db)):
    mid = get_settings().DEMO_MERCHANT_ID
    return run_agent(
        db,
        merchant_id=mid,
        user_message=payload.message,
        conversation_id=payload.conversation_id,
    )


@router.get("/conversations")
def conversations(db: Session = Depends(get_db)):
    mid = get_settings().DEMO_MERCHANT_ID
    rows = list(
        db.scalars(
            select(Conversation).where(Conversation.merchant_id == mid).order_by(Conversation.id.desc())
        )
    )
    return {
        "conversations": [
            {"id": c.id, "title": c.title, "created_at": c.created_at.isoformat() if c.created_at else None}
            for c in rows
        ]
    }


@router.get("/conversations/{conversation_id}")
def conversation_detail(conversation_id: int, db: Session = Depends(get_db)):
    mid = get_settings().DEMO_MERCHANT_ID
    conv = db.get(Conversation, conversation_id)
    if not conv or conv.merchant_id != mid:
        return {"ok": False, "error": "Not found"}
    messages = list(
        db.scalars(
            select(ChatMessage)
            .where(ChatMessage.conversation_id == conversation_id)
            .order_by(ChatMessage.id.asc())
        )
    )
    return {
        "ok": True,
        "conversation_id": conv.id,
        "messages": [
            {
                "id": m.id,
                "role": m.role,
                "content": m.content,
                "tool_name": m.tool_name,
                "tool_call_id": m.tool_call_id,
                "tool_args_json": m.tool_args_json,
                "tool_result_json": m.tool_result_json,
                "tool_status": m.tool_status,
                "created_at": m.created_at.isoformat() if m.created_at else None,
            }
            for m in messages
        ],
    }
