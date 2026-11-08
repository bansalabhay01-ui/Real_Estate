"""The property assistant."""

from fastapi import APIRouter, BackgroundTasks, Query, Request
from fastapi.concurrency import run_in_threadpool

from ..ai.assistant import chat_history, handle_chat
from ..schemas import ChatIn, ChatMessageOut, ChatOut
from ..scoring.engine import classify_in_background, publish, score_safely
from ..utils import client_ip

router = APIRouter(tags=["chat"])


@router.post("/chat", response_model=ChatOut)
async def chat(payload: ChatIn, request: Request, background: BackgroundTasks) -> ChatOut:
    """Answer from the listings (with the LLM if a key is set, templates otherwise) and save the buyer details.
    The visitor's messages are then classified (end buyer, broker, tenant, ...) in the background."""
    reply, visitor = await run_in_threadpool(handle_chat, payload, client_ip(request), request.headers.get("user-agent"))
    if visitor is not None:
        await publish(visitor, await run_in_threadpool(score_safely, visitor.id))
        background.add_task(classify_in_background, visitor.id)
    return reply


@router.get("/chat/{visitor_id}", response_model=list[ChatMessageOut])
def get_chat(visitor_id: str, limit: int = Query(50, ge=1, le=200)) -> list[ChatMessageOut]:
    """A visitor's conversation, oldest first."""
    return chat_history(visitor_id, limit=limit)
