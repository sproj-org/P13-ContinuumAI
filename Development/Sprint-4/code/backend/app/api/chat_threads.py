import logging

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import Session

from app.core.security import get_current_user
from app.db.database import get_db, invalidate_db_session
from app.db.models import ChatThread, User
from app.schemas.chat_thread import ChatThreadResponse, ChatThreadUpsert

router = APIRouter(prefix="/chat-threads", tags=["Chat Threads"])
logger = logging.getLogger(__name__)


def _list_threads(db: Session, *, user_id: int) -> list[ChatThread]:
    return (
        db.query(ChatThread)
        .filter(ChatThread.user_id == user_id)
        .order_by(ChatThread.updated_at.desc())
        .all()
    )


def _chat_persistence_unavailable() -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
        detail={
            "code": "chat_persistence_unavailable",
            "message": "Chat persistence is temporarily unavailable.",
            "hint": "You can continue working in the workspace and retry saving chat history later.",
        },
    )


@router.get("", response_model=list[ChatThreadResponse])
async def list_chat_threads(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """List all chat threads for the current user."""
    try:
        threads = _list_threads(db, user_id=current_user.id)
    except OperationalError:
        logger.warning(
            "Chat thread listing failed on the first attempt; retrying once.",
            extra={"user_id": current_user.id},
            exc_info=True,
        )
        invalidate_db_session(db)
        try:
            threads = _list_threads(db, user_id=current_user.id)
        except OperationalError:
            logger.error(
                "Chat thread listing unavailable; returning an empty list so workspace tabs continue loading.",
                extra={"user_id": current_user.id},
                exc_info=True,
            )
            invalidate_db_session(db)
            return []
    return [ChatThreadResponse.from_orm_model(t) for t in threads]


@router.put("", response_model=ChatThreadResponse)
async def upsert_chat_thread(
    data: ChatThreadUpsert,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Create or update a chat thread (matched by user + thread_key)."""
    try:
        thread = (
            db.query(ChatThread)
            .filter(
                ChatThread.user_id == current_user.id,
                ChatThread.thread_key == data.thread_key,
            )
            .first()
        )
        if thread:
            thread.turns = data.turns
            thread.chat_state = data.chat_state
            thread.last_chart_spec = data.last_chart_spec
            thread.saved_prompts = data.saved_prompts
            thread.chat_mode = data.chat_mode
        else:
            thread = ChatThread(
                user_id=current_user.id,
                thread_key=data.thread_key,
                turns=data.turns,
                chat_state=data.chat_state,
                last_chart_spec=data.last_chart_spec,
                saved_prompts=data.saved_prompts,
                chat_mode=data.chat_mode,
            )
            db.add(thread)
        db.commit()
        db.refresh(thread)
    except OperationalError:
        invalidate_db_session(db)
        logger.warning(
            "Chat thread upsert failed.",
            extra={"user_id": current_user.id, "thread_key": data.thread_key},
            exc_info=True,
        )
        raise _chat_persistence_unavailable()
    return ChatThreadResponse.from_orm_model(thread)


@router.delete("/{thread_key:path}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_chat_thread(
    thread_key: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Delete a single chat thread by key."""
    try:
        thread = (
            db.query(ChatThread)
            .filter(
                ChatThread.user_id == current_user.id,
                ChatThread.thread_key == thread_key,
            )
            .first()
        )
        if not thread:
            raise HTTPException(status_code=404, detail="Chat thread not found")
        db.delete(thread)
        db.commit()
    except OperationalError:
        invalidate_db_session(db)
        logger.warning(
            "Chat thread delete failed.",
            extra={"user_id": current_user.id, "thread_key": thread_key},
            exc_info=True,
        )
        raise _chat_persistence_unavailable()


@router.delete("", status_code=status.HTTP_204_NO_CONTENT)
async def clear_all_chat_threads(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Clear all chat threads for the current user."""
    try:
        db.query(ChatThread).filter(ChatThread.user_id == current_user.id).delete(
            synchronize_session=False
        )
        db.commit()
    except OperationalError:
        invalidate_db_session(db)
        logger.warning(
            "Clearing chat threads failed.",
            extra={"user_id": current_user.id},
            exc_info=True,
        )
        raise _chat_persistence_unavailable()
