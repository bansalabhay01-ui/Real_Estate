"""The property assistant."""

from fastapi import APIRouter, Query, Request
from fastapi.concurrency import run_in_threadpool

from ..ai.assistant import chat_history, handle_chat
from ..realtime import hub
from ..schemas import ChatIn, ChatMessageOut, ChatOut
from ..utils import client_ip

router = APIRouter(tags=["chat"])


@router.post("/chat", response_model=ChatOut)
async def chat(payload: ChatIn, request: Request) -> ChatOut:
    """Answer from the listings (with the LLM if a key is set, templates otherwise) and save the buyer details."""
    reply, visitor = await run_in_threadpool(handle_chat, payload, client_ip(request), request.headers.get("user-agent"))
    if visitor is not None:
        await hub.broadcast({"type": "visitor_update", "visitor": visitor.model_dump(mode="json")})
    return reply


@router.get("/chat/{visitor_id}", response_model=list[ChatMessageOut])
def get_chat(visitor_id: str, limit: int = Query(50, ge=1, le=200)) -> list[ChatMessageOut]:
    """A visitor's conversation, oldest first."""
    return chat_history(visitor_id, limit=limit)
