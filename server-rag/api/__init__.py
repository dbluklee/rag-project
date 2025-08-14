"""
CHEESEADE RAG Server API 패키지

OpenWebUI, Ollama, OpenAI 호환 API 제공
"""

from .routes import router
from .models import (
    ChatRequest, ChatResponse, ChatResponseChoice, ChatResponseMessage,
    ModelInfo, ModelsResponse, WebUIModelInfo, WebUIModelsResponse
)
from .services import model_service
from .auth import auth_service, get_current_user, get_current_user_optional
from .chat_handler import ChatHandler

__all__ = [
    "router",
    "ChatRequest", "ChatResponse", "ChatResponseChoice", "ChatResponseMessage",
    "ModelInfo", "ModelsResponse", "WebUIModelInfo", "WebUIModelsResponse", 
    "model_service",
    "auth_service", "get_current_user", "get_current_user_optional",
    "ChatHandler"
]