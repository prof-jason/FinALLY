"""POST /api/chat."""

from __future__ import annotations

from fastapi import APIRouter
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from . import service
from .client import LLMUnavailableError

UNAVAILABLE_MESSAGE = "The AI assistant is unavailable right now, please try again shortly."


class ChatRequest(BaseModel):
    message: str = Field(min_length=1, max_length=4000)


def create_chat_router() -> APIRouter:
    router = APIRouter()

    @router.post("/api/chat")
    async def chat(request: ChatRequest):
        message = request.message.strip()
        if not message:
            return JSONResponse(status_code=400, content={"error": "Message must not be empty"})
        try:
            return await service.handle_chat(message)
        except LLMUnavailableError:
            return JSONResponse(status_code=503, content={"error": UNAVAILABLE_MESSAGE})

    return router
