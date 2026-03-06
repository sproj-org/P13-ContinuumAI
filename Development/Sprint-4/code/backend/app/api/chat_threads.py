from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.db.database import get_db
from app.db.models import User, ChatThread
from app.core.security import get_current_user
from app.schemas.chat_thread import ChatThreadUpsert, ChatThreadResponse

router = APIRouter(prefix="/chat-threads", tags=["Chat Threads"])


@router.get("", response_model=list[ChatThreadResponse])
async def list_chat_threads(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """List all chat threads for the current user."""
    threads = (
        db.query(ChatThread)
        .filter(ChatThread.user_id == current_user.id)
        .order_by(ChatThread.updated_at.desc())
        .all()
    )
    return [ChatThreadResponse.from_orm_model(t) for t in threads]


@router.put("", response_model=ChatThreadResponse)
async def upsert_chat_thread(
    data: ChatThreadUpsert,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Create or update a chat thread (matched by user + thread_key)."""
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
    return ChatThreadResponse.from_orm_model(thread)


@router.delete("/{thread_key:path}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_chat_thread(
    thread_key: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Delete a single chat thread by key."""
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


@router.delete("", status_code=status.HTTP_204_NO_CONTENT)
async def clear_all_chat_threads(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Clear all chat threads for the current user."""
    db.query(ChatThread).filter(ChatThread.user_id == current_user.id).delete(
        synchronize_session=False
    )
    db.commit()
