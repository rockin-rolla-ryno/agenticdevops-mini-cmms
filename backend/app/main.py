"""CMMess backend — FastAPI application entry point."""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Literal

from fastapi import FastAPI
from pydantic import BaseModel

from app.assets import router as assets_router
from app.auth import router as auth_router
from app.seeding import seed_users_from_config


class HealthResponse(BaseModel):
    """Response model for GET /health."""

    status: Literal["ok"]


@asynccontextmanager
async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
    """Startup: seed accounts from the users config (FS-Q5).

    Importing the module touches no storage — only startup does.
    """
    seed_users_from_config()
    yield


app = FastAPI(title="CMMess Backend", lifespan=lifespan)
app.include_router(auth_router)
app.include_router(assets_router)


@app.get("/health", response_model=HealthResponse)
def health() -> HealthResponse:
    """Liveness check. No auth."""
    return HealthResponse(status="ok")
