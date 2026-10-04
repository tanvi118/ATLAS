import logging

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app import schemas
from app.db.database import get_db
from app.services import agent_service, memory_service

logger = logging.getLogger("atlas.chat")
router = APIRouter(tags=["chat"])


@router.post("/chat", response_model=schemas.ChatResponse)
def chat(body: schemas.ChatRequest, db: Session = Depends(get_db)):
    session_id = body.resolved_session_id()
    try:
        result = agent_service.handle_message(db, body.message, session_id)
    except Exception:
        logger.exception("Unhandled error in /chat")
        raise HTTPException(status_code=500, detail="Something went wrong while handling your message.")
    memory_service.add_message(db, session_id, "user", body.message)
    memory_service.add_message(db, session_id, "assistant", result.reply)
    return schemas.ChatResponse(**result.model_dump(), session_id=session_id)
