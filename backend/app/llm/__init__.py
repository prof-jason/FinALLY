"""LLM chat subsystem for FinAlly.

Public API:
    create_chat_router - FastAPI router for POST /api/chat
    handle_chat        - One chat turn: LLM (or mock) -> auto-execute actions -> persist
    ChatResponse       - Structured-output schema requested from the LLM
    MODEL              - The (free) OpenRouter model id
"""

from .client import MODEL, LLMUnavailableError
from .router import create_chat_router
from .schemas import ChatResponse, parse_chat_response
from .service import handle_chat

__all__ = [
    "MODEL",
    "ChatResponse",
    "LLMUnavailableError",
    "create_chat_router",
    "handle_chat",
    "parse_chat_response",
]
