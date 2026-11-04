"""HTTP and WebSocket routes, one module per group of endpoints."""

from fastapi import APIRouter

from . import chat, events, feedback, leads, listings, visitors, ws

api_router = APIRouter()
for _module in (events, visitors, listings, leads, chat, feedback, ws):
    api_router.include_router(_module.router)
