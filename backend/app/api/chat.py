"""The property assistant."""

from fastapi import APIRouter, BackgroundTasks, HTTPException, Query, Request
from fastapi.concurrency import run_in_threadpool

from ..ai.agent import handle_chat
from ..ai.assistant import chat_history
from ..realtime import hub
from ..schemas import ChatIn, ChatMessageOut, ChatOut
from ..scoring.engine import classify_in_background, publish, score_safely
from ..utils import RateLimit, client_ip

router = APIRouter(tags=["chat"])

# Each message can cost two LLM calls. Far more than people type, even many people behind one office or college network.
MESSAGES_PER_IP = RateLimit(30, 60)


@router.post("/chat", response_model=ChatOut)
async def chat(payload: ChatIn, request: Request, background: BackgroundTasks) -> ChatOut:
    """Answer from the listings and brochures (with the LLM if a key is set, templates otherwise), work out EMIs, book site
    visits and save the buyer details. The visitor's messages are then classified (end buyer, broker, ...) in the background.
    More than 30 messages a minute from one IP address get a 429."""
    ip = client_ip(request)
    if not MESSAGES_PER_IP.allow(ip or "unknown"):
        raise HTTPException(status_code=429, detail="Too many messages at once. Wait a minute, then try again.")
    reply, visitor = await run_in_threadpool(handle_chat, payload, ip, request.headers.get("user-agent"))
    if visitor is not None:
        await publish(visitor, await run_in_threadpool(score_safely, visitor.id))
        background.add_task(classify_in_background, visitor.id)
    if reply.action and reply.action.visit:
        await hub.broadcast({"type": "visit_booked", "visit": reply.action.visit.model_dump(mode="json")})
    return reply


@router.get("/chat/{visitor_id}", response_model=list[ChatMessageOut])
async def get_chat(visitor_id: str, limit: int = Query(50, ge=1, le=200)) -> list[ChatMessageOut]:
    return await run_in_threadpool(chat_history, visitor_id, limit)
