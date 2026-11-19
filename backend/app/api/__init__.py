"""HTTP and WebSocket routes, one module per group of endpoints."""

from fastapi import APIRouter

from . import chat, demo, events, feedback, leads, listings, visitors, visits, ws

api_router = APIRouter()
for _module in (events, visitors, listings, leads, chat, visits, feedback, demo, ws):
    api_router.include_router(_module.router)
