"""LeadOps API.

Run from the backend folder:  uvicorn app.main:app --reload
Interactive API docs:          http://localhost:8000/docs
"""

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from .ai.llm_client import llm
from .api import api_router
from .config import REPO_DIR, settings
from .db import init_db
from .listings import all_listings


@asynccontextmanager
async def lifespan(_app: FastAPI):
    init_db()
    all_listings()  # fail at startup, not on the first request, if listings.json is broken
    yield


app = FastAPI(title="LeadOps API", version="0.1.0", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,  # "*" by default: the SDK is meant to run on any site
    allow_methods=["*"],
    allow_headers=["*"],
)
app.include_router(api_router)

# Serves the tracking script (and its plain-HTML demo), so any site can add
# <script src="http://localhost:8000/sdk/leadops.js"></script>
_SDK_DIR = REPO_DIR / "sdk"
if _SDK_DIR.is_dir():
    app.mount("/sdk", StaticFiles(directory=_SDK_DIR), name="sdk")


@app.get("/health", tags=["meta"])
def health() -> dict:
    """Quick check that the API is up, and which LLM (or template mode) the assistant uses."""
    return {"status": "ok", "llm": llm.describe(), "listings": len(all_listings())}
